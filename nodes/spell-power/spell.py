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

The final step, `attack = base_attack x spell_buff / 100 x bonus` summed over every damage type
the spell deals, is the one piece of arithmetic in this collection that is not the oracle's:
the Python scripts stop at the spell buff. It is pinned in `cases.toml` against figures the
Prometheux implementation produced independently, which is the closest thing to a second
opinion available.

The tables and that multiply live in `lib/spells.py`, because `build-allocate` searches for
the spread that maximises a spell and has to compute the same thing. One copy, so the two
nodes cannot drift.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "lib"))

import oracle  # noqa: E402
import spells as spellbook  # noqa: E402

sys.path.insert(0, oracle.SCRIPTS)
import planner  # noqa: E402


def main():
    request = json.load(sys.stdin)
    spell_name = request["spell"]
    catalyst = request["catalyst"]

    catalog, _ = oracle.weapons()
    row = catalog.get(catalyst)
    if row is None:
        print(f"no weapon named {catalyst!r}", file=sys.stderr)
        sys.exit(1)

    # A staff casts sorceries and a seal casts incantations. Nothing in the maths knows that:
    # the spell buff is a number and the multiply does not ask what kind of spell it is, so
    # Comet from an Erdtree Seal priced at 798.766 — arithmetically correct, and about a cast
    # that cannot happen. `casts` reads the game's own enableMagic / enableMiracle flags,
    # which is how the Staff of the Great Beyond comes back as doing both.
    catalyst_casts = oracle.casts(row)

    book = spellbook.book()
    spell = book.get(spell_name)
    if spell is None:
        print(f"no spell named {spell_name!r}", file=sys.stderr)
        sys.exit(1)
    forms = spellbook.variants(book, spell["Name"])

    # A starting class is a *floor* in planner.py, not a baseline: a build with 9 intelligence
    # computed as a Wretch is computed at 10, because Wretch is flat tens. So the class is
    # reported and so is anything it lifted — a spell buff for a build nobody described is the
    # failure this collection exists to prevent, and it is 0.4 of a point, which is worse than
    # a large one because nobody would notice.
    starting_class = request.get("starting_class", "Wretch")
    given = {stat: request[stat] for stat in
             ("strength", "dexterity", "intelligence", "faith", "arcane")}
    stats_used, raised_by_class = oracle.class_floor(starting_class, given)

    build = planner.PlannerInputs(
        starting_class=starting_class,
        **given,
        rh1=planner.WeaponSlotIn(
            weapon=catalyst, affinity="Standard", upgrade=request["upgrade"]
        ),
    )
    r = planner.Planner().calculate(build)
    slot = next(w for w in r.weapons if w.slot == "RH1")
    spell_buff = float(slot.spell_buff)

    # A staff or seal boosts one family of spells, and which family a spell belongs to is the
    # one thing here the Build Planner does not publish.
    spell_families = spellbook.families().get(spell_name, [])
    bonus, applies, bonus_family = spellbook.bonus(row, spell_name, spell_families)

    base_attack = spellbook.base_attack(spell)
    attack_by_type = spellbook.attack_by_type(base_attack, spell_buff, bonus)
    attack = sum(attack_by_type.values())
    damage_types = sorted(damage for damage, value in base_attack.items() if value > 0)
    print(
        f"{spell_name} from {catalyst} +{request['upgrade']}: "
        f"SB {spell_buff:.1f} x {bonus} over {', '.join(damage_types) or 'nothing'}",
        file=sys.stderr,
    )

    requirement = spellbook.requirement(spell)
    fp_cost = spellbook.number(spell.get("mp"))
    fp_rate = spellbook.fp_rate(row)
    fp_actual = float(__import__("math").ceil(fp_cost * fp_rate))
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
        "starting_class": starting_class,
        "stats_used": stats_used,
        # Stats the starting class raised above what the caller gave. Non-empty means this
        # figure is for a slightly different character than the one asked about.
        "stats_raised_by_class": raised_by_class,
        "catalyst_casts": catalyst_casts,
        "catalyst_can_cast_this": spell.get("Type") in catalyst_casts,
        "upgrade": int(request["upgrade"]),
        "max_upgrade": oracle.max_upgrade(row),
        "spell_buff": spell_buff,
        # Per damage type, because a spell that deals two is not one number and an
        # incantation's figure is not in the magic column at all.
        "base_attack": base_attack,
        "damage_types": damage_types,
        "bonus": bonus,
        "bonus_applied": applies,
        # Named so an answer can say *why* a staff is better, not just that it is.
        "bonus_family": bonus_family,
        "spell_families": sorted(spell_families),
        "family_source": "MagicFamily.csv (Prometheux ontology)" if applies else "",
        "attack": attack,
        "attack_shown": int(attack),
        "attack_by_type": attack_by_type,
        "attack_shown_by_type": {damage: int(value) for damage, value in attack_by_type.items()},
        "fp_cost": fp_cost,
        # What it actually costs out of this catalyst. Lusat's charges 1.5x and Azur's 1.2x,
        # and a damage figure quoted beside the base cost answers the wrong question.
        "fp_cost_actual": fp_actual,
        "fp_rate": fp_rate,
        "requirement": requirement,
        "castable": castable,
        "unmet": sorted(
            stat for stat, need in requirement.items() if request[stat] < need
        ),
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
