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
    def __init__(self, json_path: Path, user_json_path: Optional[Path] = None):
        self.json_path = Path(json_path)
        # Optional writable per-user library (e.g. songs imported from sheet
        # music). Merged on top of the bundled, read-only library.
        self.user_json_path = Path(user_json_path) if user_json_path else None
        self._hymns: List[Hymn] = []
        self.reload()

    @staticmethod
    def _parse(path: Path) -> List[Hymn]:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        out: List[Hymn] = []
        for h in raw.get("hymns", []):
            verses = [Verse(label=v["label"], lines=list(v["lines"])) for v in h.get("verses", [])]
            out.append(
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
        return out

    def reload(self) -> None:
        hymns = self._parse(self.json_path)
        seen = {h.id for h in hymns}
        if self.user_json_path and self.user_json_path.exists():
            try:
                for h in self._parse(self.user_json_path):
                    if h.id not in seen:
                        hymns.append(h)
                        seen.add(h.id)
            except Exception:
                pass  # never let a bad user file break the bundled library
        hymns.sort(key=lambda x: x.title.lower())
        self._hymns = hymns

    def add_user_hymn(self, entry: dict) -> None:
        """Append (or replace) a hymn in the writable user library, then reload."""
        if not self.user_json_path:
            raise RuntimeError("no user library path configured")
        data = {"hymns": []}
        if self.user_json_path.exists():
            try:
                data = json.loads(self.user_json_path.read_text(encoding="utf-8"))
            except Exception:
                data = {"hymns": []}
        hymns = [h for h in data.get("hymns", []) if h.get("id") != entry.get("id")]
        hymns.append(entry)
        data["hymns"] = hymns
        self.user_json_path.parent.mkdir(parents=True, exist_ok=True)
        self.user_json_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self.reload()

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
