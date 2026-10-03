"""Colour themes, the stylesheet, and the floating hover effect for buttons."""
from string import Template

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QParallelAnimationGroup, QPropertyAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect

THEMES = {
    "Neon Violet": dict(bg="#12141f", bg2="#181b28", text="#f1f2ff", mute="#9aa0cc", a1="#8b5cf6", a2="#22d3ee", a3="#f472b6"),
    "Sunset":      dict(bg="#1a1216", bg2="#24181d", text="#fff1f4", mute="#c9a3b4", a1="#ff7a45", a2="#ff3d81", a3="#ffd166"),
    "Ocean":       dict(bg="#0d1620", bg2="#12202c", text="#eaf6ff", mute="#8db3cf", a1="#00b8ff", a2="#4f7cff", a3="#2dd4bf"),
    "Matcha":      dict(bg="#101814", bg2="#16201a", text="#effff5", mute="#93bfa5", a1="#34d399", a2="#a3e635", a3="#22d3ee"),
}
DEFAULT_THEME = "Neon Violet"

QSS = Template("""
* { font-family: "Poppins", "Segoe UI", "Noto Sans Devanagari", sans-serif; font-size: 13px; color: $text; }
QWidget#root { background: $bg; }
QWidget#page, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
QFrame#side { background: rgba(255,255,255,0.035); border-right: 1px solid rgba(255,255,255,0.07); }
QLabel#logo { font-size: 20px; font-weight: 700; padding: 4px 0 14px 6px; }
QLabel#title { font-size: 24px; font-weight: 700; }
QLabel#sub, QLabel#hint { color: $mute; }
QPushButton#nav { text-align: left; padding: 9px 16px; border: none; border-left: 3px solid transparent; margin: 2px 10px 2px 0;
    background: transparent; color: $mute; border-radius: 0 10px 10px 0; font-size: 14px; font-weight: 500; }
QPushButton#nav:hover { background: rgba(255,255,255,0.06); color: $text; }
QPushButton#nav:checked { color: #ffffff; border-left: 3px solid $a1; font-weight: 600;
    background: rgba(255,255,255,0.08); }
QFrame#card { background: rgba(255,255,255,0.045); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; }
QFrame#card:hover { border: 1px solid rgba(255,255,255,0.14); background: rgba(255,255,255,0.07); }
QPushButton { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; padding: 9px 18px; font-weight: 500; }
QPushButton:hover { background: rgba(255,255,255,0.14); border: 1px solid rgba(255,255,255,0.18); }
QPushButton:pressed { background: rgba(255,255,255,0.05); }
QPushButton:checked { border: none; background: $a1; color: #ffffff; }
QPushButton#primary { border: none; font-weight: 600; color: #ffffff; background: $a1; }
QPushButton#primary:hover { background: $a2; }
QPushButton#stop { border: 1px solid #ff5d8f; background: rgba(255,60,120,0.20); }
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit { background: rgba(0,0,0,0.30); border: 1px solid rgba(255,255,255,0.12);
    border-radius: 8px; padding: 8px 11px; selection-background-color: $a1; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus { border: 1px solid $a2; }
QComboBox QAbstractItemView { background: $bg2; selection-background-color: $a1; border: 1px solid rgba(255,255,255,0.15); outline: 0; }
QSlider::groove:horizontal { height: 7px; background: rgba(255,255,255,0.12); border-radius: 3px; }
QSlider::sub-page:horizontal { border-radius: 3px; background: $a1; }
QSlider::handle:horizontal { background: #ffffff; width: 18px; margin: -6px 0; border-radius: 9px; }
QCheckBox { spacing: 9px; }
QCheckBox::indicator { width: 20px; height: 20px; border-radius: 7px; border: 1px solid rgba(255,255,255,0.28); background: rgba(0,0,0,0.30); }
QCheckBox::indicator:hover { border: 1px solid $a2; }
QCheckBox::indicator:checked { border: none; background: $a1; }
QFrame#banner { border-radius: 10px; border: 1px solid rgba(255,255,255,0.12); background: $bg2; }
QFrame#banner QLabel { color: $text; font-weight: 600; }
QLabel#live { color: #ffffff; font-weight: 700; padding: 4px 12px; background: #e11d48; border-radius: 8px; }
QScrollBar:vertical { background: transparent; width: 9px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.22); border-radius: 4px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: $a1; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
""")


def build_qss(name):
    return QSS.substitute(THEMES.get(name, THEMES[DEFAULT_THEME]))


class _Floaty(QObject):
    """Makes one button 'float': its glow grows and lifts on hover, and presses down on click."""

    def __init__(self, widget, fx):
        super().__init__(widget)
        self.w, self.fx = widget, fx
        self.effect = None
        widget.installEventFilter(self)
        if fx.enabled:
            self.build()

    def build(self):
        self.effect = QGraphicsDropShadowEffect(self.w)
        self.effect.setOffset(0, 1)
        self.effect.setBlurRadius(6)
        self.effect.setColor(self.fx.color)
        self.group = QParallelAnimationGroup(self.effect)
        self.blur = QPropertyAnimation(self.effect, b"blurRadius", self.group)
        self.lift = QPropertyAnimation(self.effect, b"yOffset", self.group)
        for a in (self.blur, self.lift):
            a.setEasingCurve(QEasingCurve.OutCubic)
            self.group.addAnimation(a)
        self.w.setGraphicsEffect(self.effect)

    def remove(self):
        if self.effect is not None:
            self.group.stop()
            self.w.setGraphicsEffect(None)      # Qt deletes the effect here
            self.effect = None

    def go(self, blur, y, ms):
        if self.effect is None:
            return
        self.group.stop()
        self.blur.setDuration(ms)
        self.lift.setDuration(ms)
        self.blur.setEndValue(blur)
        self.lift.setEndValue(y)
        self.group.start()

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == QEvent.Enter:
            self.go(14, 4, 160)
        elif t == QEvent.Leave:
            self.go(6, 1, 180)
        elif t == QEvent.MouseButtonPress:
            self.go(8, 0, 70)
        elif t == QEvent.MouseButtonRelease:
            self.go(14, 4, 140)
        return False


class FX:
    """Registry of floating buttons. Lite mode turns every effect off for weak PCs."""

    def __init__(self, glow="#8b5cf6"):
        self.enabled = True
        self.color = QColor(glow)
        self.color.setAlpha(110)
        self.items = []

    def attach(self, widget):
        self.items.append(_Floaty(widget, self))

    def recolor(self, glow):
        self.color = QColor(glow)
        self.color.setAlpha(110)
        for it in self.items:
            if it.effect is not None:
                it.effect.setColor(self.color)

    def set_enabled(self, on):
        self.enabled = on
        for it in self.items:
            if on and it.effect is None:
                it.build()
            elif not on:
                it.remove()
