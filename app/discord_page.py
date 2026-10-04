"""The Discord page of ChatVoice: connect the bot, pick roles, link page, announcements."""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from .discord import post_webhook, run_bg


def _card(title, hint=""):
    f = QFrame()
    f.setObjectName("card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(18, 14, 18, 14)
    t = QLabel(title)
    t.setStyleSheet("font-size:15px; font-weight:600;")
    lay.addWidget(t)
    if hint:
        h = QLabel(hint)
        h.setObjectName("hint")
        h.setWordWrap(True)
        lay.addWidget(h)
    return f, lay


def _row(*widgets):
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    for x in widgets:
        lay.addWidget(x, 1 if isinstance(x, (QLineEdit, QComboBox)) else 0)
    return w


NICE = {"youtube": "YouTube", "twitch": "Twitch", "kick": "Kick"}


class DiscordPage(QScrollArea):
    def __init__(self, settings, cloud, bridge, links):
        super().__init__()
        self.s, self.cloud, self.bridge, self.links = settings, cloud, bridge, links
        self._announced = False
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner.setObjectName("page")
        self.setWidget(inner)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 8, 12, 12)
        lay.setSpacing(14)

        # 1. server
        c, cl = _card("1.  Connect your Discord server",
                      "Quick setup: paste the ChatVoice cloud address, add the bot to your server, then paste the server key. "
                      "For basic invite-based roles, configure only the next section; the other features are optional.")
        self.url = QLineEdit(self.s.get("cloud_url"))
        self.url.setPlaceholderText("https://chatvoice-cloud.something.workers.dev")
        self.url.editingFinished.connect(lambda: self.s.set("cloud_url", self.url.text().strip()))
        self.key = QLineEdit(self.s.get("cloud_token"))
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("Server key")
        self.key.editingFinished.connect(lambda: self.s.set("cloud_token", self.key.text().strip()))
        add = QPushButton("Add bot to my server")
        add.clicked.connect(self.open_setup)
        test = QPushButton("Test connection")
        test.setObjectName("primary")
        test.clicked.connect(self.test)
        self.status = QLabel("Not connected")
        self.status.setObjectName("sub")
        cl.addWidget(self.url)
        cl.addWidget(self.key)
        cl.addWidget(_row(add, test, self.status))
        lay.addWidget(c)

        # 2. roles from normal invite links (recommended)
        c, cl = _card("2.  Roles from your invite links  (recommended)",
                      "In Discord create a normal invite (Invite People > Edit invite link > Never expire, No limit). Paste it below and "
                      "pick a role. Everyone who joins through that invite gets the role automatically (checked every 2 minutes). "
                      "Put the YouTube invite in your video description, so people who join from YouTube get the YouTube role.")
        self.inv_edits, self.inv_boxes = {}, {}
        for src in ("youtube", "twitch", "kick"):
            e = QLineEdit(self.s.get("inv_" + src))
            e.setPlaceholderText("https://discord.gg/...")
            e.editingFinished.connect(lambda k=src, w=e: self.s.set("inv_" + k, w.text().strip()))
            cb = QComboBox()
            cb.addItem("(no role)", "")
            lab = QLabel(NICE[src])
            lab.setMinimumWidth(72)
            self.inv_edits[src], self.inv_boxes[src] = e, cb
            cl.addWidget(_row(lab, e, cb))
        save_inv = QPushButton("Save invite roles")
        save_inv.setObjectName("primary")
        save_inv.clicked.connect(self.save_invites)
        chk = QPushButton("Check now")
        chk.clicked.connect(self.check_invites)
        self.istatus = QLabel("")
        self.istatus.setObjectName("sub")
        self.istatus.setWordWrap(True)
        cl.addWidget(_row(save_inv, chk))
        cl.addWidget(self.istatus)
        lay.addWidget(c)

        advanced_toggle = QPushButton("Show advanced Discord features (optional)")
        advanced_toggle.setCheckable(True)
        lay.addWidget(advanced_toggle)
        advanced_panel = QWidget()
        advanced_lay = QVBoxLayout(advanced_panel)
        advanced_lay.setContentsMargins(0, 0, 0, 0)
        advanced_lay.setSpacing(14)
        advanced_panel.setVisible(False)
        advanced_toggle.toggled.connect(advanced_panel.setVisible)
        lay.addWidget(advanced_panel)

        # Advanced options are hidden until requested.
        c, cl = _card("Chat-activity roles (optional; needs the link page below)",
                      "Viewers who link their account get the Verified role. Active chatters become Regulars. "
                      "Anyone who sends a Super Chat or Bits gets the Supporter role. The ChatVoice role must sit above these roles in Discord.")
        self.boxes = {}
        for key, label in (("role_verified", "Verified (after linking)"), ("role_regular", "Regular (after N messages)"),
                           ("role_supporter", "Supporter (after a paid message)")):
            cb = QComboBox()
            cb.addItem("(none)", "")
            self.boxes[key] = cb
            lab = QLabel(label)
            lab.setMinimumWidth(210)
            if key == "role_regular":
                self.n = QSpinBox()
                self.n.setRange(1, 100000)
                self.n.setValue(int(self.s.get("regular_msgs")))
                cl.addWidget(_row(lab, cb, self.n, QLabel("messages")))
            else:
                cl.addWidget(_row(lab, cb))
        load = QPushButton("Load my roles")
        load.clicked.connect(self.load_roles)
        save = QPushButton("Save rules")
        save.setObjectName("primary")
        save.clicked.connect(self.save_rules)
        self.rstatus = QLabel("")
        self.rstatus.setObjectName("sub")
        cl.addWidget(_row(load, save, self.rstatus))
        advanced_lay.addWidget(c)

        c, cl = _card("Link page for chat-activity roles (optional)",
                      "Share this link in your Discord and stream description. Viewers log in with Discord, get a code, "
                      "and type  !link CODE  in your stream chat. That proves which chat account is theirs.")
        self.link = QLineEdit()
        self.link.setReadOnly(True)
        copy = QPushButton("Copy")
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.link.text()))
        cl.addWidget(_row(self.link, copy))
        advanced_lay.addWidget(c)
        self.update_link()

        c, cl = _card("Discord announcements (optional)",
                      "Create a webhook in Discord: channel settings > Integrations > Webhooks > Copy URL.")
        self.hook = QLineEdit(self.s.get("webhook_url"))
        self.hook.setPlaceholderText("https://discord.com/api/webhooks/...")
        self.hook.editingFinished.connect(lambda: self.s.set("webhook_url", self.hook.text().strip()))
        self.text = QLineEdit(self.s.get("announce_text"))
        self.text.editingFinished.connect(lambda: self.s.set("announce_text", self.text.text()))
        auto = QCheckBox("Announce automatically when I connect to a platform")
        auto.setChecked(bool(self.s.get("announce_auto")))
        auto.toggled.connect(lambda v: self.s.set("announce_auto", v))
        paid = QCheckBox("Post Super Chats / Bits to Discord")
        paid.setChecked(bool(self.s.get("post_super")))
        paid.toggled.connect(lambda v: self.s.set("post_super", v))
        now = QPushButton("Announce now")
        now.clicked.connect(self.announce_now)
        self.hstatus = QLabel("")
        self.hstatus.setObjectName("sub")
        for w in (self.hook, self.text, auto, paid, _row(now, self.hstatus)):
            cl.addWidget(w)
        advanced_lay.addWidget(c)
        lay.addStretch(1)
        bridge.done.connect(self.on_done)

    # ----- actions -----
    def open_setup(self):
        base = self.url.text().strip().rstrip("/")
        self.s.set("cloud_url", base)
        if base:
            QDesktopServices.openUrl(QUrl(base + "/setup"))
        else:
            self.status.setText("Enter the cloud address first")

    def _save_conn(self):
        self.s.set("cloud_url", self.url.text().strip())
        self.s.set("cloud_token", self.key.text().strip())

    def test(self):
        self._save_conn()
        self.status.setText("Checking...")
        run_bg(self.bridge, "ui:test", lambda: self.cloud.call("GET", "/api/config"))

    def load_roles(self):
        self._save_conn()
        self.rstatus.setText("Loading...")
        run_bg(self.bridge, "ui:roles", lambda: self.cloud.call("GET", "/api/roles"))

    def save_rules(self):
        self._save_conn()
        cfg = {"verifiedRole": self.boxes["role_verified"].currentData() or "",
               "regularRole": self.boxes["role_regular"].currentData() or "",
               "supporterRole": self.boxes["role_supporter"].currentData() or "",
               "regularMsgs": self.n.value()}
        for k, b in self.boxes.items():
            self.s.set(k, b.currentData() or "")
        self.s.set("regular_msgs", self.n.value())
        self.rstatus.setText("Saving...")
        run_bg(self.bridge, "ui:save", lambda: self.cloud.call("PUT", "/api/config", cfg))

    def save_invites(self):
        self._save_conn()
        rules = []
        for src, e in self.inv_edits.items():
            code, role = e.text().strip(), self.inv_boxes[src].currentData() or ""
            self.s.set("inv_role_" + src, role)
            if code:
                if not role:
                    self.istatus.setText("Pick a role for the %s invite first (press 'Load my roles' if the list is empty)" % NICE[src])
                    return
                rules.append({"code": code, "role": role, "label": NICE[src]})
        self.istatus.setText("Saving...")
        run_bg(self.bridge, "ui:inv", lambda: self.cloud.call("PUT", "/api/config", {"inviteRules": rules}))

    def check_invites(self):
        self._save_conn()
        self.istatus.setText("Checking...")
        run_bg(self.bridge, "ui:invcheck", lambda: self.cloud.call("POST", "/api/invites/check", {}))

    def announce_now(self):
        self.s.set("webhook_url", self.hook.text().strip())
        self.s.set("announce_text", self.text.text())
        self.hstatus.setText("Sending...")
        url, txt = self.s.get("webhook_url"), self.s.get("announce_text")
        run_bg(self.bridge, "ui:hook", lambda: post_webhook(url, "🔴 " + txt))

    def auto_announce(self):
        """Called by the main window when the first platform connects."""
        if self.s.get("announce_auto") and self.s.get("webhook_url") and not self._announced:
            self._announced = True
            self.announce_now()

    def post_paid(self, m):
        if self.s.get("post_super") and self.s.get("webhook_url"):
            where = "" if m.platform == "tip" else " on " + m.platform
            txt = "💎 **%s** sent **%s**%s%s" % (m.author, m.amount, where, (": " + m.text[:300]) if m.text else "")
            run_bg(self.bridge, "ui:hookpaid", lambda: post_webhook(self.s.get("webhook_url"), txt))

    def update_link(self):
        gid, base = self.s.get("guild_id"), self.s.get("cloud_url").strip().rstrip("/")
        self.link.setText("%s/link/%s" % (base, gid) if gid and base else "Connect your server first (step 1)")

    def _fill_roles(self, roles):
        for src, cb in self.inv_boxes.items():
            saved = self.s.get("inv_role_" + src)
            cb.clear()
            cb.addItem("(no role)", "")
            for r in roles:
                cb.addItem(r["name"], r["id"])
            cb.setCurrentIndex(max(0, cb.findData(saved)))
        for key, cb in self.boxes.items():
            saved = self.s.get(key)
            cb.clear()
            cb.addItem("(none)", "")
            for r in roles:
                cb.addItem(r["name"], r["id"])
            cb.setCurrentIndex(max(0, cb.findData(saved)))

    def on_done(self, tag, res):
        if not tag.startswith("ui:"):
            return
        err = res.get("error")
        if tag == "ui:test":
            if err:
                self.status.setText(err)
                return
            self.s.set("guild_id", res["guildId"])
            self.s.set("guild_name", res["guildName"])
            cfg = res.get("config", {})
            for k, name in (("role_verified", "verifiedRole"), ("role_regular", "regularRole"), ("role_supporter", "supporterRole")):
                if name in cfg:
                    self.s.set(k, cfg[name])
            for rule in cfg.get("inviteRules", []) or []:
                src = str(rule.get("label", "")).lower()
                if src in self.inv_edits:
                    self.inv_edits[src].setText("https://discord.gg/" + rule["code"])
                    self.s.set("inv_" + src, "https://discord.gg/" + rule["code"])
                    self.s.set("inv_role_" + src, rule["role"])
            if cfg.get("regularMsgs"):
                self.n.setValue(int(cfg["regularMsgs"]))
            self.status.setText("Connected to %s" % res["guildName"])
            self.update_link()
            self.links.refresh()
            self.load_roles()
        elif tag == "ui:roles":
            if err:
                self.rstatus.setText(err)
            else:
                self._fill_roles(res["roles"])
                self.rstatus.setText("%d roles loaded" % len(res["roles"]))
        elif tag == "ui:save":
            self.rstatus.setText(err or "Rules saved")
        elif tag == "ui:inv":
            self.istatus.setText(err or "Saved. ChatVoice's cloud checks for new members every 2 minutes.")
        elif tag == "ui:invcheck":
            if err or res.get("error"):
                self.istatus.setText(err or res["error"])
                return
            lines = []
            for r in res.get("rules", []):
                lines.append("%s: %s" % (r["label"], "invite found, used %d times so far" % r["uses"] if r.get("found")
                                         else "invite NOT found - create it in Discord or fix the link"))
            lines += res.get("notes", [])
            if res.get("assigned"):
                lines.append("Gave roles to %d new member(s)." % len(res["assigned"]))
            self.istatus.setText("\n".join(lines) or "Nothing new")
        elif tag == "ui:hook":
            self.hstatus.setText(err or "Sent")
