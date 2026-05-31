#!/usr/bin/env python3
"""Build hymns.json + populate audio/ from openhymnal.org sources.

Inputs:
    tools/alllyrics.html  (downloaded from http://openhymnal.org/alllyrics.html)
    tools/midi/*.mid      (extracted from OpenHymnal2014.06-midi.zip)

Outputs:
    hymnal/data/hymns.json
    audio/<slug>.mid
"""
from __future__ import annotations

import html
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
LYRICS_HTML = TOOLS / "alllyrics.html"
MIDI_DIR = TOOLS / "midi"
OUT_JSON = ROOT / "hymnal" / "data" / "hymns.json"
AUDIO_DIR = ROOT / "audio"


def slugify(s: str) -> str:
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


def clean_text(s: str) -> str:
    s = html.unescape(s)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def split_lines(verse: str) -> List[str]:
    """Split a verse into projector-friendly lines.

    openhymnal's alllyrics.html flattens hymn lines into a single paragraph,
    keeping the original punctuation. We split only on STRONG boundaries
    (`.`, `;`, `!`, `?`) followed by a capital letter — commas are not
    reliable (vocative "Abide, O dearest Jesus" has internal commas).
    The display window word-wraps within each returned line.
    """
    verse = re.sub(r"\s+", " ", verse).strip()
    if not verse:
        return []
    parts = re.split(r'(?<=[.;!?])\s+(?=["\'(]*[A-Z])', verse)
    cleaned = [p.strip() for p in parts if p.strip()]
    return cleaned or [verse]


FIELD_BOUNDARY = re.compile(
    r"(?:\.\s+(?=(?:Words?|Music|Setting|Translation|copyright|Translator)\b)"
    r"|\.\s*$"
    r"|$)",
    re.I,
)


def _extract_field(text: str, label: str) -> str:
    """Grab the content of `Label: ...` until the next field label or end-of-text."""
    m = re.search(
        rf"\b{label}s?:\s*(.+?)"
        r"(?=\s+(?:Words?|Music|Setting|Translation|Translator|copyright)\s*:|$)",
        text,
        re.I,
    )
    if not m:
        return ""
    val = m.group(1).strip()
    return val.rstrip(".").strip()


def parse_credits(credit_html: str) -> Dict[str, object]:
    text = clean_text(credit_html)
    result: Dict[str, object] = {
        "author": "",
        "composer": "",
        "tune": "",
        "year": 0,
        "copyright": "",
    }

    words_field = _extract_field(text, "Word")
    if words_field:
        author = re.sub(
            r",?\s*\b(circa|c\.|ca\.)?\s*1[0-9]{3}\b.*$", "", words_field, flags=re.I
        ).strip().rstrip(",")
        result["author"] = author
        ym = re.search(r"\b(1[0-9]{3})\b", words_field)
        if ym:
            result["year"] = int(ym.group(1))

    music_field = _extract_field(text, "Music")
    if music_field:
        tm = re.search(r"['\"]([^'\"]+)['\"]", music_field)
        if tm:
            result["tune"] = tm.group(1).strip()
        # Composer = music field with tune quote and year stripped
        composer = re.sub(r"['\"][^'\"]+['\"]", "", music_field)
        composer = re.sub(
            r",?\s*\b(circa|c\.|ca\.)?\s*1[0-9]{3}\b.*$", "", composer, flags=re.I
        ).strip().rstrip(",")
        result["composer"] = composer
        if not result["year"]:
            ym = re.search(r"\b(1[0-9]{3})\b", music_field)
            if ym:
                result["year"] = int(ym.group(1))

    cm = re.search(r"copyright:\s*([^.]+)", text, re.I)
    if cm:
        result["copyright"] = cm.group(1).strip().lower()

    return result


def parse_hymns(html_text: str) -> List[Dict]:
    blocks = re.split(r"<hr\s*/?>", html_text, flags=re.I)
    hymns: List[Dict] = []
    seen: set = set()
    for blk in blocks:
        m = re.search(r"<h3>(.*?)</h3>", blk, re.S | re.I)
        if not m:
            continue
        title_raw = clean_text(m.group(1))
        title = re.sub(r"\(also known as.*?\)\s*$", "", title_raw, flags=re.I).strip()
        title = re.sub(r"\s+", " ", title).strip()
        slug = slugify(title)
        if not slug or slug in seen:
            continue

        verses: List[Dict] = []
        for vm in re.finditer(r"<p>\s*(\d+)\.\s*(.+?)</p>", blk, re.S | re.I):
            num = int(vm.group(1))
            text = clean_text(vm.group(2))
            lines = split_lines(text)
            if lines:
                verses.append({"label": f"Verse {num}", "lines": lines})
        if not verses:
            continue

        cm = re.search(r"<p>\s*<i>(.+?)</i>\s*</p>", blk, re.S | re.I)
        credits = parse_credits(cm.group(1)) if cm else {}

        copyright_str = str(credits.get("copyright", "")).lower()
        if copyright_str and "public domain" not in copyright_str:
            continue

        seen.add(slug)
        hymns.append({
            "id": slug,
            "title": title,
            "author": credits.get("author") or "Unknown",
            "composer": credits.get("composer", ""),
            "tune": credits.get("tune", ""),
            "year": credits.get("year", 0),
            "copyright": credits.get("copyright") or "public domain",
            "source": "openhymnal.org",
            "verses": verses,
        })
    return hymns


def normalize_for_match(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", s).lower()


def midi_for(title: str, midi_files: List[Path]) -> Optional[Path]:
    expected = normalize_for_match(title)
    if not expected:
        return None
    fallback: Optional[Path] = None
    for mf in midi_files:
        prefix = mf.stem.split("-", 1)[0]
        norm = normalize_for_match(prefix)
        if norm == expected:
            return mf
        if (norm.startswith(expected) or expected.startswith(norm)) and fallback is None:
            fallback = mf
    return fallback


def main() -> int:
    if not LYRICS_HTML.exists():
        print(f"missing: {LYRICS_HTML}", file=sys.stderr)
        return 1
    if not MIDI_DIR.exists():
        print(f"missing: {MIDI_DIR}", file=sys.stderr)
        return 1

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    html_text = LYRICS_HTML.read_text(encoding="utf-8", errors="replace")
    hymns = parse_hymns(html_text)
    print(f"parsed {len(hymns)} hymns")

    midi_files = sorted(MIDI_DIR.rglob("*.mid"))
    print(f"found {len(midi_files)} MIDI files")

    matched = 0
    unmatched_titles: List[str] = []
    for h in hymns:
        mf = midi_for(h["title"], midi_files)
        if mf:
            dest = AUDIO_DIR / f"{h['id']}.mid"
            shutil.copyfile(mf, dest)
            h["audio"] = dest.name
            matched += 1
        else:
            h["audio"] = None
            unmatched_titles.append(h["title"])
    print(f"audio matched: {matched}/{len(hymns)}")
    if unmatched_titles[:10]:
        print("unmatched sample:")
        for t in unmatched_titles[:10]:
            print(f"  - {t}")

    payload = {
        "version": 1,
        "source": "Open Hymnal Project (openhymnal.org)",
        "license": "All hymns included are public domain in the United States.",
        "hymns": hymns,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT_JSON}  ({OUT_JSON.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
