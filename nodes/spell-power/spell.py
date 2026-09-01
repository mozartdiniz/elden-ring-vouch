#!/usr/bin/env python3
"""Spell attack power for one spell cast from one catalyst by one build.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

Three tables meet here, and they do not all come from the same place — which matters when
reading the answer:

- The **catalyst's spell buff** is `oracle/scripts/planner.py`, unmodified. It is the number
  the game shows on a staff or seal, and it carries all the stat scaling.
- The **spell's attack** and its requirements are `MagicData.csv`, from the Build Planner
  extraction.
- The **family bonus** — a staff that boosts one school of magic — needs to know which family
  a spell belongs to, and the Build Planner does not publish that. `data/MagicFamily.csv`
  does, and it came from the Prometheux ontology rather than the spreadsheet. `bonus_source`
  says when a bonus was applied, so an answer can be as sure as its weakest table.

The final step, `attack = magic_attack x spell_buff / 100 x bonus`, is the one piece of
arithmetic in this collection that is not the oracle's: the Python scripts stop at the spell
buff. It is pinned in `cases.toml` against figures the Prometheux implementation produced
independently, which is the closest thing to a second opinion available.

A staff whose bonus is already inside its spell buff — Lusat's, which trades FP cost for raw
power across every school — has a non-numeric rate in the table, and gets a multiplier of 1.
Applying it again would double-count.
"""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "lib"))

import oracle  # noqa: E402

sys.path.insert(0, oracle.SCRIPTS)
import planner  # noqa: E402

MAGIC_CSV = os.path.join(
    ROOT, "oracle", "extracted", "Build-Planner-v1.19.1", "csv", "MagicData.csv"
)
FAMILY_CSV = os.path.join(ROOT, "data", "MagicFamily.csv")


def spells():
    """Spells keyed by their **display** name, which is the one that is unique.

    `Name` is not: "Comet" is three rows — the plain cast at 292 magic attack, and two charged
    variants at 365. Keying on it silently keeps whichever came last, which is how this node
    first reported a charged Comet as an ordinary one. `Display Name` distinguishes them
    ("Comet", "Comet - Charged", "Comet - Charged (AoE)"), so it is the key, and a caller
    asking for the base name gets the base cast.
    """
    with open(MAGIC_CSV, newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("ID") and r["Name"]]

    book = {}
    for row in rows:
        display = (row.get("Display Name") or row["Name"]).strip()
        book.setdefault(display, row)
    return book


def variants(book, name):
    """Every named form of a spell — the plain cast and its charged variants."""
    return sorted(
        display
        for display, row in book.items()
        if row["Name"] == name or display == name
    )


def families():
    with open(FAMILY_CSV, newline="", encoding="utf-8") as handle:
        out = {}
        for row in csv.DictReader(handle):
            out.setdefault(row["Name"], []).append(row["Family"])
    return out


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def main():
    request = json.load(sys.stdin)
    spell_name = request["spell"]
    catalyst = request["catalyst"]

    catalog, _ = oracle.weapons()
    row = catalog.get(catalyst)
    if row is None:
        print(f"no weapon named {catalyst!r}", file=sys.stderr)
        sys.exit(1)

    book = spells()
    spell = book.get(spell_name)
    if spell is None:
        print(f"no spell named {spell_name!r}", file=sys.stderr)
        sys.exit(1)
    forms = variants(book, spell["Name"])

    build = planner.PlannerInputs(
        starting_class=request.get("starting_class", "Wretch"),
        strength=request["strength"],
        dexterity=request["dexterity"],
        intelligence=request["intelligence"],
        faith=request["faith"],
        arcane=request["arcane"],
        rh1=planner.WeaponSlotIn(
            weapon=catalyst, affinity="Standard", upgrade=request["upgrade"]
        ),
    )
    r = planner.Planner().calculate(build)
    slot = next(w for w in r.weapons if w.slot == "RH1")
    spell_buff = float(slot.spell_buff)

    # A staff boosts one family of spells. `castingBonusRate` is not always a number: Lusat's
    # reads "1.5x FP cost", because its bonus is already inside the spell buff above.
    bonus_family = row.get("castingBonusType") or ""
    bonus_rate = number(row.get("castingBonusRate"), 0.0)
    spell_families = families().get(spell_name, [])
    applies = bonus_rate > 0 and bonus_family in spell_families
    bonus = bonus_rate if applies else 1.0

    magic_attack = number(spell.get("MagicAtk"))
    attack = magic_attack * spell_buff / 100.0 * bonus
    print(
        f"{spell_name} from {catalyst} +{request['upgrade']}: "
        f"SB {spell_buff:.1f} x {bonus}",
        file=sys.stderr,
    )

    requirement = {
        "intelligence": int(number(spell.get("requirementIntellect"))),
        "faith": int(number(spell.get("requirementFaith"))),
        "arcane": int(number(spell.get("requirementLuck"))),
    }
    castable = (
        request["intelligence"] >= requirement["intelligence"]
        and request["faith"] >= requirement["faith"]
        and request["arcane"] >= requirement["arcane"]
    )

    result = {
        "spell": spell_name,
        "spell_type": spell.get("Type") or "",
        # A charged cast is a different spell with the same name and a different attack. Naming
        # the other forms keeps an answer about "Comet" from being read as covering all three.
        "forms": forms,
        "catalyst": catalyst,
        "catalyst_class": row["Weapon Class"],
        "upgrade": int(request["upgrade"]),
        "max_upgrade": oracle.max_upgrade(row),
        "spell_buff": spell_buff,
        "magic_attack": magic_attack,
        "bonus": bonus,
        "bonus_applied": applies,
        # Named so an answer can say *why* a staff is better, not just that it is.
        "bonus_family": bonus_family if applies else "",
        "spell_families": sorted(spell_families),
        "family_source": "MagicFamily.csv (Prometheux ontology)" if applies else "",
        "attack": attack,
        "attack_shown": int(attack),
        "fp_cost": number(spell.get("mp")),
        "requirement": requirement,
        "castable": castable,
        "unmet": sorted(
            stat for stat, need in requirement.items() if request[stat] < need
        ),
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
