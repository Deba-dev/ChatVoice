"""ChatVoice main window. Animations only run on interaction, so idle CPU stays near zero."""
import html
import os
import sys
import time

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontDatabase, QTextBlockFormat, QTextCursor
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QColorDialog, QComboBox, QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSlider, QSpinBox, QStackedWidget,
                               QTextEdit, QVBoxLayout, QWidget)

from . import hinglish
from .discord import Bridge, Cloud, LinkManager
from .discord_page import DiscordPage
from .overlay import Overlay
from .overlay_ui import OverlayPage
from .payments import TipPoller
from .payments_page import PaymentsPage
from .ytmod import GoogleAuth, YtModerator
from .ytmod_page import YtModPage
from .models import Message
from .moderation import Moderator
from .platforms import Hub, KickSource, TwitchSource, YouTubeSource
from .settings import Settings, data_dir
from .speech import VOICES, Speaker
from .theme import DEFAULT_THEME, FX, THEMES, build_qss
from .updater import Updater
from .version import CREATOR, STAGE, VERSION, label

COLORS = {"youtube": "#ff4d4d", "twitch": "#9146ff", "kick": "#53fc18", "test": "#00d4ff", "tip": "#ffd24d"}
TAGS = {"youtube": "YT", "twitch": "TW", "kick": "KICK", "test": "TEST", "tip": "TIP"}
PAGES = ("Connect", "Live chat", "Voice", "Moderation", "Discord", "Payments", "YouTube mod", "OBS overlays")
NAV_MARK = ("◎", "☰", "♫", "⌗", "◈", "₹", "▶", "▣")
PAGE_BLURB = (
    "Connect your streaming platforms and manage live chat from one place.",
    "Messages that will be read aloud, and the ones moderation skipped.",
    "Choose the voice that speaks your chat.",
    "Decide which messages are read and which are skipped.",
    "Link viewers and send roles through your server.",
    "Hear paid messages and tips on stream.",
    "Moderate YouTube chat from this PC.",
    "Browser sources for alerts and chat in OBS.",
)
MARKS = {"youtube": ("YT", "#ff4d4d"), "twitch": ("TW", "#9146ff"), "kick": ("KK", "#53fc18")}
CHAT_FONTS = ("Poppins", "Arial", "Segoe UI", "Calibri", "Verdana", "Tahoma", "Consolas", "Cascadia Mono", "Inter", "Roboto", "DM Sans", "Space Grotesk", "JetBrains Mono")
CHAT_WEIGHTS = (("Light", 300), ("Regular", 400), ("Medium", 500), ("Semi Bold", 600), ("Bold", 700), ("Extra Bold", 800))
CHAT_TRANSFORMS = (("Normal", "normal"), ("Uppercase", "upper"), ("Lowercase", "lower"), ("Capitalize", "caps"))
CHAT_ALIGNS = (("Left", "left"), ("Center", "center"), ("Right", "right"))


def available_chat_fonts():
    have = set(QFontDatabase.families())
    found = [name for name in CHAT_FONTS if name in have or name == "Poppins"]
    return ["System Default"] + found


def shape_chat_text(text, mode):
    if mode == "upper":
        return (text or "").upper()
    if mode == "lower":
        return (text or "").lower()
    if mode == "caps":
        return (text or "").title()
    return text or ""
ROOT = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def esc(s):
    return html.escape(s or "")


def labeled(text, widget, hint=""):
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 2, 0, 2)
    lab = QLabel(text)
    lab.setMinimumWidth(190)
    lay.addWidget(lab)
    lay.addWidget(widget, 1)
    if hint:
        h = QLabel(hint)
        h.setObjectName("hint")
        lay.addWidget(h)
    return w


