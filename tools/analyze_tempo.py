#!/usr/bin/env python3
"""Detect BPM for every MP3 in audio/ and cache to audio/<id>.tempo.json.

Idempotent — skips files that already have a tempo file.
Used by the karaoke-highlight feature in the operator window.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "audio"


def analyze(path: Path) -> dict:
    import numpy as np
    import librosa  # heavy import, defer

    y, sr = librosa.load(str(path), sr=22050, mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
    duration = float(len(y)) / sr
    # librosa 0.10+ returns tempo as ndarray; coerce robustly
    bpm = float(np.atleast_1d(np.asarray(tempo)).ravel()[0])
    return {
        "bpm": round(bpm, 2),
        "duration_s": round(duration, 3),
        "beat_count": len(beat_times),
        "beats": [round(t, 4) for t in beat_times],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="Re-analyze even if .tempo.json exists")
    parser.add_argument("--only", default="", metavar="SLUG",
                        help="Process only this one hymn id")
    args = parser.parse_args()

    if not AUDIO_DIR.exists():
        print(f"missing: {AUDIO_DIR}", file=sys.stderr)
        return 1

    mp3s = sorted(AUDIO_DIR.glob("*.mp3"))
    if args.only:
        mp3s = [p for p in mp3s if p.stem == args.only]
        if not mp3s:
            print(f"no audio/{args.only}.mp3", file=sys.stderr)
            return 1

    print(f"Analyzing {len(mp3s)} MP3s …")
    done = 0
    skipped = 0
    failed = 0
    for i, mp3 in enumerate(mp3s, 1):
        out = mp3.with_suffix(".tempo.json")
        if out.exists() and not args.force:
            skipped += 1
            continue
        try:
            info = analyze(mp3)
            out.write_text(json.dumps(info, indent=2), encoding="utf-8")
            done += 1
            if done % 20 == 0:
                print(f"  [{i:>3}/{len(mp3s)}] {mp3.stem}  bpm={info['bpm']}")
        except Exception as e:
            failed += 1
            print(f"  [{i:>3}/{len(mp3s)}] {mp3.stem}  FAIL: {e}")

    print()
    print(f"Analyzed: {done}   Skipped (already done): {skipped}   Failed: {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
