"""Dialogs for adding a Bible passage and setting the ESV API key."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from .bible import ESV_ATTRIBUTION, BibleClient, Passage


class ApiKeyDialog(QDialog):
    """Prompt for a Crossway ESV API key. Saved to settings on accept."""

    def __init__(self, current_key: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ESV API Key")
        self.resize(560, 280)

        layout = QVBoxLayout(self)

        info = QLabel(
            "<b>To enable Bible passage lookup, you need a free key from Crossway.</b><br><br>"
            "1. Go to <a href='https://api.esv.org/account/create-application/'>"
            "api.esv.org/account/create-application</a><br>"
            "2. Create a free account and an application (any name).<br>"
            "3. Copy the API token shown — it looks like 32 hex characters.<br>"
            "4. Paste it below.<br><br>"
            "The token is stored only on this computer (in <code>settings.json</code>) and "
            "is sent only to Crossway. Free tier allows 5,000 verse fetches/day."
        )
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        self.key_edit.setPlaceholderText("Paste your ESV API token here")
        if current_key:
            self.key_edit.setText(current_key)
        form.addRow("API Token:", self.key_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.key_edit.setFocus()

    def value(self) -> str:
        return self.key_edit.text().strip()


class PassageDialog(QDialog):
    """Look up an ESV passage and (optionally) add it to the playlist."""

    def __init__(self, bible: BibleClient, parent=None):
        super().__init__(parent)
        self.bible = bible
        self.fetched_passage: Optional[Passage] = None

        self.setWindowTitle("Add Bible Passage (ESV)")
        self.resize(760, 560)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.ref_edit = QLineEdit()
        self.ref_edit.setPlaceholderText(
            "John 3:16-17    ·    Romans 5:1-5    ·    Psalm 23    ·    Isaiah 53"
        )
        self.ref_edit.returnPressed.connect(self._fetch)
        form.addRow("Reference:", self.ref_edit)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.fetch_btn = QPushButton("Look up")
        self.fetch_btn.setDefault(True)
        self.fetch_btn.clicked.connect(self._fetch)
        btn_row.addWidget(self.fetch_btn)
        self.cache_label = QLabel("")
        self.cache_label.setStyleSheet("color: gray;")
        btn_row.addWidget(self.cache_label)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.canonical_label = QLabel("")
        self.canonical_label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        layout.addWidget(self.canonical_label)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Georgia", 12))
        layout.addWidget(self.preview, 1)

        attr = QLabel(ESV_ATTRIBUTION)
        attr.setStyleSheet("color: gray; font-size: 9pt;")
        attr.setWordWrap(True)
        layout.addWidget(attr)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Add to Playlist")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.ref_edit.setFocus()

    def _fetch(self) -> None:
        ref = self.ref_edit.text().strip()
        if not ref:
            return
        cached = self.bible.get_cached(ref)
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Fetching…" if not cached else "Loading from cache…")
        try:
            passage = self.bible.fetch(ref)
        except Exception as e:
            QMessageBox.warning(self, "ESV API error", str(e))
            self.fetch_btn.setEnabled(True)
            self.fetch_btn.setText("Look up")
            return
        self.fetched_passage = passage
        self.canonical_label.setText(passage.canonical)
        self.preview.setPlainText(passage.text)
        self.cache_label.setText(
            "(loaded from cache)" if cached else "(fetched fresh)"
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Look up again")
