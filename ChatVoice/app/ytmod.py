"""YouTube auto-moderation: sign in with Google, delete rule-breaking messages, time out repeat offenders.

Chat is still READ without a login (cheap and quota-free). The API is only used for the rare delete/timeout:
each one costs 50 of the project's 10,000 daily quota units, so a daily action limit protects the quota.
"""
import base64
import hashlib
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer

from PySide6.QtCore import QObject, QTimer, Signal

from .discord import run_bg
from .hinglish import EMOJI_RX, SHORTCODE_RX
from .platforms import youtube_id
from .settings import data_dir

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
RULES = {"blocked word": "mod_del_blocked", "link": "mod_del_links", "spam": "mod_del_spam", "repeat": "mod_del_spam"}


def _call(method, url, token=None, form=None, body=None, timeout=15):
    """Returns (status, json). Never raises for HTTP errors."""
    headers = {"User-Agent": "ChatVoice/0.3"}
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": {"message": "Cannot reach Google (%s)" % str(e)[:60]}}


def _err(data):
    e = (data or {}).get("error")
    if isinstance(e, dict):
        return e.get("message") or str(e.get("code", "error"))
    return (data or {}).get("error_description") or (e if isinstance(e, str) else "error")


def _norm(t):
    return re.sub(r"\s+", "", EMOJI_RX.sub("", SHORTCODE_RX.sub("", t or ""))).lower()


