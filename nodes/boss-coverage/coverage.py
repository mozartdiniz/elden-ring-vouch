#!/usr/bin/env python3
"""Which damage type or status works across a set of bosses, and where it does not.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

`boss-lookup` answers "what are this fight's numbers". Pattern 7 of the validation battery asks
the other way round — "which element covers the most bosses", "which DLC bosses are immune to
frostbite", "holy is bad against which endgame bosses" — and those are queries across the whole
table, which nothing here could do. An agent told to call `boss-lookup` 238 times would answer
from memory instead.

Two modes, because they are two questions:

**Damage coverage.** For each fight, the negation of every damage type asked about, and which
of them the fight takes most. The summary counts, per type, how many fights it is best against
and how many resist it hardest. Negation is a percentage: higher is worse for the attacker, and
a *negative* figure means the fight takes extra.

**Status coverage.** For each fight, whether a status can be applied at all and how much
buildup it resists. `9999` in the table means immune, and immune is not "tough": no amount of
buildup does anything.

**Every row is a phase, not a boss.** Rennala's bubble negates 100% of everything and her first
phase takes extra physical; one row for "Rennala" would be a number about a fight that does not
exist. `phases` counts what a name covers.
"""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BOSS_CSV = os.path.join(ROOT, "data", "BossResist.csv")

IMMUNE = 9999.0
DAMAGE = ("physical", "strike", "slash", "pierce", "magic", "fire", "lightning", "holy")
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


def number(row, column):
    try:
        return float(row[column])
    except (TypeError, ValueError, KeyError):
        return 0.0


def main():
    request = json.load(sys.stdin)
    types = list(request.get("damage_types") or [])
    statuses = list(request.get("statuses") or [])
    if not types and not statuses:
        types = ["physical", "magic", "fire", "lightning", "holy"]
    dlc = request.get("dlc")
    names = [n.lower() for n in (request.get("bosses") or [])]
    min_health = float(request.get("min_health", 0))
    limit = int(request.get("limit", 25))
    sort_by = request.get("sort_by", "health")

    with open(BOSS_CSV, newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("ShortName")]

    catalog_size = len(rows)
    if dlc is not None:
        rows = [r for r in rows if (number(r, "IsDlc") == 1.0) == bool(dlc)]
    if names:
        rows = [r for r in rows if any(n in r["ShortName"].lower() for n in names)]
    if min_health:
        rows = [r for r in rows if number(r, "Health") >= min_health]

    fights = []
    for row in rows:
        negation = {d: number(row, NEG_COLUMN[d]) for d in types}
        resist = {s: number(row, RES_COLUMN[s]) for s in statuses}
        best = min(negation, key=lambda d: (negation[d], d)) if negation else ""
        worst = max(negation, key=lambda d: (negation[d], d)) if negation else ""
        # Ties are common — a fight that negates fire, lightning and holy at 40 apiece has no
        # best element — and counting the alphabetically first one as a win would quietly
        # inflate whichever type sorts earliest.
        best_types = sorted(d for d in negation if negation[d] == negation.get(best, 0.0))
        fights.append({
            "fight": row["ShortName"],
            "location": row["Location"],
            "is_dlc": number(row, "IsDlc") == 1.0,
            "health": number(row, "Health"),
            "negation": negation,
            "best_type": best if len(best_types) == 1 else "",
            "best_types": best_types,
            "best_negation": negation.get(best, 0.0),
            "worst_type": worst,
            "worst_negation": negation.get(worst, 0.0),
            "takes_extra_from": sorted(d for d in types if negation[d] < 0),
            "resist": {s: (0.0 if v >= IMMUNE else v) for s, v in resist.items()},
            "immune_to": sorted(s for s, v in resist.items() if v >= IMMUNE),
        })

    key = {
        "health": lambda f: (-f["health"], f["fight"]),
        "name": lambda f: f["fight"],
        "best_negation": lambda f: (f["best_negation"], f["fight"]),
    }[sort_by]
    fights.sort(key=key)

    # The summary is the answer to "which element covers the most fights"; the per-fight rows
    # are what makes it checkable.
    summary = {}
    for damage in types:
        summary[damage] = {
            "best_against": sum(1 for f in fights if f["best_type"] == damage),
            "tied_best_against": sum(
                1 for f in fights if damage in f["best_types"] and not f["best_type"]
            ),
            "takes_extra": sum(1 for f in fights if f["negation"][damage] < 0),
            "resisted_50_or_more": sum(1 for f in fights if f["negation"][damage] >= 50),
            "fully_negated": sum(1 for f in fights if f["negation"][damage] >= 100),
            "average_negation": round(
                sum(f["negation"][damage] for f in fights) / len(fights), 4
            ) if fights else 0.0,
        }
    status_summary = {}
    for status in statuses:
        status_summary[status] = {
            "immune": sum(1 for f in fights if status in f["immune_to"]),
            "usable": sum(1 for f in fights if status not in f["immune_to"]),
            "average_resist": round(
                sum(f["resist"][status] for f in fights) / len(fights), 4
            ) if fights else 0.0,
        }

    best_overall = ""
    if summary:
        best_overall = min(
            summary, key=lambda d: (summary[d]["average_negation"], d)
        )
    print(
        f"{len(fights)} phases of {catalog_size}; best on average: {best_overall or 'n/a'}",
        file=sys.stderr,
    )

    result = {
        "fights": fights[:limit],
        "damage_types": types,
        "statuses": statuses,
        "summary": summary,
        "status_summary": status_summary,
        # Lowest average negation across the fights asked about. A coverage answer, not a
        # per-fight one: the winner on average can still be the worst choice for one boss.
        "best_on_average": best_overall,
        "dlc": dlc,
        "bosses": request.get("bosses") or [],
        "sort_by": sort_by,
        "catalog_size": catalog_size,
        "phases": len(fights),
        "limit": limit,
        "returned": len(fights[:limit]),
        "truncated": len(fights) > limit,
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
