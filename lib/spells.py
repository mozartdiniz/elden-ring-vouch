"""The spell tables, and the one multiply in this collection that is not the oracle's.

`MagicData.csv` is part of the Build Planner extraction and lives in `oracle/`. The family
table is not: `data/MagicFamily.csv` came from the Prometheux ontology, and a catalyst's
family bonus cannot be applied without it.

Two nodes need all of this — `spell-power`, which prices one spell, and `build-allocate`,
which searches for the spread that maximises one — so it lives here rather than in either.
The scripts in `oracle/` stop at the catalyst's spell buff; everything below that line is
this collection's, which is why it is in one place with the reasoning attached.
"""

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MAGIC_CSV = os.path.join(
    ROOT, "oracle", "extracted", "Build-Planner-v1.19.1", "csv", "MagicData.csv"
)
FAMILY_CSV = os.path.join(ROOT, "data", "MagicFamily.csv")

# The five columns a spell's attack can live in. `MagicAtk` alone covers the sorceries and
# none of the incantations: Black Flame's 244 is in `FireAtk`, and reading only the magic
# column priced every incantation in the game at nothing.
ATTACK_COLUMN = {
    "physical": "PhysAtk",
    "magic": "MagicAtk",
    "fire": "FireAtk",
    "lightning": "LtngAtk",
    "holy": "HolyAtk",
}


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def book():
    """Spells keyed by their **display** name, which is the one that is unique.

    `Name` is not: "Comet" is three rows — the plain cast at 292 magic attack, and two charged
    variants at 365. Keying on it silently keeps whichever came last, which is how a charged
    Comet was once reported as an ordinary one. `Display Name` distinguishes them ("Comet",
    "Comet - Charged", "Comet - Charged (AoE)"), so it is the key, and a caller asking for the
    base name gets the base cast.
    """
    with open(MAGIC_CSV, newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("ID") and r["Name"]]

    out = {}
    for row in rows:
        display = (row.get("Display Name") or row["Name"]).strip()
        out.setdefault(display, row)
    return out


def variants(spells, name):
    """Every named form of a spell — the plain cast and its charged variants."""
    return sorted(
        display for display, row in spells.items() if row["Name"] == name or display == name
    )


def families():
    with open(FAMILY_CSV, newline="", encoding="utf-8") as handle:
        out = {}
        for row in csv.DictReader(handle):
            out.setdefault(row["Name"], []).append(row["Family"])
    return out


def base_attack(spell):
    """The spell's own attack per damage type, before any catalyst."""
    return {damage: number(spell.get(column)) for damage, column in ATTACK_COLUMN.items()}


def bonus(catalyst_row, spell_name, spell_families):
    """The catalyst's family multiplier for this spell, and whether it applied.

    `castingBonusRate` is not always a number: Lusat's reads "1.5x FP cost", because its bonus
    is already inside the spell buff. Applying it again would double-count, so a non-numeric
    rate is no bonus at all.
    """
    family = catalyst_row.get("castingBonusType") or ""
    rate = number(catalyst_row.get("castingBonusRate"), 0.0)
    applies = rate > 0 and family in spell_families
    return (rate if applies else 1.0), applies, (family if applies else "")


def requirement(spell):
    return {
        "intelligence": int(number(spell.get("requirementIntellect"))),
        "faith": int(number(spell.get("requirementFaith"))),
        "arcane": int(number(spell.get("requirementLuck"))),
    }


def attack_by_type(base, spell_buff, family_bonus):
    """`base x spell_buff / 100 x bonus`, per damage type. The one multiply that is ours."""
    return {
        damage: value * spell_buff / 100.0 * family_bonus for damage, value in base.items()
    }
