"""Fuzzy rule matcher.

Matches spoken text against a closed vocabulary of rule/spell names using
rapidfuzz. No AI calls — instant, deterministic, and free.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

_WORD = re.compile(r"[a-z0-9']+")


def tokenize(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def normalize_name(name: str) -> str:
    return " ".join(_WORD.findall(name.lower()))


@dataclass
class Entry:
    id: str
    name: str
    category: str
    subtitle: str = ""
    aliases: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    body: list[str] = field(default_factory=list)
    source: str = ""
    ruleset: str = ""  # folder name; used for enable/disable filtering
    # Guarded entries have names that are common English words ("Shield",
    # "Light", "History"). They only match when a trigger word ("cast",
    # "check", ...) is heard nearby, to avoid constant false positives.
    guarded: bool = False
    triggers: set = field(default_factory=set)

    def to_card(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "subtitle": self.subtitle,
            "meta": self.meta,
            "body": self.body,
            "source": self.source,
        }


class RuleMatcher:
    def __init__(self, entries: list[Entry], cooldown: float = 20.0):
        self.entries = list(entries)
        self.cooldown = cooldown
        self._last_shown: dict[str, float] = {}
        # Bucket lookup keys by word count so an n-gram is only compared
        # against names of the same length.
        self._keys_by_len: dict[int, tuple[list[str], list[int]]] = {}
        for idx, entry in enumerate(self.entries):
            keys = {normalize_name(entry.name)}
            keys.update(normalize_name(a) for a in entry.aliases)
            for key in keys:
                if not key:
                    continue
                n = len(key.split())
                bucket = self._keys_by_len.setdefault(n, ([], []))
                bucket[0].append(key)
                bucket[1].append(idx)

    def match(self, text: str) -> list[Entry]:
        tokens = tokenize(text)
        if not tokens:
            return []

        candidates: list[tuple[int, float, int, int]] = []  # (n, score, pos, entry_idx)
        for n, (keys, idxs) in self._keys_by_len.items():
            if n > len(tokens):
                continue
            cutoff = 92 if n == 1 else 87
            for i in range(len(tokens) - n + 1):
                gram = " ".join(tokens[i : i + n])
                if n == 1 and len(gram) < 3:
                    continue
                hit = process.extractOne(gram, keys, scorer=fuzz.ratio, score_cutoff=cutoff)
                if hit is None:
                    continue
                _, score, key_idx = hit
                entry = self.entries[idxs[key_idx]]
                # Guard only single-word matches: a multi-word phrase like
                # "half cover" or "long rest" is specific enough on its own.
                if n == 1 and entry.guarded and entry.triggers:
                    window = set(tokens[max(0, i - 6) : i + n + 3])
                    if not (window & entry.triggers):
                        continue
                candidates.append((n, score, i, idxs[key_idx]))

        # Prefer longer, higher-scoring matches; drop overlapping spans.
        candidates.sort(key=lambda c: (-c[0], -c[1]))
        used_positions: set[int] = set()
        accepted: list[tuple[int, Entry]] = []
        seen_ids: set[str] = set()
        now = time.time()
        for n, score, i, entry_idx in candidates:
            span = set(range(i, i + n))
            entry = self.entries[entry_idx]
            if span & used_positions or entry.id in seen_ids:
                continue
            if now - self._last_shown.get(entry.id, 0.0) < self.cooldown:
                continue
            used_positions |= span
            seen_ids.add(entry.id)
            self._last_shown[entry.id] = now
            accepted.append((i, entry))

        accepted.sort(key=lambda a: a[0])  # in spoken order
        return [entry for _, entry in accepted]

    def reset_cooldowns(self) -> None:
        self._last_shown.clear()
