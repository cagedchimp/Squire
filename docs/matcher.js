// Fuzzy rule matcher — JS port of app/matcher.py.
// Matches spoken text against a closed vocabulary of rule/spell names.
// No AI calls: instant, deterministic, free.

const WORD_RE = /[a-z0-9']+/g;

export function tokenize(text) {
  return (text.toLowerCase().match(WORD_RE)) || [];
}

export function normalizeName(name) {
  return tokenize(name).join(' ');
}

// rapidfuzz-style indel ratio: 2*LCS / (len_a + len_b) * 100
function lcsLength(a, b) {
  const m = a.length, n = b.length;
  let prev = new Int16Array(n + 1);
  let curr = new Int16Array(n + 1);
  for (let i = 1; i <= m; i++) {
    const ca = a.charCodeAt(i - 1);
    for (let j = 1; j <= n; j++) {
      curr[j] = ca === b.charCodeAt(j - 1)
        ? prev[j - 1] + 1
        : Math.max(prev[j], curr[j - 1]);
    }
    [prev, curr] = [curr, prev];
  }
  return prev[n];
}

export function ratio(a, b) {
  if (!a.length || !b.length) return 0;
  if (a === b) return 100;
  return (200 * lcsLength(a, b)) / (a.length + b.length);
}

export class RuleMatcher {
  constructor(entries, cooldownMs = 20000) {
    this.entries = entries;
    this.cooldownMs = cooldownMs;
    this.lastShown = new Map(); // entry id -> timestamp
    // Bucket lookup keys by word count so an n-gram is only compared
    // against names of the same length.
    this.keysByLen = new Map(); // n -> [{key, idx}]
    entries.forEach((entry, idx) => {
      const keys = new Set([normalizeName(entry.name),
                            ...(entry.aliases || []).map(normalizeName)]);
      for (const key of keys) {
        if (!key) continue;
        const n = key.split(' ').length;
        if (!this.keysByLen.has(n)) this.keysByLen.set(n, []);
        this.keysByLen.get(n).push({ key, idx });
      }
    });
  }

  match(text) {
    const tokens = tokenize(text);
    if (!tokens.length) return [];

    const candidates = []; // {n, score, pos, idx}
    for (const [n, bucket] of this.keysByLen) {
      if (n > tokens.length) continue;
      const cutoff = n === 1 ? 92 : 87;
      for (let i = 0; i <= tokens.length - n; i++) {
        const gram = tokens.slice(i, i + n).join(' ');
        if (n === 1 && gram.length < 3) continue;
        let best = null, bestScore = cutoff;
        for (const { key, idx } of bucket) {
          // upper bound prune before the DP
          const maxPossible = (200 * Math.min(gram.length, key.length))
                              / (gram.length + key.length);
          if (maxPossible < bestScore) continue;
          const r = ratio(gram, key);
          if (r >= bestScore) { bestScore = r; best = idx; }
        }
        if (best === null) continue;
        const entry = this.entries[best];
        // Guard only single-word matches: multi-word phrases are specific.
        if (n === 1 && entry.guarded && entry.triggers?.length) {
          const windowTokens = new Set(
            tokens.slice(Math.max(0, i - 6), i + n + 3));
          if (!entry.triggers.some(t => windowTokens.has(t))) continue;
        }
        candidates.push({ n, score: bestScore, pos: i, idx: best });
      }
    }

    // Prefer longer, higher-scoring matches; drop overlapping spans.
    candidates.sort((a, b) => b.n - a.n || b.score - a.score);
    const used = new Set(), seenIds = new Set(), accepted = [];
    const now = Date.now();
    for (const c of candidates) {
      const entry = this.entries[c.idx];
      let overlaps = false;
      for (let p = c.pos; p < c.pos + c.n; p++) if (used.has(p)) overlaps = true;
      if (overlaps || seenIds.has(entry.id)) continue;
      if (now - (this.lastShown.get(entry.id) || 0) < this.cooldownMs) continue;
      for (let p = c.pos; p < c.pos + c.n; p++) used.add(p);
      seenIds.add(entry.id);
      this.lastShown.set(entry.id, now);
      accepted.push({ pos: c.pos, entry });
    }
    accepted.sort((a, b) => a.pos - b.pos); // spoken order
    return accepted.map(a => a.entry);
  }

  resetCooldowns() { this.lastShown.clear(); }
}
