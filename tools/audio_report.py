#!/usr/bin/env python3
"""Print audio coverage report for the hymn library."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HYMNS = ROOT / "hymnal" / "data" / "hymns.json"
AUDIO = ROOT / "audio"


def main() -> int:
    data = json.loads(HYMNS.read_text(encoding="utf-8"))
    hymns = data["hymns"]

    famous = [
        "Amazing Grace", "Holy, Holy, Holy", "Rock of Ages", "It Is Well",
        "Blessed Assurance", "Old Rugged Cross", "Just As I Am",
        "What a Friend We Have", "Silent Night", "O Come, All Ye Faithful",
        "Joy to the World", "Hark the Herald", "When I Survey",
        "Onward, Christian", "Crown Him With Many", "Be Thou My Vision",
        "Mighty Fortress", "In the Garden",
    ]

    print(f'{"hymn":<48} {"slug":<42} audio')
    print("-" * 110)
    for term in famous:
        matches = [h for h in hymns if term.lower() in h["title"].lower()]
        for h in matches[:1]:
            mp3 = (AUDIO / f'{h["id"]}.mp3').exists()
            mid = (AUDIO / f'{h["id"]}.mid').exists()
            tag = "MP3" if mp3 else ("MID" if mid else "---")
            print(f'{h["title"][:47]:<48} {h["id"][:41]:<42} {tag}')

    n_mp3 = sum(1 for h in hymns if (AUDIO / f'{h["id"]}.mp3').exists())
    n_mid_only = sum(
        1 for h in hymns
        if not (AUDIO / f'{h["id"]}.mp3').exists()
        and (AUDIO / f'{h["id"]}.mid').exists()
    )
    n_none = sum(
        1 for h in hymns
        if not (AUDIO / f'{h["id"]}.mp3').exists()
        and not (AUDIO / f'{h["id"]}.mid').exists()
    )
    print()
    print(f"COVERAGE: {n_mp3} MP3  +  {n_mid_only} MIDI-only  +  {n_none} no audio  =  {len(hymns)} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
