#!/usr/bin/env python3
"""Sync each hymn's "audio" field in hymns.json to what's actually in audio/.

Playback resolves audio by file presence, but the library's ♪ indicator reads
the per-hymn "audio" field. After dropping in new audio (e.g. the MIDI
backfill), run this so the indicator and metadata match reality. MP3/OGG/etc.
are preferred over MIDI, matching the app's own resolver order.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HYMNS_JSON = ROOT / "hymnal" / "data" / "hymns.json"
AUDIO_DIR = ROOT / "audio"
EXTS = (".mp3", ".ogg", ".m4a", ".wav", ".flac", ".mid", ".midi")


def resolve(slug: str) -> str | None:
    for ext in EXTS:
        if (AUDIO_DIR / f"{slug}{ext}").exists():
            return f"{slug}{ext}"
    return None


def main() -> int:
    payload = json.loads(HYMNS_JSON.read_text(encoding="utf-8"))
    changed = with_audio = 0
    for h in payload["hymns"]:
        found = resolve(h["id"])
        if found:
            with_audio += 1
        if h.get("audio") != found:
            h["audio"] = found
            changed += 1
    HYMNS_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    total = len(payload["hymns"])
    print(f"hymns: {total} | with audio: {with_audio} | fields updated: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
