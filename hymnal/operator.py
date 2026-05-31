"""Operator (control) window — library, playlist, verse navigation, audio."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .audio import AudioBackend
from .bible import ESV_ATTRIBUTION, BibleClient, Passage, chunk_passage_to_slides
from .display import DisplayWindow
from .karaoke import DEFAULT_BPM, HighlightSchedule, TempoData, words_per_second
from .library import Hymn, HymnLibrary
from .passage_dialog import ApiKeyDialog, PassageDialog


class OperatorWindow(QMainWindow):
    def __init__(
        self,
        library: HymnLibrary,
        audio_dir: Path,
        playlists_dir: Path,
        settings_path: Path,
        bible: BibleClient,
        user_audio_dir: Optional[Path] = None,
    ) -> None:
        super().__init__()
        self.library = library
        self.audio_dir = audio_dir
        # Optional per-user drop-in folder, searched *before* the bundled
        # audio so a user's own recording wins over the shipped one.
        self.user_audio_dir = user_audio_dir
        self.playlists_dir = playlists_dir
        self.settings_path = settings_path
        self.bible = bible
        self.playlists_dir.mkdir(parents=True, exist_ok=True)

        self.display: Optional[DisplayWindow] = None
        self.audio = AudioBackend(self)
        self.audio.state_changed.connect(self._on_audio_state)
        self.audio.finished.connect(self._on_audio_finished)

        # Unified "current item" — either a hymn or a passage.
        # Slides hold whatever the operator paginates through (verses or passage chunks).
        self._current_slides: List[Tuple[str, List[str]]] = []
        self._current_slide_index: int = -1
        self._current_audio_id: Optional[str] = None
        self._current_display_title: str = ""
        self._current_display_subtitle: str = ""
        self._current_display_footer: str = ""

        # Playlist entries are dicts with "type" ("hymn" | "passage").
        # Hymn:    {"type": "hymn", "id": "amazing-grace"}
        # Passage: {"type": "passage", "reference": "John 3:16",
        #           "canonical": "John 3:16", "text": "...", "fetched_at": "..."}
        self._playlist: List[Dict] = []
        self._playlist_index: int = -1
        self._is_blank: bool = False
        self._show_active: bool = False
        self._auto_advance_song: bool = False

        # Karaoke highlight state
        self._karaoke_enabled: bool = True
        self._karaoke_speed: float = 1.0
        self._karaoke_verse_start_ms: int = 0
        self._current_schedule: Optional[HighlightSchedule] = None
        self._karaoke_timer = QTimer(self)
        self._karaoke_timer.setInterval(70)
        self._karaoke_timer.timeout.connect(self._karaoke_tick)

        self.setWindowTitle("PSC Hymnal — Operator")
        self.resize(1500, 900)
        self._build_menu()
        self._build_ui()
        self._wire_shortcuts()
        self._refresh_library_list("")
        self._refresh_screen_list()
        QTimer.singleShot(0, self._load_settings)

    # ----------------------------------------------------------------- build
    def _build_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        save_act = QAction("Save Playlist…", self)
        save_act.setShortcut(QKeySequence("Ctrl+S"))
        save_act.triggered.connect(self._save_playlist)
        file_menu.addAction(save_act)
        load_act = QAction("Load Playlist…", self)
        load_act.setShortcut(QKeySequence("Ctrl+O"))
        load_act.triggered.connect(self._load_playlist)
        file_menu.addAction(load_act)
        file_menu.addSeparator()
        quit_act = QAction("Quit", self)
        quit_act.setShortcut(QKeySequence("Ctrl+Q"))
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        bible_menu = menubar.addMenu("&Bible")
        add_passage_act = QAction("Add Passage…", self)
        add_passage_act.setShortcut(QKeySequence("Ctrl+B"))
        add_passage_act.triggered.connect(self._add_passage_clicked)
        bible_menu.addAction(add_passage_act)
        api_key_act = QAction("ESV API Key…", self)
        api_key_act.triggered.connect(self._set_api_key_clicked)
        bible_menu.addAction(api_key_act)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 14, 16, 10)
        outer.setSpacing(12)

        top = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search hymns by title, author, or text…")
        self.search_edit.textChanged.connect(self._refresh_library_list)
        top.addWidget(self.search_edit, 3)

        top.addWidget(QLabel("Display:"))
        self.screen_combo = QComboBox()
        top.addWidget(self.screen_combo, 1)

        self.show_btn = QPushButton("◼ Show Display")
        self.show_btn.setObjectName("primaryBtn")
        self.show_btn.setCheckable(True)
        self.show_btn.clicked.connect(self._toggle_show)
        top.addWidget(self.show_btn)

        self.blank_btn = QPushButton("Blank (B)")
        self.blank_btn.setCheckable(True)
        self.blank_btn.clicked.connect(self._toggle_blank)
        top.addWidget(self.blank_btn)

        outer.addLayout(top)

        split = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(split, 1)

        # --- Library ---
        left_box = QGroupBox(f"Library ({len(self.library.hymns)} hymns)")
        left_layout = QVBoxLayout(left_box)
        self.library_list = QListWidget()
        self.library_list.itemSelectionChanged.connect(self._on_library_selection)
        self.library_list.itemDoubleClicked.connect(self._add_to_playlist_item)
        left_layout.addWidget(self.library_list)
        add_btn = QPushButton("Add to Playlist  ▶")
        add_btn.clicked.connect(self._add_selected_to_playlist)
        left_layout.addWidget(add_btn)
        split.addWidget(left_box)

        # --- Playlist ---
        mid_box = QGroupBox("Service Playlist")
        mid_layout = QVBoxLayout(mid_box)
        self.playlist_widget = QListWidget()
        self.playlist_widget.itemSelectionChanged.connect(self._on_playlist_selection)
        mid_layout.addWidget(self.playlist_widget)

        pl_btns = QHBoxLayout()
        up_btn = QPushButton("↑")
        up_btn.setObjectName("iconBtn")
        up_btn.clicked.connect(lambda: self._move_playlist_item(-1))
        pl_btns.addWidget(up_btn)
        down_btn = QPushButton("↓")
        down_btn.setObjectName("iconBtn")
        down_btn.clicked.connect(lambda: self._move_playlist_item(1))
        pl_btns.addWidget(down_btn)
        rm_btn = QPushButton("Remove")
        rm_btn.clicked.connect(self._remove_from_playlist)
        pl_btns.addWidget(rm_btn)
        clr_btn = QPushButton("Clear")
        clr_btn.setObjectName("destructiveBtn")
        clr_btn.clicked.connect(self._clear_playlist)
        pl_btns.addWidget(clr_btn)
        mid_layout.addLayout(pl_btns)

        bible_btn = QPushButton("✚ Add Bible Verse… (Ctrl+B)")
        bible_btn.clicked.connect(self._add_passage_clicked)
        mid_layout.addWidget(bible_btn)

        pl_io = QHBoxLayout()
        save_btn = QPushButton("Save Playlist…")
        save_btn.clicked.connect(self._save_playlist)
        pl_io.addWidget(save_btn)
        load_btn = QPushButton("Load Playlist…")
        load_btn.clicked.connect(self._load_playlist)
        pl_io.addWidget(load_btn)
        mid_layout.addLayout(pl_io)

        song_nav = QHBoxLayout()
        self.prev_s_btn = QPushButton("◀◀ Prev Song")
        self.prev_s_btn.clicked.connect(self._prev_song)
        song_nav.addWidget(self.prev_s_btn)
        self.next_s_btn = QPushButton("Next Song ▶▶")
        self.next_s_btn.clicked.connect(self._next_song)
        song_nav.addWidget(self.next_s_btn)
        mid_layout.addLayout(song_nav)
        split.addWidget(mid_box)

        # --- Hymn detail (right) ---
        right_box = QGroupBox("Now Showing")
        right_layout = QVBoxLayout(right_box)
        self.hymn_title_label = QLabel("— select a hymn —")
        self.hymn_title_label.setObjectName("hymnTitle")
        self.hymn_title_label.setWordWrap(True)
        right_layout.addWidget(self.hymn_title_label)

        self.hymn_meta_label = QLabel("")
        self.hymn_meta_label.setObjectName("hymnMeta")
        self.hymn_meta_label.setWordWrap(True)
        right_layout.addWidget(self.hymn_meta_label)

        self.verse_list = QListWidget()
        self.verse_list.itemSelectionChanged.connect(self._on_verse_selection)
        right_layout.addWidget(self.verse_list, 1)

        vbtns = QHBoxLayout()
        self.prev_v_btn = QPushButton("◀ Prev Verse (←)")
        self.prev_v_btn.clicked.connect(self._prev_verse)
        vbtns.addWidget(self.prev_v_btn)
        self.next_v_btn = QPushButton("Next Verse (→) ▶")
        self.next_v_btn.clicked.connect(self._next_verse)
        vbtns.addWidget(self.next_v_btn)
        right_layout.addLayout(vbtns)

        audio_box = QGroupBox("Audio + Karaoke")
        a_layout = QVBoxLayout(audio_box)
        self.audio_status = QLabel("no audio")
        self.audio_status.setObjectName("hymnMeta")
        a_layout.addWidget(self.audio_status)
        a_btns = QHBoxLayout()
        self.play_btn = QPushButton("▶ Play (Space)")
        self.play_btn.clicked.connect(self._toggle_audio)
        self.play_btn.setEnabled(False)
        a_btns.addWidget(self.play_btn)
        self.stop_audio_btn = QPushButton("⏹ Stop")
        self.stop_audio_btn.setObjectName("destructiveBtn")
        self.stop_audio_btn.clicked.connect(self.audio.stop)
        a_btns.addWidget(self.stop_audio_btn)
        a_layout.addLayout(a_btns)

        # divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: #E5E5EA;")
        a_layout.addWidget(div)

        self.karaoke_toggle = QCheckBox("✦ Karaoke — highlight follows audio")
        self.karaoke_toggle.setChecked(True)
        self.karaoke_toggle.toggled.connect(self._on_karaoke_toggle)
        a_layout.addWidget(self.karaoke_toggle)

        k_row = QHBoxLayout()
        k_row.addWidget(QLabel("Speed:"))
        self.karaoke_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.karaoke_speed_slider.setRange(50, 200)
        self.karaoke_speed_slider.setValue(100)
        self.karaoke_speed_slider.valueChanged.connect(self._on_karaoke_speed_changed)
        k_row.addWidget(self.karaoke_speed_slider)
        self.karaoke_speed_label = QLabel("1.00×")
        self.karaoke_speed_label.setMinimumWidth(50)
        k_row.addWidget(self.karaoke_speed_label)
        a_layout.addLayout(k_row)

        self.bpm_label = QLabel("")
        self.bpm_label.setObjectName("hymnMeta")
        a_layout.addWidget(self.bpm_label)

        right_layout.addWidget(audio_box)

        # font size slider
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Display font:"))
        self.font_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_slider.setRange(40, 250)
        self.font_slider.setValue(100)
        self.font_slider.valueChanged.connect(self._on_font_scale_changed)
        font_row.addWidget(self.font_slider)
        self.font_size_label = QLabel("100%")
        font_row.addWidget(self.font_size_label)
        right_layout.addLayout(font_row)

        split.addWidget(right_box)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setStretchFactor(2, 3)

        self.setStatusBar(QStatusBar())

    def _wire_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key.Key_Left), self).activated.connect(self._prev_verse)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self).activated.connect(self._next_verse)
        QShortcut(QKeySequence("Ctrl+Left"), self).activated.connect(self._prev_song)
        QShortcut(QKeySequence("Ctrl+Right"), self).activated.connect(self._next_song)
        QShortcut(QKeySequence(Qt.Key.Key_B), self).activated.connect(self.blank_btn.click)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self).activated.connect(self._toggle_audio)
        QShortcut(QKeySequence(Qt.Key.Key_F5), self).activated.connect(self.show_btn.click)
        QShortcut(QKeySequence("Esc"), self).activated.connect(self._stop_show)

    # ----------------------------------------------------------- library/UI
    def _refresh_library_list(self, query: str = "") -> None:
        text = self.search_edit.text().strip()
        results = self.library.search(text)
        self.library_list.clear()
        for h in results:
            prefix = "♪ " if h.has_audio else "   "
            item = QListWidgetItem(f"{prefix}{h.display}")
            item.setData(Qt.ItemDataRole.UserRole, h.id)
            self.library_list.addItem(item)
        self.statusBar().showMessage(f"{len(results)} of {len(self.library.hymns)} hymns shown")

    def _refresh_screen_list(self) -> None:
        screens = QApplication.screens()
        self.screen_combo.clear()
        primary = QApplication.primaryScreen()
        for i, scr in enumerate(screens):
            tag = "  (primary)" if scr is primary else ""
            geom = scr.geometry()
            self.screen_combo.addItem(
                f"Display {i+1}: {scr.name()} {geom.width()}×{geom.height()}{tag}", i
            )
        if len(screens) > 1:
            self.screen_combo.setCurrentIndex(1)

    def _on_library_selection(self) -> None:
        items = self.library_list.selectedItems()
        if not items:
            return
        hid = items[0].data(Qt.ItemDataRole.UserRole)
        self._set_current_hymn(self.library.get(hid))

    # ---------------------------------------------------- current-item state
    def _clear_current(self) -> None:
        self._current_slides = []
        self._current_slide_index = -1
        self._current_audio_id = None
        self._current_display_title = ""
        self._current_display_subtitle = ""
        self._current_display_footer = ""

    def _set_current_hymn(self, hymn: Optional[Hymn]) -> None:
        if not hymn:
            self._clear_current()
            self._refresh_now_showing("— select a hymn —", "")
            self._load_audio_for_current()
            return
        bits: List[str] = []
        if hymn.author:
            bits.append(f"Words: {hymn.author}")
        if hymn.composer:
            bits.append(f"Music: {hymn.composer}")
        if hymn.tune:
            bits.append(f"Tune: {hymn.tune}")
        if hymn.year:
            bits.append(str(hymn.year))
        self._current_slides = [(v.label, list(v.lines)) for v in hymn.verses]
        self._current_audio_id = hymn.id
        self._current_display_title = hymn.title
        self._current_display_subtitle = "   ·   ".join(bits)
        self._current_display_footer = ""
        self._refresh_now_showing(hymn.title, self._current_display_subtitle)
        self._load_audio_for_current()

    def _set_current_passage(self, passage: Passage) -> None:
        slides = chunk_passage_to_slides(passage.text)
        self._current_slides = slides
        self._current_audio_id = None
        self._current_display_title = passage.canonical
        self._current_display_subtitle = (
            f"ESV  ·  fetched {passage.fetched_at.split('T')[0]}"
        )
        self._current_display_footer = ESV_ATTRIBUTION
        self._refresh_now_showing(passage.canonical, self._current_display_subtitle)
        self._load_audio_for_current()

    def _refresh_now_showing(self, title: str, subtitle: str) -> None:
        self.hymn_title_label.setText(title)
        self.hymn_meta_label.setText(subtitle)
        self.verse_list.clear()
        for label, lines in self._current_slides:
            preview = lines[0][:70] + ("…" if len(lines[0]) > 70 else "")
            self.verse_list.addItem(f"{label} — {preview}")
        self._current_slide_index = -1
        if self._current_slides:
            self.verse_list.setCurrentRow(0)

    # ------------------------------------------------------------ slide nav
    def _on_verse_selection(self) -> None:
        row = self.verse_list.currentRow()
        if row < 0:
            return
        self._current_slide_index = row
        if self._show_active and not self._is_blank:
            self._push_slide_to_display()
        # Reset karaoke schedule for the new slide, anchored at current audio pos
        self._rebuild_karaoke_schedule()
        if self.audio.is_playing():
            self._karaoke_verse_start_ms = self.audio.position_ms()

    def _push_slide_to_display(self) -> None:
        if self._current_slide_index < 0 or not self._current_slides:
            return
        label, lines = self._current_slides[self._current_slide_index]
        if label.startswith("Verse") or label.startswith("v."):
            title = f"{self._current_display_title} — {label}"
        else:
            title = self._current_display_title
        lyric = "\n".join(lines)
        if self.display:
            self.display.set_verse(title, lyric, footer=self._current_display_footer)

    def _prev_verse(self) -> None:
        if self._current_slide_index > 0:
            self.verse_list.setCurrentRow(self._current_slide_index - 1)

    def _next_verse(self) -> None:
        if self._current_slide_index < len(self._current_slides) - 1:
            self.verse_list.setCurrentRow(self._current_slide_index + 1)

    # ------------------------------------------------------------- playlist
    def _add_to_playlist_item(self, item: QListWidgetItem) -> None:
        hid = item.data(Qt.ItemDataRole.UserRole)
        if hid:
            self._playlist.append({"type": "hymn", "id": hid})
            self._refresh_playlist_widget()

    def _add_selected_to_playlist(self) -> None:
        for it in self.library_list.selectedItems():
            hid = it.data(Qt.ItemDataRole.UserRole)
            if hid:
                self._playlist.append({"type": "hymn", "id": hid})
        self._refresh_playlist_widget()

    def _add_passage_clicked(self) -> None:
        if not self._ensure_api_key():
            return
        dlg = PassageDialog(self.bible, self)
        if dlg.exec() != PassageDialog.DialogCode.Accepted or not dlg.fetched_passage:
            return
        p = dlg.fetched_passage
        self._playlist.append({
            "type": "passage",
            "reference": p.reference,
            "canonical": p.canonical,
            "text": p.text,
            "fetched_at": p.fetched_at,
        })
        self._refresh_playlist_widget()
        self.playlist_widget.setCurrentRow(len(self._playlist) - 1)

    def _set_api_key_clicked(self) -> None:
        dlg = ApiKeyDialog(current_key=self.bible.api_key or "", parent=self)
        if dlg.exec() != ApiKeyDialog.DialogCode.Accepted:
            return
        self.bible.set_api_key(dlg.value())
        self._save_settings()
        self.statusBar().showMessage(
            "ESV API key saved." if self.bible.has_key else "ESV API key cleared.", 4000
        )

    def _ensure_api_key(self) -> bool:
        if self.bible.has_key:
            return True
        QMessageBox.information(
            self,
            "ESV API key needed",
            "To look up Bible passages, you need a free ESV API key from Crossway.\n\n"
            "I'll open the key dialog now — it has the signup link and instructions.",
        )
        self._set_api_key_clicked()
        return self.bible.has_key

    def _refresh_playlist_widget(self) -> None:
        self.playlist_widget.blockSignals(True)
        self.playlist_widget.clear()
        for i, entry in enumerate(self._playlist):
            label = self._playlist_label(i, entry)
            if label:
                self.playlist_widget.addItem(label)
        self.playlist_widget.blockSignals(False)
        if 0 <= self._playlist_index < len(self._playlist):
            self.playlist_widget.setCurrentRow(self._playlist_index)

    def _playlist_label(self, idx: int, entry: Dict) -> str:
        kind = entry.get("type", "hymn")
        if kind == "hymn":
            h = self.library.get(entry.get("id", ""))
            if not h:
                return f"{idx+1}. (missing hymn: {entry.get('id')})"
            prefix = "♪ " if h.has_audio else "   "
            return f"{idx+1}. {prefix}{h.title}"
        if kind == "passage":
            return f"{idx+1}. 📖 {entry.get('canonical', entry.get('reference', '?'))}"
        return f"{idx+1}. (unknown)"

    def _on_playlist_selection(self) -> None:
        idx = self.playlist_widget.currentRow()
        if idx < 0 or idx >= len(self._playlist):
            return
        self._playlist_index = idx
        entry = self._playlist[idx]
        kind = entry.get("type", "hymn")
        if kind == "hymn":
            self._set_current_hymn(self.library.get(entry.get("id", "")))
        elif kind == "passage":
            passage = Passage(
                reference=entry["reference"],
                canonical=entry["canonical"],
                text=entry["text"],
                fetched_at=entry.get("fetched_at", ""),
            )
            self._set_current_passage(passage)

    def _move_playlist_item(self, delta: int) -> None:
        idx = self.playlist_widget.currentRow()
        new_idx = idx + delta
        if not (0 <= idx < len(self._playlist) and 0 <= new_idx < len(self._playlist)):
            return
        self._playlist[idx], self._playlist[new_idx] = self._playlist[new_idx], self._playlist[idx]
        self._playlist_index = new_idx
        self._refresh_playlist_widget()

    def _remove_from_playlist(self) -> None:
        idx = self.playlist_widget.currentRow()
        if 0 <= idx < len(self._playlist):
            self._playlist.pop(idx)
            if self._playlist_index >= len(self._playlist):
                self._playlist_index = len(self._playlist) - 1
            self._refresh_playlist_widget()

    def _clear_playlist(self) -> None:
        if not self._playlist:
            return
        if (
            QMessageBox.question(self, "Clear playlist?", "Remove all songs?")
            == QMessageBox.StandardButton.Yes
        ):
            self._playlist.clear()
            self._playlist_index = -1
            self._refresh_playlist_widget()

    def _save_playlist(self) -> None:
        if not self._playlist:
            QMessageBox.information(self, "Empty", "Playlist is empty.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save playlist",
            str(self.playlists_dir / "service.json"),
            "Playlist (*.json)",
        )
        if not path:
            return
        Path(path).write_text(
            json.dumps({"version": 2, "items": self._playlist}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.statusBar().showMessage(f"Saved {path}", 4000)

    def _load_playlist(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load playlist", str(self.playlists_dir), "Playlist (*.json)"
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as e:
            QMessageBox.warning(self, "Bad playlist", str(e))
            return
        self._playlist = self._migrate_playlist(data)
        self._playlist_index = -1
        self._refresh_playlist_widget()
        self.statusBar().showMessage(f"Loaded {path}", 4000)

    def _migrate_playlist(self, data: Dict) -> List[Dict]:
        """Accept both old v1 (`{"hymns": ["id"]}`) and new v2 (`{"items": [...]}`)."""
        items = data.get("items")
        if items is not None:
            return [it for it in items if self._valid_entry(it)]
        legacy = data.get("hymns", [])
        return [{"type": "hymn", "id": h} for h in legacy if self.library.get(h)]

    def _valid_entry(self, entry: Dict) -> bool:
        kind = entry.get("type")
        if kind == "hymn":
            return bool(self.library.get(entry.get("id", "")))
        if kind == "passage":
            return bool(entry.get("text") and entry.get("reference"))
        return False

    def _next_song(self) -> None:
        if not self._playlist:
            return
        if self._playlist_index + 1 < len(self._playlist):
            self.playlist_widget.setCurrentRow(self._playlist_index + 1)

    def _prev_song(self) -> None:
        if not self._playlist:
            return
        if self._playlist_index - 1 >= 0:
            self.playlist_widget.setCurrentRow(self._playlist_index - 1)

    # ---------------------------------------------------- display + blank
    def _toggle_show(self) -> None:
        if self.show_btn.isChecked():
            self._start_show()
        else:
            self._stop_show()

    def _start_show(self) -> None:
        screens = QApplication.screens()
        if not screens:
            return
        idx = self.screen_combo.currentData()
        if not isinstance(idx, int) or idx >= len(screens):
            idx = 0
        screen = screens[idx]
        if self.display is None:
            self.display = DisplayWindow()
            self.display.escape_pressed.connect(self._stop_show)
            self.display.set_font_scale(self.font_slider.value() / 100.0)
        self.display.show_on(screen)
        self._show_active = True
        self.show_btn.setChecked(True)
        self.show_btn.setText("◼ Hide Display")
        self.activateWindow()
        self._push_slide_to_display()

    def _stop_show(self) -> None:
        if self.display:
            self.display.hide()
        self._show_active = False
        self.show_btn.setChecked(False)
        self.show_btn.setText("◼ Show Display")

    def _toggle_blank(self) -> None:
        self._is_blank = self.blank_btn.isChecked()
        if self.display:
            self.display.set_blank(self._is_blank)

    def _on_font_scale_changed(self, val: int) -> None:
        scale = val / 100.0
        self.font_size_label.setText(f"{val}%")
        if self.display:
            self.display.set_font_scale(scale)

    # --------------------------------------------------------------- audio
    def _resolve_audio_path(self, audio_id: str) -> Optional[Path]:
        search_dirs = [d for d in (self.user_audio_dir, self.audio_dir) if d]
        for d in search_dirs:
            for ext in (".mp3", ".ogg", ".m4a", ".wav", ".flac", ".mid", ".midi"):
                p = d / f"{audio_id}{ext}"
                if p.exists():
                    return p
        return None

    def _load_audio_for_current(self) -> None:
        if not self._current_audio_id:
            self.audio.load(None)
            self.audio_status.setText("(no audio for this item)")
            self.play_btn.setEnabled(False)
            self._rebuild_karaoke_schedule()
            return
        path = self._resolve_audio_path(self._current_audio_id)
        if not path:
            self.audio.load(None)
            self.audio_status.setText("no audio file")
            self.play_btn.setEnabled(False)
            self._rebuild_karaoke_schedule()
            return
        self.audio.load(path)
        self.audio_status.setText(f"loaded: {path.name}")
        self.play_btn.setEnabled(True)
        self._rebuild_karaoke_schedule()

    def _toggle_audio(self) -> None:
        self.audio.toggle_play_pause()

    def _on_audio_state(self, state: str) -> None:
        if state == "playing":
            self.play_btn.setText("⏸ Pause (Space)")
            # Anchor the karaoke timer to "now" when playback resumes
            if self._karaoke_enabled:
                self._karaoke_verse_start_ms = self.audio.position_ms()
                self._karaoke_timer.start()
        elif state == "paused":
            self.play_btn.setText("▶ Play (Space)")
            self._karaoke_timer.stop()
        elif state == "stopped":
            self.play_btn.setText("▶ Play (Space)")
            self._karaoke_timer.stop()
            if self.display:
                self.display.clear_highlight()
        elif state == "no-audio":
            self.audio_status.setText("no audio")
            self.play_btn.setEnabled(False)
            self._karaoke_timer.stop()
            if self.display:
                self.display.clear_highlight()

    def _on_audio_finished(self) -> None:
        if self._auto_advance_song and self._playlist:
            self._next_song()

    # --------------------------------------------------------- karaoke
    def _on_karaoke_toggle(self, checked: bool) -> None:
        self._karaoke_enabled = checked
        if not checked:
            self._karaoke_timer.stop()
            if self.display:
                self.display.clear_highlight()
        elif self.audio.is_playing():
            self._karaoke_verse_start_ms = self.audio.position_ms()
            self._karaoke_timer.start()

    def _on_karaoke_speed_changed(self, val: int) -> None:
        self._karaoke_speed = val / 100.0
        self.karaoke_speed_label.setText(f"{self._karaoke_speed:.2f}×")
        self._rebuild_karaoke_schedule()

    def _rebuild_karaoke_schedule(self) -> None:
        if self._current_slide_index < 0 or not self._current_slides:
            self._current_schedule = None
            self.bpm_label.setText("")
            return
        _, lines = self._current_slides[self._current_slide_index]
        n_words = sum(len(line.split()) for line in lines)

        bpm = DEFAULT_BPM
        has_real = False
        if self._current_audio_id:
            path = self._resolve_audio_path(self._current_audio_id)
            if path and path.suffix.lower() == ".mp3":
                td = TempoData.load_for(path)
                if td:
                    bpm = td.bpm
                    has_real = True

        self._current_schedule = HighlightSchedule(n_words, bpm, self._karaoke_speed)
        verse_secs = n_words / max(0.1, words_per_second(bpm, self._karaoke_speed))
        tag = "detected" if has_real else "default"
        self.bpm_label.setText(
            f"BPM {bpm:.0f} ({tag})  ·  {n_words} words  ·  ≈{verse_secs:.0f}s per verse"
        )

    def _karaoke_tick(self) -> None:
        if not self._karaoke_enabled or self._current_schedule is None:
            return
        if not self.display or not self._show_active or self._is_blank:
            return
        if not self.audio.is_playing():
            return
        elapsed_ms = self.audio.position_ms() - self._karaoke_verse_start_ms
        idx = self._current_schedule.word_at(max(0, elapsed_ms) / 1000.0)
        self.display.set_highlight(idx)

    # ----------------------------------------------------- settings/lifecycle
    def _load_settings(self) -> None:
        if not self.settings_path.exists():
            return
        try:
            s = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception:
            return
        scr = s.get("display_screen")
        if isinstance(scr, int) and 0 <= scr < self.screen_combo.count():
            self.screen_combo.setCurrentIndex(scr)
        fs = s.get("font_scale_pct")
        if isinstance(fs, int):
            self.font_slider.setValue(fs)
        self._auto_advance_song = bool(s.get("auto_advance_song", False))
        esv = s.get("esv_api_key")
        if isinstance(esv, str) and esv.strip():
            self.bible.set_api_key(esv.strip())
        if "karaoke_enabled" in s:
            self._karaoke_enabled = bool(s["karaoke_enabled"])
            self.karaoke_toggle.setChecked(self._karaoke_enabled)
        if "karaoke_speed_pct" in s and isinstance(s["karaoke_speed_pct"], int):
            self.karaoke_speed_slider.setValue(s["karaoke_speed_pct"])

    def _save_settings(self) -> None:
        s = {
            "display_screen": self.screen_combo.currentIndex(),
            "font_scale_pct": self.font_slider.value(),
            "auto_advance_song": self._auto_advance_song,
            "esv_api_key": self.bible.api_key or "",
            "karaoke_enabled": self._karaoke_enabled,
            "karaoke_speed_pct": self.karaoke_speed_slider.value(),
        }
        try:
            self.settings_path.write_text(json.dumps(s, indent=2), encoding="utf-8")
        except Exception:
            pass

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._save_settings()
        if self.display:
            self.display.close()
        self.audio.stop()
        super().closeEvent(event)
