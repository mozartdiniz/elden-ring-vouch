"""Which affinities an ash of war accepts, and which weapons it can go on.

`AshCompat` — the table already here — carries the affinity an ash *comes with* and whether it
fits any weapon. Neither answers "qual Ash aceita Blood?", which is the question every Pattern 6
question in `VALIDATION.md` turns on. `data/AshAffinity.csv` does: 982 rows, one per skill and
affinity it accepts. `data/AshClass.csv` is the same for weapon classes, with three aggregates
— `AllMelee`, `Sword`, `Polearm` — that stand for groups rather than for one class.

Both are the Prometheux workspace's compilation, not the Build Planner's, which publishes no
ash data at all.
"""

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AFFINITY_CSV = os.path.join(ROOT, "data", "AshAffinity.csv")
CLASS_CSV = os.path.join(ROOT, "data", "AshClass.csv")

# Classes in AshClass that stand for a group rather than for one weapon class.
AGGREGATE_CLASSES = {
    "AllMelee": None,          # every melee class
    "Sword": {"Straight Sword", "Greatsword", "Colossal Sword", "Light Greatsword",
              "Curved Sword", "Curved Greatsword", "Thrusting Sword",
              "Heavy Thrusting Sword", "Katana", "Great Katana", "Twinblade"},
    "Polearm": {"Spear", "Great Spear", "Halberd", "Reaper"},
}
RANGED_CLASSES = {"Bow", "Light Bow", "Greatbow", "Crossbow", "Glintstone Staff"}


def affinities():
    """`{skill: {affinity, ...}}` — every affinity the ash accepts."""
    out = {}
    with open(AFFINITY_CSV, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("Skill"):
                out.setdefault(row["Skill"], set()).add(row["Affinity"])
    return out


def classes():
    """`{skill: {weapon class, ...}}`, aggregates left as written."""
    out = {}
    with open(CLASS_CSV, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("Skill"):
                out.setdefault(row["Skill"], set()).add(row["WeaponClass"])
    return out


def fits(listed, weapon_class):
    """Whether an ash listed for `listed` can go on a weapon of `weapon_class`.

    The aggregates are the reason this is a function rather than a set membership test:
    `AllMelee` covers every melee class, `Sword` and `Polearm` cover a group each.
    """
    if weapon_class in listed:
        return True
    for name in listed:
        if name == "AllMelee":
            if weapon_class not in RANGED_CLASSES:
                return True
        elif name in AGGREGATE_CLASSES and AGGREGATE_CLASSES[name]:
            if weapon_class in AGGREGATE_CLASSES[name]:
                return True
    return False


import re as _re

_PREFIX = _re.compile(r"^\[([^\]]+)\]")


def _prefix(hit):
    match = _PREFIX.match(hit or "")
    return match.group(1) if match else ""


def varies_by_class(rows):
    """Whether this ash's hits differ by the weapon it is on."""
    return bool(variant_classes(rows))


def variant_classes(rows):
    """The weapon classes this ash's hit table gives its own rows for.

    Most ashes have one set of hits. Twenty-odd have a set *per weapon class*, labelled
    `[Reaper] Sword Dance #2` and so on — the same skill hitting differently on a reaper than on
    a dagger.
    """
    known = {c for listed in classes().values() for c in listed}
    return sorted({_prefix(row["Hit"]) for row in rows if _prefix(row["Hit"]) in known})


def hits_for(rows, weapon_class="", lacking_fp=False):
    """The hits of one ash in **one variant**, never summed across variants.

    A family's rows come in bracketed groups, and the groups are alternatives rather than a
    sequence. Most are weapon classes — `[Reaper] Sword Dance #2` is the same skill hitting
    differently on a reaper than on a dagger — and a few are other forms: `[Slow]` for Double
    Slash, `[Var1]` and `[Var2]` for Spinning Slash, `[Luster Tier 1]` for Euporia Vortex.
    Adding two groups together describes a use nobody makes: Sword Dance came back as 48 hits
    and 4,400 status motion value where on a reaper it is three hits and 275, and Double Slash
    counted its slow form on top of its normal one.

    So: the group for `weapon_class` if there is one, else the unprefixed group, else the first
    group there is. Within a group the numbered presses *are* summed — `#1`, `#2`, `#3` are the
    ash pressed again, and the total is what one full use does.

    `(Lacking FP)` rows are the same ash with the FP gone, not further hits, and are out unless
    asked for.
    """
    rows = [r for r in rows if lacking_fp or "(Lacking FP)" not in r["Hit"]]
    groups = {}
    for row in rows:
        groups.setdefault(_prefix(row["Hit"]), []).append(row)
    if weapon_class and weapon_class in groups:
        return groups[weapon_class]
    if "" in groups:
        return groups[""]
    return groups[sorted(groups)[0]] if groups else []


def variants(rows):
    """Every variant group this ash's table carries, weapon classes and otherwise."""
    return sorted({_prefix(row["Hit"]) for row in rows if _prefix(row["Hit"])})
