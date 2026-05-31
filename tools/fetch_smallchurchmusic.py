#!/usr/bin/env python3
"""Download piano-variant MP3s from SmallChurchMusic.com for our hymn library.

SmallChurchMusic.com hosts ~15,000 freely-downloadable public-domain hymn
recordings (performance copyright assigned by Rev. Clyde McLennan to
Hymnary.org, non-commercial use permitted).

This script:
  1. Crawls SCM's alphabetical first-line index (26 pages, A-Z) to build
     a {normalized_title: SID} map of every hymn on the site.
  2. For each hymn in our hymns.json, looks up a matching SID.
  3. Fetches the song-detail page for matched SIDs.
  4. Picks the best piano MP3 (prefer "-SPiano-" filenames at 128kbps).
  5. Downloads to audio/<id>.mp3, overwriting any existing file.

Idempotent: re-running re-downloads (use --skip-existing to skip files
that already exist).

Polite: 0.3s delay between requests.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
HYMNS_JSON = ROOT / "hymnal" / "data" / "hymns.json"
AUDIO_DIR = ROOT / "audio"
SCM_BASE = "https://smallchurchmusic.com/"
SCM_ALPHA = SCM_BASE + "FirstLine_List-New.php?LT={letter}"
SCM_DETAIL = SCM_BASE + "Song_Display-New.php?SID={sid}"
USER_AGENT = "PSC-Hymnal-Fetcher/1.0 (church use, contact: ps-church.com)"
REQUEST_DELAY_S = 0.3

# Regex: Song_Display-New.php?SID=NNN'><small>Title</a>  (extra <small> wrapping is common)
RE_INDEX = re.compile(
    r"Song_Display-New\.php\?SID=([\d\^]+)['\"]\s*>(.+?)</a>",
    re.I | re.S,
)
RE_TAG_STRIP = re.compile(r"<[^>]+>")
# MP3 URL pattern on a song-detail page (may be relative or absolute path)
RE_MP3 = re.compile(
    r'["\']((?:https?://[^"\']*?|/[^"\']*?|(?:[A-Za-z][\w-]*/)+)[^"\']*?\.mp3)["\']',
    re.I,
)


def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def http_get_text(url: str, timeout: int = 30) -> str:
    return http_get(url, timeout).decode("utf-8", errors="replace")


def normalize(s: str) -> str:
    """Lowercase, alphanumeric only — for fuzzy title matching."""
    s = re.sub(r"&[a-z]+;", " ", s, flags=re.I)  # strip HTML entities
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def build_scm_index(verbose: bool = True) -> Dict[str, str]:
    """Crawl A-Z pages and return {normalized_title: best_SID}."""
    index: Dict[str, str] = {}
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        url = SCM_ALPHA.format(letter=letter)
        if verbose:
            print(f"  [SCM] crawling {letter}…", end=" ", flush=True)
        try:
            html = http_get_text(url)
        except Exception as e:
            if verbose:
                print(f"FAIL ({e})")
            continue
        count = 0
        for m in RE_INDEX.finditer(html):
            sid_raw = m.group(1)
            sid = sid_raw.split("^", 1)[0]  # primary SID if compound
            raw_title = RE_TAG_STRIP.sub(" ", m.group(2))
            title = re.sub(r"\s+", " ", raw_title).strip().rstrip(",")
            key = normalize(title)
            if not key:
                continue
            # Keep first SID encountered for a given title key
            index.setdefault(key, sid)
            count += 1
        if verbose:
            print(f"{count} entries")
        time.sleep(REQUEST_DELAY_S)
    return index


def extract_piano_mp3(detail_html: str) -> Optional[str]:
    """Return the best piano MP3 path from a song-detail page, or None."""
    urls = list({u for u in RE_MP3.findall(detail_html)})
    if not urls:
        return None
    # exclude short "Snippet" preview clips and BMidi (synth-rendered) tracks
    real = [u for u in urls if "/Snippet/" not in u and "Snippet-" not in u
            and re.search(r"snippet/", u, re.I) is None]
    if not real:
        real = urls

    def score(u: str) -> Tuple[int, int]:
        """Higher score = better match. (kind, bitrate)"""
        name = u.lower()
        # priority bands
        if "-spiano-" in name:
            kind = 100
        elif "-piano-" in name and "small" not in name:
            kind = 80
        elif "spiano" in name:
            kind = 70
        elif "-piano" in name or "piano-" in name:
            kind = 60
        else:
            kind = 0
        # bitrate preference 128 > 64 > 48
        br_match = re.search(r"-(\d{2,3})-", name)
        br = int(br_match.group(1)) if br_match else 0
        return (kind, br)

    real.sort(key=score, reverse=True)
    best = real[0]
    if score(best)[0] == 0:
        return None  # no piano variant found at all
    return best


def absolutize(path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    if path.startswith("/"):
        return urllib.parse.urljoin(SCM_BASE, path)
    return urllib.parse.urljoin(SCM_BASE, "/" + path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip hymns whose audio/<id>.mp3 already exists")
    parser.add_argument("--limit", type=int, default=0,
                        help="Only process the first N matched hymns (for testing)")
    parser.add_argument("--only", metavar="SLUG", default="",
                        help="Process only the hymn with this id (debug)")
    args = parser.parse_args()

    if not HYMNS_JSON.exists():
        print(f"missing: {HYMNS_JSON} — run build_library.py first", file=sys.stderr)
        return 1
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    payload = json.loads(HYMNS_JSON.read_text(encoding="utf-8"))
    hymns: List[Dict] = payload["hymns"]
    if args.only:
        hymns = [h for h in hymns if h["id"] == args.only]
        if not hymns:
            print(f"no hymn with id={args.only}", file=sys.stderr)
            return 1

    print(f"Step 1/3 — building SCM index (26 alpha pages, ~10s)…")
    scm = build_scm_index()
    print(f"           {len(scm)} unique hymn titles on SCM\n")

    print(f"Step 2/3 — matching our {len(hymns)} hymns to SCM…")
    matched: List[Tuple[Dict, str]] = []
    for h in hymns:
        key = normalize(h["title"])
        sid = scm.get(key)
        if not sid:
            # try fallback: first few words
            for scm_key, scm_sid in scm.items():
                if scm_key.startswith(key) or key.startswith(scm_key):
                    if abs(len(scm_key) - len(key)) <= 8:
                        sid = scm_sid
                        break
        if sid:
            matched.append((h, sid))
    print(f"           {len(matched)}/{len(hymns)} matched\n")

    if args.limit:
        matched = matched[: args.limit]

    print(f"Step 3/3 — downloading piano MP3s…")
    downloaded = 0
    no_piano = 0
    failed = 0
    skipped = 0
    for i, (h, sid) in enumerate(matched, 1):
        slug = h["id"]
        dest = AUDIO_DIR / f"{slug}.mp3"
        if args.skip_existing and dest.exists():
            skipped += 1
            continue
        try:
            detail = http_get_text(SCM_DETAIL.format(sid=sid))
        except Exception as e:
            print(f"  [{i:>3}/{len(matched)}] {slug}  detail FAIL: {e}")
            failed += 1
            time.sleep(REQUEST_DELAY_S)
            continue
        mp3_rel = extract_piano_mp3(detail)
        if not mp3_rel:
            print(f"  [{i:>3}/{len(matched)}] {slug}  (no piano variant)")
            no_piano += 1
            time.sleep(REQUEST_DELAY_S)
            continue
        mp3_url = absolutize(mp3_rel)
        try:
            data = http_get(mp3_url, timeout=60)
            if len(data) < 5_000:
                raise RuntimeError(f"only {len(data)} bytes")
            dest.write_bytes(data)
            downloaded += 1
            kb = len(data) // 1024
            print(f"  [{i:>3}/{len(matched)}] {slug}  OK ({kb} KB)")
        except Exception as e:
            print(f"  [{i:>3}/{len(matched)}] {slug}  download FAIL: {e}")
            failed += 1
        time.sleep(REQUEST_DELAY_S)

    print()
    print(f"Downloaded: {downloaded}")
    print(f"No piano variant on SCM: {no_piano}")
    print(f"Skipped (already exists): {skipped}")
    print(f"Failed: {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
