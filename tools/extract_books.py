"""Extract lookup entries from the three core 5e book PDFs.

Parses spells + feats from the PHB, magic items from the DMG, and monster
stat blocks from the MM, skipping anything already covered by the (cleaner)
SRD data. Output goes to rulesets/dnd5e-books/*.json in the generic entry
format, which the app loads automatically.

Usage:  .venv\\Scripts\\python tools\\extract_books.py
Edit the BOOKS paths below if the PDFs move.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
from app.rulesets import (COMMON_WORD_MONSTERS, COMMON_WORD_SPELLS,  # noqa: E402
                          MONSTER_TRIGGERS, SPELL_TRIGGERS, load_dnd5e)

BOOKS = {
    "PHB": r"C:\Users\Jon\Downloads\DD-Player-Handbook.pdf",
    "DMG": r"C:\Users\Jon\Downloads\D&D 5E - Dungeon Master's Guide.pdf",
    "MM": r"C:\Users\Jon\Downloads\D&D 5E - Monster Manual.pdf",
}
OUT_DIR = PROJECT / "rulesets" / "dnd5e-books"

# ---------------------------------------------------------------- helpers

def letters(s: str) -> str:
    """Lowercase letters only — for comparing mangled PDF headers."""
    return re.sub(r"[^a-z]", "", s.lower())


def clean(s: str) -> str:
    s = s.replace("�", "'").replace("’", "'")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"(\d)\s*ft\s*\.", r"\1 ft.", s)
    s = re.sub(r"\s+([.,;:)])", r"\1", s)
    s = re.sub(r"\(\s+", "(", s)
    return s.strip()


def smart_title(s: str) -> str:
    small = {"of", "the", "a", "an", "and", "or", "in", "to", "for", "with", "by"}
    words = s.lower().split()
    out = [w if (w in small and i not in (0, len(words) - 1)) else w.capitalize()
           for i, w in enumerate(words)]
    return " ".join(out)


def repair_name(raw: str, candidates: dict[str, str]) -> str | None:
    """Map a mangled header ('SPEC TATOR', 'C rossbow  E xpert') to a
    canonical name via letters-only comparison. None if no match."""
    return candidates.get(letters(raw))


def paragraphs(lines: list[str]) -> list[str]:
    """Join wrapped lines, then split into paragraphs before Title Case
    trait names ending in a period ('Magical Guardians. ...')."""
    text = clean(" ".join(lines))
    parts = re.split(r"(?<=[.!\"])\s+(?=(?:[A-Z][\w'()/-]+ ){0,4}[A-Z][\w'()/-]*[.!]\s+[A-Z(])", text)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        m = re.match(r"^((?:[A-Z][\w'()/-]+ ){0,4}[A-Z][\w'()/-]*[.!])\s+(.*)$", p)
        if m and len(m.group(1)) <= 45:
            out.append(f"**{m.group(1)}** {m.group(2)}")
        else:
            out.append(p)
    return out


# ------------------------------------------------- canonical name lists

# PHB "named wizard" spells that the SRD carries under de-branded names —
# mapped so they dedupe against the SRD entry (which has spoken aliases).
NAMED_SPELL_MAP = {
    "Melf's Acid Arrow": "Acid Arrow",
    "Bigby's Hand": "Arcane Hand",
    "Evard's Black Tentacles": "Black Tentacles",
    "Drawmij's Instant Summons": "Instant Summons",
    "Leomund's Secret Chest": "Secret Chest",
    "Leomund's Tiny Hut": "Tiny Hut",
    "Mordenkainen's Faithful Hound": "Faithful Hound",
    "Mordenkainen's Magnificent Mansion": "Magnificent Mansion",
    "Mordenkainen's Private Sanctum": "Private Sanctum",
    "Mordenkainen's Sword": "Arcane Sword",
    "Nystul's Magic Aura": "Arcanist's Magic Aura",
    "Otiluke's Freezing Sphere": "Freezing Sphere",
    "Otiluke's Resilient Sphere": "Resilient Sphere",
    "Otto's Irresistible Dance": "Irresistible Dance",
    "Rary's Telepathic Bond": "Telepathic Bond",
    "Tasha's Hideous Laughter": "Hideous Laughter",
    "Tenser's Floating Disk": "Floating Disk",
}

PHB_EXTRA_SPELLS = [
    "Arcane Gate",
    "Armor of Agathys", "Arms of Hadar", "Aura of Life", "Aura of Purity",
    "Aura of Vitality", "Banishing Smite", "Beast Sense", "Blade Ward",
    "Blinding Smite", "Branding Smite", "Chromatic Orb", "Circle of Power",
    "Cloud of Daggers", "Compelled Duel", "Conjure Barrage", "Conjure Volley",
    "Cordon of Arrows", "Crown of Madness", "Crusader's Mantle",
    "Destructive Wave", "Dissonant Whispers", "Elemental Weapon",
    "Ensnaring Strike", "Feign Death", "Friends", "Grasping Vine",
    "Hail of Thorns", "Hex", "Hunger of Hadar", "Lightning Arrow",
    "Phantasmal Force", "Power Word Heal", "Ray of Sickness",
    "Searing Smite", "Staggering Smite", "Swift Quiver", "Telepathy",
    "Thorn Whip", "Thunderous Smite", "Tsunami", "Witch Bolt",
    "Wrathful Smite",
]

PHB_FEATS = [
    "Actor", "Alert", "Athlete", "Charger", "Crossbow Expert",
    "Defensive Duelist", "Dual Wielder", "Dungeon Delver", "Durable",
    "Elemental Adept", "Grappler", "Great Weapon Master", "Healer",
    "Heavily Armored", "Heavy Armor Master", "Inspiring Leader", "Keen Mind",
    "Lightly Armored", "Linguist", "Lucky", "Mage Slayer", "Magic Initiate",
    "Martial Adept", "Medium Armor Master", "Mobile", "Moderately Armored",
    "Mounted Combatant", "Observant", "Polearm Master", "Resilient",
    "Ritual Caster", "Savage Attacker", "Sentinel", "Sharpshooter",
    "Shield Master", "Skilled", "Skulker", "Spell Sniper", "Tavern Brawler",
    "Tough", "War Caster", "Weapon Master",
]

MM_EXTRA_MONSTERS = [
    "Aarakocra", "Allosaurus", "Ankylosaurus", "Banshee", "Barlgura",
    "Beholder", "Beholder Zombie", "Blue Slaad", "Bullywug", "Cambion",
    "Chasme", "Crawling Claw", "Cyclops", "Death Slaad", "Death Tyrant",
    "Demilich", "Displacer Beast", "Drow Elite Warrior", "Drow Mage",
    "Drow Priestess of Lolth", "Duodrone", "Empyrean", "Faerie Dragon",
    "Flameskull", "Flumph", "Fomorian", "Galeb Duhr", "Gas Spore",
    "Gray Slaad", "Green Slaad", "Red Slaad", "Slaad Tadpole",
    "Gnoll Fang of Yeenoghu", "Gnoll Pack Lord", "Goristro", "Grell",
    "Grick Alpha", "Githyanki Knight", "Githyanki Warrior",
    "Githzerai Monk", "Githzerai Zerth", "Half-Red Dragon Veteran",
    "Helmed Horror", "Hook Horror", "Intellect Devourer", "Jackalwere",
    "Kenku", "Kuo-toa", "Kuo-toa Archpriest", "Kuo-toa Whip", "Manes",
    "Mind Flayer", "Mind Flayer Arcanist", "Monodrone", "Myconid Sprout",
    "Myconid Adult", "Myconid Sovereign", "Nothic", "Orc Eye of Gruumsh",
    "Orc War Chief", "Orog", "Pentadrone", "Peryton", "Piercer",
    "Poltergeist", "Quadrone", "Quaggoth", "Quaggoth Thonot", "Revenant",
    "Sahuagin Baron", "Sahuagin Priestess", "Scarecrow", "Shadow Demon",
    "Shadow Dragon", "Young Red Shadow Dragon", "Spectator", "Thri-kreen",
    "Tridrone", "Troglodyte", "Umber Hulk", "Water Weird", "Winged Kobold",
    "Yochlol", "Yuan-ti Abomination", "Yuan-ti Malison", "Yuan-ti Pureblood",
    "Mezzoloth", "Nycaloth", "Ultroloth", "Arcanaloth", "Young Remorhaz",
    "Ogre Zombie",
    "Behir", "Dao", "Marid", "Death Knight", "Adult Blue Dracolich",
    "Goblin Boss", "Hobgoblin Captain", "Hobgoblin Warlord",
    "Lizardfolk Shaman", "Lizard King/Queen", "Half-Ogre", "Fire Snake",
    "Spore Servant", "Quaggoth Spore Servant", "Yeti", "Abominable Yeti",
    "Spined Devil", "Dracolich", "Bone Naga",
]

# Raw MM headers that need explicit mapping to a canonical name.
MM_HEADER_ALIASES = {
    "samplesporeservant": "Spore Servant",
    "spineddevilspinagon": "Spined Devil",
    "gnomedeep": "Deep Gnome (Svirfneblin)",
}

COMMON_WORD_FEATS_TRIGGERS = {"feat", "feats", "take", "takes", "took",
                              "taking", "pick", "picked", "picks", "have",
                              "has", "level", "asi"}

# Canonical names for DMG magic items missing from the SRD. Extracted names
# that don't (fuzzy-)match the SRD or this list are rejected — PDF caps
# headers are too mangled to trust raw.
DMG_EXTRA_ITEMS = [
    "Apparatus of Kwalish", "Blackrazor", "Book of Exalted Deeds",
    "Book of Vile Darkness", "Cap of Water Breathing",
    "Glamoured Studded Leather", "Cloak of Invisibility",
    "Daern's Instant Fortress", "Driftglobe", "Efreeti Chain",
    "Elixir of Health", "Eye and Hand of Vecna", "Eye of Vecna",
    "Hand of Vecna", "Gloves of Thievery", "Heward's Handy Haversack",
    "Instrument of the Bards", "Iron Bands of Bilarro",
    "Keoghtom's Ointment", "Moonblade", "Nolzur's Marvelous Pigments",
    "Potion of Fire Breath", "Potion of Invulnerability",
    "Potion of Longevity", "Potion of Vitality", "Quiver of Ehlonna",
    "Saddle of the Cavalier", "Scroll of Protection", "Sending Stones",
    "Sentinel Shield", "Staff of the Adder", "Sword of Answering",
    "Sword of Vengeance", "Tome of the Stilled Tongue", "Wand of Orcus",
    "Weapon of Warning", "Whelm", "Wave", "Axe of the Dwarvish Lords",
    "Orb of Dragonkind", "Sword of Kas",
]

# ---------------------------------------------------------------- parsers

def get_pages(path: str) -> list[str]:
    reader = PdfReader(path)
    return [(p.extract_text() or "") for p in reader.pages]


LEVEL_RE = re.compile(
    r"^\s*(?:(\d)(?:st|nd|rd|th)-\s*level\s+(\w+)|(\w+)\s+cantrip)\s*(\(ritual\))?\s*$",
    re.I)
FIELD_RE = re.compile(r"^\s*(Casting Time|Range|Components|Duration)\s*:\s*(.*)$")


def parse_phb_spells(pages: list[str], name_map: dict[str, str]) -> tuple[list[dict], list[str]]:
    lines: list[str] = []
    for t in pages[180:]:
        lines.extend(t.split("\n"))

    anchors = []
    for i, line in enumerate(lines):
        if LEVEL_RE.match(line) and any(
                "Casting Time" in lines[j] for j in range(i + 1, min(i + 6, len(lines)))):
            anchors.append(i)

    spells, unmatched = [], []
    for a_idx, i in enumerate(anchors):
        # name = nearest non-empty preceding line
        j = i - 1
        while j >= 0 and not lines[j].strip():
            j -= 1
        raw_name = lines[j].strip() if j >= 0 else ""
        name = name_map.get(letters(raw_name))
        if name is None:
            unmatched.append(raw_name)
            name = smart_title(re.sub(r"\s+", " ", raw_name))
        m = LEVEL_RE.match(lines[i])
        if m.group(1):
            subtitle = f"Level {m.group(1)} {m.group(2).capitalize()}"
        else:
            subtitle = f"{m.group(3).capitalize()} cantrip"
        if m.group(4):
            subtitle += " (ritual)"

        end = anchors[a_idx + 1] - 1 if a_idx + 1 < len(anchors) else min(i + 80, len(lines))
        meta, body_lines, current_field = {}, [], None
        for line in lines[i + 1: end]:
            fm = FIELD_RE.match(line)
            if fm:
                current_field = fm.group(1)
                meta[current_field] = clean(fm.group(2))
            elif current_field and not body_lines and len(meta) < 4 and line.strip() \
                    and not re.match(r"^[A-Z]", line.strip()):
                meta[current_field] += " " + clean(line)
            else:
                current_field = None
                body_lines.append(line)
        body = paragraphs(body_lines)
        body = [re.sub(r"^At Higher Levels\.?\s*", "**At Higher Levels.** ", p)
                if p.startswith("At Higher Levels") else p for p in body]
        spells.append({"name": name, "subtitle": subtitle, "meta": meta, "body": body})
    return spells, unmatched


def parse_phb_feats(pages: list[str]) -> list[dict]:
    feat_map = {letters(f): f for f in PHB_FEATS}
    lines: list[str] = []
    for t in pages[145:170]:
        lines.extend(t.split("\n"))

    hits = [(i, feat_map[letters(l)]) for i, l in enumerate(lines)
            if letters(l) in feat_map and len(l.strip()) <= 40]
    feats = []
    seen = set()
    for h_idx, (i, name) in enumerate(hits):
        if name in seen:
            continue
        seen.add(name)
        end = hits[h_idx + 1][0] if h_idx + 1 < len(hits) else min(i + 60, len(lines))
        block = lines[i + 1: end]
        meta = {}
        if block and block[0].strip().startswith("Prerequisite"):
            meta["Prerequisite"] = clean(re.sub(r"^Prerequisite:?", "", block[0]))
            block = block[1:]
        body = paragraphs([l.replace("â€¢", "-").replace("ï¿½", "-") for l in block])
        feats.append({"name": name, "meta": meta, "body": body})
    return feats


ITEM_START_RE = re.compile(
    r"^\s*(Armor|Weapon|Wondrous item|Potion|Ring|Rod|Scroll|Staff|Wand)\s*[(,]",
    re.I)
RARITY_RE = re.compile(
    r"\b(common|uncommon|rare|very rare|legendary|artifact|rarity varies)\b", re.I)
CAPS_LINE_RE = re.compile(r"^[A-Z][A-Z0-9 '\-,+/()]{2,45}$")


def parse_dmg_items(pages: list[str]) -> tuple[list[dict], list[str]]:
    lines: list[str] = []
    for t in pages:
        lines.extend(t.split("\n"))

    anchors = []  # (name_line_idx, type_line_idx)
    for i, line in enumerate(lines):
        # rarity may wrap onto the next line
        if not (ITEM_START_RE.match(line.strip())
                and (RARITY_RE.search(line)
                     or (i + 1 < len(lines) and RARITY_RE.search(lines[i + 1])
                         and len(lines[i + 1]) < 60))):
            continue
        j = i - 1
        while j >= 0 and not lines[j].strip():
            j -= 1
        if j >= 0 and CAPS_LINE_RE.match(lines[j].strip()) and len(letters(lines[j])) >= 3:
            anchors.append((j, i))

    items, skipped = [], []
    for a_idx, (nj, ti) in enumerate(anchors):
        name = smart_title(clean(lines[nj]))
        subtitle = clean(lines[ti])
        end = anchors[a_idx + 1][0] if a_idx + 1 < len(anchors) else min(ti + 80, len(lines))
        body = paragraphs(lines[ti + 1: end])
        if not body:
            skipped.append(name)
            continue
        items.append({"name": name, "subtitle": subtitle, "body": body})
    return items, skipped


CREATURE_RE = re.compile(
    r"^\s*(Tiny|Small|Medium|Large|Huge|Gargantuan)\s+"
    r"(aberration|beast|celestial|construct|dragon|elemental|fey|fiend|giant|"
    r"humanoid|monstrosity|ooze|plant|undead|swarm)\b.*",
    re.I)
# 'Armor Class 17 (natural armor)' — extracts reliably even when the
# size/type line above it is garbled, so it anchors each stat block.
AC_RE = re.compile(r"^\s*Armor Class\s+\d")
SIZE_WORDS = ("tiny", "small", "medium", "large", "huge", "gargantuan")
MM_SKIP_LETTERS = {"actions", "reactions", "legendaryactions", "lairactions",
                   "regionaleffects", "str", "dex", "con", "int", "wis", "cha",
                   "index", "indexofstatblocks"}


def parse_mm_monsters(pages: list[str], name_map: dict[str, str],
                      targeted: set[str]) -> tuple[list[dict], list[str], list[str]]:
    # Flatten with page ids so we can bias name association to same page.
    lines: list[tuple[int, str]] = []
    for pno, t in enumerate(pages):
        lines.extend((pno, l) for l in t.split("\n"))

    from rapidfuzz import fuzz, process as rf_process
    map_keys = list(name_map)

    anchor_idx = [i for i, (_, l) in enumerate(lines) if AC_RE.match(l)]
    headers = {}      # line idx -> canonical name
    raw_headers = {}  # line idx -> raw caps text (no canonical match)
    for i, (_, l) in enumerate(lines):
        s = l.strip()
        if (not CAPS_LINE_RE.match(s) or letters(s) in MM_SKIP_LETTERS
                or s.startswith("VARIANT")):
            continue
        key = letters(re.sub(r"\([^)]*\)", "", s))  # drop '(spinagon)' parentheticals
        canonical = name_map.get(key) or MM_HEADER_ALIASES.get(key)
        if canonical is None and len(key) >= 6:
            # OCR tolerance: 'PERYTQN' -> 'peryton'
            hit = rf_process.extractOne(key, map_keys, scorer=fuzz.ratio, score_cutoff=85)
            if hit:
                canonical = name_map[hit[0]]
        if canonical:
            headers[i] = canonical
        elif len(key) >= 4:
            raw_headers[i] = s

    monsters, fallback_named, unnamed = [], [], []
    used_headers: set[int] = set()
    claimed: set[str] = set()

    def inside_header(i, hdr_end, page):
        cand = [h for h in headers if i < h < hdr_end and h not in used_headers
                and letters(headers[h]) not in claimed
                and abs(lines[h][0] - page) <= 1]
        return min(cand, key=lambda x: abs(x - i)) if cand else None

    def preceding_header(i, page):
        cand = [h for h in headers if i - 200 <= h < i and h not in used_headers
                and letters(headers[h]) not in claimed
                and abs(lines[h][0] - page) <= 3]
        return max(cand) if cand else None

    # Precompute block extents/text for every anchor.
    blocks = []
    for a_pos, i in enumerate(anchor_idx):
        page = lines[i][0]
        # block start: the size/type line just above the AC line, if present
        start = i
        for back in range(1, 4):
            if i - back >= 0 and lines[i - back][1].strip():
                if letters(lines[i - back][1]).startswith(SIZE_WORDS):
                    start = i - back
                break
        # block end: next stat block (minus its size line), capped at 2 pages
        end = anchor_idx[a_pos + 1] - 2 if a_pos + 1 < len(anchor_idx) else len(lines)
        end = min(end, i + 160)
        while end > i and lines[min(end, len(lines) - 1)][0] > page + 1:
            end -= 1
        text_lines = [lines[x][1] for x in range(start, min(end + 1, len(lines)))
                      if x not in headers and x not in raw_headers]
        if not letters(text_lines[0]).startswith(SIZE_WORDS):
            text_lines.insert(0, "")  # keep slot 0 = subtitle line
        hdr_end = anchor_idx[a_pos + 1] if a_pos + 1 < len(anchor_idx) else len(lines)
        blocks.append({
            "i": i, "end": end, "hdr_end": hdr_end, "page": page,
            "text_lines": text_lines,
            # Name matching/verification uses only the stat block proper —
            # the full range can sweep in a NEIGHBOR's lore, and "the block
            # mentions mind flayers" must not mean "this IS the mind flayer".
            "stat_low": " ".join(text_lines[:40]).lower(),
            "name": None,
        })

    def name_words_in_body(name, body_low):
        words = re.split(r"[ /]+", name.lower())
        return any(w in body_low for w in words if len(w) >= 4)

    # Pass A (high confidence): header inside/after the block (stopping
    # short of the next block, whose own header sits just above it, and
    # verified against the block text), then the name the stat block
    # calls its own creature.
    for b in blocks:
        h = inside_header(b["i"], b["hdr_end"] - 4, b["page"])
        if h is not None and name_words_in_body(headers[h], b["stat_low"]):
            used_headers.add(h)
            b["name"] = headers[h]
        else:
            b["name"] = _name_from_body(b["stat_low"], name_map, claimed)
        if b["name"]:
            claimed.add(letters(b["name"]))

    # Pass B (lower confidence, runs only after all sure names are taken):
    # nearest preceding unused header, verified by any word of the name
    # appearing in the block ('gnoll' validates 'Gnoll Pack Lord').
    for b in blocks:
        if b["name"]:
            continue
        h = preceding_header(b["i"], b["page"])
        if h is not None and name_words_in_body(headers[h], b["stat_low"]):
            used_headers.add(h)
            b["name"] = headers[h]
            claimed.add(letters(b["name"]))

    def strong_verify(name, body_low):
        """The label must really be this block's creature: full name, or its
        most distinctive (longest) word, must appear in the block text."""
        probe = name.lower().split("/")[0].strip()
        if _mentions(probe, body_low):
            return True
        words = [w for w in probe.split() if len(w) >= 4]
        return bool(words) and _mentions(max(words, key=len), body_low) > 0

    def rescue(names):
        # For known-missing names, find the unnamed block that mentions
        # them most. Only touches otherwise-dropped blocks.
        for name in sorted(names, key=len, reverse=True):
            if letters(name) in claimed:
                continue
            probe_full = name.lower().split("/")[0].strip()
            words = [w for w in re.split(r"[ /,-]+", name.lower())
                     if len(w) >= 3 and w not in ("the", "of")]
            best, best_score = None, 0
            for b in blocks:
                if b["name"]:
                    continue
                score = (2 * _mentions(probe_full, b["stat_low"])
                         + sum(_mentions(w, b["stat_low"]) for w in words))
                if score > best_score:
                    best, best_score = b, score
            if best is not None and best_score >= 2:
                best["name"] = name
                claimed.add(letters(name))

    # Pass C: targeted rescue for the known-missing whitelist names.
    rescue(targeted)

    # Pass D: strip labels that fail verification (a block labeled 'Mind
    # Flayer' that never says 'flayer' is someone else's stat block), then
    # rescue the freed names into their true blocks.
    freed = []
    for b in blocks:
        if b["name"] and not strong_verify(b["name"], b["stat_low"]):
            freed.append(b["name"])
            claimed.discard(letters(b["name"]))
            b["name"] = None
    rescue(set(freed) | targeted)
    for b in blocks:  # anything rescued must also verify
        if b["name"] and not strong_verify(b["name"], b["stat_low"]):
            claimed.discard(letters(b["name"]))
            b["name"] = None

    for b in blocks:
        if b["name"]:
            monsters.append(_build_monster(b["name"], b["text_lines"]))
            continue
        # Unresolvable -> skip the block (SRD dupes and family pages land
        # here), but report the raw header for review.
        cand = [h for h in raw_headers if b["i"] - 25 <= h < b["end"]
                and abs(lines[h][0] - b["page"]) <= 1]
        if cand:
            h = min(cand, key=lambda x: abs(x - b["i"]))
            fallback_named.append(
                _repair_spacing(raw_headers[h], " ".join(b["text_lines"])))
        else:
            unnamed.append(clean(lines[b["i"]][1]))
    return monsters, fallback_named, unnamed


def _mentions(probe: str, text: str) -> int:
    """Word-boundary occurrence count — 'guard' must not match 'guarding'."""
    return len(re.findall(rf"\b{re.escape(probe)}\b", text))


def _name_from_body(body_low: str, name_map: dict[str, str],
                    claimed: set[str]) -> str | None:
    """Pick the canonical monster name mentioned most often in a stat block.
    Requires >= 2 mentions; ties go to the longest (most specific) name."""
    best, best_score = None, 0
    for canonical in set(name_map.values()):
        if letters(canonical) in claimed:
            continue
        probe = canonical.lower().split("/")[0].strip()
        if len(probe) < 4:
            continue
        count = _mentions(probe, body_low)
        score = count * 100 + len(probe)
        if count >= 2 and score > best_score:
            best, best_score = canonical, score
    return best


def _repair_spacing(caps: str, body: str) -> str:
    """Merge spurious intra-word spaces in a caps header when the merged
    word actually appears in the accompanying text."""
    body_low = body.lower()
    words = clean(caps).split(" ")
    out = [words[0]] if words else []
    for w in words[1:]:
        merged = (out[-1] + w).lower() if out else w.lower()
        if out and merged in body_low:
            out[-1] = out[-1] + w
        else:
            out.append(w)
    return smart_title(" ".join(out))


STAT_FIELDS = [
    ("AC", r"Armor Class\s+([^\n]+)"),
    ("HP", r"Hit Points\s+([^\n]+)"),
    ("Speed", r"Speed\s+([^\n]+)"),
    ("Saves", r"Saving Throws\s+([^\n]+)"),
    ("Skills", r"Skills\s+([^\n]+)"),
    ("Vulnerable", r"Damage Vulnerabilities\s+([^\n]+)"),
    ("Resistant", r"Damage Resistances?\s+([^\n]+)"),
    ("Immune", r"Damage Immunities\s+([^\n]+)"),
    ("Condition Immunities", r"Condition Immunities\s+([^\n]+)"),
    ("Senses", r"Senses\s+([^\n]+)"),
    ("Languages", r"Languages\s+([^\n]+)"),
    ("Challenge", r"Challenge\s+([^\n]+)"),
]


def _build_monster(name: str, text_lines: list[str]) -> dict:
    text = "\n".join(text_lines)
    subtitle = clean(text_lines[0]) if text_lines else ""
    meta = {}
    for label, pat in STAT_FIELDS:
        m = re.search(pat, text)
        if m:
            meta[label] = clean(m.group(1))
            text = text.replace(m.group(0), "\n")
    ability_bits = re.findall(r"\b(STR|DEX|CON|INT|WIS|CHA)\b\s*\n\s*(\d+)\s*\(([^)]{1,6})\)", text)
    if ability_bits:
        order = {k: n for n, k in enumerate(["STR", "DEX", "CON", "INT", "WIS", "CHA"])}
        ability_bits.sort(key=lambda b: order.get(b[0], 9))
        meta["Abilities"] = " · ".join(
            f"{a} {v} ({clean(mod).replace(' ', '')})" for a, v, mod in ability_bits)
        text = re.sub(r"\b(STR|DEX|CON|INT|WIS|CHA)\b\s*\n\s*\d+\s*\([^)]{1,6}\)", "\n", text)
    if "Challenge" in meta:
        cr = meta.pop("Challenge")
        subtitle = f"{subtitle} — CR {cr}"

    # Split into segments at ACTIONS/REACTIONS/LEGENDARY ACTIONS lines
    # BEFORE paragraph bolding, so headers don't tear bold markers apart.
    section_names = {"actions": "### Actions", "reactions": "### Reactions",
                     "legendaryactions": "### Legendary Actions"}
    segments, titles = [[]], [None]
    for l in text.split("\n")[1:]:
        key = letters(l)
        if key in section_names and len(l.strip()) <= 24:
            titles.append(section_names[key])
            segments.append([])
        elif l.strip():
            segments[-1].append(l)
    body = []
    for title, seg in zip(titles, segments):
        if title:
            body.append(title)
        body.extend(paragraphs(seg))
    return {"name": name, "subtitle": subtitle, "meta": meta, "body": body}


# ---------------------------------------------------------------- main

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    srd = load_dnd5e()
    srd_names = {letters(e.name) for e in srd}
    srd_spell_names = [e.name for e in srd if e.category == "Spell"]
    srd_monster_names = [e.name for e in srd if e.category == "Monster"]

    spell_map = {letters(n): n for n in srd_spell_names + PHB_EXTRA_SPELLS}
    spell_map.update({letters(named): srd for named, srd in NAMED_SPELL_MAP.items()})
    monster_map = {letters(n): n for n in srd_monster_names + MM_EXTRA_MONSTERS}

    report = {}

    # ---- PHB ----
    pages = get_pages(BOOKS["PHB"])
    spells, unmatched = parse_phb_spells(pages, spell_map)
    new_spells = []
    for s in spells:
        if letters(s["name"]) in srd_names:
            continue
        nm = s["name"].lower()
        guarded = nm in COMMON_WORD_SPELLS or (len(nm.split()) == 1)
        new_spells.append({
            "id": f"dnd5e:phb:spell:{letters(s['name'])}",
            "name": s["name"], "category": "Spell", "subtitle": s["subtitle"],
            "meta": s["meta"], "body": s["body"], "source": "PHB",
            "guarded": guarded,
            "triggers": sorted(SPELL_TRIGGERS) if guarded else [],
        })
    report["PHB spells parsed"] = len(spells)
    report["PHB spells new (non-SRD)"] = len(new_spells)
    report["PHB spell headers unmatched"] = unmatched

    feats = parse_phb_feats(pages)
    new_feats = []
    for f in feats:
        if letters(f["name"]) in srd_names:
            continue
        guarded = len(f["name"].split()) == 1
        new_feats.append({
            "id": f"dnd5e:phb:feat:{letters(f['name'])}",
            "name": f["name"], "category": "Feat", "subtitle": "Feat",
            "meta": f["meta"], "body": f["body"], "source": "PHB",
            "guarded": guarded,
            "triggers": sorted(COMMON_WORD_FEATS_TRIGGERS) if guarded else [],
        })
    report["PHB feats new"] = len(new_feats)

    with open(OUT_DIR / "phb.json", "w", encoding="utf-8") as f:
        json.dump(new_spells + new_feats, f, indent=1, ensure_ascii=False)

    # ---- DMG ----
    from rapidfuzz import fuzz, process as rf_process
    srd_item_names = [e.name for e in srd if e.category == "Magic Item"]
    item_map = {letters(n): n for n in srd_item_names + DMG_EXTRA_ITEMS}
    item_keys = list(item_map)

    items, skipped = parse_dmg_items(get_pages(BOOKS["DMG"]))
    new_items, seen, rejected = [], set(), []
    for it in items:
        key = letters(it["name"])
        canonical = item_map.get(key)
        if canonical is None and len(key) >= 6:
            hit = rf_process.extractOne(key, item_keys, scorer=fuzz.ratio,
                                        score_cutoff=88)
            if hit:
                canonical = item_map[hit[0]]
        if canonical is None:
            rejected.append(it["name"])
            continue
        key = letters(canonical)
        if key in srd_names or key in seen:
            continue
        seen.add(key)
        new_items.append({
            "id": f"dnd5e:dmg:item:{key}",
            "name": canonical, "category": "Magic Item",
            "subtitle": it["subtitle"], "body": it["body"], "source": "DMG",
        })
    report["DMG items parsed"] = len(items)
    report["DMG items new (non-SRD)"] = len(new_items)
    report["DMG names rejected (unmatched)"] = sorted(set(rejected))
    with open(OUT_DIR / "dmg-magic-items.json", "w", encoding="utf-8") as f:
        json.dump(new_items, f, indent=1, ensure_ascii=False)

    # ---- MM ----
    monsters, fallback_named, unnamed = parse_mm_monsters(
        get_pages(BOOKS["MM"]), monster_map, set(MM_EXTRA_MONSTERS))
    new_monsters, seen = [], set()
    for m in monsters:
        key = letters(m["name"])
        if key in srd_names or key in seen:
            continue
        seen.add(key)
        nm = m["name"].lower()
        guarded = nm in COMMON_WORD_MONSTERS
        new_monsters.append({
            "id": f"dnd5e:mm:monster:{key}",
            "name": m["name"], "category": "Monster", "subtitle": m["subtitle"],
            "meta": m["meta"], "body": m["body"], "source": "MM",
            "guarded": guarded,
            "triggers": sorted(MONSTER_TRIGGERS) if guarded else [],
        })
    report["MM stat blocks matched to names"] = len(monsters)
    report["MM monsters new (non-SRD)"] = len(new_monsters)
    report["MM names from fallback repair"] = sorted(fallback_named)
    report["MM anchors without names"] = len(unnamed)
    claimed = {letters(m["name"]) for m in monsters}
    report["MM whitelist never claimed"] = sorted(
        n for n in MM_EXTRA_MONSTERS if letters(n) not in claimed)
    with open(OUT_DIR / "mm-monsters.json", "w", encoding="utf-8") as f:
        json.dump(new_monsters, f, indent=1, ensure_ascii=False)

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

