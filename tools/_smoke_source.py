"""Headless construction smoke test (offscreen Qt). Not shipped."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from hymnal.bible import BibleClient
from hymnal.library import HymnLibrary
from hymnal.operator import OperatorWindow
from hymnal.paths import resource_root, user_data_root
from hymnal.styles import apply_to

app = QApplication(sys.argv)
apply_to(app)
res, data = resource_root(), user_data_root()
print("resource_root:", res)
print("user_data_root:", data)
lib = HymnLibrary(res / "hymnal" / "data" / "hymns.json")
print("hymns loaded:", len(lib.hymns))
bible = BibleClient(cache_path=data / "passages.json")
ua = data / "audio"
ua.mkdir(parents=True, exist_ok=True)
op = OperatorWindow(
    library=lib,
    audio_dir=res / "audio",
    playlists_dir=data / "playlists",
    settings_path=data / "settings.json",
    bible=bible,
    user_audio_dir=ua,
)
print("audio for amazing-grace:", op._resolve_audio_path("amazing-grace"))
op.show()
QTimer.singleShot(300, app.quit)
print("exec rc:", app.exec())
print("OK")
