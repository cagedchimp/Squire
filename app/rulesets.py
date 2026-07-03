"""Ruleset loading.

Each ruleset is a folder under rulesets/. The D&D 5e SRD has a dedicated
adapter that converts the 5e-bits SRD JSON into generic entries. Any other
folder (e.g. ug-unearthed) is loaded generically: every *.json file in it is
a list of entry objects with keys: id, name, category, subtitle, aliases,
meta, body, guarded, triggers. Files starting with "_" are skipped.
"""
from __future__ import annotations

import json
from pathlib import Path

from .matcher import Entry

RULESETS_DIR = Path(__file__).resolve().parent.parent / "rulesets"

# Spell names that are common English words — only match near a cast-word.
SPELL_TRIGGERS = {"cast", "casts", "casting", "casted", "spell", "spells",
                  "concentrate", "concentrating", "concentration", "counterspell",
                  "ritual", "prepare", "prepared", "upcast", "level"}
COMMON_WORD_SPELLS = {
    "aid", "alarm", "bane", "bless", "blight", "blur", "command", "commune",
    "confusion", "contagion", "darkness", "daylight", "divination", "dream",
    "earthquake", "etherealness", "fabricate", "fear", "foresight", "gate",
    "grease", "guidance", "gust", "harm", "haste", "heal", "heroism",
    "imprisonment", "invisibility", "jump", "knock", "levitate", "light",
    "mending", "message", "mislead", "regenerate", "resistance",
    "resurrection", "sanctuary", "scrying", "seeming", "sending", "shatter",
    "shield", "silence", "sleep", "slow", "suggestion", "sunbeam", "sunburst",
    "symbol", "tongues", "web", "weird", "wish",
}

# Spoken variants Whisper often produces as two words, plus the "named
# wizard" versions players actually say for de-branded SRD spells.
SPELL_ALIASES = {
    "acid-arrow": ["melf's acid arrow", "melfs acid arrow"],
    "arcane-hand": ["bigby's hand", "bigbys hand"],
    "black-tentacles": ["evard's black tentacles", "evards black tentacles"],
    "instant-summons": ["drawmij's instant summons"],
    "secret-chest": ["leomund's secret chest", "leomunds secret chest"],
    "tiny-hut": ["leomund's tiny hut", "leomunds tiny hut"],
    "faithful-hound": ["mordenkainen's faithful hound"],
    "magnificent-mansion": ["mordenkainen's magnificent mansion"],
    "private-sanctum": ["mordenkainen's private sanctum"],
    "arcane-sword": ["mordenkainen's sword", "mordenkainens sword"],
    "arcanists-magic-aura": ["nystul's magic aura", "nystuls magic aura"],
    "freezing-sphere": ["otiluke's freezing sphere", "otilukes freezing sphere"],
    "resilient-sphere": ["otiluke's resilient sphere", "otilukes resilient sphere"],
    "irresistible-dance": ["otto's irresistible dance", "ottos irresistible dance"],
    "telepathic-bond": ["rary's telepathic bond", "rarys telepathic bond"],
    "hideous-laughter": ["tasha's hideous laughter", "tashas hideous laughter"],
    "floating-disk": ["tenser's floating disk", "tensers floating disk"],
    "counterspell": ["counter spell"],
    "fireball": ["fire ball"],
    "thunderwave": ["thunder wave"],
    "moonbeam": ["moon beam"],
    "sunbeam": ["sun beam"],
    "sunburst": ["sun burst"],
    "shapechange": ["shape change"],
    "stoneskin": ["stone skin"],
    "goodberry": ["good berry"],
    "shillelagh": ["shelaylee", "shalaylee"],
    "eldritch-blast": ["eldrich blast"],
    "feeblemind": ["feeble mind"],
    "cloudkill": ["cloud kill"],
    "flamestrike": ["flame strike"],
    "spiritual-weapon": ["spirit weapon"],
}

