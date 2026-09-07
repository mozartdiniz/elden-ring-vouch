#!/usr/bin/env python3
"""What a build takes: defences, damage negation from armour, and status resistances.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

The arithmetic is `oracle/scripts/planner.py`, unmodified. Three different things get called
"defence" in Elden Ring and they are not interchangeable, so this node keeps them apart:

- **defences** are the flat per-element numbers that come from stats alone.
- **negation** is the percentage an armour set removes, and is the figure on the equipment
  screen. Reported as both the fraction the maths uses and the percentage a player reads,
  rounded the way the planner's own display rounds it, so quoting either is quoting a
  returned value.
- **resistances** are the four status bars — immunity, robustness, focus, vitality — which
  come from stats *and* armour and have nothing to do with damage.

Physical negation splits three ways. Strike, slash and pierce differ from each other and from
the plain physical figure, and a set that is good against one is often poor against another;
collapsing them to one number would be the useful part thrown away.

Talismans are not modelled — `planner.py` stubbed `EffectData_Active` — so this node does not
take one, and `talismans_modelled` says so.
"""

import json
import os
import sys

# The status a node exits with to refuse: it understood the question and there is no answer.
# vouch turns it into exit 16, a refusal, with this node's stderr as the reason — where every
# non-zero exit used to become exit 20, a defect, which tells the caller the node is broken
# and throws away the rest of their question along with the part that had none.
REFUSE = 3

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "lib"))

import judgement  # noqa: E402
import oracle  # noqa: E402

sys.path.insert(0, oracle.SCRIPTS)
import planner  # noqa: E402

STATS = (
    "vigor", "mind", "endurance", "strength",
    "dexterity", "intelligence", "faith", "arcane",
)
SLOTS = ("head", "chest", "arms", "legs")
DAMAGE = ("physical", "strike", "slash", "pierce", "magic", "fire", "lightning", "holy")
ELEMENTS = ("physical", "magic", "fire", "lightning", "holy")
RESISTS = ("immunity", "robustness", "focus", "vitality")


def main():
    request = json.load(sys.stdin)
    # A judgement, not a fact. See lib/judgement.py: leaving it to the caller meant leaving
    # it to a model, which chose differently between runs.
    chosen, assumed = judgement.applied(request, "starting_class")
    starting_class = chosen["starting_class"]
    armour = {slot: (request.get(slot) or "Empty") for slot in SLOTS}

    classes = planner.load_starting_classes()
    if starting_class not in classes:
        print(f"no starting class named {starting_class!r}", file=sys.stderr)
        sys.exit(REFUSE)
    minimums = {stat: int(classes[starting_class][stat]) for stat in STATS}
    asked = {stat: request.get(stat) for stat in STATS}

    inputs = planner.PlannerInputs(
        starting_class=starting_class,
        **asked,
        **armour,
    )
    r = planner.Planner().calculate(inputs)
    worn = sorted(slot for slot in SLOTS if armour[slot] != "Empty")
    print(f"{starting_class}, {len(worn)} armour piece(s)", file=sys.stderr)

    result = {
        "starting_class": starting_class,
        # What the collection decided because nobody else did.
        "assumed": assumed,
        "level": int(r.level),
        "stats": {stat: int(r.final_stats[stat]) for stat in STATS},
        # The same reporting character-build does, for the same reason: a stat nobody named is
        # a class minimum rather than a choice, and a stat asked for below that floor comes
        # back raised. Both are substitutions, and a node that absorbed them would have an
        # answer quoting numbers the user never picked.
        "stats_given": sorted(s for s, v in asked.items() if v is not None),
        "stats_from_class_minimum": sorted(s for s, v in asked.items() if v is None),
        "stats_raised_to_class_minimum": sorted(
            stat for stat, value in asked.items()
            if value is not None and value < minimums[stat]
        ),
        "armour": armour,
        "armour_worn": worn,
        # From stats alone: what the character resists before anything is worn.
        "defence": {e: int(r.defenses[e]) for e in ELEMENTS},
        # From armour: the share of incoming damage removed. The fraction is what the maths
        # uses; the percentage is what the equipment screen shows, rounded as the planner's
        # own display rounds it, so a reader can quote either without doing the conversion.
        "negation": {d: float(r.negation[d]) for d in DAMAGE},
        "negation_percent": {
            d: planner.excel_round(100.0 * float(r.negation[d]), 3) for d in DAMAGE
        },
        # The multiplier damage is scaled by: 1.0 means nothing is absorbed.
        "absorb": {d: float(r.absorb[d]) for d in DAMAGE},
        # Status bars. Not damage, and not affected by damage negation.
        "resist": {k: int(r.resists[k]) for k in RESISTS},
        "hp": int(r.hp),
        "armour_weight": float(r.equipped_weight),
        "talismans_modelled": False,
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
