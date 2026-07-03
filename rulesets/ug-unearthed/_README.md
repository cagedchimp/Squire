# Ug Unearthed ruleset

Drop one or more `.json` files in this folder and they are loaded
automatically at startup. Files starting with `_` are ignored (like this one
and `_sample.json`).

Each file is a JSON **list** of entries:

```json
[
  {
    "name": "Big Rock",                 // required — what players say
    "category": "Attack",               // badge shown on the card
    "subtitle": "Basic action",         // italic line next to the name
    "aliases": ["throw rock", "rock throw"],  // other spoken phrasings
    "meta": {"Cost": "1 grunt", "Range": "Thrown"},
    "body": ["Paragraphs of rule text.", "Markdown **bold** and tables work."],
    "guarded": false,                   // true = only match near a trigger word
    "triggers": []                      // e.g. ["use", "uses"] when guarded
  }
]
```

Tips:
- Add `aliases` for every way the rule is said out loud — matching is fuzzy,
  but an alias for common shorthand helps a lot.
- Set `"guarded": true` with `triggers` for entries whose name is a common
  English word, so casual conversation doesn't trigger them.

Copy `_sample.json` to `entries.json` and edit it to get started.