# Monster names that are common English words — guard like spells.
COMMON_WORD_MONSTERS = {
    "ape", "badger", "bat", "boar", "cat", "crab", "deer", "eagle", "elk",
    "frog", "goat", "hawk", "hyena", "jackal", "lion", "lizard", "mule",
    "octopus", "owl", "panther", "pony", "rat", "raven", "scorpion",
    "spider", "tiger", "vulture", "weasel", "wolf", "shadow",
    "guard", "knight", "priest", "mage", "noble", "scout", "spy", "thug",
    "veteran", "acolyte", "bandit", "commoner", "cultist", "druid",
    "gladiator", "berserker",
}
MONSTER_TRIGGERS = {"attack", "attacks", "attacking", "attacked", "appears",
                    "appear", "see", "spot", "fight", "fighting", "initiative",
                    "stats", "stat", "hp", "ac", "cr", "roll", "rolls", "kill",
                    "kills", "hits", "hit", "summon", "summons", "giant",
                    "dire", "swarm"}

SKILL_TRIGGERS = {"check", "checks", "roll", "rolls", "rolled", "rolling",
                  "skill", "proficiency", "proficient", "bonus", "make",
                  "makes", "expertise"}

RULE_TRIGGERS = {"rule", "rules", "how", "work", "works"}

# Extra spoken aliases so common table phrases hit the right rule section.
RULE_SECTION_ALIASES = {
    "resting": ["long rest", "short rest"],
    "cover": ["half cover", "three quarters cover", "total cover", "full cover"],
    "advantage-and-disadvantage": ["advantage", "disadvantage"],
    "making-an-attack": ["attack roll", "opportunity attack", "attack of opportunity",
                         "unarmed strike", "grapple", "grappling", "shove", "shoving",
                         "two weapon fighting"],
    "damage-and-healing": ["hit points", "critical hit", "crit", "death saving throw",
                           "death save", "death saves", "temporary hit points",
                           "instant death", "dying"],
    "saving-throws": ["saving throw", "saving throws", "save dc"],
    "ability-checks": ["ability check", "contest", "group check", "passive check"],
    "actions-in-combat": ["dodge action", "dash", "disengage", "ready an action",
                          "readied action", "help action", "hide action"],
    "the-order-of-combat": ["initiative", "surprise round", "surprised", "your turn",
                            "bonus action", "reaction"],
    "movement-and-position": ["difficult terrain", "flanking", "squeeze", "squeezing"],
    "mounted-combat": ["mounted", "mount", "dismount"],
    "underwater-combat": ["underwater"],
    "casting-a-spell": ["spell slot", "spell slots", "components", "somatic", "verbal",
                        "material component", "area of effect", "spell attack",
                        "spell save"],
    "what-is-a-spell": ["cantrip", "cantrips", "spell level", "school of magic"],
    "the-environment": ["falling", "fall damage", "suffocating", "suffocation",
                        "drowning", "vision", "darkvision", "blindsight", "truesight",
                        "food and water", "obscured", "heavily obscured", "lightly obscured"],
    "objects": ["breaking objects", "object hit points"],
    "poisons": ["poison", "poisoned weapon"],
    "diseases": ["disease"],
    "madness": ["madness"],
    "traps": ["trap"],
    "attunement": ["attune", "attuned", "attuning"],
    "movement": ["travel pace", "forced march", "jumping", "climbing", "swimming",
                 "crawling", "high jump", "long jump"],
}
# Single-word rule sections that would fire constantly in normal speech.
GUARDED_RULE_SECTIONS = {"time", "objects", "movement", "cover", "madness",
                         "traps", "poisons", "diseases", "resting"}


