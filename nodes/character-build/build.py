#!/usr/bin/env python3
"""Fill in a character build from a starting class and whatever stats the user named.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

The arithmetic is `oracle/scripts/planner.py`, unmodified. This node exists because of a
failure seen on the first live run of the eval suite: asked for a strength-faith build at
60/60, the agent called `attack-power` — which needs all five stats — and made the other three
up. It then quoted one of them back to the user ("your 12 dexterity"), and `vouch attest`
refused the 12, because no node had produced it.

The fix is not to check harder downstream. It is to stop making the caller invent a number:
an unspecified stat here is the **starting class's minimum**, which is real data. Every stat
`attack-power` is then given traces to a return value, and a build that is short of a
requirement is short of it for a reason the user can act on — pick another class — rather than
because an agent guessed.

`level` is the rune level that spread costs, which is what a question phrased "at RL150" is
really about — and `target_level` answers the rest of that question. An eval run asked for a
build "at RL150", got RL103 back, and wrote "47 levels spare"; attestation refused the 47,
because subtracting is arithmetic and no node had returned it. A figure a reader will quote
has to exist as a return value.
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


def main():
    request = json.load(sys.stdin)
    # The class is a judgement, not a fact, and leaving it to the caller meant leaving it to a
    # model — which chose a different one each run. lib/judgement.py has the reasoning.
    chosen, assumed = judgement.applied(request, "starting_class")
    starting_class = chosen["starting_class"]
    target_level = request.get("target_level")

    classes = planner.load_starting_classes()
    if starting_class not in classes:
        # Reachable only past the precondition, which lists the ten classes.
        print(f"no starting class named {starting_class!r}", file=sys.stderr)
        sys.exit(REFUSE)

    # `None` is planner.py's "use the class minimum". A stat the caller left out is one the
    # user did not name, and the minimum is the honest reading of that.
    asked = {stat: request.get(stat) for stat in STATS}
    inputs = planner.PlannerInputs(starting_class=starting_class, **asked)
    print(
        f"{starting_class} with {sum(1 for v in asked.values() if v is not None)} stats given",
        file=sys.stderr,
    )
    r = planner.calculate(inputs) if hasattr(planner, "calculate") else planner.Planner().calculate(inputs)

    final = {stat: int(r.final_stats[stat]) for stat in STATS}
    minimums = {stat: int(classes[starting_class][stat]) for stat in STATS}

    result = {
        "starting_class": starting_class,
        # What the collection decided because nobody else did. An answer must say so.
        "assumed": assumed,
        "level": int(r.level),
        "stats": final,
        "class_minimums": minimums,
        # Which stats the user actually named, so an answer can say what was assumed rather
        # than presenting a class minimum as a choice someone made.
        "stats_given": sorted(s for s, v in asked.items() if v is not None),
        "stats_from_class_minimum": sorted(s for s, v in asked.items() if v is None),
        # A class cannot go below its own floor, so a stat asked for below it comes back
        # raised. That is a substitution, and substitutions have to be reported rather than
        # absorbed — otherwise an answer repeats a number the user chose and did not get.
        "stats_raised_to_class_minimum": sorted(
            stat
            for stat, value in asked.items()
            if value is not None and value < minimums[stat]
        ),
        # A class does not start at rune level 1: its own stat spread already costs levels.
        # Rune level is the stat sum minus 79, so Wretch's flat 10s land on RL1 and Hero's
        # spread on RL7. Reporting it means a caller never has to work out where levels went.
        "class_level": sum(minimums.values()) - 79,
        "points_spent": sum(final[s] - minimums[s] for s in STATS),
        "hp": int(r.hp),
        "fp": int(r.fp),
        "stamina": int(r.stamina),
        "equip_load": float(r.equip_load),
        # `planner.py` calls this `extra_levels`, and it is the rune level these same stats
        # would cost on the best-fitting class — directly comparable to `level` above, not a
        # saving on its own. The saving is the difference, so report that separately rather
        # than leaving a caller to subtract two numbers and quote a figure no node returned.
        # Zero rather than absent when no target was given: a caller reading these gets a
        # number either way, and a contract mentioning them stays evaluable.
        "target_level": int(target_level or 0),
        "levels_to_target": int(target_level - r.level) if target_level else 0,
        "optimal_class": r.optimal_class,
        "optimal_class_level": int(r.extra_levels),
        "levels_saved_by_optimal_class": int(r.level) - int(r.extra_levels),
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
