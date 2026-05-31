#!/usr/bin/env python3
"""Convert MIDI fallbacks to OGG/MP3 using FluidSynth + a soundfont.

Renders every audio/<slug>.mid that lacks a corresponding .mp3/.ogg/.wav.
Idempotent — re-runs skip already-rendered files. Safe to interrupt and resume.

Prerequisites (one-time setup):
  1. FluidSynth binary
     Windows: download fluidsynth-X.X.X-win10-x64.zip from
              https://github.com/FluidSynth/fluidsynth/releases/latest
     Either add bin/ to PATH, or unzip into  tools/fluidsynth/
     (script accepts either)

  2. A soundfont (.sf2 or .sf3) — anything works, drop it in tools/.
     Recommended (free, decent organ/piano):
       - GeneralUser GS    (~30MB)  http://schristiancollins.com
       - MuseScore_General (~30MB)  https://musescore.org/en/handbook/4/soundfonts-and-sfz-files
       - TimGM6mb.sf2      (~6MB)   widely mirrored — search "TimGM6mb.sf2"

  3. (optional) ffmpeg on PATH for compact MP3/OGG output. Without it,
     output stays as WAV — still works, just larger files.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
AUDIO_DIR = ROOT / "audio"

# extensions checked to decide "already has audio"
EXISTING_EXTS = (".mp3", ".ogg", ".m4a", ".wav", ".flac")


def find_fluidsynth() -> Optional[str]:
    local = TOOLS / "fluidsynth" / "fluidsynth.exe"
    if local.exists():
        return str(local)
    for bin_dir in TOOLS.glob("fluidsynth*/bin/fluidsynth.exe"):
        return str(bin_dir)
    return shutil.which("fluidsynth")


def find_soundfont() -> Optional[Path]:
    for ext in ("*.sf3", "*.sf2"):
        for p in sorted(TOOLS.rglob(ext)):
            return p
    return None


def find_ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg")


def print_setup() -> None:
    print("""
─────────────────────────────────────────────────────────────────
Setup needed. One-time install:

  1) Get FluidSynth (Windows binary):
     https://github.com/FluidSynth/fluidsynth/releases/latest
     Download fluidsynth-X.X.X-win10-x64.zip
     Either:
       • Unzip and add bin/ to PATH, or
       • Unzip into:  tools/fluidsynth/   (script finds it there too)

  2) Get a SoundFont (.sf2 or .sf3) — pick one:
     • GeneralUser GS   ~30 MB   http://schristiancollins.com
     • MuseScore_General ~30 MB  https://musescore.org/en/handbook/4/soundfonts-and-sfz-files
     • TimGM6mb.sf2      ~6 MB   widely mirrored
     Drop the file anywhere in tools/  (script auto-detects)

  3) (Optional) Install ffmpeg for compact MP3 output:
     winget install ffmpeg
     Without ffmpeg the script produces .wav (works but larger)

Then re-run:
     py tools/midi_to_audio.py
─────────────────────────────────────────────────────────────────
""")


def render_midi_to_wav(fs: str, sf: Path, midi: Path, out_wav: Path) -> bool:
    cmd = [
        fs, "-ni",
        "-F", str(out_wav),
        "-r", "44100",
        "-g", "0.8",
        str(sf), str(midi),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return False
    return r.returncode == 0 and out_wav.exists() and out_wav.stat().st_size > 2048


def encode_with_ffmpeg(ffmpeg: str, src_wav: Path, dest: Path) -> bool:
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", str(src_wav),
        "-codec:a", "libmp3lame" if dest.suffix == ".mp3" else "libvorbis",
        "-q:a", "4",
        str(dest),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return r.returncode == 0 and dest.exists() and dest.stat().st_size > 1024


def main() -> int:
    fs = find_fluidsynth()
    sf = find_soundfont()
    if not fs or not sf:
        if not fs:
            print("[X] FluidSynth not found (looked in PATH and tools/fluidsynth/)")
        if not sf:
            print(f"[X] No .sf2/.sf3 soundfont found under {TOOLS}/")
        print_setup()
        return 1

    ffmpeg = find_ffmpeg()
    print(f"FluidSynth: {fs}")
    print(f"SoundFont:  {sf.name}  ({sf.stat().st_size // 1024} KB)")
    print(f"ffmpeg:     {ffmpeg or '(not found — will keep WAV files)'}")
    print()

    target_ext = ".mp3" if ffmpeg else ".wav"

    midis = sorted(AUDIO_DIR.glob("*.mid"))
    if not midis:
        print(f"no .mid files in {AUDIO_DIR}")
        return 1

    todo: list[Path] = []
    skipped = 0
    for m in midis:
        slug = m.stem
        if any((AUDIO_DIR / f"{slug}{e}").exists() for e in EXISTING_EXTS):
            skipped += 1
            continue
        todo.append(m)

    print(f"{len(midis)} MIDI files in audio/")
    print(f"{skipped} already have richer audio  ·  {len(todo)} to render")
    if not todo:
        print("Nothing to do.")
        return 0
    print()

    rendered = 0
    failed = 0
    with tempfile.TemporaryDirectory(prefix="hymnsynth_") as tmpdir:
        tmp = Path(tmpdir)
        for i, midi in enumerate(todo, 1):
            slug = midi.stem
            tmp_wav = tmp / f"{slug}.wav"
            dest = AUDIO_DIR / f"{slug}{target_ext}"

            print(f"  [{i:>3}/{len(todo)}] {slug}", end=" ... ", flush=True)
            ok = render_midi_to_wav(fs, sf, midi, tmp_wav)
            if not ok:
                print("FAIL (FluidSynth)")
                failed += 1
                continue

            if ffmpeg:
                ok = encode_with_ffmpeg(ffmpeg, tmp_wav, dest)
                if not ok:
                    print("FAIL (ffmpeg)")
                    failed += 1
                    tmp_wav.unlink(missing_ok=True)
                    continue
                tmp_wav.unlink(missing_ok=True)
            else:
                shutil.move(str(tmp_wav), str(dest))

            kb = dest.stat().st_size // 1024
            print(f"OK ({kb} KB)")
            rendered += 1

    print()
    print(f"Rendered: {rendered}   Failed: {failed}   Already had audio: {skipped}")
    if failed and not rendered:
        print_setup()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
