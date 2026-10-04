"""Speech queue: neural voices (edge-tts, online) with Windows voices (offline) as fallback."""
import asyncio
import os
import tempfile
import threading
import time
import zlib
from collections import deque

from PySide6.QtCore import QLocale, QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from . import hinglish

try:
    from PySide6.QtTextToSpeech import QTextToSpeech
except Exception:  # offline voices unavailable
    QTextToSpeech = None

VOICES = [
    ("Hindi female - Swara", "hi-IN-SwaraNeural"),
    ("Hindi male - Madhur", "hi-IN-MadhurNeural"),
    ("Indian English female - Neerja", "en-IN-NeerjaNeural"),
    ("Indian English male - Prabhat", "en-IN-PrabhatNeural"),
]
POOL_HI = ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural"]
POOL_ALL = [v for _, v in VOICES]


class Speaker(QObject):
    busy_changed = Signal(bool)
    note = Signal(str)                  # info/warning lines for the UI
    _generated = Signal(int, str, str)  # token, mp3 path, error

    def __init__(self, settings):
        super().__init__()
        self.s = settings
        self.queue = deque()
        self.busy = False
        self.token = 0
        self.player = None
        self.audio = None
        self.tts = None
        self.current_file = None
        self.current_spoken = ""
        self._generated.connect(self._on_generated)
        self.watchdog = QTimer(self)
        self.watchdog.setSingleShot(True)
        self.watchdog.timeout.connect(self.skip)

    # ----- public -----
    def say(self, author, text, amount=""):
        """Queue a message. Oldest are dropped when chat is faster than speech."""
        text = hinglish.normalize(text).strip()
        if not text and not amount:
            return
        if len(text) > self.s.get("max_len"):
            text = text[: self.s.get("max_len")] + "..."
        if amount:
            spoken = "%s sent %s. %s" % (author, amount, text)
        else:
            spoken = ("%s: %s" % (author, text)) if self.s.get("read_name") else text
        if self.s.get("muted"):
            return
        self.queue.append((author, spoken, bool(amount)))
        while len(self.queue) > self.s.get("queue_max"):
            # drop the oldest normal message first; paid messages are kept
            drop = next((i for i, q in enumerate(self.queue) if not q[2]), 0)
            del self.queue[drop]
        self._pump()

    def skip(self):
        """Stop whatever is being spoken and move on."""
        self.token += 1
        self.watchdog.stop()
        if self.player:
            self.player.stop()
        if self.tts:
            self.tts.stop()
        self._finish()

    def clear(self):
        self.queue.clear()
        self.skip()

    # ----- internals -----
    def _voice_for(self, author, spoken):
        if self.s.get("per_viewer"):
            pool = POOL_HI if hinglish.has_devanagari(spoken) else POOL_ALL
            return pool[zlib.crc32(author.encode("utf-8")) % len(pool)]
        return self.s.get("hi_voice") if hinglish.has_devanagari(spoken) else self.s.get("en_voice")

    def _pump(self):
        if self.busy or not self.queue:
            return
        author, spoken, _paid = self.queue.popleft()
        self.current_spoken = spoken
        self.busy = True
        self.busy_changed.emit(True)
        self.token += 1
        self.watchdog.start(45000)
        if self.s.get("engine") == "neural":
            threading.Thread(target=self._generate, args=(self.token, spoken, self._voice_for(author, spoken)),
                             daemon=True).start()
        else:
            self._speak_windows(spoken)

    def _generate(self, token, spoken, voice):
        path = os.path.join(tempfile.gettempdir(), "chatvoice_%d_%d.mp3" % (os.getpid(), int(time.time() * 1000)))
        try:
            import edge_tts
            pct = int(self.s.get("rate")) * 10
            asyncio.run(edge_tts.Communicate(spoken, voice, rate="%+d%%" % pct).save(path))
            self._generated.emit(token, path, "")
        except Exception as e:
            self._generated.emit(token, "", str(e)[:80])

    def _on_generated(self, token, path, err):
        if token != self.token:           # skipped while generating
            if path:
                self._remove(path)
            return
        if err or not path:
            self.note.emit("Neural voice unavailable (%s) - using Windows voice" % (err or "no audio"))
            return self._speak_windows(self.current_spoken)
        if self.player is None:
            self.player = QMediaPlayer(self)
            self.audio = QAudioOutput(self)
            self.player.setAudioOutput(self.audio)
            self.player.mediaStatusChanged.connect(self._on_status)
            self.player.errorOccurred.connect(lambda *a: self._finish())
        self.audio.setVolume(self.s.get("volume") / 100.0)
        self.current_file = path
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

    def _on_status(self, status):
        if status in (QMediaPlayer.MediaStatus.EndOfMedia, QMediaPlayer.MediaStatus.InvalidMedia):
            self._finish()

    def _speak_windows(self, spoken):
        if QTextToSpeech is None:
            self.note.emit("No Windows voice available")
            return self._finish()
        if self.tts is None:
            self.tts = QTextToSpeech(self)
            self.tts.stateChanged.connect(self._on_tts_state)
        if self.tts.state() == QTextToSpeech.State.Error or not self.tts.availableVoices():
            self.note.emit("No Windows voice found - add one in Windows Settings > Speech")
            return self._finish()
        self.tts.setVolume(self.s.get("volume") / 100.0)
        self.tts.setRate(max(-1.0, min(1.0, self.s.get("rate") / 5.0)))
        want = "hi" if hinglish.has_devanagari(spoken) else "en"
        for v in self.tts.availableVoices():
            if v.locale().name().lower().startswith(want):
                self.tts.setVoice(v)
                break
        self._tts_started = False
        self.tts.say(spoken)

    def _on_tts_state(self, state):
        if state == QTextToSpeech.State.Speaking:
            self._tts_started = True
        elif state in (QTextToSpeech.State.Ready, QTextToSpeech.State.Error) and getattr(self, "_tts_started", False):
            self._tts_started = False
            self._finish()

    def _remove(self, path):
        try:
            os.remove(path)
        except Exception:
            pass

    def _finish(self):
        if self.current_file:
            self._remove(self.current_file)
            self.current_file = None
        was = self.busy
        self.busy = False
        self.watchdog.stop()
        if was:
            self.busy_changed.emit(False)
        QTimer.singleShot(150, self._pump)
