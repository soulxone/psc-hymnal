#!/usr/bin/env python3
"""Import public-domain hymns from Project Gutenberg hymnals into hymns.json.

Project Gutenberg texts are public domain in the United States and may be
freely redistributed. We extract ONLY the public-domain hymn text (title,
verses, author, meter) — never Gutenberg's boilerplate — and tag each hymn
with its source book.

These hymnals share a consistent, semantic HTML structure:

    <div class="hymn" id="hNNNN">           (or  <div id="hNNN" title="…">)
        <h3>NNN. <span class="meter">…</span> <span class="sc">Author</span></h3>
        <div class="verse">
            <p class="t"><span class="vn">1</span>First line…</p>   (or <div class="t">)
            <div class="l">Indented line…</div>
        </div>
        …

Merge-only: existing hymns in hymns.json are preserved untouched; new hymns
(deduped by slug) are appended. Re-running is idempotent.

Usage:
    py tools/import_gutenberg.py --dry-run      # parse + report, write nothing
    py tools/import_gutenberg.py                # parse + merge into hymns.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup  # type: ignore

ROOT = Path(__file__).resolve().parent.parent
HYMNS_JSON = ROOT / "hymnal" / "data" / "hymns.json"
CACHE_DIR = ROOT / "tools" / "gutenberg"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36"

# Public-domain hymnals to import. All comfortably pre-1929 → PD in the US.
BOOKS = [
    {"id": 20476, "title": "Hymns for Christian Devotion", "year": 1846},
    {"id": 33180, "title": "A Book of Hymns for Public and Private Devotion", "year": 1846},
]

URL_TEMPLATES = [
    "https://www.gutenberg.org/cache/epub/{id}/pg{id}.html",
    "https://www.gutenberg.org/files/{id}/{id}-h/{id}-h.htm",
]

VN_RE = re.compile(r"^\s*\d+\s*")
AUTHOR_CLASSES = ("sc", "author", "auth", "byline", "attribution")


def slugify(s: str) -> str:
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def fetch_book(book: Dict) -> Optional[str]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"pg{book['id']}.html"
    if cache.exists() and cache.stat().st_size > 10_000:
        print(f"  (cached) {cache.name}")
        return cache.read_text(encoding="utf-8", errors="replace")
    for tmpl in URL_TEMPLATES:
        url = tmpl.format(id=book["id"])
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read().decode("utf-8", errors="replace")
            cache.write_text(data, encoding="utf-8")
            print(f"  downloaded {url} ({len(data):,} bytes)")
            return data
        except Exception as e:  # noqa: BLE001
            print(f"  miss {url}: {e}")
    return None


def extract_verses(hymn_div) -> List[Dict]:
    verses: List[Dict] = []
    for i, vd in enumerate(hymn_div.find_all("div", class_="verse"), 1):
        lines: List[str] = []
        for el in vd.find_all(["p", "div"], recursive=False):
            if "pb" in (el.get("class") or []):  # page-break marker
                continue
            txt = clean(el.get_text(" ", strip=True))
            if txt:
                lines.append(txt)
        if lines:
            lines[0] = clean(VN_RE.sub("", lines[0]))
            lines = [ln for ln in lines if ln]
        if lines:
            verses.append({"label": f"Verse {i}", "lines": lines})
    return verses


def extract_author(hymn_div) -> str:
    for cls in AUTHOR_CLASSES:
        el = hymn_div.find(class_=cls)
        if el:
            a = clean(el.get_text(" ", strip=True)).strip(".").strip()
            if a and not re.fullmatch(r"[\d.\s]+", a):
                return a
    return "Unknown"


def title_from(verses: List[Dict]) -> str:
    if not verses or not verses[0]["lines"]:
        return ""
    return verses[0]["lines"][0].strip().rstrip(",;:.!?—- ").strip()


def parse_book(html: str, book: Dict) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[Dict] = []
    for hd in soup.find_all("div", id=re.compile(r"^h\d+$")):
        verses = extract_verses(hd)
        if not verses:
            continue
        title = title_from(verses)
        if len(title) < 3:
            continue
        meter_el = hd.find(class_="meter")
        out.append({
            "id": slugify(title),
            "title": title,
            "author": extract_author(hd),
            "composer": "",
            "tune": "",
            "meter": clean(meter_el.get_text(" ", strip=True)) if meter_el else "",
            "year": book["year"],
            "copyright": "public domain",
            "source": f"Project Gutenberg #{book['id']} - {book['title']}",
            "verses": verses,
            "audio": None,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="parse + report, write nothing")
    args = ap.parse_args()

    try:  # Windows consoles default to cp1252 and choke on em-dashes etc.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if not HYMNS_JSON.exists():
        print(f"missing {HYMNS_JSON}", file=sys.stderr)
        return 1
    payload = json.loads(HYMNS_JSON.read_text(encoding="utf-8"))
    existing: List[Dict] = payload["hymns"]
    seen = {h["id"] for h in existing}
    print(f"existing hymns: {len(existing)}")

    added: List[Dict] = []
    for book in BOOKS:
        print(f"\n[{book['id']}] {book['title']}")
        html = fetch_book(book)
        if not html:
            print("  FAILED to fetch; skipping")
            continue
        parsed = parse_book(html, book)
        kept = dup = 0
        for h in parsed:
            if not h["id"] or h["id"] in seen:
                dup += 1
                continue
            seen.add(h["id"])
            added.append(h)
            kept += 1
        print(f"  parsed {len(parsed)} candidates -> added {kept}, skipped {dup} (dupe/blank)")

    print(f"\nNEW: {len(added)}   library: {len(existing)} -> {len(existing) + len(added)}")

    if args.dry_run:
        print("\n--- sample of new hymns ---")
        for h in added[:4]:
            print(f"\n* {h['title']}  [{h['author']} | {h['meter']}]  ({h['source']})")
            for v in h["verses"][:1]:
                for ln in v["lines"]:
                    print(f"    {ln}")
        return 0

    payload["hymns"] = existing + added
    payload["sources"] = sorted({h.get("source", "") for h in payload["hymns"] if h.get("source")})
    HYMNS_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {HYMNS_JSON} ({HYMNS_JSON.stat().st_size:,} bytes, {len(payload['hymns'])} hymns)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
