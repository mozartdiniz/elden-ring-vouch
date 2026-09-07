#!/usr/bin/env python3
"""Rank the spells a build can cast from one catalyst, by what they hit for.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

`spell-power` prices one spell from one catalyst. The question players actually ask is the
other way round — "what are the best fire incantations for 60 faith?" — and answering it means
pricing every spell in the school and dropping the ones the build cannot cast. Three hundred
and eighty-four spells is not something to do one call at a time.

Two filters do most of the work, and they are different questions.

**Damage type** is what the spell deals: `fire` finds every incantation that does fire damage,
whatever school it belongs to. **Family** is what a catalyst boosts: the Godslayer family is
what Godslayer's Seal multiplies by 1.1, and it comes from `data/MagicFamily.csv`, which is
the Prometheux ontology's table rather than the Build Planner's. `family_source` says so on
every row that used it.

A spell the build cannot cast is dropped rather than ranked at zero, with the shortfall
available on request — the same rule `weapon-rank` follows, for the same reason: a spell that
cannot be cast is not a weak spell.

The ranking is on attack out of *this* catalyst. Change the catalyst and the order changes,
which is the point of asking.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "lib"))

import judgement  # noqa: E402
import oracle  # noqa: E402
import spells as spellbook  # noqa: E402

sys.path.insert(0, oracle.SCRIPTS)
import planner  # noqa: E402

COMBAT = ("strength", "dexterity", "intelligence", "faith", "arcane")
DAMAGE = ("physical", "magic", "fire", "lightning", "holy")


def main():
    request = json.load(sys.stdin)
    stats = {s: int(request[s]) for s in COMBAT}
    catalyst = request["catalyst"]
    limit = int(request.get("limit", 15))
    include_uncastable = bool(request.get("include_uncastable", False))
    want_damage = (request.get("damage_type") or "").strip().lower()
    want_family = (request.get("family") or "").strip()
    want_type = (request.get("spell_type") or "").strip()

    catalog, _ = oracle.weapons()
    row = catalog.get(catalyst)
    if row is None:
        print(f"no weapon named {catalyst!r}; call weapon-lookup first", file=sys.stderr)
        sys.exit(1)

    casts = oracle.casts(row)
    upgrade = int(request.get("upgrade", oracle.max_upgrade(row)))

    # The starting class is a floor on every stat inside planner.py, so leaving it out computes
    # a build with 9 intelligence as one with 10 and ranks a slightly different character's
    # spells. Reported, along with anything it lifted.
    # Was a silent `.get(..., "Wretch")` — the same default, applied without saying so,
    # which is precisely bug 17. The value is unchanged; what is new is that it is reported.
    chosen, assumed = judgement.applied(request, "starting_class")
    starting_class = chosen["starting_class"]
    stats_used, raised_by_class = oracle.class_floor(starting_class, stats)
    build = planner.PlannerInputs(
        starting_class=starting_class,
        rh1=planner.WeaponSlotIn(weapon=catalyst, affinity="Standard", upgrade=upgrade),
        **stats,
    )
    priced = planner.Planner().calculate(build)
    spell_buff = float(next(w for w in priced.weapons if w.slot == "RH1").spell_buff)

    book = spellbook.book()
    families = spellbook.families()

    considered = 0
    uncastable = 0
    rows = []
    for name, spell in book.items():
        spell_type = spell.get("Type") or ""
        # A catalyst casts what it casts. Ranking a sorcery for a seal would be a list of
        # figures for casts that cannot happen.
        if spell_type not in casts:
            continue
        if want_type and spell_type != want_type:
            continue
        spell_families = families.get(name, [])
        if want_family and want_family not in spell_families:
            continue

        base = spellbook.base_attack(spell)
        if want_damage and not base.get(want_damage, 0.0) > 0:
            continue
        considered += 1

        bonus, bonus_applied, bonus_family = spellbook.bonus(row, name, spell_families)
        by_type = spellbook.attack_by_type(base, spell_buff, bonus)
        attack = sum(by_type.values())

        requirement = spellbook.requirement(spell)
        shortfall = {
            stat: need - stats[stat]
            for stat, need in requirement.items()
            if need and stats[stat] < need
        }
        if shortfall:
            uncastable += 1
            if not include_uncastable:
                continue

        rows.append({
            "spell": name,
            "spell_type": spell_type,
            "damage_types": sorted(d for d, v in base.items() if v > 0),
            "base_attack": base,
            "attack": attack,
            "attack_shown": int(attack),
            "attack_by_type": by_type,
            "fp_cost": spellbook.number(spell.get("mp")),
            "bonus": bonus,
            "bonus_applied": bonus_applied,
            "bonus_family": bonus_family,
            "families": sorted(spell_families),
            "family_source": (
                "MagicFamily.csv (Prometheux ontology)" if bonus_applied else ""
            ),
            "requirement": requirement,
            "castable": not shortfall,
            "shortfall": shortfall,
        })

    rows.sort(key=lambda r: (-r["attack"], r["spell"]))
    truncated = len(rows) > limit
    ranked = rows[:limit]
    print(
        f"{catalyst} +{upgrade}: spell buff {spell_buff:.1f}, "
        f"{len(rows)} of {considered} spells rankable",
        file=sys.stderr,
    )

    result = {
        "ranked": ranked,
        "catalyst": catalyst,
        "catalyst_class": row["Weapon Class"],
        "catalyst_casts": casts,
        "upgrade": upgrade,
        "max_upgrade": oracle.max_upgrade(row),
        "spell_buff": spell_buff,
        "best": ranked[0]["spell"] if ranked else "",
        "best_attack": ranked[0]["attack"] if ranked else 0.0,
        "damage_type": want_damage,
        "family": want_family,
        "spell_type": want_type,
        "catalog_size": len(book),
        "considered": considered,
        "castable": considered - uncastable,
        "uncastable": uncastable,
        "include_uncastable": include_uncastable,
        "stats": stats,
        "starting_class": starting_class,
        # What the collection decided because nobody else did.
        "assumed": assumed,
        "stats_used": stats_used,
        "stats_raised_by_class": raised_by_class,
        "limit": limit,
        "returned": len(ranked),
        "truncated": truncated,
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
