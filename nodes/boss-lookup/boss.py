#!/usr/bin/env python3
"""Resolve a boss, and report every phase of the fight separately.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

The numbers come from `data/BossResist.csv`, which is not the Build Planner extraction — it
comes from the Prometheux ontology, compiled from the community PvE data sheet. Health, poise,
per-type defences and negations, status resistances, at NG.

Three things about that table shape this node, and two of them are traps.

**A boss is not one set of numbers.** Phases are a game mechanic, not an ambiguity to be
refused: Rennala's first phase has 3493 health, no poise and *negative* physical negation,
while her second has 4097, 80 poise and twice the frost resistance. So a resolved boss comes
back as a list of phases, each with its own figures, and there is deliberately no
boss-level defence or negation to quote instead. An answer about "Rennala" that gives one
number is answering a question about a fight that does not exist.

**A name is not an identity.** Forty-seven names in the table appear more than once, because
the same enemy is fought in different places with different health — there are nine Death Rite
Birds, from 3442 to 28905. The identity of an encounter is its name *and* its location, and a
query that matches several locations resolves to nothing until one is chosen, exactly as an
ambiguous weapon name does.

**Immunity is not a large number.** The table writes 9999 in a resistance column to mean the
status cannot be applied at all. Passing that through invites an answer about how hard
something is to poison when the truth is that it cannot be poisoned, so it is reported in
`immune_to` instead.

Each phase's `negation` is on the percentage scale `optimal-affinity` expects, so the phase a
caller cares about can be handed straight to it. A negative negation means that phase takes
*more* of that damage type.
"""

import csv
import json
import os
import re
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

# "Rennala, Queen of the Full Moon - Bubble (Phase 1)" is the fight's own structure written
# into a name: a base, an optional variant, and an optional phase number.
PHASE = re.compile(r"^(?P<base>.+?)(?: - (?P<variant>[^(]+?))?\s*\(Phase (?P<phase>\d+)\)$")


def split_name(short_name):
    """The encounter this row belongs to, and what the table calls this part of it."""
    match = PHASE.match(short_name)
    if not match:
        return short_name, ""
    base = match.group("base").strip()
    variant = (match.group("variant") or "").strip()
    label = f"Phase {match.group('phase')}"
    return base, f"{variant} ({label})" if variant else label


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


def number(row, column):
    try:
        return float(row[column])
    except (TypeError, ValueError, KeyError):
        return 0.0


def phase_of(row, label):
    resist = {k: number(row, v) for k, v in RES_COLUMN.items()}
    negation = {d: number(row, NEG_COLUMN[d]) for d in DAMAGE}
    return {
        "label": label,
        "health": number(row, "Health"),
        "poise": number(row, "Poise"),
        "defence": {d: number(row, DEF_COLUMN[d]) for d in DAMAGE},
        "negation": negation,
        "resist": {k: (0.0 if v >= IMMUNE else v) for k, v in resist.items()},
        "immune_to": sorted(k for k, v in resist.items() if v >= IMMUNE),
        "weak_to": sorted(d for d in DAMAGE if negation[d] < 0),
    }


def main():
    request = json.load(sys.stdin)
    query = request["query"]
    wanted_location = (request.get("location") or "").strip()
    include_dlc = request.get("include_dlc", True)

    with open(BOSS_CSV, newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("ShortName")]
    if not include_dlc:
        rows = [r for r in rows if number(r, "IsDlc") == 0]

    # An encounter is a name in a place. Grouping on the name alone loses eight of the nine
    # Death Rite Birds and answers about whichever happened to be last in the file.
    encounters = {}
    for row in rows:
        base, label = split_name(row["ShortName"])
        location = (row.get("Location") or "").strip()
        encounters.setdefault((base, location), []).append((label, row))

    if wanted_location:
        target = normalize(wanted_location)
        encounters = {
            key: value for key, value in encounters.items() if target in normalize(key[1])
        }

    names = sorted({base for base, _ in encounters})
    candidates = resolve(query, names)

    # One name can still be several encounters. Both are ambiguity, and the caller needs to
    # know which kind: a different boss, or the same boss somewhere else.
    places = sorted(
        location for (base, location) in encounters if base in candidates
    ) if len(candidates) == 1 else []

    resolved = candidates[0] if len(candidates) == 1 and len(places) == 1 else ""
    print(
        f"{query!r} matched {len(candidates)} boss(es), {len(places)} location(s)",
        file=sys.stderr,
    )

    phases = []
    if resolved:
        seen = set()
        for label, row in encounters[(resolved, places[0])]:
            phase = phase_of(row, label)
            fingerprint = json.dumps(phase, sort_keys=True)
            if fingerprint not in seen:
                seen.add(fingerprint)
                phases.append(phase)
        # Fight order: by phase number, with the plain form of a phase before its variants,
        # so Rennala reads Phase 1, Bubble (Phase 1), Phase 2 rather than alphabetically.
        def order(phase):
            match = re.search(r"Phase (\d+)", phase["label"])
            return (
                int(match.group(1)) if match else 99,
                "(" in phase["label"] and not phase["label"].startswith("Phase"),
                phase["label"],
            )

        phases.sort(key=order)

    result = {
        "query": query,
        "resolved": resolved,
        "location": places[0] if resolved else "",
        "is_dlc": bool(number(encounters[(resolved, places[0])][0][1], "IsDlc"))
        if resolved
        else False,
        "match_count": len(candidates),
        "candidates": candidates[:MAX_CANDIDATES],
        "candidates_truncated": len(candidates) > MAX_CANDIDATES,
        "ambiguous": len(candidates) > 1 or len(places) > 1,
        # Which kind of ambiguity, so a caller asks the right follow-up question.
        "locations": places[:MAX_CANDIDATES] if len(places) > 1 else [],
        "catalog_size": len(names),
        # Every phase of the fight, each with its own figures. There is no boss-level defence
        # or negation on purpose: for a multi-phase fight there is no such number.
        "phases": phases,
        "phase_count": len(phases),
        "multi_phase": len(phases) > 1,
        # Whether the table names the phases. When it does not, several entries under one name
        # and location are what the sheet records, not a labelling this node invented.
        "phases_labelled": bool(phases) and all(p["label"] for p in phases),
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