class PlatformCard(QFrame):
    def __init__(self, key, title, placeholder, source, settings, extra=None, hint="", field=""):
        super().__init__()
        self.setObjectName("tile")
        self.key, self.source, self.s = key, source, settings
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        head = QHBoxLayout()
        head.setSpacing(10)
        letter, color = MARKS.get(key, ("•", "#888888"))
        mark = QLabel(letter)
        mark.setAlignment(Qt.AlignCenter)
        mark.setFixedSize(36, 36)
        mark.setStyleSheet("background:%s; color:#0b0b10; font-weight:700; font-size:12px; border-radius:10px;" % color)
        head.addWidget(mark)
        names = QVBoxLayout()
        names.setSpacing(0)
        name = QLabel(title)
        name.setStyleSheet("font-size:15px; font-weight:650;")
        names.addWidget(name)
        if hint:
            h = QLabel(hint)
            h.setObjectName("hint")
            h.setWordWrap(True)
            names.addWidget(h)
        head.addLayout(names, 1)
        self.status = QLabel("●  Offline")
        self.status.setObjectName("pill")
        head.addWidget(self.status, 0, Qt.AlignTop)
        lay.addLayout(head)
        cap = QLabel(field or placeholder)
        cap.setObjectName("field")
        lay.addWidget(cap)
        self.edit = QLineEdit(settings.get(key))
        self.edit.setPlaceholderText(placeholder)
        lay.addWidget(self.edit)
        self.extra = None
        if extra:
            box = QFrame()
            box.setObjectName("advanced")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(0, 4, 0, 0)
            bl.setSpacing(4)
            lab = QLabel(extra[1])
            lab.setObjectName("hint")
            bl.addWidget(lab)
            self.extra = QLineEdit(settings.get(extra[0]))
            self.extra.setObjectName("optional")
            self.extra.setPlaceholderText("Optional")
            bl.addWidget(self.extra)
            lay.addWidget(box)
        self.btn = QPushButton("Connect")
        self.btn.setObjectName("primary")
        self.btn.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.btn, 0, Qt.AlignLeft)
        self.btn.clicked.connect(self.toggle)
        self.edit.returnPressed.connect(self.toggle)

    def enterEvent(self, event):
        if not self.s.get("lite_mode") and self.graphicsEffect() is None:
            shade = QGraphicsDropShadowEffect(self)
            shade.setBlurRadius(28)
            shade.setOffset(0, 10)
            shade.setColor(QColor(0, 0, 0, 160))
            self.setGraphicsEffect(shade)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setGraphicsEffect(None)
        super().leaveEvent(event)

    def args(self):
        self.s.set(self.key, self.edit.text().strip())
        if self.extra is not None:
            self.s.set("kick_room", self.extra.text().strip())
            return (self.edit.text().strip(), self.extra.text().strip())
        return (self.edit.text().strip(),)

    def toggle(self):
        if self.source.running:
            self.source.stop()
            self._show("Stopping...", False)
        else:
            self.source.start(*self.args())

    def _show(self, text, ok):
        self.status.setText("●  " + text)
        if ok:
            kind = "pillOn"
        elif "..." in text:
            kind = "pillWait"
        elif text in ("Not connected", "Disconnected", "Offline"):
            kind = "pill"
            self.status.setText("●  Offline")
        else:
            kind = "pillBad"
        self.status.setObjectName(kind)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        if self.source.running and "..." in text:
            self.btn.setText("Connecting...")
            role = "primary"
        elif self.source.running:
            self.btn.setText("Disconnect")
            role = "stop"
        elif kind == "pillBad":
            self.btn.setText("Retry")
            role = "primary"
        else:
            self.btn.setText("Connect")
            role = "primary"
        self.btn.setObjectName(role)
        self.btn.style().unpolish(self.btn)
        self.btn.style().polish(self.btn)

    def set_status(self, text, ok):
        self._show(text, ok)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("ChatVoice (%s) \u2014 by %s" % (STAGE, CREATOR))
        self.resize(1180, 760)
        self.setMinimumSize(980, 680)
        self.s = Settings()
        self.hub = Hub()
        self.speaker = Speaker(self.s)
        self.words_path = os.path.join(data_dir(), "hinglish_words.txt")
        self.blocked_path = os.path.join(data_dir(), "blocked_words.txt")
        hinglish.load_words(self.words_path)
        hinglish.on_unknown = self._unknown_word
        self.mod = Moderator(self.s, self.blocked_path)
        self.connected = set()
        self._anims = []
        self._anim_targets = []
        self.fx = FX()
        self.fx.enabled = not bool(self.s.get("lite_mode"))
        self.bridge = Bridge()
        self.cloud = Cloud(self.s)
        self.links = LinkManager(self.s, self.cloud, self.bridge, os.path.join(data_dir(), "counts.json"))
        self.discord = DiscordPage(self.s, self.cloud, self.bridge, self.links)
        self.poller = TipPoller(self.s, self.cloud, self.bridge)
        self.payments = PaymentsPage(self.s, self.cloud, self.bridge, self.poller)
        self.gauth = GoogleAuth(self.s)
        self.ytmod = YtModerator(self.s, self.gauth, self.bridge)
        self.ytpage = YtModPage(self.s, self.gauth, self.bridge, self.ytmod)
        self.overlay = Overlay(self.s, os.path.join(ROOT, "assets", "fonts"), self._overlay_cfg)
        self.overlay.start()
        self.ovpage = OverlayPage(self.s, self.overlay)
        self.updater = Updater(self.s)
        self.pending_update = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())
        canvas = QWidget()
        canvas.setObjectName("canvas")
        right = QVBoxLayout(canvas)
        right.setContentsMargins(28, 18, 28, 18)
        right.setSpacing(14)
        right.addWidget(self._build_topbar())
        self.banner = self._build_banner()
        right.addWidget(self.banner)
        self.stack = QStackedWidget()
        for page in (self._page_connect(), self._page_feed(), self._page_voice(), self._page_mod(), self.discord, self.payments, self.ytpage, self.ovpage):
            self.stack.addWidget(page)
        right.addWidget(self.stack, 1)
        root.addWidget(canvas, 1)

        self.hub.message.connect(self.on_message)
        self.hub.status.connect(self.on_status)
        self.speaker.note.connect(lambda t: self.feed.append("<span style='color:#ffb020'>%s</span>" % esc(t)))
        self.links.notice.connect(lambda t: self.feed.append("<span style='color:#7c9cff'>Discord: %s</span>" % esc(t)))
        self.sync = QTimer(self)                      # report activity to Discord once a minute
        self.sync.timeout.connect(self.links.save)
        self.sync.start(60000)
        self.relink = QTimer(self)                    # refresh the list of linked viewers every 5 minutes
        self.relink.timeout.connect(self.links.refresh)
        self.relink.start(300000)
        QTimer.singleShot(2000, self.links.refresh)
        self.poller.tip.connect(self.on_tip)
        self.poller.notice.connect(lambda t: self.feed.append("<span style='color:#ffd24d'>%s</span>" % esc(t)))
        self.ytmod.notice.connect(lambda t: self.feed.append("<span style='color:#ff8a5c'>YouTube mod: %s</span>" % esc(t)))
        QTimer.singleShot(2500, self.poller.apply)
        self.updater.found.connect(self._update_found)
        self.updater.status.connect(self._update_status)
        self.updater.message.connect(lambda t: self.feed.append("<span style='color:#7cf0c0'>Update: %s</span>" % esc(t)))
        self.updater.progress.connect(self.banner_text.setText)
        self.updater.quit_now.connect(lambda: QTimer.singleShot(400, QApplication.quit))
        QTimer.singleShot(6000, self._auto_update)
        self.apply_theme(self.s.get("theme"))
        self.goto(0)

    # ---------- layout ----------
    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("side")
        side.setFixedWidth(228)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(0, 16, 0, 14)
        lay.setSpacing(2)
        self.logo = QLabel("ChatVoice")
        self.logo.setObjectName("logo")
        self.logo.setContentsMargins(16, 0, 12, 8)
        lay.addWidget(self.logo)
        self.nav = QButtonGroup(self)
        self.nav.setExclusive(True)
        groups = (("Workspace", (0, 1, 2)), ("Tools", (3, 4, 5, 6, 7)))
        for title, indexes in groups:
            g = QLabel(title.upper())
            g.setObjectName("group")
            lay.addWidget(g)
            for i in indexes:
                b = QPushButton("%s    %s" % (NAV_MARK[i], PAGES[i]))
                b.setObjectName("nav")
                b.setCheckable(True)
                b.setCursor(Qt.PointingHandCursor)
                self.nav.addButton(b, i)
                lay.addWidget(b)
        self.nav.idClicked.connect(self.goto)
        lay.addStretch(1)
        box = QWidget()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(16, 8, 16, 4)
        bl.setSpacing(6)
        lab = QLabel("SETTINGS")
        lab.setObjectName("group")
        bl.addWidget(lab)
        theme = QComboBox()
        theme.addItems(list(THEMES))
        theme.setCurrentText(self.s.get("theme") if self.s.get("theme") in THEMES else DEFAULT_THEME)
        theme.currentTextChanged.connect(self.apply_theme)
        bl.addWidget(theme)
        lite = QCheckBox("Lite mode")
        lite.setToolTip("Turns off fade and hover motion. Use it on slow PCs or while gaming.")
        lite.setChecked(bool(self.s.get("lite_mode")))
        lite.toggled.connect(self._lite)
        bl.addWidget(lite)
        upd = QPushButton("Check for updates")
        upd.setCursor(Qt.PointingHandCursor)
        upd.clicked.connect(lambda: self.updater.check(True))
        bl.addWidget(upd)
        lay.addWidget(box)
        ver = QLabel(label())
        ver.setObjectName("hint")
        ver.setContentsMargins(16, 4, 12, 0)
        by = QLabel(CREATOR)
        by.setObjectName("hint")
        by.setContentsMargins(16, 0, 12, 0)
        lay.addWidget(ver)
        lay.addWidget(by)
        return side

    def _build_banner(self):
        b = QFrame()
        b.setObjectName("banner")
        lay = QHBoxLayout(b)
        lay.setContentsMargins(16, 8, 12, 8)
        self.banner_text = QLabel("")
        self.banner_text.setWordWrap(True)
        lay.addWidget(self.banner_text, 1)
        self.upd_btn = QPushButton("Update now")
        self.upd_btn.setObjectName("primary")
        self.upd_btn.clicked.connect(self._update_now)
        later = QPushButton("Later")
        later.clicked.connect(b.hide)
        lay.addWidget(self.upd_btn)
        lay.addWidget(later)
        b.hide()
        return b

    def _update_found(self, info):
        self.pending_update = info
        self.banner_text.setText("A new version is available: %s (you have %s)" % (info["version"], VERSION))
        self.upd_btn.setEnabled(True)
        self.upd_btn.show()
        self.banner.show()

    def _update_status(self, text):
        self.pending_update = None
        self.banner_text.setText(text)
        self.upd_btn.hide()
        self.banner.show()

    def _update_now(self):
        info = self.pending_update
        if not info:
            return
        if not info.get("asset"):
            self.feed.append("<span style='color:#7cf0c0'>Update: No installer file is attached to this release yet.</span>")
            return
        self.banner_text.setText("Downloading update...")
        self.upd_btn.setEnabled(False)
        self.updater.install(info)

    def _auto_update(self):
        if self.s.get("auto_update_check") and time.time() - float(self.s.get("update_last") or 0) > 20 * 3600:
            self.updater.check(False)

    def _overlay_cfg(self):
        t = THEMES.get(self.s.get("theme"), THEMES[DEFAULT_THEME])
        return {"colors": {"a1": t["a1"], "a2": t["a2"], "a3": t["a3"]}, "sound": bool(self.s.get("ov_sound")),
                "seconds": int(self.s.get("ov_seconds")), "showMessage": bool(self.s.get("ov_show_message")),
                "chatSeconds": int(self.s.get("ov_chat_seconds")), "maxLines": 8}

    def _build_topbar(self):
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 8)
        left = QVBoxLayout()
        left.setSpacing(2)
        row = QHBoxLayout()
        self.title = QLabel("Connect")
        self.title.setObjectName("title")
        row.addWidget(self.title)
        self.live = QLabel("● LIVE")
        self.live.setObjectName("live")
        self.live_fx = QGraphicsOpacityEffect(self.live)
        self.live.setGraphicsEffect(self.live_fx)
        self.live.hide()
        self.pulse = QPropertyAnimation(self.live_fx, b"opacity", self)
        self.pulse.setDuration(1600)
        self.pulse.setKeyValueAt(0, 1.0)
        self.pulse.setKeyValueAt(0.5, 0.35)
        self.pulse.setKeyValueAt(1, 1.0)
        self.pulse.setLoopCount(-1)
        row.addWidget(self.live)
        row.addStretch(1)
        left.addLayout(row)
        self.blurb = QLabel(PAGE_BLURB[0])
        self.blurb.setObjectName("sub")
        self.blurb.setWordWrap(True)
        left.addWidget(self.blurb)
        lay.addLayout(left, 1)
        self.mute_btn = QPushButton("Mute")
        self.mute_btn.setObjectName("quiet")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setChecked(bool(self.s.get("muted")))
        self.mute_btn.setToolTip("Silence the voice and clear the queue")
        self.mute_btn.setCursor(Qt.PointingHandCursor)
        self.mute_btn.toggled.connect(self._mute)
        skip = QPushButton("Skip")
        skip.setObjectName("quiet")
        skip.setToolTip("Skip the message being spoken")
        skip.setCursor(Qt.PointingHandCursor)
        skip.clicked.connect(self.speaker.skip)
        test = QPushButton("Test voice")
        test.setObjectName("quiet")
        test.setToolTip("Speak a short sample")
        test.setCursor(Qt.PointingHandCursor)
        test.clicked.connect(self.test_voice)
        for b in (self.mute_btn, skip, test):
            lay.addWidget(b, 0, Qt.AlignTop)
        return bar

    def _stat(self, number, caption):
        chip = QFrame()
        chip.setObjectName("stat")
        lay = QVBoxLayout(chip)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(0)
        num = QLabel(number)
        num.setObjectName("statNum")
        cap = QLabel(caption)
        cap.setObjectName("hint")
        lay.addWidget(num)
        lay.addWidget(cap)
        return chip, num

    def _sync_summary(self):
        on = len(self.connected)
        self.num_on.setText(str(on))
        self.num_off.setText(str(3 - on))

    def _page_connect(self):
        page = QWidget()
        page.setObjectName("page")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 4, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(14)
        stats = QHBoxLayout()
        stats.setSpacing(10)
        platforms, _ = self._stat("3", "Platforms")
        connected, self.num_on = self._stat("0", "Connected")
        offline, self.num_off = self._stat("3", "Offline")
        for chip in (platforms, connected, offline):
            stats.addWidget(chip, 1)
        lay.addLayout(stats)
        self.cards = {
            "youtube": PlatformCard("youtube", "YouTube Live", "Paste a live link or video ID", YouTubeSource(self.hub), self.s,
                                    hint="Public live chat. No sign-in.", field="Stream link or video ID"),
            "twitch": PlatformCard("twitch", "Twitch", "Channel name", TwitchSource(self.hub), self.s,
                                   hint="Reads chat without a token.", field="Channel name"),
            "kick": PlatformCard("kick", "Kick", "Channel name", KickSource(self.hub), self.s,
                                 extra=("kick_room", "Chatroom ID, only if the name lookup fails"),
                                 hint="Public chat by channel name.", field="Channel name"),
        }
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.addWidget(self.cards["youtube"], 0, 0)
        grid.addWidget(self.cards["twitch"], 0, 1)
        grid.addWidget(self.cards["kick"], 1, 0)
        aside = QFrame()
        aside.setObjectName("aside")
        al = QVBoxLayout(aside)
        al.setContentsMargins(18, 16, 18, 16)
        title = QLabel("One voice for every chat")
        title.setStyleSheet("font-size:15px; font-weight:650;")
        body = QLabel("Connect any mix of platforms. ChatVoice speaks the messages you allow, and keeps passwords off this page.")
        body.setObjectName("sub")
        body.setWordWrap(True)
        al.addWidget(title)
        al.addWidget(body)
        al.addStretch(1)
        grid.addWidget(aside, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        lay.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        return page

    def _page_feed(self):
        page = QWidget()
        page.setObjectName("page")
        lay = QHBoxLayout(page)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(12)
        self.feed = QTextEdit()
        self.feed.setObjectName("feed")
        self.feed.setReadOnly(True)
        self.feed.document().setMaximumBlockCount(300)
        self.feed.setPlaceholderText("Chat messages appear here. Grey lines were skipped by moderation.")
        lay.addWidget(self.feed, 1)
        lay.addWidget(self._chat_style_panel())
        self._apply_chat_style()
        return page

    def _chat_style_panel(self):
        panel = QFrame()
        panel.setObjectName("tile")
        panel.setFixedWidth(232)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(6)
        title = QLabel("Text style")
        title.setStyleSheet("font-size:14px; font-weight:650;")
        outer.addWidget(title)
        note = QLabel("Live chat messages only")
        note.setObjectName("hint")
        outer.addWidget(note)
        self.chat_font = QComboBox()
        for name in available_chat_fonts():
            self.chat_font.addItem(name, "" if name == "System Default" else name)
        self.chat_font.setCurrentIndex(max(0, self.chat_font.findData(self.s.get("chat_font") or "")))
        self.chat_font.currentIndexChanged.connect(lambda _: self._save_chat("chat_font", self.chat_font.currentData()))
        outer.addWidget(self._style_label("Font"))
        outer.addWidget(self.chat_font)
        self.chat_size, size_row = self._style_slider("chat_size", 10, 32, lambda v: "%d px" % v)
        outer.addWidget(self._style_label("Size"))
        outer.addLayout(size_row)
        self.chat_weight = QComboBox()
        for name, value in CHAT_WEIGHTS:
            self.chat_weight.addItem(name, value)
        self.chat_weight.setCurrentIndex(max(0, self.chat_weight.findData(int(self.s.get("chat_weight") or 400))))
        self.chat_weight.currentIndexChanged.connect(lambda _: self._save_chat("chat_weight", int(self.chat_weight.currentData())))
        outer.addWidget(self._style_label("Weight"))
        outer.addWidget(self.chat_weight)
        color_row = QHBoxLayout()
        self.chat_color_btn = QPushButton()
        self.chat_color_btn.setObjectName("quiet")
        self.chat_color_btn.setCursor(Qt.PointingHandCursor)
        self.chat_color_btn.clicked.connect(self._pick_chat_color)
        color_row.addWidget(self.chat_color_btn, 1)
        outer.addWidget(self._style_label("Color"))
        outer.addLayout(color_row)
        self.chat_line, line_row = self._style_slider("chat_line", 10, 20, lambda v: "%.1f" % (v / 10))
        outer.addWidget(self._style_label("Line height"))
        outer.addLayout(line_row)
        self.chat_track, track_row = self._style_slider("chat_track", -1, 4, lambda v: "%d px" % v)
        outer.addWidget(self._style_label("Letter spacing"))
        outer.addLayout(track_row)
        self.chat_opacity, fade_row = self._style_slider("chat_opacity", 0, 100, lambda v: "%d%%" % v)
        outer.addWidget(self._style_label("Opacity"))
        outer.addLayout(fade_row)
        self.chat_transform = QComboBox()
        for name, value in CHAT_TRANSFORMS:
            self.chat_transform.addItem(name, value)
        self.chat_transform.setCurrentIndex(max(0, self.chat_transform.findData(self.s.get("chat_transform") or "normal")))
        self.chat_transform.currentIndexChanged.connect(lambda _: self._save_chat("chat_transform", self.chat_transform.currentData()))
        outer.addWidget(self._style_label("Transform"))
        outer.addWidget(self.chat_transform)
        self.chat_style = QComboBox()
        self.chat_style.addItem("Normal", False)
        self.chat_style.addItem("Italic", True)
        self.chat_style.setCurrentIndex(1 if self.s.get("chat_italic") else 0)
        self.chat_style.currentIndexChanged.connect(lambda _: self._save_chat("chat_italic", bool(self.chat_style.currentData())))
        outer.addWidget(self._style_label("Style"))
        outer.addWidget(self.chat_style)
        self.chat_align = QComboBox()
        for name, value in CHAT_ALIGNS:
            self.chat_align.addItem(name, value)
        self.chat_align.setCurrentIndex(max(0, self.chat_align.findData(self.s.get("chat_align") or "left")))
        self.chat_align.currentIndexChanged.connect(lambda _: self._save_chat("chat_align", self.chat_align.currentData()))
        outer.addWidget(self._style_label("Alignment"))
        outer.addWidget(self.chat_align)
        outer.addWidget(self._style_label("Preview"))
        self.chat_preview = QLabel("Samir: Hello everyone!\nAlex: Welcome to the stream!")
        self.chat_preview.setWordWrap(True)
        self.chat_preview.setMinimumHeight(64)
        outer.addWidget(self.chat_preview)
        reset = QPushButton("Reset to default")
        reset.setObjectName("quiet")
        reset.setCursor(Qt.PointingHandCursor)
        reset.clicked.connect(self._reset_chat_style)
        outer.addWidget(reset)
        outer.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setFixedWidth(248)
        scroll.setWidget(panel)
        return scroll

    def _style_label(self, text):
        lab = QLabel(text)
        lab.setObjectName("field")
        return lab

    def _style_slider(self, key, lo, hi, fmt):
        row = QHBoxLayout()
        sl = QSlider(Qt.Horizontal)
        sl.setRange(lo, hi)
        sl.setValue(int(self.s.get(key)))
        value = QLabel(fmt(sl.value()))
        value.setObjectName("hint")
        value.setMinimumWidth(42)
        sl.valueChanged.connect(lambda v, k=key, f=fmt, lab=value: (lab.setText(f(v)), self._save_chat(k, int(v))))
        row.addWidget(sl, 1)
        row.addWidget(value)
        return sl, row

    def _save_chat(self, key, value):
        self.s.set(key, value)
        self._apply_chat_style()

    def _pick_chat_color(self):
        current = QColor(self.s.get("chat_color") or "#f4f4f8")
        chosen = QColorDialog.getColor(current, self, "Live chat text color")
        if chosen.isValid():
            self._save_chat("chat_color", chosen.name())

    def _reset_chat_style(self):
        from .settings import DEFAULTS
        for key in ("chat_font", "chat_size", "chat_weight", "chat_color", "chat_line", "chat_track", "chat_opacity", "chat_transform", "chat_italic", "chat_align"):
            self.s.set(key, DEFAULTS[key])
        self.chat_font.setCurrentIndex(max(0, self.chat_font.findData("")))
        self.chat_size.setValue(int(DEFAULTS["chat_size"]))
        self.chat_weight.setCurrentIndex(max(0, self.chat_weight.findData(400)))
        self.chat_line.setValue(int(DEFAULTS["chat_line"]))
        self.chat_track.setValue(int(DEFAULTS["chat_track"]))
        self.chat_opacity.setValue(int(DEFAULTS["chat_opacity"]))
        self.chat_transform.setCurrentIndex(0)
        self.chat_style.setCurrentIndex(0)
        self.chat_align.setCurrentIndex(0)
        self._apply_chat_style()

    def _apply_chat_style(self):
        family = self.s.get("chat_font") or "Poppins"
        size = int(self.s.get("chat_size") or 13)
        weight = int(self.s.get("chat_weight") or 400)
        italic = bool(self.s.get("chat_italic"))
        track = int(self.s.get("chat_track") or 0)
        color = QColor(self.s.get("chat_color") or "#f4f4f8")
        color.setAlphaF(max(0, min(100, int(self.s.get("chat_opacity") or 100))) / 100)
        align = {"center": Qt.AlignCenter, "right": Qt.AlignRight}.get(self.s.get("chat_align"), Qt.AlignLeft)
        font = QFont(family if family != "System Default" else "Poppins")
        if not self.s.get("chat_font"):
            font = QFont("Poppins")
        font.setPixelSize(size)
        font.setWeight(QFont.Weight(weight) if weight in (100, 200, 300, 400, 500, 600, 700, 800, 900) else QFont.Weight.Normal)
        font.setItalic(italic)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, track)
        css = "QTextEdit#feed { color: %s; font-family: \"%s\"; font-size: %dpx; font-weight: %d; font-style: %s; background: rgba(0,0,0,0.35); border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; }" % (
            color.name(QColor.NameFormat.HexArgb), font.family(), size, weight, "italic" if italic else "normal")
        self.feed.setFont(font)
        self.feed.setStyleSheet(css)
        self.feed.setAlignment(align)
        block = QTextBlockFormat()
        block.setLineHeight(float(int(self.s.get("chat_line") or 10) * 10), 1)
        block.setAlignment(align)
        cursor = QTextCursor(self.feed.document())
        cursor.beginEditBlock()
        block_cursor = self.feed.document().firstBlock()
        while block_cursor.isValid():
            cursor.setPosition(block_cursor.position())
            cursor.setBlockFormat(block)
            block_cursor = block_cursor.next()
        cursor.endEditBlock()
        if hasattr(self, "chat_preview"):
            self.chat_preview.setFont(font)
            self.chat_preview.setAlignment(align)
            self.chat_preview.setStyleSheet("color: %s; background: rgba(0,0,0,0.28); border-radius: 10px; padding: 8px;" % color.name(QColor.NameFormat.HexArgb))
            sample = shape_chat_text("Samir: Hello everyone!", self.s.get("chat_transform")) + "\n" + shape_chat_text("Alex: Welcome to the stream!", self.s.get("chat_transform"))
            self.chat_preview.setText(sample)
        if hasattr(self, "chat_color_btn"):
            self.chat_color_btn.setText(self.s.get("chat_color") or "#f4f4f8")
            self.chat_color_btn.setStyleSheet("QPushButton { color: %s; }" % (self.s.get("chat_color") or "#f4f4f8"))

    def _bind_check(self, text, key):
        cb = QCheckBox(text)
        cb.setChecked(bool(self.s.get(key)))
        cb.toggled.connect(lambda v: self.s.set(key, v))
        return cb

    def _bind_slider(self, key, lo, hi):
        sl = QSlider(Qt.Horizontal)
        sl.setRange(lo, hi)
        sl.setValue(int(self.s.get(key)))
        sl.valueChanged.connect(lambda v: self.s.set(key, v))
        return sl

    def _bind_spin(self, key, lo, hi, suffix=""):
        sp = QSpinBox()
        sp.setRange(lo, hi)
        sp.setSuffix(suffix)
        sp.setValue(int(self.s.get(key)))
        sp.valueChanged.connect(lambda v: self.s.set(key, v))
        return sp

    def _voice_combo(self, key):
        cb = QComboBox()
        for name, vid in VOICES:
            cb.addItem(name, vid)
        cb.setCurrentIndex(max(0, cb.findData(self.s.get(key))))
        cb.currentIndexChanged.connect(lambda _: self.s.set(key, cb.currentData()))
        return cb

    def _page_voice(self):
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 8, 0, 0)
        eng = QComboBox()
        eng.addItem("Neural voices (online, best quality)", "neural")
        eng.addItem("Windows voices (offline)", "windows")
        eng.setCurrentIndex(max(0, eng.findData(self.s.get("engine"))))
        eng.currentIndexChanged.connect(lambda _: self.s.set("engine", eng.currentData()))
        lay.addWidget(labeled("Voice engine", eng))
        lay.addWidget(labeled("Hindi (Devanagari) voice", self._voice_combo("hi_voice")))
        lay.addWidget(labeled("Hinglish / English voice", self._voice_combo("en_voice")))
        lay.addWidget(self._bind_check("Different voice for each viewer", "per_viewer"))
        lay.addWidget(labeled("Speed", self._bind_slider("rate", -5, 5)))
        lay.addWidget(labeled("Volume", self._bind_slider("volume", 0, 100)))
        lay.addWidget(self._bind_check("Say the viewer's name first", "read_name"))
        lay.addWidget(self._bind_check("Read Super Chats / Bits (paid messages are never dropped)", "read_super"))
        lay.addWidget(labeled("Max queued messages", self._bind_spin("queue_max", 1, 20),
                              "older ones are dropped when chat is fast"))
        row = QHBoxLayout()
        b1 = QPushButton("Edit Hinglish word list")
        b1.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.words_path)))
        b2 = QPushButton("Reload word list")
        b2.clicked.connect(lambda: self.feed.append("<span style='color:#8a93a8'>Loaded %d short-form words</span>"
                                                      % hinglish.load_words(self.words_path)))
        row.addWidget(b1)
        row.addWidget(b2)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        return page

    def _page_mod(self):
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 8, 0, 0)
        note = QLabel("These filters decide what gets read aloud. Skipped messages stay visible in grey on the Live chat page.")
        note.setObjectName("sub")
        note.setWordWrap(True)
        lay.addWidget(note)
        for text, key in (("Skip messages with links", "skip_links"), ("Skip !commands", "skip_cmds"),
                          ("Ignore known bots (Nightbot, StreamElements, ...)", "ignore_bots"),
                          ("Only read moderators and the streamer", "mods_only")):
            lay.addWidget(self._bind_check(text, key))
        lay.addWidget(labeled("Max message length", self._bind_spin("max_len", 20, 500, " chars")))
        lay.addWidget(labeled("Ignore repeats for", self._bind_spin("dedupe_secs", 0, 120, " s")))
        lay.addWidget(labeled("Same viewer cooldown", self._bind_spin("user_cooldown", 0, 60, " s")))
        lay.addWidget(QLabel("Blocked words (one per line, never read aloud, also blocks paid messages)"))
        self.blocked_edit = QPlainTextEdit()
        try:
            with open(self.blocked_path, encoding="utf-8") as f:
                self.blocked_edit.setPlainText(f.read())
        except Exception:
            pass
        lay.addWidget(self.blocked_edit, 1)
        save = QPushButton("Save blocked words")
        save.setObjectName("primary")
        save.clicked.connect(self._save_blocked)
        lay.addWidget(save, 0, Qt.AlignLeft)
        return page

    # ---------- behaviour ----------
    def apply_theme(self, name):
        if name not in THEMES:
            name = DEFAULT_THEME
        t = THEMES[name]
        self.s.set("theme", name)
        self.setStyleSheet(build_qss(name))
        self.logo.setText('<span style="color:%s">🎙 Chat</span><span style="color:%s">Voice</span>' % (t["a3"], t["a2"]))
        self.fx.recolor(t["a1"])

    def _lite(self, on):
        self.s.set("lite_mode", on)
        self.fx.set_enabled(not on)
        if on:
            self.pulse.stop()
            self.live_fx.setOpacity(1.0)
        elif self.connected:
            self.pulse.start()

    def _end_anim(self):
        for g in self._anims:
            g.stop()
        for w in self._anim_targets:
            w.setGraphicsEffect(None)
        self._anims, self._anim_targets = [], []

    def goto(self, i):
        self._end_anim()
        self.nav.button(i).setChecked(True)
        self.title.setText(PAGES[i])
        self.blurb.setText(PAGE_BLURB[i])
        page = self.stack.widget(i)
        self.stack.setCurrentIndex(i)
        if self.s.get("lite_mode"):
            return
        group = QParallelAnimationGroup(self)
        targets = [page]
        fx = QGraphicsOpacityEffect(page)
        fx.setOpacity(0.0)
        page.setGraphicsEffect(fx)
        a = QPropertyAnimation(fx, b"opacity")
        a.setDuration(160)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.OutCubic)
        group.addAnimation(a)
        group.finished.connect(self._end_anim)
        self._anims, self._anim_targets = [group], targets
        group.start()

    def _mute(self, v):
        self.s.set("muted", v)
        if v:
            self.speaker.clear()

    def _save_blocked(self):
        try:
            with open(self.blocked_path, "w", encoding="utf-8") as f:
                f.write(self.blocked_edit.toPlainText())
            self.mod.reload_blocked()
            self.feed.append("<span style='color:#8a93a8'>Blocked words saved (%d)</span>" % len(self.mod.blocked))
        except Exception as e:
            self.feed.append("<span style='color:#ff5470'>Could not save: %s</span>" % esc(str(e)))

    def _unknown_word(self, w):
        self.feed.append("<span style='color:#8a93a8'>new short word '%s' - add it in Voice > Edit word list</span>" % esc(w))

    def on_status(self, platform, text, ok):
        card = self.cards.get(platform)
        if card:
            card.set_status(text, ok)
        (self.connected.add if ok else self.connected.discard)(platform)
        self._sync_summary()
        if ok:
            self.discord.auto_announce()
        if self.connected and self.live.isHidden():
            self.live.show()
            self.pulse.start()
        elif not self.connected and not self.live.isHidden():
            self.pulse.stop()
            self.live.hide()

    def on_message(self, m):
        is_link = self.links.handle(m)
        ok, reason = self.mod.check(m)
        if is_link:
            ok, reason = False, "link code (processing)"
        elif not ok and m.platform == "youtube" and not m.mod:
            self.ytmod.flag(m, reason)
        color = COLORS.get(m.platform, "#8a93a8")
        amt = " <span style='color:#ffd24d'>[%s]</span>" % esc(m.amount) if m.amount else ""
        tag = "<span style='color:%s'><b>%s</b></span>" % (color, TAGS.get(m.platform, "?"))
        if ok:
            author = shape_chat_text(m.author, self.s.get("chat_transform"))
            text = shape_chat_text(m.text, self.s.get("chat_transform"))
            self.feed.append("%s <b>%s</b>%s: %s" % (tag, esc(author), amt, esc(text)))
            self.speaker.say(m.author, m.text, m.amount if m.kind == "super" else "")
            if m.platform != "tip":
                self.overlay.push("chat", {"platform": m.platform, "name": m.author, "text": m.text})
            if m.kind == "super":
                self.overlay.push("alert", {"platform": m.platform, "name": m.author, "amount": m.amount, "message": m.text})
            if m.kind == "super":
                self.discord.post_paid(m)
        else:
            author = shape_chat_text(m.author, self.s.get("chat_transform"))
            text = shape_chat_text(m.text, self.s.get("chat_transform"))
            self.feed.append("<span style='color:#5d667d'>%s %s: %s <i>(skipped: %s)</i></span>"
                             % (TAGS.get(m.platform, "?"), esc(author), esc(text), reason))

    def on_tip(self, ev):
        msg, note = (ev.get("message") or "").strip(), ""
        if msg and self.mod._blocked_hit(msg):
            msg, note = "", "message hidden: blocked word"
        elif msg and ev.get("currency") == "INR" and float(ev.get("value") or 0) < int(self.s.get("tip_min")):
            msg, note = "", "message not read: below the minimum amount"
        self.on_message(Message("tip", ev.get("name") or "Someone", msg, "super", ev.get("display", "")))
        if note:
            self.feed.append("<span style='color:#5d667d'>%s</span>" % esc(note))

    def test_voice(self):
        for m in (Message("test", "Test", "bhai kya krra hoga, nhi pta yr, bht mast stream h lol"),
                  Message("test", "Test", "नमस्ते दोस्तों, चैट रीडर चालू है।")):
            self.on_message(m)
        self.goto(1)

    def closeEvent(self, e):
        self.links.save()
        self.overlay.stop()
        for c in self.cards.values():
            c.source.stop()
        self.speaker.clear()
        super().closeEvent(e)
