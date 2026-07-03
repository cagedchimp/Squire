# Squire — TTRPG Ruleset Lookup webapp

> This folder is served by GitHub Pages (Settings → Pages → deploy from
> branch `main`, folder `/docs`).

Static, serverless version of the ruleset lookup: listens to your game
(microphone, or a Discord/Zoom tab via audio share), transcribes speech
**in the browser** with Whisper (transformers.js, WebGPU/WASM), and pops up
the matching rule card. No backend, no API keys, no ongoing cost — the
speech model downloads once (~40–80 MB) and is cached by the browser.

## Run locally

Any static file server works:

```powershell
python -m http.server 8322
# then open http://localhost:8322
```

(Serving from `file://` won't work — modules/workers need http.)

## GitHub Pages

Pages serves this `docs/` folder from the `main` branch — pushing to
`main` redeploys the site automatically.

**Content policy:** the published site ships **SRD data only** (Creative
Commons). Content extracted from books you own is never committed — build
it locally with `tools/extract_books.py`, then load the resulting JSON
files into your own browser with the **Import ruleset** button. Imported
rulesets live in your browser's localStorage and are never uploaded
anywhere.

## Usage

- **Microphone** — table play. Grant mic permission.
- **Tab / system audio** — for Discord/Zoom: pick the tab or screen in the
  share dialog and check **"Also share audio"** (Chrome on Windows can share
  full system audio when you pick a screen).
- **Model** — `base.en` is a good default. `tiny.en` for weak hardware,
  `small.en` for best accuracy (WebGPU recommended).
- **Import ruleset** — load custom or book-extracted rulesets from JSON
  files (e.g. the `rulesets/dnd5e-books/*.json` you generate locally, or
  Ug Unearthed later); same entry format as
  `rulesets/ug-unearthed/_README.md`. Stored per-browser in localStorage.
- **Ruleset chips** (header) — click to enable/disable a ruleset's matches,
  e.g. turn off D&D during an Og session so overlapping terms ("sleep",
  "rest", "run away") resolve to the right game. Remembered per browser.
- **Simulate box** — type what a player might say to test without audio.

## Updating the data

Rule data is baked into `data/rulesets.json`. Regenerate it from the main
project after any ruleset change:

```powershell
.venv\Scripts\python tools\build_webapp_data.py
```

## Browser support

Chrome/Edge on desktop are the target (AudioWorklet + WASM everywhere,
WebGPU where available; system-audio share is Chrome-only). Firefox/Safari
work for microphone + WASM but can't share tab audio.
