"""Music page: play your own no-copyright / licensed music on stream, with a now-playing overlay for OBS."""
import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QLabel, QListWidget, QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget

from .music import import_downloads
from .settings import data_dir
from .theme import DEFAULT_THEME, THEMES
from .ui_kit import (FormScrollArea, bind_switch, copy_row, field_row, hrow, info_box, make_badge, meter_row,
                     option_switch_row, section_card, set_badge, status_row)


class MusicPage(FormScrollArea):
    def __init__(self, settings, player, overlay):
        super().__init__()
        self.s, self.player = settings, player
        inner = QWidget()
        inner.setObjectName("page")
        self.setWidget(inner)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 8, 12, 12)
        lay.setSpacing(14)
        accent = THEMES.get(self.s.get("theme"), THEMES[DEFAULT_THEME])["a1"]

        # ---------- now playing ----------
        c, cl = section_card("Now playing", "Music that is safe for streams plays here. Your voice lowers it while chat is being read.")
        self.state = make_badge("\u25cf  Stopped", "pill")
        self.title = QLabel("Nothing playing")
        self.title.setObjectName("pageTitle")
        self.title.setWordWrap(True)
        self.artist = QLabel("")
        self.artist.setObjectName("settingNote")
        cl.addWidget(status_row(self.state))
        cl.addWidget(self.title)
        cl.addWidget(self.artist)
        self.prev_btn = QPushButton("\u23ee  Previous")
        self.play_btn = QPushButton("\u25b6  Play")
        self.play_btn.setObjectName("primary")
        self.next_btn = QPushButton("Next  \u23ed")
        for b, fn in ((self.prev_btn, player.prev), (self.play_btn, player.toggle), (self.next_btn, player.next)):
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
        cl.addWidget(hrow(self.prev_btn, self.play_btn, self.next_btn))
        cl.addWidget(option_switch_row("Shuffle", "Play the songs in a random order.", bind_switch(self.s, "music_shuffle", accent)))
        cl.addWidget(option_switch_row("Start music when ChatVoice opens", "Starts the first song automatically.", bind_switch(self.s, "music_autoplay", accent)))
        lay.addWidget(c)

        # ---------- StreamBeats download library ----------
        c, cl = section_card(
            "Get StreamBeats music",
            "Browse and download music from the official StreamBeats catalog, then import the downloaded tracks or album ZIP here.",
        )
        cl.addWidget(info_box(
            "StreamBeats offers a free creator license for synchronizing its tracks with Twitch and YouTube videos. "
            "ChatVoice does not bundle or redistribute the music: download it from StreamBeats/Bandcamp yourself, then import it here. "
            "A license does not guarantee that automated copyright systems will never flag a stream; keep the official license page as proof.",
            "License and claims",
        ))
        browse = QPushButton("Browse StreamBeats catalog")
        browse.setObjectName("primary")
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.streambeats.com/")))
        downloads = QPushButton("Download free music")
        downloads.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://streambeats.bandcamp.com/")))
        licensing = QPushButton("View usage license")
        licensing.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.streambeats.com/licensing")))
        self.import_btn = QPushButton("Import downloaded tracks / album ZIP")
        self.import_btn.clicked.connect(self.import_files)
        self.import_status = QLabel("")
        self.import_status.setObjectName("sub")
        cl.addWidget(hrow(browse, downloads, licensing))
        cl.addWidget(hrow(self.import_btn, self.import_status))
        lay.addWidget(c)

        # ---------- local library ----------
        c, cl = section_card("Your music", "Choose a folder with songs you are allowed to use. Name files like \"Artist - Title.mp3\" to show them nicely.")
        self.folder = QLabel(self.s.get("music_folder") or "No folder chosen")
        self.folder.setObjectName("settingNote")
        self.folder.setWordWrap(True)
        choose = QPushButton("Choose music folder")
        choose.setObjectName("primary")
        choose.setCursor(Qt.PointingHandCursor)
        choose.clicked.connect(self.choose_folder)
        rescan = QPushButton("Rescan")
        rescan.clicked.connect(lambda: self.player.load_folder(self.s.get("music_folder")) if self.s.get("music_folder") else None)
        self.count = QLabel("")
        self.count.setObjectName("sub")
        cl.addWidget(self.folder)
        cl.addWidget(hrow(choose, rescan, self.count))
        self.list = QListWidget()
        self.list.setMinimumHeight(190)
        self.list.itemDoubleClicked.connect(lambda item: self.player.play_index(self.list.row(item)))
        cl.addWidget(self.list)
        self.empty = info_box("Nothing here yet. Pick a folder of songs, or get some from the free sources below. Double-click a song to play it.", "No music loaded")
        cl.addWidget(self.empty)
        lay.addWidget(c)

        # ---------- mixing ----------
        c, cl = section_card("Mix with your voice", "Keep the music under the chat voice so viewers hear both.")
        vol = QSlider(Qt.Horizontal)
        vol.setRange(0, 100)
        vol.setValue(int(self.s.get("music_volume")))
        vol.valueChanged.connect(self.player.set_volume)
        cl.addWidget(meter_row("Music volume", "How loud the music is.", vol, lambda v: "%d%%" % v))
        cl.addWidget(option_switch_row("Lower the music while chat is read aloud", "Fades the music down whenever ChatVoice speaks.",
                                       bind_switch(self.s, "music_duck", accent)))
        duck = QSlider(Qt.Horizontal)
        duck.setRange(5, 80)
        duck.setValue(int(self.s.get("music_duck_pct")))
        duck.valueChanged.connect(lambda v: (self.s.set("music_duck_pct", v), self.player.refresh_settings()))
        cl.addWidget(meter_row("Lowered to", "Music level while the voice is speaking.", duck, lambda v: "%d%%" % v))
        lay.addWidget(c)

        # ---------- OBS ----------
        c, cl = section_card("Show the song on stream", "In OBS: Sources > + > Browser. Width 700, Height 160. Shows title and artist in the corner, "
                                                         "which also gives credit for tracks that ask for it.")
        wrap, self.music_url = copy_row(overlay.url("music"))
        cl.addWidget(wrap)
        lay.addWidget(c)

        # ---------- finding music ----------
        c, cl = section_card("Other music sources", "Licenses vary by track and provider; check the permissions for your platform and keep proof.")
        cl.addWidget(info_box(
            "\u2022 <a href='https://www.youtube.com/audiolibrary'>YouTube Audio Library</a> \u2014 YouTube states its Audio Library tracks are copyright-safe on YouTube; this does not establish Twitch rights.<br>"
            "\u2022 <a href='https://incompetech.com/music/royalty-free/'>Incompetech</a> \u2014 check the individual license and provide required credit.<br>"
            "\u2022 <a href='https://mixkit.co/free-stock-music/'>Mixkit</a> and <a href='https://freemusicarchive.org/'>Free Music Archive</a> \u2014 review the exact track license before streaming.",
            "Read each license"))
        cl.addWidget(info_box(
            "No service can guarantee that a copyright-claim system will never make a mistake. Use the provider's authorized download, "
            "follow its license, and keep a copy of the permission and download details. Do not redistribute music files from ChatVoice.",
            "Stay safe"))
        lay.addWidget(c)
        lay.addStretch(1)

        player.changed.connect(self.refresh)
        self.refresh(reload_list=True)

    def import_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import StreamBeats downloads", os.path.expanduser("~/Downloads"),
            "Audio files and album ZIPs (*.mp3 *.wav *.ogg *.flac *.m4a *.aac *.wma *.opus *.zip)",
        )
        if not paths:
            return
        folder = os.path.join(data_dir(), "Music")
        try:
            imported = import_downloads(paths, folder)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Music import failed", str(error))
            self.import_status.setText("Import failed")
            return
        if not imported:
            QMessageBox.information(self, "No supported tracks", "The selected download did not contain supported audio files.")
            return
        count = self.player.load_folder(folder)
        self.import_status.setText("Imported %d tracks" % len(imported))
        self.count.setText("%d songs in your library" % count)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose your music folder", self.s.get("music_folder") or os.path.expanduser("~"))
        if folder:
            self.player.load_folder(folder)

    def refresh(self, reload_list=False):
        p = self.player
        st = p.state()
        self.title.setText(st["title"] or "Nothing playing")
        self.artist.setText(st["artist"])
        set_badge(self.state, "\u25cf  Playing" if st["playing"] else ("\u25cf  Paused" if p.current() else "\u25cf  Stopped"),
                  "pillOn" if st["playing"] else "pill")
        self.play_btn.setText("\u23f8  Pause" if st["playing"] else "\u25b6  Play")
        self.folder.setText(self.s.get("music_folder") or "No folder chosen")
        if reload_list or self.list.count() != len(p.tracks):
            self.list.clear()
            for t in p.tracks:
                self.list.addItem(("%s \u2014 %s" % (t["artist"], t["title"])) if t["artist"] else t["title"])
        if 0 <= p.index < self.list.count():
            self.list.setCurrentRow(p.index)
        self.count.setText("%d songs" % len(p.tracks) if p.tracks else "")
        self.empty.setVisible(not p.tracks)
        self.list.setVisible(bool(p.tracks))
