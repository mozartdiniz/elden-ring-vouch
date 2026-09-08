#!/usr/bin/env python3
"""What a status proc actually does — the damage, the duration, and the debuff.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

The collection has had the buildup figures since the beginning: how much frost a weapon
applies per hit. What it never had was what happens when the bar fills, so question 11.3 —
*"how is frostbite buildup calculated and what exactly does the proc do"* — was answered with
an honest refusal, and 11.6 and 11.4 with it. Both shipping models stopped on 11.3 three runs
each and said the collection has no rule for it.

They were right about the collection and wrong about the data. `StatusEffectData.csv` has been
vendored the whole time, 1,512 rows, and **no node read it**. That is the third instance in
this project of the table already knowing and the code not looking.

**It reports the spread rather than picking a figure.** A status is not one effect: frost has
six distinct ones across 268 rows, bleed thirteen across 270, because a player's weapon and an
enemy's attack apply the same status with different numbers. The most common is returned as
`typical` with the count that makes it typical, and every variant comes back beside it. A node
that picked one and said nothing would be answering a question about *a* frost proc as though
it were *the* frost proc.
"""

import collections
import csv
import json
import os
import sys

# The status a node exits with to refuse: it understood the question and there is no answer.
REFUSE = 3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "lib"))

import oracle  # noqa: E402

# What the proc does, as the game's own column names. Reported rather than reinterpreted: the
# figures are quotable as they stand, and inventing a unit for them here would be exactly the
# kind of small sum this collection refuses to hand a model.
EFFECT_FIELDS = (
    "effectEndurance",
    "changeHpRate",
    "changeHpPoint",
    "changeMpRate",
    "changeMpPoint",
    "neutralDamageCutRate",
)

# The buildup a source applies, per status. Already elsewhere in the collection for weapons;
# carried here so one call answers both halves of "how does this status work".
BUILDUP_FIELD = {
    "Poison": "poizonAttackPower",
    "Rot": "diseaseAttackPower",
    "Bleed": "bloodAttackPower",
    "Frost": "freezeAttackPower",
    "Sleep": "sleepAttackPower",
    "Madness": "madnessAttackPower",
    "Death": "curseAttackPower",
    "Eternal Sleep": "curseAttackPower",
}


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def rows():
    # The same path shape `lib/spells.py` uses. The extraction's version is in the directory
    # name on purpose: re-vendoring a different one should fail loudly here rather than read a
    # table that no longer matches the figures everything else is pinned against.
    path = os.path.join(
        oracle.ROOT, "oracle", "extracted", "Build-Planner-v1.19.1", "csv",
        "StatusEffectData.csv",
    )
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def variant(row):
    """The proc, as a dict of the fields that are not neutral."""
    out = {}
    for field in EFFECT_FIELDS:
        value = number(row[field])
        neutral = 1.0 if field == "neutralDamageCutRate" else 0.0
        if value != neutral and value != -1.0:
            out[field] = round(value, 6)
    return out


def main():
    request = json.load(sys.stdin)
    status = request["status"]

    table = rows()
    known = sorted({r["statusType"] for r in table})
    if status not in known:
        print(f"no status named {status!r}; the table has {', '.join(known)}", file=sys.stderr)
        sys.exit(REFUSE)

    mine = [r for r in table if r["statusType"] == status]
    counted = collections.Counter(
        json.dumps(variant(r), sort_keys=True) for r in mine
    )

    variants = [
        {
            "effect": json.loads(shape),
            "rows": count,
            # A proc that changes nothing is a row that carries buildup and no consequence —
            # Death is 197 of those, because what it does is not a number.
            "inert": json.loads(shape) == {},
        }
        for shape, count in counted.most_common()
    ]

    buildup_field = BUILDUP_FIELD.get(status, "")
    buildups = sorted({number(r[buildup_field]) for r in mine if number(r[buildup_field]) > 0})

    print(f"{status}: {len(mine)} rows, {len(variants)} distinct proc(s)", file=sys.stderr)

    result = {
        "status": status,
        "rows": len(mine),
        # The one most sources apply. Named rather than silently chosen: `typical_rows` of
        # `rows` is how much of the table agrees with it.
        "typical": variants[0]["effect"],
        "typical_rows": variants[0]["rows"],
        "variants": variants,
        "variant_count": len(variants),
        "buildup_field": buildup_field,
        "buildup_values": buildups,
        "statuses": known,
        # What this node does not have, said in the result rather than left to be discovered:
        # the rate a bar fills and drains is in no table here, so "why does a lower-buildup
        # weapon proc faster" cannot be computed from this.
        "accumulation_modelled": False,
        "fields": list(EFFECT_FIELDS),
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
