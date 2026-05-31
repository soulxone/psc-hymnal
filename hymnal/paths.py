"""Resolve resource (read-only) and user-data (writable) directories.

Works both when running from source and when frozen by PyInstaller.

In a frozen build the bundled data (``hymns.json``, ``audio/``) is shipped
read-only next to the executable — PyInstaller exposes its location via
``sys._MEIPASS`` — while anything the app *writes* (settings, the ESV
passage cache, saved playlists, user-supplied audio) must live in a
per-user writable location, because the install directory is typically
read-only once the app is installed to Program Files.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "PSC Hymnal"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Directory containing read-only bundled resources (hymns.json, audio/)."""
    if is_frozen():
        # PyInstaller sets _MEIPASS to the unpacked bundle root; fall back to
        # the executable's own folder if it is somehow absent.
        meipass = getattr(sys, "_MEIPASS", None)
        return Path(meipass) if meipass else Path(sys.executable).resolve().parent
    # Running from source: repo root is one level up from this package.
    return Path(__file__).resolve().parent.parent


def user_data_root() -> Path:
    """Per-user writable directory for settings, cache, playlists, audio.

    Created on first access. Falls back to the source tree when running
    unfrozen so dev runs keep their existing local settings.json.
    """
    if is_frozen():
        if sys.platform == "win32":
            base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        elif sys.platform == "darwin":
            base = str(Path.home() / "Library" / "Application Support")
        else:
            base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        root = Path(base) / APP_DIR_NAME
    else:
        root = resource_root()
    root.mkdir(parents=True, exist_ok=True)
    return root
