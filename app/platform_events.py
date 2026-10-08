"""Authenticated Twitch EventSub alerts."""
import asyncio
import json
import threading

from PySide6.QtCore import QObject, Signal


def _count(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def parse_twitch_event(notification):
    metadata = notification.get("metadata") or {}
    payload = notification.get("payload") or {}
    event = payload.get("event") or {}
    kind = metadata.get("subscription_type")
    name = event.get("user_name") or "Someone"

    if kind == "channel.follow":
        return {"platform": "twitch", "category": "follow", "name": name, "message": ""}
    if kind == "channel.subscribe":
        if event.get("is_gift"):
            return None
        tier = {"1000": "Tier 1", "2000": "Tier 2", "3000": "Tier 3"}.get(event.get("tier"), "New subscription")
        return {"platform": "twitch", "category": "subscription", "name": name, "amount": tier, "message": ""}
    if kind == "channel.subscription.message":
        months = _count(event.get("cumulative_months"))
        tier = {"1000": "Tier 1", "2000": "Tier 2", "3000": "Tier 3"}.get(event.get("tier"), "Subscription")
        message = (event.get("message") or {}).get("text") or ""
        detail = "%s · %d months" % (tier, months) if months else tier
        return {"platform": "twitch", "category": "subscription", "name": name, "amount": detail, "message": message}
    if kind == "channel.subscription.gift":
        total = max(1, _count(event.get("total")) or 1)
        tier = {"1000": "Tier 1", "2000": "Tier 2", "3000": "Tier 3"}.get(event.get("tier"), "subscription")
        giver = "Anonymous supporter" if event.get("is_anonymous") else name
        return {"platform": "twitch", "category": "gift", "name": giver,
                "amount": "%d %s subscriptions" % (total, tier), "message": ""}
    if kind == "channel.raid":
        viewers = _count(event.get("viewers"))
        return {"platform": "twitch", "category": "raid", "name": name,
                "amount": "%d viewers" % viewers if viewers else "", "message": ""}
    return None


class TwitchEventSub(QObject):
    alert = Signal(object)
    notice = Signal(str)

    URL = "wss://eventsub.wss.twitch.tv/ws?keepalive_timeout_seconds=30"

    def __init__(self, platform_auth):
        super().__init__()
        self.platform_auth = platform_auth
        self.stop_event = threading.Event()
        self.thread = None
        self._seen = set()
        self._seen_order = []

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self):
        if self.running:
            return
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=lambda: asyncio.run(self._run()), daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    async def _run(self):
        import websockets

        url = self.URL
        migrated = False
        while not self.stop_event.is_set():
            reconnect = False
            try:
                async with websockets.connect(url, open_timeout=15, close_timeout=5) as socket:
                    welcomed = False
                    while not self.stop_event.is_set():
                        try:
                            raw = await asyncio.wait_for(socket.recv(), timeout=1)
                        except asyncio.TimeoutError:
                            continue
                        message = json.loads(raw)
                        metadata = message.get("metadata") or {}
                        message_type = metadata.get("message_type")

                        if message_type == "session_welcome":
                            welcomed = True
                            session = ((message.get("payload") or {}).get("session") or {})
                            if not migrated:
                                result = await asyncio.to_thread(
                                    self.platform_auth.subscribe_eventsub, session.get("id", ""))
                                self._subscription_status(result)
                            else:
                                self.notice.emit("Twitch alert connection resumed.")
                            migrated = False
                        elif message_type == "session_reconnect":
                            session = ((message.get("payload") or {}).get("session") or {})
                            reconnect_url = session.get("reconnect_url") or ""
                            if reconnect_url.startswith("wss://"):
                                url = reconnect_url
                                migrated = True
                                reconnect = True
                                break
                        elif message_type == "notification":
                            self._emit_notification(message)

                    if self.stop_event.is_set():
                        return
                    if reconnect:
                        continue
                    if welcomed:
                        raise ConnectionError("Twitch EventSub closed the connection")
            except Exception as error:
                if not self.stop_event.is_set():
                    self.notice.emit("Twitch alert connection lost: %s" % str(error)[:120])
            if self.stop_event.wait(5):
                return
            url = self.URL
            migrated = False

    def _subscription_status(self, result):
        if result.get("status") == 401:
            self.platform_auth.refresh("twitch")
            self.notice.emit("Twitch login expired. Sign in again to restore Twitch alerts.")
            return
        subscribed = result.get("subscribed") or []
        failed = result.get("failed") or []
        if subscribed:
            self.notice.emit("Twitch alerts connected: %s." % ", ".join(
                kind.replace("channel.", "").replace(".", " ") for kind in subscribed))
        if failed:
            if failed and all(item.get("status") == 401 for item in failed):
                self.platform_auth.refresh("twitch")
                self.notice.emit("Twitch login expired. Sign in again to restore Twitch alerts.")
                return
            missing = ", ".join(item.get("type", "").replace("channel.", "").replace(".", " ") for item in failed)
            self.notice.emit(
                "Some Twitch alerts need new permissions (%s). Disconnect and sign in to Twitch again to approve them."
                % missing)
        if not subscribed and not failed:
            self.notice.emit(result.get("error") or "Twitch did not activate any alert subscriptions.")

    def _emit_notification(self, message):
        metadata = message.get("metadata") or {}
        message_id = metadata.get("message_id")
        if message_id:
            if message_id in self._seen:
                return
            self._seen.add(message_id)
            self._seen_order.append(message_id)
            if len(self._seen_order) > 500:
                self._seen.discard(self._seen_order.pop(0))
        alert = parse_twitch_event(message)
        if alert:
            self.alert.emit(alert)
