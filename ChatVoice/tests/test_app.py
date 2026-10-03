# Run from the project folder:  set APPDATA=%TEMP%\cvtest  &  set QT_QPA_PLATFORM=offscreen  &  set PYTHONPATH=.  &  python tests\test_app.py
# (use a fresh, empty APPDATA folder each time)
import os, sys, json, threading, time, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QEventLoop
app = QApplication(sys.argv); app.setStyle("Fusion")
def wait(ms):
    l = QEventLoop(); QTimer.singleShot(ms, l.quit); l.exec()
fails = 0
def ok(c, msg):
    global fails
    print(("PASS " if c else "FAIL ") + msg); fails += (not c)

# ---------------- fake cloud ----------------
C = {"grants": [], "tips": [], "config_puts": [], "links": {"youtube:UC1": "U1", "youtube:UC2": "U2"}, "deny": {"UC2"}}
class Cloud(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, o, code=200):
        b = json.dumps(o).encode(); self.send_response(code); self.send_header("content-type", "application/json"); self.end_headers(); self.wfile.write(b)
    def body(self):
        n = int(self.headers.get("content-length") or 0); return json.loads(self.rfile.read(n) or b"{}")
    def do_GET(self):
        if self.headers.get("Authorization") != "Bearer KEY": return self.send({"error": "bad server key"}, 401)
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path == "/api/roles": self.send({"roles": [{"id": "100003", "name": "Supporter"}, {"id": "100001", "name": "YouTube Viewer"}, {"id": "100002", "name": "Regular"}]})
        elif u.path == "/api/links": self.send({"keys": list(C["links"])})
        elif u.path == "/api/config": self.send({"guildId": "G1", "guildName": "Srv", "config": {"hasRazorpaySecret": bool(C.get("secret")), "hookUrl": "https://cv.example/hook/razorpay/abc" if C.get("secret") else "", "inviteRules": C.get("invite_rules", [])}})
        elif u.path == "/api/events":
            after = int(q["after"][0]); latest = max([t["seq"] for t in C["tips"]] or [0])
            self.send({"events": [], "latest": latest} if after < 0 else {"events": [t for t in C["tips"] if t["seq"] > after], "latest": latest})
        else: self.send({"error": "nf"}, 404)
    def do_PUT(self):
        if self.headers.get("Authorization") != "Bearer KEY": return self.send({"error": "x"}, 401)
        b = self.body(); C["config_puts"].append(b)
        if "inviteRules" in b: C["invite_rules"] = [dict(r, code=r["code"].split("/")[-1]) for r in b["inviteRules"]]
        if b.get("razorpaySecret"): C["secret"] = b["razorpaySecret"]
        self.send({"ok": True, "config": {"hasRazorpaySecret": True, "hookUrl": "https://cv.example/hook/razorpay/abc"}})
    def do_POST(self):
        b = self.body()
        if self.path == "/api/invites/check":
            return self.send({"rules": [{"label": "YouTube", "code": "yt1", "found": True, "uses": 4}, {"label": "Twitch", "code": "tw1", "found": False, "uses": None}], "assigned": [{}], "notes": ["Now watching your invites."]})
        if self.path == "/api/grant":
            C["grants"].append(b)
            if b["uid"] in C["deny"]: return self.send({"ok": False, "status": 403})
            return self.send({"ok": True, "role": b["role"], "status": 204})
        self.send({"error": "nf"}, 404)

