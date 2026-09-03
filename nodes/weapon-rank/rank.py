#!/usr/bin/env python3
"""Rank the weapons a build can actually use, by what they hit for.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

The question this exists for is "what are the strongest weapons I can use with these stats",
and it was the one shape the collection could not answer at all. Every other node here starts
from a weapon the caller already named; nothing looked across the catalogue. An agent told to
"call attack-power once per weapon and rank what comes back" would need 570 calls, so in
practice it would rank from memory instead — which is the failure this collection exists to
prevent.

The arithmetic is still the oracle's. Every row is one `ap_calc.py` result at the caller's
stats, and each weapon is priced at **its own cap**: a somber weapon at +10 and a smithing
one at +25 is the comparison a player is choosing between, and holding them all at one number
would compare weapons nobody wields.

Three things worth knowing when reading the result.

**Requirements are a filter, not a footnote.** A weapon the build cannot hold is not a weak
option, it is not an option, and `ap_calc` prices it anyway with a penalty. Those rows are
dropped unless the caller asks for them, and when they are asked for, each carries the
shortfall per stat rather than a flag.

**`affinity = "best"` changes what is being ranked.** By default every infusable weapon is
priced Standard, which is the weapon as found. Asking for the best affinity prices all
thirteen and keeps the winner, which is a different and usually higher list — and the answer
has to say which one it is.

**Total attack rating is not "strongest".** It ignores status buildup, reach, moveset, and
the ash of war, and `ranked_on` says so out loud. Status buildup comes back per row so a
bleed weapon is not silently ranked below a bigger number.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "lib"))

import oracle  # noqa: E402
import spells as spellbook  # noqa: E402

sys.path.insert(0, oracle.SCRIPTS)
import ap_calc  # noqa: E402

COMBAT = ("strength", "dexterity", "intelligence", "faith", "arcane")
DAMAGE = ("physical", "magic", "fire", "lightning", "holy")
STATUS = ("poison", "scarlet_rot", "bleed", "frost", "sleep", "madness")
AFFINITIES = (
    "Standard", "Heavy", "Keen", "Quality", "Fire", "Flame Art", "Lightning",
    "Sacred", "Magic", "Cold", "Poison", "Blood", "Occult",
)
CATALYST_CLASSES = ("Glintstone Staff", "Sacred Seal")


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def main():
    request = json.load(sys.stdin)
    stats = {s: int(request[s]) for s in COMBAT}
    two_hand = bool(request.get("two_hand", False))
    want_class = (request.get("weapon_class") or "").strip()
    affinity_mode = request.get("affinity", "Standard")
    limit = int(request.get("limit", 15))
    include_unusable = bool(request.get("include_unusable", False))
    spell_name = request.get("spell", "")
    # planner.py floors every stat at the starting class's, so a hard-coded Wretch quietly
    # ranked catalysts for a build with ten intelligence when the caller said nine.
    starting_class = request.get("starting_class", "Wretch")

    catalog, _ = oracle.weapons()
    calc = ap_calc.ApCalc()

    spell_row = None
    if spell_name:
        spell_row = spellbook.book().get(spell_name)
        if spell_row is None:
            print(f"no spell named {spell_name!r}; call spell-power to resolve it",
                  file=sys.stderr)
            sys.exit(1)
        import planner
        spell_planner = planner.Planner()
        spell_base = spellbook.base_attack(spell_row)
        spell_families = spellbook.families().get(spell_name, [])
        spell_requirement = spellbook.requirement(spell_row)
        spell_type = spell_row.get("Type") or ""

    # Two-handing multiplies strength by 1.5 before requirements are checked.
    effective_strength = int(stats["strength"] * 1.5) if two_hand else stats["strength"]

    def shortfall_of(result):
        out = {}
        for stat in COMBAT:
            need = result.requirements.get(stat)
            if not need:
                continue
            have = effective_strength if stat == "strength" else stats[stat]
            if have < int(need):
                out[stat] = int(need) - have
        return out

    considered = 0
    unusable = 0
    not_weapons = 0
    rows = []
    for name, row in catalog.items():
        weapon_class = str(row.get("Weapon Class") or "")
        # The catalogue is not 570 weapons. **Eighty-one of its rows are consumables** — fire
        # pots, aromatics, throwing knives — and fifteen of those have no weapon ID at all,
        # which is what made an unfiltered ranking crash rather than return them. Nothing here
        # is a weapon a build wields, so they are counted and skipped rather than dropped
        # silently: "570 weapons" in an answer would be a number nobody can check.
        if row.get("ID") is None or weapon_class == "Consumable":
            not_weapons += 1
            continue
        if want_class and weapon_class.lower() != want_class.lower():
            continue
        # A staff casts sorceries and a seal casts incantations. Ranking catalysts without that
        # filter put the Golden Order Seal at the top of a list of the best catalysts for a
        # *sorcery*, above every staff — a well-formed number for a cast that cannot happen.
        if spell_row is not None and spell_type not in oracle.casts(row):
            continue
        cap = oracle.max_upgrade(row)
        infusable = bool(row["isInfuse"])
        considered += 1

        candidates = AFFINITIES if (infusable and affinity_mode == "best") else (
            [affinity_mode if infusable and affinity_mode != "best" else "Standard"]
        )

        best_row = None
        for affinity in candidates:
            result = calc.calculate(ap_calc.Inputs(
                weapon_class=weapon_class, weapon=name, affinity=affinity, upgrade=cap,
                two_hand=two_hand, **stats,
            ))
            short = shortfall_of(result)
            attack = {d: number((result.total or {}).get(d)) for d in DAMAGE}
            status = {s: number((result.total or {}).get(s)) for s in STATUS}

            if spell_row is not None:
                build = planner.PlannerInputs(
                    starting_class=starting_class,
                    rh1=planner.WeaponSlotIn(weapon=name, affinity=affinity, upgrade=cap),
                    **stats,
                )
                priced = spell_planner.calculate(build)
                buff = float(next(w for w in priced.weapons if w.slot == "RH1").spell_buff)
                bonus, bonus_applied, bonus_family = spellbook.bonus(
                    row, spell_name, spell_families
                )
                score = sum(spellbook.attack_by_type(spell_base, buff, bonus).values())
                for stat, need in spell_requirement.items():
                    if need and stats[stat] < need:
                        short[stat] = max(short.get(stat, 0), need - stats[stat])
            else:
                buff, bonus, bonus_applied, bonus_family = 0.0, 1.0, False, ""
                score = float(result.total_ar)

            candidate = {
                "weapon": name,
                # A shield's attack rating is not what a shield is for. Guard boost and the
                # negation split are, and they cost nothing to carry.
                "guard_boost": int(result.guard_boost),
                "guard_negation": {
                    d: number((result.guard_negation or {}).get(d)) for d in DAMAGE
                },
                "weapon_class": weapon_class,
                "affinity": affinity,
                "infusable": infusable,
                "upgrade": cap,
                "max_upgrade": cap,
                "score": score,
                "score_shown": int(score),
                "total_ar": float(result.total_ar),
                "total_ar_rounded": int(result.total_ar_rounded),
                "attack_shown": {d: int(attack[d]) for d in DAMAGE},
                "status_shown": {s: int(status[s]) for s in STATUS},
                "spell_buff": buff,
                "spell_bonus": bonus,
                "spell_bonus_applied": bonus_applied,
                "spell_bonus_family": bonus_family,
                "requirements_met": not short,
                "shortfall": short,
            }
            if best_row is None or candidate["score"] > best_row["score"]:
                best_row = candidate

        if not best_row["requirements_met"]:
            unusable += 1
            if not include_unusable:
                continue
        rows.append(best_row)

    rows.sort(key=lambda r: (-r["score"], r["weapon"]))
    truncated = len(rows) > limit
    ranked = rows[:limit]
    print(
        f"ranked {len(rows)} of {considered} weapons ({unusable} the build cannot hold)",
        file=sys.stderr,
    )

    result = {
        "ranked": ranked,
        "ranked_on": "spell_attack" if spell_row is not None else "total_ar",
        "spell_type": spell_type if spell_row is not None else "",
        "ranked_on_note": (
            "What the named spell hits for out of each catalyst."
            if spell_row is not None else
            "Total attack rating. It ignores status buildup, reach, moveset and the ash of "
            "war, all of which decide which weapon is better in a fight."
        ),
        "spell": spell_name,
        "best": ranked[0]["weapon"] if ranked else "",
        "best_score": ranked[0]["score"] if ranked else 0.0,
        "catalog_size": len(catalog),
        "not_weapons": not_weapons,
        "weapon_class": want_class,
        "considered": considered,
        "usable": considered - unusable,
        "unusable": unusable,
        "include_unusable": include_unusable,
        "affinity_mode": affinity_mode,
        "two_hand": two_hand,
        "stats": stats,
        "starting_class": starting_class,
        "stats_raised_by_class": oracle.class_floor(starting_class, stats)[1],
        "limit": limit,
        "returned": len(ranked),
        "truncated": truncated,
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
