#!/usr/bin/env python3
"""What a loadout weighs, and which roll it leaves you with.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

The arithmetic is `oracle/scripts/planner.py`, unmodified. Equip load depends on endurance
alone; what it is spent on is armour and weapons, and the answer players actually want is not
a number but a category — light, medium or heavy roll — plus how far from the next one they
are.

**Talismans are not accepted, on purpose.** Great-Jar's Arsenal and Erdtree's Favor raise equip
load, and `planner.py` does not model talisman effects: the Build Planner port stubbed them.
A node that took a talisman and silently ignored it would answer a different question than the
one it was asked, so it does not take one. `talismans_modelled` says so in the result, because
a caller has no other way to know the figure is before talismans.

`end_for_light_roll` and `end_for_mid_roll` are the endurance needed to reach those rolls with
this exact loadout, which is the actionable half of the answer — "you are 2.3 over" is useful,
"level endurance to 27" is more so.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "lib"))

import oracle  # noqa: E402

sys.path.insert(0, oracle.SCRIPTS)
import planner  # noqa: E402

SLOTS = ("head", "chest", "arms", "legs")
WEAPON_SLOTS = ("rh1", "rh2", "rh3", "lh1", "lh2", "lh3")


def reachable(value):
    """An endurance requirement, or 0 when the planner says the roll cannot be reached."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def main():
    request = json.load(sys.stdin)
    endurance = request["endurance"]
    weapons = request.get("weapons", [])

    armour = {slot: (request.get(slot) or "Empty") for slot in SLOTS}
    slots = {
        name: planner.WeaponSlotIn(weapon=weapons[i])
        for i, name in enumerate(WEAPON_SLOTS)
        if i < len(weapons)
    }

    inputs = planner.PlannerInputs(
        starting_class=request.get("starting_class", "Wretch"),
        endurance=endurance,
        **{slot: armour[slot] for slot in SLOTS},
        **slots,
    )
    r = planner.Planner().calculate(inputs)
    print(
        f"endurance {endurance}: {r.equipped_weight:.1f} / {r.equip_load:.1f}", file=sys.stderr
    )

    # `encumbrance_pct` is the planner's own display string, e.g. "52.9%". Parsed rather than
    # recomputed, so the figure keeps the sheet's rounding instead of gaining ours.
    percent = float(str(r.encumbrance_pct).rstrip("%"))

    result = {
        "endurance": int(r.final_stats["endurance"]),
        "equip_load": float(r.equip_load),
        "equipped_weight": float(r.equipped_weight),
        # Two different margins, and conflating them is easy: `load_remaining` is how much
        # capacity is unused, while the planner's `weight_left` is how much more can be
        # carried *before the roll changes* — 70% of the cap for a medium roll, not 100%. At
        # 37.3 of 72 those are 34.7 and 13.1, and only the second answers "how much more can I
        # pick up and still medium-roll".
        "load_remaining": float(r.equip_load) - float(r.equipped_weight),
        "weight_before_roll_change": float(r.weight_left),
        "encumbrance_percent": percent,
        "roll": r.roll,
        "armour": armour,
        "weapons": list(weapons),
        # Endurance needed to reach each roll with this exact loadout. Zero means the roll is
        # out of reach at 99 endurance, which is a real answer: drop weight instead. The
        # planner says that with the string "Not Possible" rather than a number, so it is
        # translated here rather than allowed to reach the output as a type the schema would
        # reject and a contract could not compare.
        "end_for_light_roll": reachable(r.end_for_light_roll),
        "end_for_mid_roll": reachable(r.end_for_mid_roll),
        # Not a placeholder for a future feature: the Build Planner port never modelled
        # talisman effects, so any figure here is before Great-Jar's Arsenal and its like.
        "talismans_modelled": False,
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
