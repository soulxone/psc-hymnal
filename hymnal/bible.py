"""ESV passage fetching via Crossway's official API + on-disk cache.

This module never contains Bible text. Passages are fetched at runtime
using the user's own Crossway API key (free at https://api.esv.org/),
then cached in passages.json for offline reuse.

Crossway free-tier allows ~5000 verse fetches per day per key — plenty
for church use.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ESV_API_URL = "https://api.esv.org/v3/passage/text/"

# Crossway requires this attribution wherever ESV text is displayed.
ESV_ATTRIBUTION = (
    "Scripture quotations are from the ESV® Bible (The Holy Bible, "
    "English Standard Version®), copyright © 2001 by Crossway, "
    "a publishing ministry of Good News Publishers. Used by permission. "
    "All rights reserved."
)


@dataclass
class Passage:
    reference: str       # what the user typed
    canonical: str       # what the API normalized it to
    text: str            # passage text with [N] verse markers
    fetched_at: str      # ISO timestamp

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "Passage":
        return cls(
            reference=d["reference"],
            canonical=d["canonical"],
            text=d["text"],
            fetched_at=d.get("fetched_at", ""),
        )


VERSE_MARKER = re.compile(r"\[(\d+)\]\s*")


def chunk_passage_to_slides(text: str, verses_per_slide: int = 2) -> List[Tuple[str, List[str]]]:
    """Split a passage into projector-friendly slides.

    Returns a list of (label, lines) tuples. Each slide has 1-2 verses by
    default. The label is "v.N" or "v.N-M" if the API returned verse numbers.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    verses: List[Tuple[int, str]] = []
    parts = VERSE_MARKER.split(text)
    if parts[0].strip():
        verses.append((0, parts[0].strip()))
    for i in range(1, len(parts), 2):
        num = int(parts[i])
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if body:
            verses.append((num, body))

    if not verses:
        return [("Passage", [text])]

    slides: List[Tuple[str, List[str]]] = []
    i = 0
    while i < len(verses):
        chunk = verses[i : i + verses_per_slide]
        nums = [n for n, _ in chunk if n > 0]
        if not nums:
            label = "Passage"
        elif len(nums) == 1:
            label = f"v.{nums[0]}"
        else:
            label = f"v.{nums[0]}–{nums[-1]}"
        lines = [body for _, body in chunk]
        slides.append((label, lines))
        i += verses_per_slide
    return slides


class BibleClient:
    """ESV API client with on-disk JSON cache."""

    def __init__(self, cache_path: Path, api_key: Optional[str] = None):
        self.cache_path = Path(cache_path)
        self.api_key = api_key
        self._cache: Dict[str, Passage] = {}
        self._load_cache()

    def set_api_key(self, key: Optional[str]) -> None:
        self.api_key = key.strip() if key else None

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    # ---------------------------------------------------------------- cache
    def _cache_key(self, reference: str) -> str:
        return re.sub(r"\s+", " ", reference).strip().lower()

    def _load_cache(self) -> None:
        if not self.cache_path.exists():
            return
        try:
            raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            return
        for k, v in raw.items():
            try:
                self._cache[k] = Passage.from_dict(v)
            except Exception:
                continue

    def _save_cache(self) -> None:
        try:
            data = {k: v.to_dict() for k, v in self._cache.items()}
            self.cache_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass

    def get_cached(self, reference: str) -> Optional[Passage]:
        return self._cache.get(self._cache_key(reference))

    # ---------------------------------------------------------------- fetch
    def fetch(self, reference: str, force_refresh: bool = False) -> Passage:
        key = self._cache_key(reference)
        if not force_refresh and key in self._cache:
            return self._cache[key]
        if not self.api_key:
            raise RuntimeError(
                "No ESV API key set. Get one at "
                "https://api.esv.org/account/create-application/"
            )

        params = {
            "q": reference,
            "include-passage-references": "false",
            "include-verse-numbers": "true",
            "include-footnotes": "false",
            "include-headings": "false",
            "include-short-copyright": "false",
            "include-passage-horizontal-lines": "false",
            "include-heading-horizontal-lines": "false",
            "indent-poetry": "false",
            "indent-paragraphs": "0",
        }
        url = ESV_API_URL + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url, headers={"Authorization": f"Token {self.api_key}"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            if e.code == 401:
                raise RuntimeError("ESV API rejected the key (HTTP 401). Check your token.")
            raise RuntimeError(f"ESV API error {e.code}: {body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"ESV API connection failed: {e.reason}")

        passages = payload.get("passages") or []
        if not passages or not passages[0].strip():
            raise RuntimeError(f'No passage found for "{reference}".')

        passage = Passage(
            reference=reference,
            canonical=payload.get("canonical", reference) or reference,
            text=passages[0].strip(),
            fetched_at=datetime.now().isoformat(timespec="seconds"),
        )
        self._cache[key] = passage
        self._save_cache()
        return passage
