#!/usr/bin/env python3
"""Read a sheet-music PDF/image and turn it into a playable piano track.

Pipeline:
    PDF -> page image (PyMuPDF) -> OMR (oemer) -> MusicXML
        -> MIDI (music21, forced to Piano) -> piano WAV/MP3 (FluidSynth + soundfont)

Optionally (--add) registers the result as a hymn so the app can play it.

This is a *content-prep* tool. Its heavy ML deps (oemer, onnxruntime, music21)
live in the separate `.venv_omr` and are NEVER bundled into the shipped app —
the app just plays the resulting audio like any other hymn. Run it with that
interpreter:

    .venv_omr\\Scripts\\python.exe tools\\import_sheet_music.py SCORE.pdf --mp3 --add

Optical Music Recognition is approximate; clean engraved scores work best.
Always listen to the result before trusting it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
AUDIO_DIR = ROOT / "audio"
HYMNS_JSON = ROOT / "hymnal" / "data" / "hymns.json"
sys.path.insert(0, str(TOOLS))


def slugify(s: str) -> str:
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


# --------------------------------------------------------------- PDF handling
def render_pdf(pdf: Path, out_png: Path, dpi: int = 300) -> Path:
    import fitz  # PyMuPDF
    doc = fitz.open(str(pdf))
    doc[0].get_pixmap(dpi=dpi).save(str(out_png))
    return out_png


def extract_metadata(pdf: Path) -> Dict[str, str]:
    """Title (largest-font text), plus a public-domain flag, from the text layer."""
    import fitz
    doc = fitz.open(str(pdf))
    page = doc[0]
    full = page.get_text()
    biggest_size, biggest_text = 0.0, ""
    try:
        for blk in page.get_text("dict")["blocks"]:
            for line in blk.get("lines", []):
                for span in line.get("spans", []):
                    txt = span["text"].strip()
                    if len(txt) >= 4 and span["size"] > biggest_size and not txt.lower().startswith(("text:", "tune:", "www")):
                        biggest_size, biggest_text = span["size"], txt
    except Exception:
        pass
    title = re.sub(r"\s+", " ", biggest_text).strip(" -—–")
    return {
        "title": title,
        "public_domain": "public domain" in full.lower(),
        "raw_text": full,
    }


# ------------------------------------------------------------------------ OMR
def run_oemer(img: Path, out_dir: Path, timeout: int = 2400) -> Optional[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    oemer = Path(sys.executable).with_name("oemer.exe")
    cmd = [str(oemer)] if oemer.exists() else [sys.executable, "-m", "oemer.ete"]
    env = dict(os.environ, ORT_DISABLE_TENSORRT="1")
    # oemer is very chatty; stream its output to a log file rather than
    # buffering ~MBs of progress bars in memory, and give CPU inference room.
    log = out_dir / f"{img.stem}.oemer.log"
    print(f"  running OMR (oemer) on CPU — can take 10-15 min. log: {log}")
    with open(log, "w", encoding="utf-8", errors="replace") as lf:
        try:
            subprocess.run(cmd + [str(img), "-o", str(out_dir)], env=env,
                           stdout=lf, stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired:
            print(f"  oemer timed out after {timeout}s (see {log})")
            return None
    xml = out_dir / f"{img.stem}.musicxml"
    if xml.exists():
        return xml
    print(f"  oemer produced no MusicXML — see {log}")
    return None


def musicxml_to_midi(xml: Path, midi: Path, tempo_bpm: int = 96,
                     gap_threshold: float = 8.0) -> Dict[str, object]:
    """Convert OMR MusicXML to a playable piano MIDI.

    oemer often gets note *pitches/durations* right but mangles the measure
    timeline — scattering notes across huge offset gaps (a single hymn came out
    48 minutes long). We rebuild the timeline: keep each note's duration and the
    small offsets *within* a phrase (so chords stay together), but collapse the
    large artifact gaps *between* phrases so the piece plays continuously.
    """
    import copy
    import warnings
    from music21 import converter, instrument, stream, tempo
    warnings.filterwarnings("ignore")

    score = converter.parse(str(xml))
    notes = sorted(score.flatten().notes, key=lambda n: float(n.offset))

    part = stream.Part()
    part.insert(0, instrument.Piano())          # GM program 0 — acoustic grand
    part.insert(0, tempo.MetronomeMark(number=tempo_bpm))

    shift = 0.0
    prev = None
    for n in notes:
        off = float(n.offset)
        if prev is not None:
            gap = off - float(prev.offset)
            if gap > gap_threshold:             # oemer measure-offset artifact
                desired = min(float(prev.quarterLength) or 1.0, 2.0)
                shift += gap - desired
        part.insert(off - shift, copy.deepcopy(n))
        prev = n

    out = stream.Score()
    out.insert(0, part)
    out.write("midi", fp=str(midi))
    pitches = sorted({(n.pitches[0].name if n.isChord else n.name) for n in notes})
    return {"notes": len(notes), "pitch_classes": pitches,
            "length_ql": round(float(part.highestTime), 1)}


# -------------------------------------------------------------- piano render
def render_piano_audio(midi: Path, dest_stem: Path) -> Optional[Path]:
    """MIDI -> .mp3 (or .wav) via FluidSynth + soundfont in tools/. None if unavailable."""
    try:
        from midi_to_audio import (find_fluidsynth, find_soundfont, find_ffmpeg,
                                    render_midi_to_wav, encode_with_ffmpeg)
    except Exception as e:
        print(f"  (skip audio render: {e})")
        return None
    fs, sf = find_fluidsynth(), find_soundfont()
    if not fs or not sf:
        print("  (skip audio render: FluidSynth or soundfont not found in tools/)")
        return None
    ffmpeg = find_ffmpeg()
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "out.wav"
        if not render_midi_to_wav(fs, sf, midi, wav):
            print("  (FluidSynth render failed)")
            return None
        if ffmpeg:
            dest = dest_stem.with_suffix(".mp3")
            if encode_with_ffmpeg(ffmpeg, wav, dest):
                return dest
        dest = dest_stem.with_suffix(".wav")
        import shutil
        shutil.copyfile(wav, dest)
        return dest


# -------------------------------------------------------------- identify/add
def identify(title: str) -> Optional[Dict]:
    if not HYMNS_JSON.exists() or not title:
        return None
    hymns = json.loads(HYMNS_JSON.read_text(encoding="utf-8"))["hymns"]
    key = _norm(title)
    for h in hymns:
        if _norm(h["title"]) == key or _norm(h["title"]).startswith(key) or key.startswith(_norm(h["title"])):
            return h
    return None


def add_to_library(slug: str, title: str, meta: Dict, audio_name: Optional[str]) -> str:
    payload = json.loads(HYMNS_JSON.read_text(encoding="utf-8"))
    hymns = payload["hymns"]
    if any(h["id"] == slug for h in hymns):
        return f"'{slug}' already in library — not duplicated"
    hymns.append({
        "id": slug,
        "title": title,
        "author": "Unknown",
        "composer": "",
        "tune": "",
        "year": 0,
        "copyright": "public domain" if meta.get("public_domain") else "unknown",
        "source": f"Sheet music (OMR): {meta.get('source_file', '')}",
        "verses": [{"label": "Transcribed", "lines": [
            title, "(audio transcribed from sheet music — verify accuracy)"]}],
        "audio": audio_name,
    })
    payload["hymns"] = hymns
    HYMNS_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return f"added '{slug}' to library ({len(hymns)} hymns)"


# ------------------------------------------------------------------------ CLI
def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="sheet-music PDF or image (png/jpg)")
    ap.add_argument("--mp3", action="store_true", help="also render piano MP3/WAV via FluidSynth")
    ap.add_argument("--add", action="store_true", help="register as a playable hymn in hymns.json + audio/")
    ap.add_argument("--title", default="", help="override the auto-detected title")
    ap.add_argument("-o", "--outdir", default=str(TOOLS / "sheet_music_out"),
                    help="where to write .musicxml/.mid (default tools/sheet_music_out)")
    ap.add_argument("--emit-json", default="",
                    help="write a small JSON result file (for the app to consume)")
    ap.add_argument("--tempo", type=int, default=96,
                    help="playback tempo in BPM for the transcription (default 96)")
    args = ap.parse_args()

    src = Path(args.source).resolve()
    if not src.exists():
        print(f"not found: {src}", file=sys.stderr)
        return 1
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # 1. metadata + page image
    meta: Dict[str, object] = {"title": "", "public_domain": False, "source_file": src.name}
    if src.suffix.lower() == ".pdf":
        print(f"[1/4] reading PDF: {src.name}")
        meta.update(extract_metadata(src))
        img = render_pdf(src, outdir / f"{src.stem}.png")
    else:
        print(f"[1/4] image: {src.name}")
        img = src
    title = args.title or str(meta.get("title") or "") or src.stem
    meta["source_file"] = src.name
    print(f"      title: {title!r}   public-domain text: {meta.get('public_domain')}")

    known = identify(title)
    if known:
        print(f"      ↳ matches a hymn already in the library: '{known['id']}'"
              f" (has audio: {bool(known.get('audio'))})")

    # 2. OMR -> MusicXML
    print("[2/4] optical music recognition")
    xml = run_oemer(img, outdir)
    if not xml:
        return 2

    # 3. MusicXML -> piano MIDI
    print("[3/4] MusicXML -> piano MIDI")
    midi = outdir / f"{src.stem}.mid"
    stats = musicxml_to_midi(xml, midi, tempo_bpm=args.tempo)
    print(f"      {stats['notes']} notes, pitch classes {stats['pitch_classes']}")
    print(f"      wrote {midi}")

    # 4. optional piano audio render
    audio_path: Optional[Path] = None
    if args.mp3:
        print("[4/4] rendering piano audio (FluidSynth + soundfont)")
        audio_path = render_piano_audio(midi, outdir / src.stem)
        if audio_path:
            print(f"      wrote {audio_path} ({audio_path.stat().st_size // 1024} KB)")
    else:
        print("[4/4] (skipped audio render; pass --mp3 for a piano recording)")

    # optional: register as a playable hymn
    if args.add:
        slug = slugify(title) or src.stem
        chosen = audio_path or midi
        dest_audio = AUDIO_DIR / f"{slug}{chosen.suffix}"
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copyfile(chosen, dest_audio)
        msg = add_to_library(slug, title, meta, dest_audio.name)
        print(f"[add] copied audio -> {dest_audio.name}; {msg}")

    if args.emit_json:
        Path(args.emit_json).write_text(json.dumps({
            "title": title,
            "identified_id": known["id"] if known else None,
            "public_domain": bool(meta.get("public_domain")),
            "midi": str(midi),
            "audio": str(audio_path) if audio_path else None,
        }, indent=2), encoding="utf-8")
        print(f"[json] wrote {args.emit_json}")

    print("\nDone. OMR is approximate — open the MIDI/MP3 and verify before use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
