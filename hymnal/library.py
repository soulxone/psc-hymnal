"""Hymn library: load, search, and represent public-domain hymns."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class Verse:
    label: str
    lines: List[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass(frozen=True)
class Hymn:
    id: str
    title: str
    author: str
    year: int
    tune: str
    composer: str
    verses: List[Verse]
    audio_filename: Optional[str] = None

    @property
    def display(self) -> str:
        if self.year:
            return f"{self.title}  ({self.year} — {self.author})"
        return f"{self.title}  ({self.author})" if self.author else self.title

    @property
    def has_audio(self) -> bool:
        return bool(self.audio_filename)


class HymnLibrary:
    def __init__(self, json_path: Path):
        self.json_path = Path(json_path)
        self._hymns: List[Hymn] = []
        self.reload()

    def reload(self) -> None:
        raw = json.loads(self.json_path.read_text(encoding="utf-8"))
        hymns: List[Hymn] = []
        for h in raw.get("hymns", []):
            verses = [Verse(label=v["label"], lines=list(v["lines"])) for v in h["verses"]]
            hymns.append(
                Hymn(
                    id=h["id"],
                    title=h["title"],
                    author=h.get("author", "Unknown"),
                    year=int(h.get("year") or 0),
                    tune=h.get("tune", ""),
                    composer=h.get("composer", ""),
                    verses=verses,
                    audio_filename=h.get("audio"),
                )
            )
        hymns.sort(key=lambda x: x.title.lower())
        self._hymns = hymns

    @property
    def hymns(self) -> List[Hymn]:
        return list(self._hymns)

    def get(self, hymn_id: str) -> Optional[Hymn]:
        for h in self._hymns:
            if h.id == hymn_id:
                return h
        return None

    def search(self, query: str) -> List[Hymn]:
        q = query.strip().lower()
        if not q:
            return self.hymns
        results: List[Hymn] = []
        for h in self._hymns:
            if q in h.title.lower() or q in h.author.lower():
                results.append(h)
                continue
            if any(q in line.lower() for v in h.verses for line in v.lines):
                results.append(h)
        return results