def _load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_dnd5e() -> list[Entry]:
    data_dir = RULESETS_DIR / "dnd5e" / "data"
    entries: list[Entry] = []

    for spell in _load_json(data_dir / "5e-SRD-Spells.json"):
        level = spell.get("level", 0)
        school = spell.get("school", {}).get("name", "")
        subtitle = (f"{school} cantrip" if level == 0
                    else f"Level {level} {school}".strip())
        meta = {
            "Casting Time": spell.get("casting_time", ""),
            "Range": spell.get("range", ""),
            "Components": ", ".join(spell.get("components", [])),
            "Duration": ("Concentration, " if spell.get("concentration") else "")
                        + spell.get("duration", ""),
        }
        if spell.get("material"):
            meta["Materials"] = spell["material"]
        classes = ", ".join(c["name"] for c in spell.get("classes", []))
        if classes:
            meta["Classes"] = classes
        body = list(spell.get("desc", []))
        for para in spell.get("higher_level", []):
            body.append(f"**At Higher Levels.** {para}")
        name_norm = spell["name"].lower()
        guarded = name_norm in COMMON_WORD_SPELLS
        entries.append(Entry(
            id=f"dnd5e:spell:{spell['index']}",
            name=spell["name"],
            category="Spell",
            subtitle=subtitle,
            aliases=SPELL_ALIASES.get(spell["index"], []),
            meta=meta,
            body=body,
            source="D&D 5e SRD",
            guarded=guarded,
            triggers=SPELL_TRIGGERS if guarded else set(),
        ))

    for cond in _load_json(data_dir / "5e-SRD-Conditions.json"):
        entries.append(Entry(
            id=f"dnd5e:condition:{cond['index']}",
            name=cond["name"],
            category="Condition",
            body=list(cond.get("desc", [])),
            source="D&D 5e SRD",
        ))

    for skill in _load_json(data_dir / "5e-SRD-Skills.json"):
        ability = skill.get("ability_score", {}).get("name", "")
        entries.append(Entry(
            id=f"dnd5e:skill:{skill['index']}",
            name=skill["name"],
            category="Skill",
            subtitle=f"{ability} check" if ability else "",
            body=list(skill.get("desc", [])),
            source="D&D 5e SRD",
            guarded=True,
            triggers=SKILL_TRIGGERS,
        ))

    for section in _load_json(data_dir / "5e-SRD-Rule-Sections.json"):
        idx = section["index"]
        name_norm = section["name"].lower()
        guarded = name_norm in GUARDED_RULE_SECTIONS
        entries.append(Entry(
            id=f"dnd5e:rule:{idx}",
            name=section["name"],
            category="Rule",
            aliases=RULE_SECTION_ALIASES.get(idx, []),
            body=[section.get("desc", "")],
            source="D&D 5e SRD",
            guarded=guarded,
            triggers=RULE_TRIGGERS if guarded else set(),
        ))

    for mon in _load_json(data_dir / "5e-SRD-Monsters.json"):
        entries.append(_monster_entry(mon))

    for item in _load_json(data_dir / "5e-SRD-Magic-Items.json"):
        rarity = item.get("rarity", {}).get("name", "")
        cat = item.get("equipment_category", {}).get("name", "")
        entries.append(Entry(
            id=f"dnd5e:item:{item['index']}",
            name=item["name"],
            category="Magic Item",
            subtitle=", ".join(x for x in (cat, rarity) if x),
            body=list(item.get("desc", [])),
            source="D&D 5e SRD",
        ))

    return entries


def _mod(score: int) -> str:
    m = (score - 10) // 2
    return f"{'+' if m >= 0 else ''}{m}"


