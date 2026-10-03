"""OBS overlays page: copy the two addresses into OBS Browser sources."""
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget

from .discord_page import _card, _row


class OverlayPage(QScrollArea):
    def __init__(self, settings, overlay):
        super().__init__()
        self.s, self.overlay = settings, overlay
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner.setObjectName("page")
        self.setWidget(inner)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 8, 12, 12)
        lay.setSpacing(14)

        status = QLabel("Overlay server running on this PC (port %d)" % overlay.port if overlay.port else overlay.error)
        status.setObjectName("sub")
        lay.addWidget(status)

        c, cl = _card("Alerts on screen  (payments, Super Chats, Bits)",
                      "In OBS: Sources > + > Browser > Create new > paste this address. Width 1280, Height 420. "
                      "It stays invisible until an alert comes, then pops up with colours from your theme.")
        self.alert_url = self._url_row(cl, overlay.url("alert"))
        test = QPushButton("Send a test alert")
        test.setObjectName("primary")
        test.clicked.connect(lambda: overlay.push("alert", {"platform": "tip", "name": "Rahul", "amount": "₹100",
                                                            "message": "Great stream bhai, keep it up!"}))
        cl.addWidget(_row(test))
        lay.addWidget(c)

        c, cl = _card("Chat on screen",
                      "In OBS: Sources > + > Browser > paste this address. Width 520, Height 760. The background is transparent; "
                      "lines fade away by themselves.")
        self.chat_url = self._url_row(cl, overlay.url("chat"))
        test2 = QPushButton("Send a test chat message")
        test2.clicked.connect(lambda: overlay.push("chat", {"platform": "youtube", "name": "Neha", "text": "Namaste doston! 🙏"}))
        cl.addWidget(_row(test2))
        lay.addWidget(c)

        c, cl = _card("Options")
        for label, key, lo, hi in (("Alert stays on screen (seconds)", "ov_seconds", 3, 30), ("Chat lines stay (seconds)", "ov_chat_seconds", 5, 120)):
            sp = QSpinBox()
            sp.setRange(lo, hi)
            sp.setValue(int(self.s.get(key)))
            sp.valueChanged.connect(lambda v, k=key: self.s.set(k, v))
            cl.addWidget(_row(QLabel(label), sp))
        for text, key in (("Show the viewer's message in the alert", "ov_show_message"),
                          ("Play a short chime with each alert (your voice already reads it aloud)", "ov_sound")):
            cb = QCheckBox(text)
            cb.setChecked(bool(self.s.get(key)))
            cb.toggled.connect(lambda v, k=key: self.s.set(k, v))
            cl.addWidget(cb)
        hint = QLabel("Changes apply to OBS within a second. Only this PC can open these addresses.")
        hint.setObjectName("hint")
        cl.addWidget(hint)
        lay.addWidget(c)
        lay.addStretch(1)

    def _url_row(self, layout, url):
        e = QLineEdit(url)
        e.setReadOnly(True)
        b = QPushButton("Copy")
        b.clicked.connect(lambda: QGuiApplication.clipboard().setText(e.text()))
        layout.addWidget(_row(e, b))
        return e