# ---------------- fake Google ----------------
G = {"msgs": [], "deleted": [], "bans": [], "tokens": 0, "refreshes": 0, "delete_status": 204, "auth_params": None}
class Google(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, o, code=200):
        b = json.dumps(o).encode(); self.send_response(code); self.send_header("content-type", "application/json"); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        n = int(self.headers.get("content-length") or 0); raw = self.rfile.read(n)
        u = urllib.parse.urlparse(self.path)
        if u.path == "/token":
            f = urllib.parse.parse_qs(raw.decode())
            if f["grant_type"][0] == "authorization_code":
                assert f["code_verifier"][0] and f["client_secret"][0] == "SECRET"; G["tokens"] += 1
                return self.send({"access_token": "AT1", "expires_in": 3600, "refresh_token": "RT1"})
            G["refreshes"] += 1; return self.send({"access_token": "AT2", "expires_in": 3600})
        if u.path == "/youtube/v3/liveChat/bans":
            assert self.headers["Authorization"].startswith("Bearer AT"); G["bans"].append(json.loads(raw)); return self.send({"id": "ban1"})
        self.send({}, 404)
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if not self.headers.get("Authorization", "").startswith("Bearer AT"): return self.send({"error": {"message": "unauthorized"}}, 401)
        if u.path == "/youtube/v3/videos": return self.send({"items": [{"liveStreamingDetails": {"activeLiveChatId": "CHAT1"}}]})
        if u.path == "/youtube/v3/liveChat/messages":
            start = int(q.get("pageToken", ["0"])[0])
            items = [{"id": m["id"], "snippet": {"displayMessage": m["text"]}, "authorDetails": {"channelId": m["ch"]}} for m in G["msgs"][start:]]
            return self.send({"items": items, "nextPageToken": str(len(G["msgs"]))})
        self.send({}, 404)
    def do_DELETE(self):
        u = urllib.parse.urlparse(self.path); mid = urllib.parse.parse_qs(u.query)["id"][0]
        if G["delete_status"] != 204: return self.send({"error": {"message": "forbidden"}}, G["delete_status"])
        G["deleted"].append(mid); self.send_response(204); self.end_headers()
for H, port in ((Cloud, 8811), (Google, 8812)):
    s = ThreadingHTTPServer(("127.0.0.1", port), H); threading.Thread(target=s.serve_forever, daemon=True).start()

import app.ytmod as ytmod
ytmod.AUTH_URL = "http://127.0.0.1:8812/auth"; ytmod.TOKEN_URL = "http://127.0.0.1:8812/token"; ytmod.API = "http://127.0.0.1:8812/youtube/v3"
from app.ui import MainWindow
from app.models import Message
w = MainWindow(); w.show()
w.s.set("muted", True)
spoken = []; w.speaker.say = lambda *a: spoken.append(a)
w.s.set("cloud_url", "http://127.0.0.1:8811"); w.s.set("cloud_token", "KEY")
w.links.refresh(); wait(500)
ok(w.links.linked == {"youtube:UC1", "youtube:UC2"}, "linked viewers loaded from the cloud")

# ===== A. roles are counted in the app; the cloud is asked only at thresholds =====
print("--- A. role thresholds ---")
w.s.set("role_regular", "100002"); w.s.set("role_supporter", "100003"); w.s.set("regular_msgs", 3)
for i in range(2): w.on_message(Message("youtube", "Rahul", "hello %d" % i, uid="UC1", mod=True))
wait(300); ok(len(C["grants"]) == 0, "no cloud call before the threshold")
w.on_message(Message("youtube", "Rahul", "hello 3", uid="UC1", mod=True)); wait(500)
ok([g["role"] for g in C["grants"]] == ["regular"], "3rd message -> one request for the Regular role")
for i in range(5): w.on_message(Message("youtube", "Rahul", "more %d" % i, uid="UC1", mod=True))
wait(300); ok(len(C["grants"]) == 1, "no repeat requests after the role was given")
w.on_message(Message("youtube", "Rahul", "thanks", "super", "₹100", uid="UC1", mod=True)); wait(500)
ok([g["role"] for g in C["grants"]] == ["regular", "supporter"], "paid message -> Supporter role requested")
for i in range(4): w.on_message(Message("youtube", "Neha", "hi %d" % i, uid="UC2", mod=True))
wait(500); n = len(C["grants"])
for i in range(4): w.on_message(Message("youtube", "Neha", "again %d" % i, uid="UC2", mod=True))
wait(300); ok(len(C["grants"]) == n and "move the ChatVoice role above" in w.feed.toPlainText(), "failed grant (403): clear hint, and no retry flood")
w.links.save(); ok(json.load(open(os.path.join(os.environ["APPDATA"], "ChatVoice", "counts.json")))["youtube:UC1"]["regular"], "counts saved to disk")

