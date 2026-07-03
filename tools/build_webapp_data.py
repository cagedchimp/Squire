"""Export loaded rulesets to docs/data/rulesets.json for the static webapp.

    .venv\\Scripts\\python tools\\build_webapp_data.py [--exclude NAME ...]

The public site is built with `--exclude dnd5e-books` so copyrighted book
content never ships in the repo — load those JSONs into your own browser
with the webapp's Import Ruleset button instead.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
# app.rulesets is imported inside main() after sys.path is set up

OUT = PROJECT / "docs" / "data" / "rulesets.json"


def main():
    excluded = set()
    if "--exclude" in sys.argv:
        excluded = set(sys.argv[sys.argv.index("--exclude") + 1:])

    from app.rulesets import RULESETS_DIR, load_dnd5e, load_generic
    entries, summaries = [], []
    for folder in sorted(RULESETS_DIR.iterdir()):
        if not folder.is_dir() or folder.name in excluded:
            continue
        loaded = load_dnd5e() if folder.name == "dnd5e" else load_generic(folder)
        if loaded:
            entries.extend(loaded)
            summaries.append({"name": folder.name, "entries": len(loaded)})

    payload = {
        "rulesets": summaries,
        "entries": [{
            "id": e.id,
            "name": e.name,
            "category": e.category,
            "subtitle": e.subtitle,
            "aliases": e.aliases,
            "meta": e.meta,
            "body": e.body,
            "source": e.source,
            "guarded": e.guarded,
            "triggers": sorted(e.triggers),
        } for e in entries],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote {OUT} — {len(entries)} entries, "
          f"{OUT.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