def _monster_entry(mon: dict) -> Entry:
    """Convert a 5e-bits SRD monster into a rule card entry."""
    cr = mon.get("challenge_rating", "?")
    if isinstance(cr, float) and cr < 1 and cr > 0:
        cr = {0.125: "1/8", 0.25: "1/4", 0.5: "1/2"}.get(cr, cr)
    subtitle = (f"{mon.get('size', '')} {mon.get('type', '')}, "
                f"{mon.get('alignment', '')} — CR {cr}").strip()

    ac_list = mon.get("armor_class", [])
    ac = ", ".join(f"{a.get('value', '?')} ({a.get('type', '')})" for a in ac_list)
    speed = ", ".join(f"{k} {v}" for k, v in mon.get("speed", {}).items())
    abilities = " · ".join(
        f"{lbl} {mon.get(key, 10)} ({_mod(mon.get(key, 10))})"
        for lbl, key in (("STR", "strength"), ("DEX", "dexterity"),
                         ("CON", "constitution"), ("INT", "intelligence"),
                         ("WIS", "wisdom"), ("CHA", "charisma")))
    meta = {
        "AC": ac,
        "HP": f"{mon.get('hit_points', '?')} ({mon.get('hit_dice', '')})",
        "Speed": speed,
        "Abilities": abilities,
    }
    profs = [f"{p['proficiency']['name'].replace('Saving Throw: ', '').replace('Skill: ', '')} "
             f"+{p['value']}" for p in mon.get("proficiencies", [])]
    if profs:
        meta["Saves/Skills"] = ", ".join(profs)
    for label, key in (("Vulnerable", "damage_vulnerabilities"),
                       ("Resistant", "damage_resistances"),
                       ("Immune", "damage_immunities")):
        if mon.get(key):
            meta[label] = ", ".join(mon[key])
    if mon.get("condition_immunities"):
        meta["Condition Immunities"] = ", ".join(
            c["name"] for c in mon["condition_immunities"])
    senses = mon.get("senses", {})
    if senses:
        meta["Senses"] = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in senses.items())
    if mon.get("languages"):
        meta["Languages"] = mon["languages"]

    body = []
    for ab in mon.get("special_abilities", []) or []:
        body.append(f"**{ab['name']}.** {ab['desc']}")
    if mon.get("actions"):
        body.append("### Actions")
        for act in mon["actions"]:
            body.append(f"**{act['name']}.** {act['desc']}")
    if mon.get("legendary_actions"):
        body.append("### Legendary Actions")
        for act in mon["legendary_actions"]:
            body.append(f"**{act['name']}.** {act['desc']}")

    name_norm = mon["name"].lower()
    guarded = name_norm in COMMON_WORD_MONSTERS
    return Entry(
        id=f"dnd5e:monster:{mon['index']}",
        name=mon["name"],
        category="Monster",
        subtitle=subtitle,
        meta=meta,
        body=body,
        source="D&D 5e SRD",
        guarded=guarded,
        triggers=MONSTER_TRIGGERS if guarded else set(),
    )


def load_generic(folder: Path) -> list[Entry]:
    entries: list[Entry] = []
    for path in sorted(folder.glob("*.json")):
        if path.name.startswith("_"):
            continue
        for raw in _load_json(path):
            entries.append(Entry(
                id=raw.get("id") or f"{folder.name}:{raw['name'].lower().replace(' ', '-')}",
                name=raw["name"],
                category=raw.get("category", "Rule"),
                subtitle=raw.get("subtitle", ""),
                aliases=raw.get("aliases", []),
                meta=raw.get("meta", {}),
                body=raw.get("body", []),
                source=raw.get("source", folder.name),
                guarded=raw.get("guarded", False),
                triggers=set(raw.get("triggers", [])),
            ))
    return entries


def load_all() -> tuple[list[Entry], list[dict]]:
    """Load every ruleset folder. Returns (entries, ruleset summaries)."""
    all_entries: list[Entry] = []
    summaries: list[dict] = []
    if not RULESETS_DIR.exists():
        return all_entries, summaries
    for folder in sorted(RULESETS_DIR.iterdir()):
        if not folder.is_dir():
            continue
        if folder.name == "dnd5e":
            entries = load_dnd5e()
        else:
            entries = load_generic(folder)
        if entries:
            all_entries.extend(entries)
            summaries.append({"name": folder.name, "entries": len(entries)})
    return all_entries, summaries
