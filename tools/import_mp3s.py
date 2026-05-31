#!/usr/bin/env python3
"""Overlay MP3 audio from openhymnal.org special-edition zips.

Reads MP3 files in tools/mp3_extracted/ (extracted from the Christmas, Easter,
and Visitation MP3 zips downloaded from openhymnal.org), matches each by
filename to a hymn in hymns.json, and copies it to audio/<id>.mp3.

The operator window checks .mp3 before .mid, so MP3 silently takes over once
the file exists. Re-runnable; existing files are overwritten.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
MP3_DIR = ROOT / "tools" / "mp3_extracted"
HYMNS_JSON = ROOT / "hymnal" / "data" / "hymns.json"
AUDIO_DIR = ROOT / "audio"

LEADING_NUM = re.compile(r"^\d+\.")


def normalize(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", s).lower()


def title_key(title: str) -> str:
    return normalize(title)


def mp3_key(stem: str) -> str:
    """Strip leading '06.' numbering and take the part before the first '-'."""
    s = LEADING_NUM.sub("", stem)
    prefix = s.split("-", 1)[0]
    return normalize(prefix)


def main() -> int:
    if not HYMNS_JSON.exists():
        print(f"missing: {HYMNS_JSON} — run build_library.py first", file=sys.stderr)
        return 1
    if not MP3_DIR.exists():
        print(f"missing: {MP3_DIR}", file=sys.stderr)
        return 1

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.loads(HYMNS_JSON.read_text(encoding="utf-8"))
    hymns: List[Dict] = payload["hymns"]

    by_key: Dict[str, Dict] = {title_key(h["title"]): h for h in hymns}

    mp3_files = sorted(MP3_DIR.rglob("*.mp3"))
    print(f"found {len(mp3_files)} MP3 files")
    print(f"hymns in library: {len(hymns)}")

    matched = 0
    unmatched: List[str] = []
    for mf in mp3_files:
        key = mp3_key(mf.stem)
        hymn: Optional[Dict] = by_key.get(key)
        if hymn is None:
            # fallback: prefix match
            for k, h in by_key.items():
                if k.startswith(key) or key.startswith(k):
                    hymn = h
                    break
        if hymn is None:
            unmatched.append(mf.name)
            continue
        dest = AUDIO_DIR / f"{hymn['id']}.mp3"
        shutil.copyfile(mf, dest)
        hymn["audio"] = dest.name
        matched += 1

    payload["hymns"] = hymns
    HYMNS_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"MP3 matched: {matched}/{len(mp3_files)}")
    if unmatched:
        print(f"unmatched MP3s ({len(unmatched)}):")
        for u in unmatched[:15]:
            print(f"  - {u}")
        if len(unmatched) > 15:
            print(f"  ... and {len(unmatched) - 15} more")

    total_audio = sum(1 for f in AUDIO_DIR.iterdir() if f.suffix in (".mp3", ".mid"))
    n_mp3 = sum(1 for f in AUDIO_DIR.iterdir() if f.suffix == ".mp3")
    n_mid = sum(1 for f in AUDIO_DIR.iterdir() if f.suffix == ".mid")
    print(f"\naudio/ now: {n_mp3} MP3 + {n_mid} MIDI = {total_audio} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
