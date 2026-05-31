"""iOS-inspired Qt Style Sheet for the operator window."""
from __future__ import annotations

# iOS / iPadOS palette
BG          = "#F2F2F7"   # systemGroupedBackground
CARD        = "#FFFFFF"
BORDER      = "#E5E5EA"   # opaqueSeparator
BORDER_HARD = "#D1D1D6"
TEXT        = "#1C1C1E"   # label
TEXT_SECOND = "#6E6E73"   # secondaryLabel
TEXT_TERT   = "#8E8E93"   # tertiaryLabel
ACCENT      = "#4ABFAB"   # PSC mint (brand)
ACCENT_DARK = "#3a9e8a"
ACCENT_DEEP = "#2d8071"
LINK_BLUE   = "#007AFF"   # iOS systemBlue
DESTRUCTIVE = "#FF3B30"   # iOS systemRed

STYLE_SHEET = f"""
/* ---------- base ---------- */
QMainWindow, QDialog {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Segoe UI Variable Display", "Segoe UI", "SF Pro Text", -apple-system, sans-serif;
    font-size: 11pt;
}}

QWidget {{
    color: {TEXT};
    background-color: transparent;
}}

QLabel {{
    background-color: transparent;
}}

/* ---------- "card" group boxes ---------- */
QGroupBox {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
    margin-top: 22px;
    padding: 22px 14px 14px 14px;
    font-weight: 600;
    font-size: 10pt;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 10px;
    color: {TEXT_SECOND};
    background-color: transparent;
    margin-left: 8px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-size: 8pt;
}}

/* ---------- buttons ---------- */
QPushButton {{
    background-color: {CARD};
    color: {LINK_BLUE};
    border: 1px solid {BORDER_HARD};
    border-radius: 10px;
    padding: 8px 16px;
    font-weight: 500;
    min-height: 22px;
}}
QPushButton:hover {{
    background-color: {BG};
    border-color: {TEXT_TERT};
}}
QPushButton:pressed {{
    background-color: {BORDER};
}}
QPushButton:disabled {{
    background-color: {BG};
    color: {TEXT_TERT};
    border-color: {BORDER};
}}
QPushButton:checked {{
    background-color: {ACCENT};
    color: white;
    border-color: {ACCENT_DARK};
}}

/* primary CTA button — Show Display */
QPushButton#primaryBtn {{
    background-color: {ACCENT};
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-weight: 600;
    min-height: 24px;
}}
QPushButton#primaryBtn:hover {{
    background-color: {ACCENT_DARK};
}}
QPushButton#primaryBtn:pressed {{
    background-color: {ACCENT_DEEP};
}}
QPushButton#primaryBtn:checked {{
    background-color: {ACCENT_DEEP};
}}

/* destructive button — clear playlist, stop */
QPushButton#destructiveBtn {{
    color: {DESTRUCTIVE};
}}

/* tiny round nav buttons (up/down arrows) */
QPushButton#iconBtn {{
    min-width: 36px;
    max-width: 36px;
    padding: 6px;
    font-size: 14pt;
}}

/* ---------- inputs ---------- */
QLineEdit {{
    background-color: {CARD};
    border: 1px solid {BORDER_HARD};
    border-radius: 10px;
    padding: 10px 14px;
    selection-background-color: {LINK_BLUE};
    selection-color: white;
    min-height: 22px;
}}
QLineEdit:focus {{
    border-color: {LINK_BLUE};
    border-width: 2px;
    padding: 9px 13px;
}}

QTextEdit {{
    background-color: {CARD};
    border: 1px solid {BORDER_HARD};
    border-radius: 10px;
    padding: 10px;
    selection-background-color: {LINK_BLUE};
    selection-color: white;
}}

QComboBox {{
    background-color: {CARD};
    border: 1px solid {BORDER_HARD};
    border-radius: 10px;
    padding: 8px 12px;
    min-height: 22px;
}}
QComboBox:hover {{ border-color: {TEXT_TERT}; }}
QComboBox::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid {TEXT_SECOND};
    margin-right: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 4px;
    selection-background-color: {ACCENT};
    selection-color: white;
    outline: none;
}}

/* ---------- list widgets ---------- */
QListWidget {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 6px;
    outline: none;
}}
QListWidget::item {{
    padding: 9px 12px;
    border-radius: 8px;
    margin: 1px 2px;
    color: {TEXT};
}}
QListWidget::item:hover:!selected {{
    background-color: {BG};
}}
QListWidget::item:selected {{
    background-color: {ACCENT};
    color: white;
}}
QListWidget::item:selected:!active {{
    background-color: {ACCENT_DARK};
    color: white;
}}

/* ---------- sliders ---------- */
QSlider::groove:horizontal {{
    height: 4px;
    background-color: {BORDER};
    border-radius: 2px;
    margin: 0 6px;
}}
QSlider::sub-page:horizontal {{
    background-color: {ACCENT};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background-color: {CARD};
    border: 1px solid {BORDER_HARD};
    width: 22px;
    height: 22px;
    margin: -10px -1px;
    border-radius: 12px;
}}
QSlider::handle:horizontal:hover {{
    background-color: {BG};
}}

/* ---------- menus ---------- */
QMenuBar {{
    background-color: {CARD};
    border-bottom: 1px solid {BORDER};
    padding: 4px 8px;
    color: {TEXT};
}}
QMenuBar::item {{
    padding: 6px 14px;
    background: transparent;
    border-radius: 8px;
    margin: 0 2px;
}}
QMenuBar::item:selected {{
    background-color: {BG};
}}

QMenu {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 6px;
    color: {TEXT};
}}
QMenu::item {{
    padding: 8px 24px 8px 16px;
    border-radius: 6px;
    margin: 1px;
}}
QMenu::item:selected {{
    background-color: {ACCENT};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background-color: {BORDER};
    margin: 4px 8px;
}}

/* ---------- status bar ---------- */
QStatusBar {{
    background-color: transparent;
    color: {TEXT_SECOND};
    border-top: 1px solid {BORDER};
    padding: 4px 10px;
    font-size: 9pt;
}}
QStatusBar::item {{ border: none; }}

/* ---------- splitter ---------- */
QSplitter::handle {{
    background-color: transparent;
}}
QSplitter::handle:horizontal {{ width: 10px; }}
QSplitter::handle:vertical   {{ height: 10px; }}

/* ---------- scroll bars ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px;
}}
QScrollBar::handle:vertical {{
    background-color: {BORDER_HARD};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {TEXT_TERT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px 4px;
}}
QScrollBar::handle:horizontal {{
    background-color: {BORDER_HARD};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {TEXT_TERT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
    background: none;
}}

/* ---------- dialog buttons ---------- */
QDialogButtonBox QPushButton {{
    min-width: 90px;
}}

/* ---------- form layout ---------- */
QFormLayout {{ spacing: 8px; }}

/* "Now Showing" emphasis title — set objectName="hymnTitle" in code */
QLabel#hymnTitle {{
    font-size: 16pt;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#hymnMeta {{
    color: {TEXT_SECOND};
    font-size: 9pt;
}}
"""


def apply_to(app) -> None:
    """Apply the iOS theme to a QApplication."""
    app.setStyleSheet(STYLE_SHEET)