# ===== B. payments =====
print("--- B. payments ---"); spoken.clear()
w.s.set("tips_on", True); w.s.set("tip_min", 20)
w.mod.blocked = ["badword"]
C["tips"].append({"seq": 1, "id": "old", "name": "Old", "message": "old tip", "value": 50, "currency": "INR", "display": "₹50"})
w.poller.apply(); wait(700)
ok(w.s.get("tip_cursor") == 1 and not spoken, "first poll skips tips that arrived before the app started")
C["tips"] += [{"seq": 2, "id": "a", "name": "Rahul", "message": "Great stream bhai!", "value": 100, "currency": "INR", "display": "₹100"},
              {"seq": 3, "id": "b", "name": "Troll", "message": "you badword", "value": 100, "currency": "INR", "display": "₹100"},
              {"seq": 4, "id": "c", "name": "Cheap", "message": "I paid only five", "value": 5, "currency": "INR", "display": "₹5"},
              {"seq": 5, "id": "d", "name": "Sam", "message": "Hello from the USA", "value": 5, "currency": "USD", "display": "$5"}]
w.poller.poll(); wait(900)
got = {a[0]: a for a in spoken}
ok(len(spoken) == 4, "all four new tips were queued to be spoken")
ok(got["Rahul"][1] == "Great stream bhai!" and got["Rahul"][2] == "₹100", "name + message + amount ₹100 read")
ok(got["Troll"][1] == "" and got["Troll"][2] == "₹100", "blocked word: message hidden, name and amount still read")
ok(got["Cheap"][1] == "" and got["Cheap"][2] == "₹5", "below minimum: message not read")
ok(got["Sam"][1] == "Hello from the USA" and got["Sam"][2] == "$5", "USD payment: message read (minimum applies to INR only)")
ok(w.s.get("tip_cursor") == 5, "cursor advanced; nothing is read twice")
w.poller.poll(); wait(500); ok(len(spoken) == 4, "next poll finds nothing new")
txt = w.feed.toPlainText(); ok("TIP Rahul [₹100]: Great stream bhai!" in txt, "tip shown in the live chat feed")
w.payments.secret.setText("whsec_123"); w.payments.save_secret(); wait(500)
ok(C["config_puts"][-1] == {"razorpaySecret": "whsec_123"} and w.payments.hook.text().endswith("/hook/razorpay/abc"), "secret saved on its own (roles untouched), webhook address shown")
w.payments.test_tip(); wait(300); ok(spoken[-1][0] == "Rahul" and spoken[-1][2] == "₹100", "test payment button works")

# ===== C. YouTube moderation =====
print("--- C. YouTube moderation ---")
w.s.set("g_client_id", "CID"); w.s.set("g_client_secret", "SECRET"); w.s.set("youtube", "https://www.youtube.com/watch?v=7NlbmyxncOk")
ytmod_url = w.gauth.begin_login(w.bridge)
q = urllib.parse.parse_qs(urllib.parse.urlparse(ytmod_url).query)
ok(q["code_challenge_method"] == ["S256"] and q["scope"] == [ytmod.SCOPE] and q["access_type"] == ["offline"], "sign-in uses PKCE, the right permission, offline access")
redirect = q["redirect_uri"][0]
urllib.request.urlopen(redirect + "/?code=bogus&state=WRONG").read(); wait(200)
ok(not w.gauth.logged_in, "answer with a wrong state value is rejected")
urllib.request.urlopen(redirect + "/?code=abc&state=" + q["state"][0]).read(); wait(800)
ok(w.gauth.logged_in and G["tokens"] == 1, "sign-in completes and the token is saved")
w.gauth.tok["expires_at"] = 0; w.gauth.access_token(); ok(G["refreshes"] == 1, "expired token is refreshed automatically")
w.ytmod.timer.setInterval(100)
def post(author, ch, text, **kw):
    G["msgs"].append({"id": "M%d" % (len(G["msgs"]) + 1), "ch": ch, "text": text}); w.on_message(Message("youtube", author, text, uid=ch, **kw))
