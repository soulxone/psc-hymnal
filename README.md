# PSC Hymnal

Local Python app for projecting public-domain hymn lyrics on a secondary screen
during worship, with optional MIDI/MP3 playback. Sourced from
[The Open Hymnal Project](http://openhymnal.org/).

## What's included

- **308 hymns** with full verse lyrics, parsed from openhymnal.org's
  `alllyrics.html`
- **132 MP3 recordings** from openhymnal.org's Christmas, Easter, and
  Visitation special-edition packs (real instrumentation, not synth)
- **151 MIDI fallbacks** matched from `OpenHymnal2014.06-midi.zip`
  (plays through the OS GM synthesizer — adequate but tinny)
- **25 hymns are lyrics-only** (no audio available from openhymnal yet)
- Operator (control) window + fullscreen lyrics window on a second monitor
- Search by title / author / lyric text
- Service playlist — queue hymns in order, save/load as JSON
- Verse-by-verse advance with keyboard shortcuts

The audio resolver prefers MP3 over MIDI, so dropping any
`audio/<id>.mp3` automatically wins over the bundled MIDI.

All hymns shipped are public domain in the United States.

## Setup

```powershell
# from D:\ps-church_com\hymnal_app
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py run.py
```

## API keys & secrets

This app needs **one** secret — a free **ESV API key** from Crossway — and
only if you want to project Bible passages. Hymn lyrics and audio playback
need no key at all.

**Get your own key (free, ~2 minutes):**

1. Sign up at <https://api.esv.org/account/create-application/>
2. Create an "application" (any name — e.g. "My Church Hymnal")
3. Copy the API token (looks like ~40 hex characters)
4. Launch the app, open **Bible → ESV API Key…**, paste it, click OK

Crossway's free tier allows 5,000 verse fetches/day — ample for worship use.
Your key is sent only to Crossway, never to the maintainers.

**Where your key is stored — and why it's never in this repo:**

Your key is saved locally in `settings.json`, next to your other preferences:

| How you run it | Location of `settings.json`            |
| -------------- | -------------------------------------- |
| Installed app  | `%APPDATA%\PSC Hymnal\settings.json`   |
| From source    | `hymnal_app\settings.json` (this repo) |

> ⚠️ **`settings.json` is listed in `.gitignore` and must never be committed
> or shared** — it holds *your* private key. See
> [`settings.example.json`](settings.example.json) for the key-free format.
> The maintainers' own key is deliberately **not** in this repository; every
> installation supplies its own. If you fork the project, keep it that way.

## Refreshing the library

If openhymnal.org adds new hymns, re-run the downloaders:

```powershell
# 1. Lyrics + MIDI
Invoke-WebRequest http://openhymnal.org/alllyrics.html -OutFile tools/alllyrics.html
Invoke-WebRequest http://openhymnal.org/OpenHymnal2014.06-midi.zip -OutFile tools/openhymnal-midi.zip
Expand-Archive tools/openhymnal-midi.zip tools/midi -Force
py tools/build_library.py

# 2. MP3 packs (266MB total — three special editions)
$mp3 = @{
  'christmas.zip'  = 'http://openhymnal.org/OpenHymnalChristmas2025.zip'
  'easter.zip'     = 'http://openhymnal.org/OpenHymnalEaster2026.zip'
  'visitation.zip' = 'http://openhymnal.org/OpenHymnalVisitation2026.zip'
}
foreach ($p in $mp3.GetEnumerator()) {
  Invoke-WebRequest $p.Value -OutFile "tools/mp3_zips/$($p.Key)" -UseBasicParsing
  Expand-Archive "tools/mp3_zips/$($p.Key)" tools/mp3_extracted -Force
}
py tools/import_mp3s.py

# 3. (optional) audit which hymns lack audio
py tools/audio_report.py
```

The `tools/mp3_zips/` and `tools/mp3_extracted/` folders are scratch space
— safe to delete once `import_mp3s.py` has populated `audio/`.

## Keyboard shortcuts

| Key            | Action                          |
| -------------- | ------------------------------- |
| `←` / `→`      | Previous / next verse (or slide for a passage) |
| `Ctrl+←` / `→` | Previous / next song in playlist |
| `Space`        | Play / pause audio              |
| `B`            | Blank / unblank display         |
| `F5`           | Toggle display window           |
| `Esc`          | Hide display                    |
| `Ctrl+B`       | Add Bible passage to playlist   |
| `Ctrl+S` / `O` | Save / load playlist            |

## Bible passages (ESV)

The app can insert ESV Bible passages into the service playlist alongside
hymns. This needs a free ESV API key — see
[API keys & secrets](#api-keys--secrets) above to obtain and configure your
own. (ESV text is copyrighted by Crossway and is fetched with your key, never
bundled in this repo.)

Once your key is set, **Bible → Add Passage…** (or `Ctrl+B`), type a reference
like `John 3:16-17`, click **Look up**, **Add to Playlist**. The passage
appears in the playlist with a 📖 marker. When selected, long passages
auto-chunk into 2-verse slides for projection.

Passages are cached in `passages.json` after the first fetch — no
re-hitting the API for the same reference. Free tier: 5,000 fetches/day.

Crossway's required attribution shows automatically as a small footer
on the display whenever an ESV passage is up.

## Dropping your own audio

The app looks for audio in `audio/<hymn-id>.<ext>`. To use your own recording
of *Amazing Grace*, drop a file at:

```
audio/amazing-grace.mp3
```

Supported: `.mp3 .ogg .m4a .wav .flac .mid .midi`.

MP3/OGG/etc. play through `QMediaPlayer` (Windows Media Foundation); MIDI plays
through `pygame.mixer` (Windows GM synth).

## Building a Windows installer

The repo ships the build recipe for a standalone, no-Python-required
Windows app:

```powershell
# from D:\ps-church_com\hymnal_app, with the venv active
pip install pyinstaller pillow

py tools/make_icon.py            # → hymnal.ico (from the PSC logo)
pyinstaller --noconfirm --clean hymnal.spec   # → dist\PSC Hymnal\ (one-folder)

# then compile the installer (Inno Setup 6 — install via: winget install JRSoftware.InnoSetup)
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer.iss
# → dist\PSC-Hymnal-Setup.exe
```

`PSC-Hymnal-Setup.exe` is a per-user installer (no admin/UAC needed). It
installs to `%LOCALAPPDATA%\Programs\PSC Hymnal`, adds Start Menu (and
optional Desktop) shortcuts, and registers an uninstaller. All user data —
settings, the ESV cache, saved playlists, and any drop-in audio — lives
under `%APPDATA%\PSC Hymnal`, so it survives uninstall/reinstall.

> Note: `audio/` (≈700 MB) is **not** committed — re-fetch it with the
> "Refreshing the library" steps above before building, or the app will
> simply run lyrics-only.

## Project layout

```
hymnal_app/
├── run.py                     entry point
├── requirements.txt
├── README.md
├── hymnal/
│   ├── app.py                 QApplication wiring
│   ├── operator.py            control window
│   ├── display.py             fullscreen lyrics window
│   ├── audio.py               MIDI + media playback
│   ├── library.py             hymn data model
│   └── data/hymns.json        308 hymns (built from openhymnal.org)
├── audio/                     drop-folder for audio (MIDI seeded)
├── playlists/                 saved service playlists (.json)
└── tools/
    ├── build_library.py       parses openhymnal sources → hymns.json
    ├── alllyrics.html         (cached download)
    └── midi/                  (extracted MIDI files)
```

## Credits

Hymn text, MIDI, and arrangements: **The Open Hymnal Project**
(<http://openhymnal.org/>), maintained by Brian J. Dumont.
All hymns in this distribution are public domain in the USA.