class GoogleAuth:
    def __init__(self, settings, path=None):
        self.s = settings
        self.path = path or os.path.join(data_dir(), "google_token.json")
        self.tok = {}
        try:
            with open(self.path, encoding="utf-8") as f:
                self.tok = json.load(f)
        except Exception:
            pass

    def client(self):
        cid, sec = self.s.get("g_client_id").strip(), self.s.get("g_client_secret").strip()
        if not cid:
            try:
                with open(os.path.join(data_dir(), "google_client.json"), encoding="utf-8") as f:
                    d = json.load(f)
                cid, sec = d.get("client_id", ""), d.get("client_secret", "")
            except Exception:
                pass
        return cid, sec

    @property
    def logged_in(self):
        return bool(self.tok.get("refresh_token"))

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.tok, f)
        except Exception:
            pass

    def logout(self):
        self.tok = {}
        try:
            os.remove(self.path)
        except Exception:
            pass

    def begin_login(self, bridge, timeout=300):
        """Returns the web address to open. A tiny local server catches Google's answer, then signals bridge 'yt:login'."""
        cid, sec = self.client()
        if not cid or not sec:
            raise ValueError("Enter the Google client ID and secret first (see YT-MODERATION-SETUP.txt)")
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(16)
        got = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                ok = q.get("state", [""])[0] == state and "code" in q
                if ok:
                    got["code"] = q["code"][0]
                elif "error" in q:
                    got["error"] = q["error"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                msg = "Signed in. You can close this tab and go back to ChatVoice." if ok else "Not signed in. You can close this tab."
                self.wfile.write(("<html><body style='font:18px sans-serif;background:#0e1118;color:#eee;padding:40px'>%s</body></html>" % msg).encode())

        server = HTTPServer(("127.0.0.1", 0), Handler)
        server.timeout = 1
        redirect = "http://127.0.0.1:%d" % server.server_port
        url = AUTH_URL + "?" + urllib.parse.urlencode({
            "client_id": cid, "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
            "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
            "access_type": "offline", "prompt": "consent"})

        def work():
            end = time.time() + timeout
            while time.time() < end and "code" not in got and "error" not in got:
                server.handle_request()
            server.server_close()
            if "code" not in got:
                bridge.done.emit("yt:login", {"error": got.get("error") or "Sign-in timed out"})
                return
            st, d = _call("POST", TOKEN_URL, form={"code": got["code"], "client_id": cid, "client_secret": sec,
                                                   "code_verifier": verifier, "redirect_uri": redirect,
                                                   "grant_type": "authorization_code"})
            if st != 200 or "refresh_token" not in d:
                bridge.done.emit("yt:login", {"error": _err(d) if d else "Google refused the sign-in"})
                return
            self.tok = {"access_token": d["access_token"], "expires_at": time.time() + int(d.get("expires_in", 3600)),
                        "refresh_token": d["refresh_token"]}
            self._save()
            bridge.done.emit("yt:login", {"ok": True})

        threading.Thread(target=work, daemon=True).start()
        return url

    def access_token(self):
        if not self.logged_in:
            raise ValueError("Sign in with Google first")
        if self.tok.get("expires_at", 0) > time.time() + 60:
            return self.tok["access_token"]
        cid, sec = self.client()
        st, d = _call("POST", TOKEN_URL, form={"client_id": cid, "client_secret": sec,
                                               "refresh_token": self.tok["refresh_token"], "grant_type": "refresh_token"})
        if st != 200 or "access_token" not in d:
            if (d or {}).get("error") == "invalid_grant":
                self.logout()
                raise ValueError("Google sign-in expired - sign in again")
            raise ValueError("Could not refresh the Google sign-in: " + _err(d))
        self.tok["access_token"] = d["access_token"]
        self.tok["expires_at"] = time.time() + int(d.get("expires_in", 3600))
        self._save()
        return self.tok["access_token"]


class YtModerator(QObject):
    notice = Signal(str)

    def __init__(self, settings, auth, bridge):
        super().__init__()
        self.s, self.auth, self.bridge = settings, auth, bridge
        self.pending = []
        self.recent = deque(maxlen=400)
        self.done_ids = set()
        self.page_token = None
        self.video = None
        self.chat_id = None
        self.busy = False
        self.offences = {}
        self.timed_out = {}
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self.sweep)
        bridge.done.connect(self.on_done)

    # ----- called from the main window -----
    def flag(self, m, reason):
        """Queue a message for deletion if the matching rule is switched on. Returns True if queued."""
        key = RULES.get(reason)
        if not key or not self.s.get(key) or not self.auth.logged_in or not m.uid or m.kind != "chat":
            return False
        self.pending.append({"channel": m.uid, "text": m.text, "author": m.author, "reason": reason})
        if not self.timer.isActive():
            self.timer.start()
        return True

    def sweep(self):
        if self.busy:
            self.timer.start()
            return
        if not self.pending:
            return
        items, self.pending = self.pending, []
        self.busy = True
        run_bg(self.bridge, "yt:sweep", lambda: self._do(items))

    def on_done(self, tag, res):
        if tag != "yt:sweep":
            return
        self.busy = False
        for line in res.get("notes", []):
            self.notice.emit(line)
        if res.get("error"):
            self.notice.emit("YouTube moderation problem: %s" % res["error"])
        if self.pending:
            self.timer.start()

    def used_today(self):
        return int(self.s.get("yt_actions_count")) if self.s.get("yt_actions_date") == str(date.today()) else 0

    # ----- runs in a background thread -----
    def _spend(self):
        today = str(date.today())
        if self.s.get("yt_actions_date") != today:
            self.s.set("yt_actions_date", today)
            self.s.set("yt_actions_count", 0)
        self.s.set("yt_actions_count", int(self.s.get("yt_actions_count")) + 1)

    def _left(self):
        return int(self.s.get("mod_budget")) - self.used_today()

    def _chat(self, token):
        vid = youtube_id(self.s.get("youtube") or "")
        if not vid:
            raise ValueError("Enter your live link on the Connect page first")
        if vid != self.video:
            st, d = _call("GET", "%s/videos?part=liveStreamingDetails&id=%s" % (API, urllib.parse.quote(vid)), token)
            if st != 200:
                raise ValueError(_err(d))
            cid = ((d.get("items") or [{}])[0].get("liveStreamingDetails") or {}).get("activeLiveChatId")
            if not cid:
                raise ValueError("No live chat found for that video - is the stream live?")
            self.video, self.chat_id, self.page_token = vid, cid, None
            self.recent.clear()
            self.done_ids.clear()
        return self.chat_id

    def _pull(self, token):
        for _ in range(3):
            q = {"liveChatId": self.chat_id, "part": "snippet,authorDetails", "maxResults": "200"}
            if self.page_token:
                q["pageToken"] = self.page_token
            st, d = _call("GET", API + "/liveChat/messages?" + urllib.parse.urlencode(q), token)
            if st != 200:
                raise ValueError(_err(d))
            items = d.get("items", [])
            for it in items:
                self.recent.append({"id": it["id"], "channel": it["authorDetails"]["channelId"],
                                    "text": it["snippet"].get("displayMessage", "")})
            self.page_token = d.get("nextPageToken") or self.page_token
            if len(items) < 200:
                break

    def _find(self, it):
        mine = [r for r in self.recent if r["channel"] == it["channel"] and r["id"] not in self.done_ids]
        want = _norm(it["text"])
        for r in reversed(mine):
            if _norm(r["text"]) == want:
                return r["id"]
        recent_mine = mine[-1:] if len(mine) == 1 else []
        return recent_mine[0]["id"] if recent_mine else None

    def _do(self, items):
        notes = []
        token = self.auth.access_token()
        self._chat(token)
        self._pull(token)
        dry = bool(self.s.get("mod_dry_run"))
        for it in items:
            mid = self._find(it)
            if not mid:
                notes.append("Could not find %s's message to remove (it may be too old)" % it["author"])
                continue
            if dry:
                notes.append("TEST MODE: would delete %s's message (%s)" % (it["author"], it["reason"]))
            else:
                if self._left() <= 0:
                    notes.append("Daily moderation limit reached - no more deletions today")
                    break
                st, d = _call("DELETE", "%s/liveChat/messages?id=%s" % (API, urllib.parse.quote(mid)), token)
                if st not in (200, 204):
                    hint = " - the signed-in account must be the channel owner or a moderator" if st == 403 else ""
                    notes.append("Could not delete %s's message: %s%s" % (it["author"], _err(d), hint))
                    continue
                self._spend()
                self.done_ids.add(mid)
                notes.append("Deleted %s's message (%s)" % (it["author"], it["reason"]))
            self._offence(it, token, dry, notes)
        return {"notes": notes}

    def _offence(self, it, token, dry, notes):
        ch, now = it["channel"], time.time()
        dq = self.offences.setdefault(ch, deque())
        dq.append(now)
        while dq and now - dq[0] > 600:
            dq.popleft()
        if len(dq) < int(self.s.get("mod_timeout_after")) or now < self.timed_out.get(ch, 0):
            return
        secs = int(self.s.get("mod_timeout_secs"))
        if dry:
            notes.append("TEST MODE: would time out %s for %d seconds" % (it["author"], secs))
            return
        if self._left() <= 0:
            return
        st, d = _call("POST", API + "/liveChat/bans?part=snippet", token, body={"snippet": {
            "liveChatId": self.chat_id, "type": "temporary", "banDurationSeconds": secs,
            "bannedUserInfo": {"channelId": ch}}})
        if st in (200, 201):
            self._spend()
            self.timed_out[ch] = now + secs
            notes.append("Timed out %s for %d seconds (repeated rule breaking)" % (it["author"], secs))
        else:
            notes.append("Could not time out %s: %s" % (it["author"], _err(d)))