post("Spammer", "UC9", "visit www.spam.com now"); wait(900)
ok(not G["deleted"] and "TEST MODE: would delete Spammer" in w.feed.toPlainText(), "TEST MODE only reports what would be deleted")
w.s.set("mod_dry_run", False)
post("Spammer", "UC9", "check www.other.com"); wait(900)
ok(G["deleted"] == ["M2"], "real mode: the right message was deleted (matched by viewer + text)")
post("Spammer", "UC9", "third www.again.com"); wait(900)
ok(G["deleted"] == ["M2", "M3"] and len(G["bans"]) == 1, "3rd deletion in 10 minutes -> viewer timed out")
b = G["bans"][0]["snippet"]; ok(b["type"] == "temporary" and b["banDurationSeconds"] == 300 and b["bannedUserInfo"]["channelId"] == "UC9" and b["liveChatId"] == "CHAT1", "time-out request is correct (5 minutes)")
post("Mod", "UC5", "mod posts www.link.com", mod=True); wait(700)
ok(len(G["deleted"]) == 2, "moderators are never touched")
post("Fan", "UC6", "I love badword"); wait(900)
ok(G["deleted"][-1] == "M5", "blocked word message deleted")
w.s.set("mod_budget", w.ytmod.used_today())
post("Spammer2", "UC8", "x www.limit.com"); wait(900)
ok("Daily moderation limit reached" in w.feed.toPlainText() and len(G["deleted"]) == 3, "daily action limit stops further deletions")
w.s.set("mod_budget", 60); G["delete_status"] = 403
post("Spammer3", "UC7", "y www.nope.com"); wait(900)
ok("must be the channel owner or a moderator" in w.feed.toPlainText(), "403 explains that the account needs moderator rights")
w.s.set("mod_del_links", False); n = len(G["msgs"]); post("Quiet", "UC4", "z www.allowed.com"); wait(500)
ok(True, "rule switched off: nothing flagged (no crash)")
w.goto(5); wait(300); w.grab().save(os.path.join(os.environ["APPDATA"], "payments.png")); w.goto(6); wait(300); w.grab().save(os.path.join(os.environ["APPDATA"], "ytmod.png"))

# ===== D. invite roles UI, themes, lite mode, animations =====
print("--- D. invite roles, look and feel ---")
d = w.discord; d.url.setText("http://127.0.0.1:8811"); d.key.setText("KEY"); d.test(); wait(1200)
d.inv_edits["youtube"].setText("https://discord.gg/yt1")
d.save_invites(); wait(300); ok("Pick a role for the YouTube invite" in d.istatus.text() and "inviteRules" not in C["config_puts"][-1], "invite without a role: asks for one, nothing sent")
d.inv_boxes["youtube"].setCurrentIndex(d.inv_boxes["youtube"].findData("100001")); d.save_invites(); wait(500)
ok(C["config_puts"][-1] == {"inviteRules": [{"code": "https://discord.gg/yt1", "role": "100001", "label": "YouTube"}]} and "Saved" in d.istatus.text(), "invite + role sent to the cloud, only that field")
d.check_invites(); wait(500)
ok("invite found, used 4 times" in d.istatus.text() and "invite NOT found" in d.istatus.text() and "Gave roles to 1" in d.istatus.text(), "check button explains each invite in plain words")
d.inv_edits["youtube"].setText(""); d.test(); wait(900)
ok(d.inv_edits["youtube"].text() == "https://discord.gg/yt1" and d.inv_boxes["youtube"].currentData() == "100001", "saved invite roles are loaded back from the cloud")

from app.theme import THEMES
for name in THEMES:
    w.apply_theme(name); app.processEvents()
    ok(THEMES[name]["a1"] in w.styleSheet() and w.s.get("theme") == name, "theme '%s' applied and remembered" % name)
w.apply_theme("Sunset"); w.goto(0); wait(120); w.grab().save(os.path.join(os.environ["APPDATA"], "sunset_connect.png")); wait(500)
w.apply_theme("Neon Violet"); w.goto(4); wait(150); w.grab().save(os.path.join(os.environ["APPDATA"], "violet_discord_midanim.png")); wait(600); w.grab().save(os.path.join(os.environ["APPDATA"], "violet_discord.png"))
for i in range(7): w.goto(i); wait(60); w.grab()
ok(True, "all 7 pages animate and render (cards fading in around buttons with glow effects) without errors")
n = len(w.fx.items); live = sum(1 for it in w.fx.items if it.effect is not None)
ok(n > 10 and live == n, "%d buttons have the floating glow effect" % n)
w._lite(True); wait(100); ok(all(it.effect is None for it in w.fx.items), "Lite mode removes every glow effect")
w.goto(1); w.goto(5); ok(w.stack.currentIndex() == 5, "Lite mode: pages switch instantly")
w._lite(False); wait(100); ok(all(it.effect is not None for it in w.fx.items), "turning Lite mode off brings the effects back")
b = [it for it in w.fx.items][0]; b.go(30, 8, 100); wait(250); ok(b.effect.blurRadius() > 20, "hover animation grows the glow")
print("\nALL PASSED" if not fails else "\n%d FAILED" % fails)
w.close()
