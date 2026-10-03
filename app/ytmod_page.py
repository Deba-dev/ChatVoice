"""YouTube auto-moderation page."""
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget

from .discord_page import _card, _row


class YtModPage(QScrollArea):
    def __init__(self, settings, auth, bridge, moderator):
        super().__init__()
        self.s, self.auth, self.bridge, self.mod = settings, auth, bridge, moderator
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner.setObjectName("page")
        self.setWidget(inner)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 8, 12, 12)
        lay.setSpacing(14)

        c, cl = _card("1.  Sign in with the moderator account",
                      "Reading chat needs no sign-in. Deleting messages does. Sign in with your channel account, or better, with a separate "
                      "'ChatVoice bot' Google account that you added as a moderator in YouTube Studio > Settings > Community.")
        self.cid = QLineEdit(self.s.get("g_client_id"))
        self.cid.setPlaceholderText("Google client ID (from your Google Cloud project)")
        self.cid.editingFinished.connect(lambda: self.s.set("g_client_id", self.cid.text().strip()))
        self.csec = QLineEdit(self.s.get("g_client_secret"))
        self.csec.setEchoMode(QLineEdit.Password)
        self.csec.setPlaceholderText("Google client secret")
        self.csec.editingFinished.connect(lambda: self.s.set("g_client_secret", self.csec.text().strip()))
        self.sign_in = QPushButton("Sign in with Google")
        self.sign_in.setObjectName("primary")
        self.sign_in.clicked.connect(self.login)
        out = QPushButton("Sign out")
        out.clicked.connect(self.logout)
        self.state = QLabel("")
        self.state.setObjectName("sub")
        for w in (self.cid, self.csec, _row(self.sign_in, out, self.state)):
            cl.addWidget(w)
        lay.addWidget(c)

        c, cl = _card("2.  What to remove",
                      "Mods and the streamer are never touched. Start in TEST MODE: ChatVoice only tells you what it WOULD delete.")
        for text, key in (("Delete messages with blocked words (from the Moderation page)", "mod_del_blocked"),
                          ("Delete messages with links", "mod_del_links"),
                          ("Delete spam and repeated messages", "mod_del_spam"),
                          ("TEST MODE: only show what would be deleted (turn off to really delete)", "mod_dry_run")):
            cb = QCheckBox(text)
            cb.setChecked(bool(self.s.get(key)))
            cb.toggled.connect(lambda v, k=key: self.s.set(k, v))
            cl.addWidget(cb)
        for label, key, lo, hi, suffix in (("Daily action limit (each delete costs 50 of Google's 10,000 daily units)", "mod_budget", 1, 190, ""),
                                           ("Time out a viewer after this many deletions in 10 minutes", "mod_timeout_after", 2, 20, ""),
                                           ("Time-out length", "mod_timeout_secs", 10, 3600, " s")):
            sp = QSpinBox()
            sp.setRange(lo, hi)
            sp.setSuffix(suffix)
            sp.setValue(int(self.s.get(key)))
            sp.valueChanged.connect(lambda v, k=key: self.s.set(k, v))
            cl.addWidget(_row(QLabel(label), sp))
        self.used = QLabel("")
        self.used.setObjectName("hint")
        cl.addWidget(self.used)
        lay.addWidget(c)
        lay.addStretch(1)
        bridge.done.connect(self.on_done)
        self.refresh()

    def refresh(self):
        self.state.setText("Signed in" if self.auth.logged_in else "Not signed in")
        self.used.setText("Actions used today: %d of %d" % (self.mod.used_today(), int(self.s.get("mod_budget"))))

    def login(self):
        self.s.set("g_client_id", self.cid.text().strip())
        self.s.set("g_client_secret", self.csec.text().strip())
        try:
            url = self.auth.begin_login(self.bridge)
        except Exception as e:
            self.state.setText(str(e))
            return
        QDesktopServices.openUrl(QUrl(url))
        self.state.setText("Finish signing in in your browser...")

    def logout(self):
        self.auth.logout()
        self.refresh()

    def on_done(self, tag, res):
        if tag == "yt:login":
            self.state.setText("Signed in" if res.get("ok") else "Sign-in failed: %s" % res.get("error"))
        if tag == "yt:sweep":
            self.refresh()
