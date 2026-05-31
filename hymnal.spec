# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PSC Hymnal (one-folder, windowed Windows build)."""
from pathlib import Path

ROOT = Path(SPECPATH)

# Read-only resources shipped beside the executable (resolved at runtime via
# sys._MEIPASS in hymnal/paths.py). Target paths must mirror what app.py expects:
#   resource_root()/hymnal/data/hymns.json   and   resource_root()/audio/*
datas = [
    (str(ROOT / "hymnal" / "data" / "hymns.json"), "hymnal/data"),
    (str(ROOT / "audio"), "audio"),
]

# Offline-only / unused heavyweights — keep them out of the bundle.
excludes = [
    "librosa", "soundfile", "numba", "llvmlite", "scipy", "sklearn",
    "matplotlib", "pandas", "tkinter", "IPython", "pytest",
    "PyQt5", "PySide6", "PySide2", "PyQt6.QtWebEngineCore", "PyQt6.QtQuick3D",
    "PyQt6.Qt3DCore", "PyQt6.QtBluetooth", "PyQt6.QtNfc", "PyQt6.QtSql",
]

a = Analysis(
    ["run.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["pygame", "pygame.mixer"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PSC Hymnal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ROOT / "hymnal.ico"),
    version=str(ROOT / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PSC Hymnal",
)
