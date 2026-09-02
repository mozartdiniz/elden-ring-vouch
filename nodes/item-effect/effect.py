#!/usr/bin/env python3
"""What talismans, crystal tears and great runes do — individually and together.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

The tables are `EffectData.csv` from the Build Planner extraction, joined to the talisman,
crystal tear and great rune catalogues so an item's kind is known rather than guessed.

**It combines them.** A character wears up to four talismans, and asking what four talismans do
together means summing stat bonuses and multiplying rates. That is arithmetic, and arithmetic
left to a caller is arithmetic a model performs — the failure this whole collection keeps
closing upstream. So `combined` is returned alongside the per-item breakdown, and
postconditions check it against the parts.

**The multipliers come back in the shape the next node wants.** `attack_multiplier` carries all
eight damage kinds, with a physical bonus already expanded across strike, slash and pierce, so
it drops straight into `optimal-affinity`'s `damage_multiplier` without a caller reshaping it.

**Nothing here is applied automatically.** `planner.py` never modelled talisman effects, so
`character-build`, `equip-load` and `defence` all report figures *before* these. This node says
what an item is worth; putting that together with a build is the caller's job, and the numbers
to do it with are all returned.
"""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CSV_DIR = os.path.join(ROOT, "oracle", "extracted", "Build-Planner-v1.19.1", "csv")

STAT_COLUMN = {
    "vigor": "addLifeForceStatus", "mind": "addWillpowerStatus",
    "endurance": "addEndureStatus", "strength": "addStrengthStatus",
    "dexterity": "addDexterityStatus", "intelligence": "addMagicStatus",
    "faith": "addFaithStatus", "arcane": "addLuckStatus",
}
# One attack rate per element; physical covers its three subtypes.
ATTACK_COLUMN = {
    "physical": "physicsAttackPowerRate", "magic": "magicAttackPowerRate",
    "fire": "fireAttackPowerRate", "lightning": "thunderAttackPowerRate",
    "holy": "darkAttackPowerRate",
}
PHYSICAL_KINDS = ("physical", "strike", "slash", "pierce")
DAMAGE_KINDS = PHYSICAL_KINDS + ("magic", "fire", "lightning", "holy")
# What the wearer takes. Above 1.0 means *more* damage taken, as on Radagon's Soreseal.
TAKEN_COLUMN = {
    "physical": "neutralDamageCutRate", "strike": "blowDamageCutRate",
    "slash": "slashDamageCutRate", "pierce": "thrustDamageCutRate",
    "magic": "magicDamageCutRate", "fire": "fireDamageCutRate",
    "lightning": "thunderDamageCutRate", "holy": "darkDamageCutRate",
}
RESIST_COLUMN = {
    "poison": "changePoisonResistPoint", "scarlet_rot": "changeDiseaseResistPoint",
    "bleed": "changeBloodResistPoint", "frost": "changeFreezeResistPoint",
    "sleep": "changeSleepResistPoint", "madness": "changeMadnessResistPoint",
    "death": "changeCurseResistPoint",
}
RATE_COLUMN = {
    "max_hp": "maxHpRate", "max_fp": "maxMpRate",
    "max_stamina": "maxStaminaRate", "equip_load": "equipWeightChangeRate",
}

CATALOGUES = (
    ("talisman", "TalismanData.csv"),
    ("crystal tear", "CrystalTearData.csv"),
    ("great rune", "GreatRuneData.csv"),
)


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def effects():
    """EffectData keyed by name. Row 0 is a spacer; row 1 is the real header."""
    with open(os.path.join(CSV_DIR, "EffectData.csv"), newline="", encoding="utf-8") as h:
        rows = list(csv.reader(h))
    header = rows[1]
    out = {}
    for row in rows[2:]:
        record = dict(zip(header, row))
        if record.get("Name"):
            out.setdefault(record["Name"], record)
    return out


def kinds():
    """Which catalogue each name belongs to, so an item's kind is known rather than guessed."""
    out = {}
    for kind, filename in CATALOGUES:
        with open(os.path.join(CSV_DIR, filename), newline="", encoding="utf-8") as h:
            for row in csv.reader(h):
                if row and row[0] and row[0] != "Talisman" and not row[0].startswith("//"):
                    out.setdefault(row[0], kind)
    return out


def describe(name, record):
    stats = {s: int(number(record.get(c))) for s, c in STAT_COLUMN.items()}
    attack = {e: number(record.get(c), 1.0) or 1.0 for e, c in ATTACK_COLUMN.items()}

    return {
        "item": name,
        "text": (record.get("Effects") or "").strip(),
        "stats": stats,
        # Expanded to the eight kinds optimal-affinity's damage_multiplier expects: a physical
        # bonus applies to strike, slash and pierce as well.
        "attack_multiplier": {
            **{k: attack["physical"] for k in PHYSICAL_KINDS},
            **{e: attack[e] for e in ("magic", "fire", "lightning", "holy")},
        },
        # Above 1.0 means the wearer takes *more* of that damage type.
        "damage_taken": {
            k: number(record.get(c), 1.0) or 1.0 for k, c in TAKEN_COLUMN.items()
        },
        "resist": {s: number(record.get(c)) for s, c in RESIST_COLUMN.items()},
        "rates": {r: number(record.get(c), 1.0) or 1.0 for r, c in RATE_COLUMN.items()},
    }


def main():
    request = json.load(sys.stdin)
    items = request["items"]

    book = effects()
    catalogue = kinds()

    missing = [name for name in items if name not in book]
    if missing:
        print(f"no effect table entry for: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    described = [describe(name, book[name]) for name in items]
    print(f"{len(described)} item(s)", file=sys.stderr)

    combined_stats = {
        stat: sum(d["stats"][stat] for d in described) for stat in STAT_COLUMN
    }
    combined_attack = {
        kind: _product(d["attack_multiplier"][kind] for d in described)
        for kind in DAMAGE_KINDS
    }
    combined_taken = {
        kind: _product(d["damage_taken"][kind] for d in described) for kind in TAKEN_COLUMN
    }
    combined_resist = {
        status: sum(d["resist"][status] for d in described) for status in RESIST_COLUMN
    }
    combined_rates = {
        rate: _product(d["rates"][rate] for d in described) for rate in RATE_COLUMN
    }

    result = {
        "items": list(items),
        "kinds": [catalogue.get(name, "other") for name in items],
        "effects": described,
        "combined": {
            "stats": combined_stats,
            "attack_multiplier": combined_attack,
            "damage_taken": combined_taken,
            "resist": combined_resist,
            "rates": combined_rates,
        },
        # Some items only have prose: a tear that restores HP has no column to put it in.
        # Saying so keeps "no numbers" from being read as "no effect".
        "quantified": [d["item"] for d in described if _has_numbers(d)],
        "text_only": [d["item"] for d in described if not _has_numbers(d)],
        # Nothing in this collection applies these automatically.
        "applied_to_a_build": False,
    }
    json.dump(result, sys.stdout)


def _product(values):
    total = 1.0
    for value in values:
        total *= value
    return round(total, 9)


def _has_numbers(described):
    return (
        any(described["stats"].values())
        or any(v != 1.0 for v in described["attack_multiplier"].values())
        or any(v != 1.0 for v in described["damage_taken"].values())
        or any(described["resist"].values())
        or any(v != 1.0 for v in described["rates"].values())
    )


if __name__ == "__main__":
    main()
