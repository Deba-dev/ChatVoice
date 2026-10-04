"""Payments page: connect the streamer's Razorpay webhook and choose how payments are read."""
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QCheckBox, QComboBox, QFrame, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget

from .discord import run_bg
from .discord_page import _card, _row


GATEWAYS = {
    "razorpay": ("Razorpay", "Razorpay webhook secret (you choose it in the Razorpay dashboard)",
                 "Razorpay > Settings > Webhooks > Add: paste this address and the SAME secret, tick only the event payment.captured. "
                 "On your Payment Page add two fields labelled Name and Message."),
    "stripe": ("Stripe", "Stripe signing secret (starts with whsec_)",
               "Stripe Dashboard > Developers > Webhooks > Add endpoint: paste this address, choose the event checkout.session.completed, "
               "then paste the endpoint's signing secret here. On your Payment Link add custom fields labelled Name and Message."),
    "cashfree": ("Cashfree", "Cashfree secret key",
                 "Cashfree Dashboard > Developers > Webhooks: paste this address. The secret is your Payment Gateway secret key. "
                 "Add Name and Message fields to your payment form. (Field names are not confirmed yet - see PAYMENTS-SETUP.txt.)"),
    "generic": ("Any other tool (Zapier, Make, n8n, Google Apps Script...)", "A secret you choose",
                'Send a POST with JSON {"name":"...","message":"...","amount":100,"currency":"INR"} to this address, with the header '
                "X-ChatVoice-Secret set to your secret (or put it in the JSON as \"secret\")."),
}


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
                      "Viewers pay on a payment page in YOUR OWN payment account (money goes straight to you). "
                      "Your payment service tells ChatVoice, and ChatVoice reads the name, amount and message aloud. "
                      "Do the Discord page first: payments use the same server connection.")
        self.cfg = {}
        self.gw = QComboBox()
        for key, (label, _, _) in GATEWAYS.items():
            self.gw.addItem(label, key)
        self.gw.setCurrentIndex(max(0, self.gw.findData(self.s.get("pay_gateway"))))
        self.gw.currentIndexChanged.connect(self._gateway_changed)
        cl.addWidget(self.gw)
        self.secret = QLineEdit()
        self.secret.setEchoMode(QLineEdit.Password)
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
        self.how = QLabel()
        self.how.setObjectName("hint")
        self.how.setWordWrap(True)
        cl.addWidget(self.how)
        cl.addWidget(_row(self.hook, copy))
        self._gateway_changed()
        lay.addWidget(c)

        c, cl = _card("2.  Reading payments aloud",
                      "On your payment page, add two fields labelled 'Name' and 'Message'. ChatVoice finds them by their labels.")
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

    def _gateway_changed(self):
        key = self.gw.currentData()
        self.s.set("pay_gateway", key)
        self.secret.setPlaceholderText(GATEWAYS[key][1])
        self.how.setText(GATEWAYS[key][2])
        self._show_cfg()

    def _show_cfg(self):
        key = self.gw.currentData()
        self.hook.setText((self.cfg.get("hookUrls") or {}).get(key, ""))
        if self.cfg:
            self.state.setText("Secret saved on server" if self.cfg.get("has%sSecret" % key.capitalize()) else "No secret saved yet")

    def refresh(self):
        self.state.setText("Checking...")
        run_bg(self.bridge, "pay:cfg", lambda: self.cloud.call("GET", "/api/config"))

    def save_secret(self):
        text = self.secret.text().strip()
        if not text:
            self.state.setText("Type the secret first")
            return
        self.state.setText("Saving...")
        field = self.gw.currentData() + "Secret"
        run_bg(self.bridge, "pay:save", lambda: self.cloud.call("PUT", "/api/config", {field: text}))

    def test_tip(self):
        self.poller.tip.emit({"name": "Rahul", "message": "Great stream bhai, keep it up!", "value": 100.0,
                              "currency": "INR", "display": "₹100"})

    def on_done(self, tag, res):
        if not tag.startswith("pay:"):
            return
        if res.get("error"):
            self.state.setText(res["error"])
            return
        self.cfg = res.get("config", {})
        self._show_cfg()
        if tag == "pay:save":
            self.secret.clear()
            self.state.setText("Saved. Now add the address below in your payment service.")
