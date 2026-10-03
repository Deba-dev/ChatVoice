"""Payments page: connect the streamer's Razorpay webhook and choose how payments are read."""
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QCheckBox, QFrame, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget

from .discord import run_bg
from .discord_page import _card, _row


class PaymentsPage(QScrollArea):
    def __init__(self, settings, cloud, bridge, poller):
        super().__init__()
        self.s, self.cloud, self.bridge, self.poller = settings, cloud, bridge, poller
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner.setObjectName("page")
        self.setWidget(inner)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 8, 12, 12)
        lay.setSpacing(14)

        c, cl = _card("1.  Connect your payment page",
                      "Viewers pay on a payment page in YOUR OWN Razorpay account (money goes straight to you). "
                      "Razorpay tells ChatVoice, and ChatVoice reads the name, amount and message aloud. "
                      "Do the Discord page first: payments use the same server connection.")
        self.secret = QLineEdit()
        self.secret.setEchoMode(QLineEdit.Password)
        self.secret.setPlaceholderText("Razorpay webhook secret (you choose it in the Razorpay dashboard)")
        save = QPushButton("Save secret")
        save.setObjectName("primary")
        save.clicked.connect(self.save_secret)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        self.state = QLabel("")
        self.state.setObjectName("sub")
        cl.addWidget(self.secret)
        cl.addWidget(_row(save, refresh, self.state))
        self.hook = QLineEdit()
        self.hook.setReadOnly(True)
        self.hook.setPlaceholderText("Webhook address appears here after you save the secret")
        copy = QPushButton("Copy")
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.hook.text()))
        cl.addWidget(QLabel("Paste this address into Razorpay > Settings > Webhooks (event: payment.captured):"))
        cl.addWidget(_row(self.hook, copy))
        lay.addWidget(c)

        c, cl = _card("2.  Reading payments aloud",
                      "On your payment page, add two fields: 'Name' and 'Message'. ChatVoice finds them by their labels.")
        on = QCheckBox("Listen for payments and read them aloud")
        on.setChecked(bool(self.s.get("tips_on")))
        on.toggled.connect(self._toggle)
        self.minimum = QSpinBox()
        self.minimum.setRange(0, 100000)
        self.minimum.setPrefix("₹ ")
        self.minimum.setValue(int(self.s.get("tip_min")))
        self.minimum.valueChanged.connect(lambda v: self.s.set("tip_min", v))
        self.status = QLabel("Not listening")
        self.status.setObjectName("sub")
        test = QPushButton("Send a test payment")
        test.clicked.connect(self.test_tip)
        cl.addWidget(on)
        cl.addWidget(_row(QLabel("Read the viewer's message only from"), self.minimum, QLabel("and above (INR payments)")))
        cl.addWidget(_row(test, self.status))
        note = QLabel("Messages with blocked words are never read; the name and amount still are. "
                      "Payments are also posted to Discord if you enabled that on the Discord page.")
        note.setObjectName("hint")
        note.setWordWrap(True)
        cl.addWidget(note)
        lay.addWidget(c)
        lay.addStretch(1)
        bridge.done.connect(self.on_done)
        poller.status.connect(self.status.setText)

    def _toggle(self, v):
        self.s.set("tips_on", v)
        self.poller.apply()

    def refresh(self):
        self.state.setText("Checking...")
        run_bg(self.bridge, "pay:cfg", lambda: self.cloud.call("GET", "/api/config"))

    def save_secret(self):
        text = self.secret.text().strip()
        if not text:
            self.state.setText("Type the secret first")
            return
        self.state.setText("Saving...")
        run_bg(self.bridge, "pay:save", lambda: self.cloud.call("PUT", "/api/config", {"razorpaySecret": text}))

    def test_tip(self):
        self.poller.tip.emit({"name": "Rahul", "message": "Great stream bhai, keep it up!", "value": 100.0,
                              "currency": "INR", "display": "₹100"})

    def on_done(self, tag, res):
        if not tag.startswith("pay:"):
            return
        if res.get("error"):
            self.state.setText(res["error"])
            return
        cfg = res.get("config", {})
        self.hook.setText(cfg.get("hookUrl", ""))
        if tag == "pay:save":
            self.secret.clear()
            self.state.setText("Saved. Now add the address below in Razorpay.")
        else:
            self.state.setText("Secret saved on server" if cfg.get("hasRazorpaySecret") else "No secret saved yet")
