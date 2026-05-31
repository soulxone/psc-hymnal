#!/usr/bin/env python3
"""Backfill MIDI audio from The Cyber Hymnal's *sanctioned bulk downloads*.

The Cyber Hymnal (hymntime.com) asks crawlers for a 300 s delay, so we do NOT
crawl it. Instead we use the archive files it *explicitly offers* on its
download page (https://www.hymntime.com/tch/misc/download.htm):

  * tch-idx.7z          — title -> primary MIDI tune index (tch-idx.txt)
  * tch-mid<a..z>.7z    — the MIDI files, split by first letter of filename

Its copyright page permits reposting public-domain material with attribution.
MIDIs are tiny (~5-15 KB), so this backfills audio for hundreds of hymns while
adding only a few MB. We match by EXACT normalized title (no fuzzy guessing) so
we never attach the wrong tune, and we only fill hymns that have no audio yet.

Usage:
    py tools/fetch_cyberhymnal_midi.py --dry-run   # match + report, copy nothing
    py tools/fetch_cyberhymnal_midi.py             # download archives + copy MIDIs
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, Optional

import py7zr  # type: ignore

ROOT = Path(__file__).resolve().parent.parent
HYMNS_JSON = ROOT / "hymnal" / "data" / "hymns.json"
AUDIO_DIR = ROOT / "audio"
CACHE = ROOT / "tools" / "cyberhymnal"
MIDI_OUT = CACHE / "midi"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"
IDX_URL = "http://www.hymntime.com/tch/tch-idx.7z"
MID_URL = "http://www.hymntime.com/tch/mid/zip/tch-mid{letter}.7z"
AUDIO_EXTS = (".mp3", ".ogg", ".m4a", ".wav", ".flac", ".mid", ".midi")
DOWNLOAD_GAP_S = 2.0  # polite spacing between the (few) archive downloads


def norm(s: str) -> str:
    s = re.sub(r"&[a-z]+;", " ", s, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def download(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r:
            dest.write_bytes(r.read())
        print(f"    downloaded {dest.name} ({dest.stat().st_size // 1024} KB)")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"    FAILED {url}: {e}")
        return False


def load_index() -> Dict[str, str]:
    """Return {normalized_title: midi_basename} from tch-idx.txt."""
    CACHE.mkdir(parents=True, exist_ok=True)
    idx7z = CACHE / "tch-idx.7z"
    if not download(IDX_URL, idx7z):
        return {}
    with py7zr.SevenZipFile(idx7z, "r") as z:
        z.extractall(CACHE / "idx")
    txt = next((CACHE / "idx").rglob("tch-idx.txt"))
    mapping: Dict[str, str] = {}
    for line in txt.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip() or line.startswith(("_", "TITLE")) or "Cyber Hymnal" in line:
            continue
        parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
        if len(parts) != 2:
            continue
        title, midi = parts[0].strip(), parts[1].strip().split()[0]
        key = norm(title)
        if key and midi:
            mapping.setdefault(key, midi)
    return mapping


def has_audio(slug: str) -> bool:
    return any((AUDIO_DIR / f"{slug}{ext}").exists() for ext in AUDIO_EXTS)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="match + report, copy nothing")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    payload = json.loads(HYMNS_JSON.read_text(encoding="utf-8"))
    hymns = payload["hymns"]
    print(f"hymns: {len(hymns)}")

    print("loading Cyber Hymnal title->MIDI index...")
    index = load_index()
    print(f"  index entries: {len(index)}")
    if not index:
        return 1

    # Match audio-less hymns by exact normalized title.
    want: Dict[str, str] = {}   # slug -> midi_basename
    already = 0
    for h in hymns:
        slug = h["id"]
        if has_audio(slug):
            already += 1
            continue
        midi = index.get(norm(h["title"]))
        if midi:
            want[slug] = midi
    print(f"  already have audio: {already}")
    print(f"  audio-less hymns matched to a MIDI: {len(want)}")

    if args.dry_run:
        for slug, midi in list(want.items())[:12]:
            print(f"    {slug}  ->  {midi}.mid")
        print(f"  (would need archives: {sorted({m[0].lower() for m in want.values()})})")
        return 0

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    MIDI_OUT.mkdir(parents=True, exist_ok=True)
    letters = sorted({m[0].lower() for m in want.values() if m[:1].isalpha()})
    print(f"downloading {len(letters)} MIDI archives: {letters}")
    for i, ltr in enumerate(letters):
        if download(MID_URL.format(letter=ltr), CACHE / f"tch-mid{ltr}.7z"):
            with py7zr.SevenZipFile(CACHE / f"tch-mid{ltr}.7z", "r") as z:
                z.extractall(MIDI_OUT)
        if i < len(letters) - 1:
            time.sleep(DOWNLOAD_GAP_S)

    # Index every extracted MIDI by lowercased basename.
    midi_paths: Dict[str, Path] = {}
    for p in MIDI_OUT.rglob("*.mid"):
        midi_paths.setdefault(p.stem.lower(), p)

    copied = missing = 0
    for slug, midi in want.items():
        src = midi_paths.get(midi.lower())
        if not src:
            missing += 1
            continue
        shutil.copyfile(src, AUDIO_DIR / f"{slug}.mid")
        copied += 1
    print(f"\ncopied {copied} MIDIs into audio/   (matched-but-missing-file: {missing})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
