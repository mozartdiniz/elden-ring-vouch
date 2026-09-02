#!/usr/bin/env python3
"""Resolve a boss by name, and report what it takes and what it resists.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

The numbers come from `data/BossResist.csv`, which is not the Build Planner extraction — it
comes from the Prometheux ontology, compiled from the community PvE data sheet. Health,
defences, negations, status resistances and poise, at NG.

Two things this does beyond looking a row up.

**A phase is a different fight.** Bosses appear once per phase, and the phases are not alike:
Rennala Phase 1 has 3493 health, no poise and *negative* physical negation, while Phase 2 has
4097, 80 poise and doubles its fire, lightning and holy resistance. "rennala" matches three
rows — both phases and the bubble — so it resolves to nothing and the caller has to ask which
was meant, exactly as an ambiguous weapon name does.

**Immunity is not a large number.** The table writes 9999 in a resistance column to mean the
status cannot be applied at all. Passing that through as a number invites an answer about how
hard something is to poison when the truth is that it cannot be poisoned, so it is reported
in `immune_to` instead.

`negation` is on the same percentage scale `optimal-affinity` expects, so a boss's figures can
be handed straight to it. A negative negation means the boss takes *more* of that damage type
than the raw number suggests.
"""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BOSS_CSV = os.path.join(ROOT, "data", "BossResist.csv")

# The table's own sentinel: this status cannot be applied at all.
IMMUNE = 9999.0

DAMAGE = ("physical", "strike", "slash", "pierce", "magic", "fire", "lightning", "holy")
DEF_COLUMN = {
    "physical": "DefPhys", "strike": "DefStrike", "slash": "DefSlash",
    "pierce": "DefPierce", "magic": "DefMagic", "fire": "DefFire",
    "lightning": "DefLtng", "holy": "DefHoly",
}
NEG_COLUMN = {
    "physical": "NegPhys", "strike": "NegStrike", "slash": "NegSlash",
    "pierce": "NegPierce", "magic": "NegMagic", "fire": "NegFire",
    "lightning": "NegLtng", "holy": "NegHoly",
}
RES_COLUMN = {
    "poison": "ResPoison", "scarlet_rot": "ResRot", "bleed": "ResBleed",
    "frost": "ResFrost", "sleep": "ResSleep", "madness": "ResMadness",
    "death": "ResDeath",
}

MAX_CANDIDATES = 20


def normalize(text):
    text = text.lower().replace("'", "").replace("’", "")
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())


def resolve(query, names):
    target = normalize(query)
    exact = [name for name in names if normalize(name) == target]
    if exact:
        return exact
    tokens = target.split()
    if not tokens:
        return []
    return sorted(name for name in names if all(t in normalize(name) for t in tokens))


def main():
    request = json.load(sys.stdin)
    query = request["query"]
    include_dlc = request.get("include_dlc", True)

    with open(BOSS_CSV, newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("ShortName")]
    if not include_dlc:
        rows = [r for r in rows if float(r.get("IsDlc") or 0) == 0]
    catalog = {r["ShortName"]: r for r in rows}

    candidates = resolve(query, list(catalog))
    print(f"{query!r} matched {len(candidates)} of {len(catalog)}", file=sys.stderr)

    resolved = candidates[0] if len(candidates) == 1 else ""
    row = catalog[resolved] if resolved else None

    def num(column):
        return float(row[column]) if row else 0.0

    resist = {k: num(v) for k, v in RES_COLUMN.items()} if row else {
        k: 0.0 for k in RES_COLUMN
    }

    result = {
        "query": query,
        "resolved": resolved,
        "location": (row.get("Location") or "") if row else "",
        "is_dlc": bool(float(row.get("IsDlc") or 0)) if row else False,
        "match_count": len(candidates),
        "candidates": candidates[:MAX_CANDIDATES],
        "candidates_truncated": len(candidates) > MAX_CANDIDATES,
        "ambiguous": len(candidates) > 1,
        "catalog_size": len(catalog),
        "health": num("Health"),
        "poise": num("Poise"),
        # Straight into optimal-affinity's `defense` and `negation`, which are on these scales.
        "defence": {d: num(DEF_COLUMN[d]) for d in DAMAGE} if row else {d: 0.0 for d in DAMAGE},
        "negation": {d: num(NEG_COLUMN[d]) for d in DAMAGE} if row else {d: 0.0 for d in DAMAGE},
        # 9999 means the status cannot be applied. Reported separately, and left out of the
        # numbers, so nobody answers "how hard is it to poison" about something unpoisonable.
        "resist": {k: (0.0 if v >= IMMUNE else v) for k, v in resist.items()},
        "immune_to": sorted(k for k, v in resist.items() if v >= IMMUNE),
        # The damage types this boss takes more of than its defence alone implies.
        "weak_to": sorted(
            d for d in DAMAGE
            if row and num(NEG_COLUMN[d]) < 0
        ),
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
