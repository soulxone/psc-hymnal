"""Fullscreen lyrics display window for the projection monitor."""
from __future__ import annotations

import html
import re
from typing import List, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QPalette, QScreen
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

# Token kinds for the karaoke renderer
TOK_WORD = "word"
TOK_SPACE = "space"
TOK_BREAK = "break"

HIGHLIGHT_BG = "#4ABFAB"   # mint
PAST_COLOR = "#7a7a7a"
FUTURE_COLOR = "#ffffff"


class DisplayWindow(QWidget):
    escape_pressed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PSC Hymnal — Display")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)

        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor("#000000"))
        self.setPalette(pal)
        self.setAutoFillBackground(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(120, 80, 120, 80)
        layout.setSpacing(40)

        self.title_label = QLabel("")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("color: #888888;")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        layout.addStretch(1)

        self.lyric_label = QLabel("")
        self.lyric_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lyric_label.setWordWrap(True)
        self.lyric_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(self.lyric_label)

        layout.addStretch(2)

        self.footer_label = QLabel("")
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer_label.setStyleSheet("color: #555555;")
        self.footer_label.setWordWrap(True)
        self.footer_label.hide()
        layout.addWidget(self.footer_label)

        self._is_blank: bool = False
        self._last_lyric: str = ""
        self._last_title: str = ""
        self._last_footer: str = ""
        self._user_font_scale: float = 1.0
        self._tokens: List[Tuple[str, str]] = []
        self._word_count: int = 0
        self._highlight_index: int = -1
        self._apply_fonts()

    # ----------------------------------------------------------- presentation
    def show_on(self, screen: QScreen) -> None:
        geom = screen.geometry()
        self.move(geom.topLeft())
        self.resize(geom.size())
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def set_verse(self, title: str, lyric: str, footer: str = "") -> None:
        self._last_title = title
        self._last_lyric = lyric
        self._last_footer = footer
        self._tokens, self._word_count = self._tokenize(lyric)
        self._highlight_index = -1
        if self._is_blank:
            return
        self.title_label.setText(title)
        self._render_lyric()
        if footer:
            self.footer_label.setText(footer)
            self.footer_label.show()
        else:
            self.footer_label.hide()
        self._apply_fonts()

    @property
    def word_count(self) -> int:
        return self._word_count

    def set_highlight(self, word_index: int) -> None:
        """Highlight the Nth word (0-indexed). -1 clears the highlight."""
        if word_index == self._highlight_index:
            return
        self._highlight_index = word_index
        if not self._is_blank:
            self._render_lyric()

    def clear_highlight(self) -> None:
        self.set_highlight(-1)

    def _tokenize(self, text: str) -> Tuple[List[Tuple[str, str]], int]:
        tokens: List[Tuple[str, str]] = []
        n_words = 0
        lines = text.split("\n")
        for li, line in enumerate(lines):
            words = re.findall(r"\S+", line)
            for wi, w in enumerate(words):
                tokens.append((TOK_WORD, w))
                n_words += 1
                if wi < len(words) - 1:
                    tokens.append((TOK_SPACE, " "))
            if li < len(lines) - 1:
                tokens.append((TOK_BREAK, ""))
        return tokens, n_words

    def _render_lyric(self) -> None:
        if not self._tokens:
            self.lyric_label.setText("")
            return
        idx = self._highlight_index
        parts: List[str] = ['<div style="line-height:130%;">']
        word_i = 0
        for kind, text in self._tokens:
            if kind == TOK_BREAK:
                parts.append("<br>")
            elif kind == TOK_SPACE:
                parts.append(" ")
            else:  # word
                esc = html.escape(text)
                if idx < 0:
                    parts.append(f'<span style="color:{FUTURE_COLOR};">{esc}</span>')
                elif word_i == idx:
                    parts.append(
                        f'<span style="background-color:{HIGHLIGHT_BG}; '
                        f'color:white;">&nbsp;{esc}&nbsp;</span>'
                    )
                elif word_i < idx:
                    parts.append(f'<span style="color:{PAST_COLOR};">{esc}</span>')
                else:
                    parts.append(f'<span style="color:{FUTURE_COLOR};">{esc}</span>')
                word_i += 1
        parts.append("</div>")
        self.lyric_label.setTextFormat(Qt.TextFormat.RichText)
        self.lyric_label.setText("".join(parts))

    def set_blank(self, blank: bool) -> None:
        self._is_blank = blank
        if blank:
            self.title_label.setText("")
            self.lyric_label.setText("")
            self.footer_label.hide()
        else:
            self.title_label.setText(self._last_title)
            self._render_lyric()
            if self._last_footer:
                self.footer_label.setText(self._last_footer)
                self.footer_label.show()
            self._apply_fonts()

    def set_font_scale(self, scale: float) -> None:
        self._user_font_scale = max(0.4, min(2.5, scale))
        self._apply_fonts()

    # ------------------------------------------------------------- internals
    def _apply_fonts(self) -> None:
        text = self.lyric_label.text()
        chars = len(text)
        if chars == 0:
            base = 56
        elif chars < 80:
            base = 80
        elif chars < 200:
            base = 60
        elif chars < 400:
            base = 46
        else:
            base = 36
        h = self.height() or 1080
        h_factor = h / 1080.0
        size = int(base * h_factor * self._user_font_scale)
        size = max(20, size)

        lf = QFont("Georgia", size, QFont.Weight.Bold)
        self.lyric_label.setFont(lf)

        tf = QFont("Georgia", max(16, size // 3), QFont.Weight.Normal)
        tf.setItalic(True)
        self.title_label.setFont(tf)

        ff = QFont("Arial", max(10, size // 6), QFont.Weight.Normal)
        self.footer_label.setFont(ff)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_fonts()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
            self.showNormal()
            self.hide()
        else:
            super().keyPressEvent(event)
