#!/usr/bin/env python3
"""Who a character can play with, and what upgrade keeps them there.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

Every Pattern 10 question in `VALIDATION.md` is half a stat spread and half this: "monta os
status e diz o upgrade de arma que me mantém no matchmaking de Stormveil". `build-allocate`
does the first half and nothing did the second, which is a shame, because it is the most
deterministic thing in the game — two formulas and a lookup table, all of them in the
extraction and none of them ported until now.

**The level bands are the spreadsheet's formulas, unchanged.** Summon signs are
`level x 0.9 - 10` to `level x 1.1 + 10`, a cipher ring widens that to ±15, an invasion is
`level x 0.9` to `level x 1.1 + 20`, and each has a *different* range for being summoned than
for summoning — which is the part people get wrong.

**The weapon range is a lookup, not a formula**, and a somber upgrade is worth 2.5 standard
ones: `TRUNC(upgrade x 2.5)` is the conversion the sheet uses, so a somber +6 matches like a
standard +15.

**Areas are the soft part.** `data/AreaLevel.csv` says which level band an area is built for,
and that is somebody's judgement where a matchmaking range is arithmetic. It is reported
separately and labelled, so an answer can be as sure as its weakest table.
"""

import csv
import json
import math
import os
import sys

# The status a node exits with to refuse: it understood the question and there is no answer.
# vouch turns it into exit 16, a refusal, with this node's stderr as the reason — where every
# non-zero exit used to become exit 20, a defect, which tells the caller the node is broken
# and throws away the rest of their question along with the part that had none.
REFUSE = 3

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
MATCH_CSV = os.path.join(
    ROOT, "oracle", "extracted", "Build-Planner-v1.19.1", "csv", "MatchmakingCalcData.csv"
)
AREA_CSV = os.path.join(ROOT, "data", "AreaLevel.csv")

MAX_LEVEL = 713


def excel_round(value):
    """Excel rounds halves away from zero; Python rounds them to even."""
    return int(math.floor(value + 0.5)) if value >= 0 else -int(math.floor(-value + 0.5))


def band(level, spread, cap_low, cap_high):
    """One channel's four figures, straight from the sheet.

    `summoning` is who this character can put a sign down for; `summoned_by` is who can call
    them. They are not the same range, and the sheet computes them separately.
    """
    if level >= cap_low:
        return {
            "summoning": {"lower": cap_low, "upper": MAX_LEVEL},
            "summoned_by": {"lower": cap_low, "upper": MAX_LEVEL},
        }
    low = max(level * 0.9 - spread, 1)
    high = min(level * 1.1 + spread, cap_high)
    by_low = max((level - spread) / 1.1, 1)
    by_high = min((level + spread) / 0.9, cap_high)
    return {
        "summoning": {"lower": excel_round(low), "upper": excel_round(high - 0.01)},
        "summoned_by": {"lower": excel_round(by_low + 0.05), "upper": excel_round(by_high)},
    }


def invasion_band(level):
    """Invasions drop the -10 on the bottom and widen the top to +20."""
    if level >= 301:
        return {
            "invading": {"lower": 301, "upper": MAX_LEVEL},
            "invaded_by": {"lower": 301, "upper": MAX_LEVEL},
        }
    return {
        "invading": {
            "lower": excel_round(max(level * 0.9, 1)),
            "upper": excel_round(min(level * 1.1 + 20, 300) - 0.01),
        },
        "invaded_by": {
            "lower": excel_round(max((level - 20) / 1.1, 1) + 0.05),
            "upper": excel_round(min(level / 0.9, 300)),
        },
    }


def reinforce_table():
    """`{reinforce: (lower, upper, somber_lower, somber_upper)}` from the sheet's own columns."""
    with open(MATCH_CSV, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    table = {}
    for row in rows:
        if len(row) < 11 or not row[6]:
            continue
        try:
            table[int(float(row[6]))] = tuple(int(float(row[i] or 0)) for i in (7, 8, 9, 10))
        except ValueError:
            continue
    return table


def areas():
    with open(AREA_CSV, newline="", encoding="utf-8") as handle:
        return [r for r in csv.DictReader(handle) if r.get("Area")]


def main():
    request = json.load(sys.stdin)
    level = int(request["level"])
    upgrade = request.get("upgrade")
    somber = bool(request.get("somber", False))
    wanted_area = (request.get("area") or "").strip().lower()

    table = reinforce_table()
    # A somber upgrade is worth two and a half standard ones. Comparing a somber +6 against a
    # standard +6 is the mistake this conversion exists to stop.
    effective = int(upgrade * 2.5) if (upgrade is not None and somber) else upgrade

    weapon_range = None
    if upgrade is not None:
        row = table.get(effective if somber else upgrade)
        if row is None:
            print(f"no matchmaking row for upgrade {upgrade}", file=sys.stderr)
            sys.exit(REFUSE)
        weapon_range = {
            "standard": {"lower": row[0], "upper": row[1]},
            "somber": {"lower": row[2], "upper": row[3]},
        }

    rows = areas()
    fits = [
        {
            "area": r["Area"],
            "level_min": float(r["LevelMin"]),
            "level_max": float(r["LevelMax"]),
            "note": (r.get("SmithingHint") or "").strip(),
        }
        for r in rows
        if float(r["LevelMin"]) <= level <= float(r["LevelMax"])
    ]
    named = None
    if wanted_area:
        for r in rows:
            if wanted_area in r["Area"].lower():
                named = {
                    "area": r["Area"],
                    "level_min": float(r["LevelMin"]),
                    "level_max": float(r["LevelMax"]),
                    "level_fits": float(r["LevelMin"]) <= level <= float(r["LevelMax"]),
                }
                break

    print(
        f"RL{level}"
        + (f" +{upgrade}{' somber' if somber else ''}" if upgrade is not None else "")
        + f": {len(fits)} areas in band",
        file=sys.stderr,
    )

    result = {
        "level": level,
        "upgrade": upgrade,
        "somber": somber,
        "effective_upgrade": effective,
        "summon_signs": band(level, 10, 306, 305),
        "cipher_ring": band(level, 15, 306, 305),
        "invasions": invasion_band(level),
        "weapon_range": weapon_range,
        "areas_in_band": fits,
        "area": named,
        "area_source": "AreaLevel.csv (Prometheux ontology) — a judgement, not a matchmaking rule",
        "max_level": MAX_LEVEL,
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
