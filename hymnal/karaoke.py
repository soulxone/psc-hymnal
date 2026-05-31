"""Tempo-driven karaoke highlight scheduling.

Maps audio playback time to a current word index, using BPM detected
offline by tools/analyze_tempo.py.

The math is a deliberate approximation — hymns rarely sing 1 word per beat
literally (think melismas and held notes), so the operator can tune via a
0.5×–2.0× speed multiplier. The point is to give a moving cursor that
roughly tracks the tempo of the recording.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


DEFAULT_BPM = 70.0           # fallback when no tempo cache for this audio
SYLLABLES_PER_WORD = 1.4     # average for English hymnody


@dataclass(frozen=True)
class TempoData:
    bpm: float
    duration_s: float

    @classmethod
    def load_for(cls, audio_path: Path) -> Optional["TempoData"]:
        tempo_path = audio_path.with_suffix(".tempo.json")
        if not tempo_path.exists():
            return None
        try:
            d = json.loads(tempo_path.read_text(encoding="utf-8"))
            return cls(
                bpm=float(d.get("bpm", 0)) or DEFAULT_BPM,
                duration_s=float(d.get("duration_s", 0)),
            )
        except Exception:
            return None


def words_per_second(bpm: float, speed_multiplier: float = 1.0) -> float:
    """Convert BPM → words/sec for a hymn-style cadence."""
    bpm = max(20.0, bpm or DEFAULT_BPM)
    return (bpm / 60.0) / SYLLABLES_PER_WORD * max(0.1, speed_multiplier)


class HighlightSchedule:
    """Translates elapsed time into a current word index."""

    def __init__(self, total_words: int, bpm: float, speed_multiplier: float = 1.0):
        self.total_words = max(0, total_words)
        self.bpm = bpm
        self._wps = words_per_second(bpm, speed_multiplier)

    def word_at(self, elapsed_seconds: float) -> int:
        if self.total_words == 0:
            return -1
        idx = int(max(0.0, elapsed_seconds) * self._wps)
        return min(idx, self.total_words - 1)

    def estimated_verse_seconds(self) -> float:
        if self._wps <= 0:
            return 0.0
        return self.total_words / self._wps
