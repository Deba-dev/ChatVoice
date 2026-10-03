"""Payment alerts: the streamer's own gateway -> cloud -> this app (polled every few seconds)."""
from PySide6.QtCore import QObject, QTimer, Signal

from .discord import run_bg


class TipPoller(QObject):
    tip = Signal(object)        # dict: name, message, value, currency, display
    notice = Signal(str)
    status = Signal(str)

    def __init__(self, settings, cloud, bridge):
        super().__init__()
        self.s, self.cloud, self.bridge = settings, cloud, bridge
        self.busy = False
        self._warned = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        bridge.done.connect(self.on_done)

    def apply(self):
        """Start or stop listening according to the setting."""
        if self.s.get("tips_on"):
            self.timer.start(8000)
            self.status.emit("Starting...")
            self.poll()
        else:
            self.timer.stop()
            self.status.emit("Not listening")

    def poll(self):
        if self.busy or not self.s.get("tips_on"):
            return
        if not self.cloud.configured:
            self.status.emit("Connect your server on the Discord page first")
            return
        cur = self.s.get("tip_cursor")
        self.busy = True
        run_bg(self.bridge, "tips", lambda: self.cloud.call("GET", "/api/events?after=%d" % (-1 if cur is None else int(cur))))

    def on_done(self, tag, res):
        if tag != "tips":
            return
        self.busy = False
        if "error" in res:
            self.status.emit("Problem: %s" % res["error"])
            if "not set up" in res["error"] and not self._warned:
                self._warned = True
                self.notice.emit("Payments: %s" % res["error"])
            return
        first = self.s.get("tip_cursor") is None
        if not first:
            for e in res.get("events", []):
                self.tip.emit(e)
        latest = int(res.get("latest", 0))
        if first or latest > int(self.s.get("tip_cursor") or 0):
            self.s.set("tip_cursor", latest)
        self.status.emit("Listening for payments")
