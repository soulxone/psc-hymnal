"""Application entrypoint — wires the QApplication + operator window."""
from __future__ import annotations

import os
import sys

from PyQt6.QtWidgets import QApplication

from .bible import BibleClient
from .library import HymnLibrary
from .operator import OperatorWindow
from .paths import resource_root, user_data_root
from .styles import apply_to as apply_theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("PSC Hymnal")
    app.setOrganizationName("Pleasant Springs Church")
    apply_theme(app)

    # Read-only bundled resources vs. per-user writable data. When installed,
    # the program folder is read-only, so settings/cache/playlists/user audio
    # all live under %APPDATA%\PSC Hymnal (see hymnal/paths.py).
    res = resource_root()
    data = user_data_root()

    library_path = res / "hymnal" / "data" / "hymns.json"
    if not library_path.exists():
        print(
            f"hymn library not found: {library_path}\n"
            "Run tools/build_library.py first to download and parse openhymnal.org.",
            file=sys.stderr,
        )
        return 2

    user_audio_dir = data / "audio"
    user_audio_dir.mkdir(parents=True, exist_ok=True)

    library = HymnLibrary(library_path, user_json_path=data / "user_hymns.json")
    bible = BibleClient(cache_path=data / "passages.json")

    op = OperatorWindow(
        library=library,
        audio_dir=res / "audio",
        playlists_dir=data / "playlists",
        settings_path=data / "settings.json",
        bible=bible,
        user_audio_dir=user_audio_dir,
    )
    op.show()

    # Gated self-test (inert unless PSC_HYMNAL_SMOKE is set in the env). Used to
    # verify a frozen build end-to-end: it exercises the pygame (MIDI) and
    # QMediaPlayer (MP3) backends, writes a result file, then quits.
    if os.environ.get("PSC_HYMNAL_SMOKE"):
        from PyQt6.QtCore import QTimer

        report = {"hymns": len(library.hymns)}
        audio_dir = res / "audio"
        mid = next(iter(sorted(audio_dir.glob("*.mid"))), None)
        mp3 = next(iter(sorted(audio_dir.glob("*.mp3"))), None)
        try:
            if mid is not None:
                op.audio.load(mid)          # exercises pygame.mixer.init()
                report["pygame_midi"] = True
            if mp3 is not None:
                op.audio.load(mp3)          # exercises QMediaPlayer / WMF
                report["qmediaplayer_mp3"] = True
        except Exception as e:              # noqa: BLE001 - report, don't crash
            report["audio_error"] = repr(e)
        (data / "smoke_result.txt").write_text(
            "\n".join(f"{k}={v}" for k, v in report.items()) + "\nOK\n",
            encoding="utf-8",
        )
        QTimer.singleShot(800, app.quit)

    return app.exec()
