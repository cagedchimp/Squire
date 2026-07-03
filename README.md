# TTRPG Ruleset Lookup

> **Also available as a static webapp** — see [docs/](docs/README.md):
> same lookup, but speech-to-text runs in the browser (transformers.js +
> WebGPU). Served by GitHub Pages straight from the `docs/` folder.

Listens to your game table (microphone) **or** your computer's audio
(Discord, Zoom — via WASAPI loopback, no virtual cable needed), transcribes
speech locally with Whisper, and instantly pops up the matching rule card:
a player says *"I cast Fireball"* and the Fireball spell appears on screen.

**Ongoing cost: $0.** Speech-to-text runs locally (faster-whisper) and rule
matching is local fuzzy search over the ruleset — no AI API calls at all.

## Quick start

Double-click **`run.bat`** — it creates a virtual environment, installs
dependencies (first run only), starts the server, and opens
http://127.0.0.1:8321 in your browser.

Or manually:

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python run.py
```

Then in the browser:
1. Pick an audio source — **System audio: …** entries capture whatever plays
   through that output device (Discord/Zoom); **Microphone: …** entries
   listen to the room.
2. Pick a Whisper model (`base.en` is a good default; `small.en` is more
   accurate if your CPU keeps up; first use downloads the model once).
3. **Start listening.** Matched rules appear as cards; the live transcript
   shows along the bottom.

No audio handy? Type into the **Simulate** box at the bottom, e.g.
`I cast fireball at the goblins` or `make a stealth check`.

## What it knows (~1,270 entries)

From the CC-licensed 5e SRD (`rulesets/dnd5e/`):
- All 319 SRD spells (with casting time, range, components, damage, etc.)
- All 334 SRD monsters (full stat blocks)
- All 15 conditions, all 18 skills, SRD magic items
- Core rule sections (cover, resting, opportunity attacks, death saves, …)

Extracted from the three core book PDFs (`rulesets/dnd5e-books/` — kept
**out of the repo**; generate locally from your own PDFs with
`tools/extract_books.py`):
- 42 PHB-only spells (Hex, Chromatic Orb, Witch Bolt, the smites, …), plus
  spoken aliases so "Tasha's Hideous Laughter" or "Bigby's Hand" find the
  SRD's de-branded entries
- 40 PHB feats (Sharpshooter, War Caster, Lucky, …)
- 36 DMG magic items missing from the SRD (Blackrazor, Wand of Orcus, …)
- 73 MM monsters missing from the SRD (Beholder, Mind Flayer, Displacer
  Beast, Death Knight, Yeti, the slaadi/yugoloths/modrons, …)

Every book-extracted monster label is verified against its own stat block
text; unverifiable blocks are dropped rather than risk showing the wrong
stats. A few stat blocks (e.g. Kenku) are images in the PDF and can't be
extracted. The extraction report prints on each run of
[tools/extract_books.py](tools/extract_books.py).

Common-word names ("Shield", "Light", "History", "Wolf", "Lucky") are
**guarded**: they only trigger when heard near words like *cast/spell*,
*check/roll*, *attack*, or *feat*, so normal table chatter doesn't spam
cards.

## Adding rulesets (e.g. Ug Unearthed)

Create a folder under `rulesets/` and drop in `.json` files — see
[rulesets/ug-unearthed/_README.md](rulesets/ug-unearthed/_README.md) for the
entry format and a sample file. Restart the server and it's live.

## Tuning

- False positives / missed matches: adjust score cutoffs in
  [app/matcher.py](app/matcher.py) (`cutoff = 92 if n == 1 else 87`) and the
  guarded-word lists in [app/rulesets.py](app/rulesets.py).
- Repeat suppression: a rule won't re-fire within 20 s
  (`RuleMatcher(cooldown=...)`).
- Speech chunking (how long a pause ends an utterance): `SpeechChunker`
  in [app/audio.py](app/audio.py).

## Architecture

```
audio device (mic or WASAPI loopback)      PyAudioWPatch
  └─> 100ms blocks @16kHz mono            app/audio.py
       └─> energy-VAD utterance chunks    SpeechChunker
            └─> local Whisper STT         app/transcriber.py (faster-whisper)
                 └─> fuzzy name match     app/matcher.py (rapidfuzz)
                      └─> WebSocket push  app/main.py (FastAPI)
                           └─> rule card  static/index.html
```
