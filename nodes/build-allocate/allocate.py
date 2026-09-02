#!/usr/bin/env python3
"""Spend a rune level's worth of points on one weapon, and say what the result hits for.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

This is the node the collection was missing: every real question is "monta a distribuição" —
give me the spread — and everything else here reports on a spread somebody already chose.

**The arithmetic is still the oracle's.** Nothing new is computed. The node searches over stat
spreads and asks `ap_calc.py` what each one is worth, so every figure it returns is one that
`attack-power` would return for the same spread. What is new is the search, not the maths.

**The survivability floors are the caller's, not the node's.** How much vigor a build "should"
have is a judgement with nothing behind it, and a node that picked one would be presenting an
opinion as a calculation. So `vigor`, `mind` and `endurance` floors are required inputs, they
are echoed in the result, and an answer has to say they were chosen rather than computed.
Everything above those floors is spent maximising the objective, which *is* computed.

**An impossible build is an answer, not an error.** If the floors and the weapon's
requirements cost more than the target level, there is no such character — and the useful
reply is "that needs RL163", not a refusal. `feasible` says which case this is and
`minimum_level` says what it would take.

The search is a greedy climb — repeatedly spend the point that buys the most — followed by a
pairwise pass that moves points between stats while that still helps. Scaling curves have soft
caps, so a pure climb can stall just below one; the second pass is what gets over them.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "lib"))

import oracle  # noqa: E402

sys.path.insert(0, oracle.SCRIPTS)
import ap_calc  # noqa: E402

ALL_STATS = (
    "vigor", "mind", "endurance", "strength",
    "dexterity", "intelligence", "faith", "arcane",
)
# The five the weapon cares about; the other three are survivability the caller sets floors for.
COMBAT = ("strength", "dexterity", "intelligence", "faith", "arcane")
FLOOR_STATS = ("vigor", "mind", "endurance")
STATUS = ("poison", "scarlet_rot", "bleed", "frost", "sleep", "madness")
DAMAGE = ("physical", "magic", "fire", "lightning", "holy")
MAX_STAT = 99
# Rune level 1 is a stat sum of 79.
LEVEL_BASE = 79


def objective(result, focus):
    """What the search is maximising. `attack` is total AR; anything else is a status bar."""
    if focus == "attack":
        return float(result.total_ar)
    return float((result.total or {}).get(focus) or 0.0)


def main():
    request = json.load(sys.stdin)
    weapon = request["weapon"]
    focus = request.get("focus", "attack")
    target_level = request["target_level"]
    two_hand = request.get("two_hand", False)

    catalog, _ = oracle.weapons()
    row = catalog.get(weapon)
    if row is None:
        print(f"no weapon named {weapon!r}; call weapon-lookup first", file=sys.stderr)
        sys.exit(1)

    import planner

    classes = planner.load_starting_classes()
    starting_class = request["starting_class"]
    if starting_class not in classes:
        print(f"no starting class named {starting_class!r}", file=sys.stderr)
        sys.exit(1)
    minimums = {stat: int(classes[starting_class][stat]) for stat in ALL_STATS}
    class_level = sum(minimums.values()) - LEVEL_BASE

    calc = ap_calc.ApCalc()

    def evaluate(stats):
        return calc.calculate(
            ap_calc.Inputs(
                weapon_class=row["Weapon Class"],
                weapon=weapon,
                affinity=request["affinity"],
                upgrade=request["upgrade"],
                two_hand=two_hand,
                **{s: stats[s] for s in COMBAT},
            )
        )

    # --- the floor: class minimums, then the caller's survivability floors, then the
    # weapon's own requirements. Everything here is forced; nothing is a choice.
    stats = dict(minimums)
    floors = {stat: int(request[stat]) for stat in FLOOR_STATS}
    for stat, floor in floors.items():
        stats[stat] = max(stats[stat], min(floor, MAX_STAT))

    requirements = evaluate(stats).requirements
    for stat in COMBAT:
        need = requirements.get(stat)
        if need:
            # Two-handing multiplies strength by 1.5, so the raw stat needed is lower.
            if stat == "strength" and two_hand:
                need = -(-int(need) * 2 // 3)
            stats[stat] = max(stats[stat], min(int(need), MAX_STAT))

    minimum_level = sum(stats.values()) - LEVEL_BASE
    feasible = minimum_level <= target_level
    budget = max(0, target_level - minimum_level)
    print(
        f"{weapon}: floor costs RL{minimum_level}, {budget} points to spend toward {focus}",
        file=sys.stderr,
    )

    # --- the search. Every candidate is priced by the oracle, so the winner's figures are
    # figures `attack-power` would give for the same spread.
    searched = 0
    # What the objective is worth before a single point is spent on it. If the search cannot
    # beat this, nothing the caller levels improves what they asked to maximise — true of
    # every weapon whose status buildup is flat, like Star Fist's frost.
    at_minimum = objective(evaluate(stats), focus)
    best = at_minimum
    if feasible and budget:
        searched += 1

        for _ in range(budget):
            gains = []
            for stat in COMBAT:
                if stats[stat] >= MAX_STAT:
                    continue
                trial = dict(stats)
                trial[stat] += 1
                gains.append((objective(evaluate(trial), focus), stat))
            searched += len(gains)
            if not gains:
                break
            gain, stat = max(gains)
            if gain <= best:
                # Nothing left that helps; the rest buys health instead of damage.
                break
            best, stats[stat] = gain, stats[stat] + 1

        # Soft caps make a pure climb stall just below a breakpoint. Moving points between two
        # stats can clear one, so keep trying while it helps.
        improved = True
        while improved:
            improved = False
            for take in COMBAT:
                for give in COMBAT:
                    if take == give or stats[take] <= minimums.get(take, 1):
                        continue
                    if stats[give] >= MAX_STAT or stats[take] - 1 < 1:
                        continue
                    trial = dict(stats)
                    trial[take] -= 1
                    trial[give] += 1
                    searched += 1
                    if trial[take] < requirement_floor(requirements, take, two_hand):
                        continue
                    value = objective(evaluate(trial), focus)
                    if value > best:
                        best, stats, improved = value, trial, True

        # Anything the search would not spend goes to vigor: it is the only stat that is
        # never wasted, and leaving points unspent would not be a build at the target level.
        spare = target_level - (sum(stats.values()) - LEVEL_BASE)
        if spare > 0:
            for stat in ("vigor", "endurance", "mind"):
                room = MAX_STAT - stats[stat]
                take = min(room, spare)
                stats[stat] += take
                spare -= take
                if not spare:
                    break

    final = evaluate(stats)
    attack = {d: float((final.total or {}).get(d) or 0.0) for d in DAMAGE}
    status = {s: float((final.total or {}).get(s) or 0.0) for s in STATUS}

    result = {
        "weapon": weapon,
        "weapon_class": row["Weapon Class"],
        "affinity": request["affinity"],
        "upgrade": int(request["upgrade"]),
        "max_upgrade": oracle.max_upgrade(row),
        "two_hand": bool(two_hand),
        "starting_class": starting_class,
        "focus": focus,
        "target_level": int(target_level),
        "level": sum(stats.values()) - LEVEL_BASE,
        "class_level": class_level,
        "points_spent": sum(stats.values()) - sum(minimums.values()),
        "stats": {stat: int(stats[stat]) for stat in ALL_STATS},
        "class_minimums": minimums,
        # The caller's judgement, echoed so an answer has to own it.
        "floors": floors,
        "floors_are_the_callers_choice": True,
        # Whether the target level can hold this build at all.
        "feasible": bool(feasible),
        "minimum_level": int(minimum_level),
        "total_ar": float(final.total_ar),
        "total_ar_rounded": int(final.total_ar_rounded),
        "attack": attack,
        "attack_shown": {d: int(attack[d]) for d in DAMAGE},
        "status": status,
        "status_shown": {s: int(status[s]) for s in STATUS},
        "objective_value": objective(final, focus),
        "objective_at_minimum": at_minimum,
        "objective_gain": round(objective(final, focus) - at_minimum, 9),
        # False means the focus does not respond to levelling at all: the spread below is the
        # floor plus points that had nowhere useful to go. Say so rather than presenting it as
        # an optimised build.
        "objective_responds_to_stats": objective(final, focus) > at_minimum,
        "requirements_met": all(final.req_met.get(s, True) for s in COMBAT),
        "searched": searched,
    }
    json.dump(result, sys.stdout)


def requirement_floor(requirements, stat, two_hand):
    need = requirements.get(stat)
    if not need:
        return 1
    if stat == "strength" and two_hand:
        return -(-int(need) * 2 // 3)
    return int(need)


if __name__ == "__main__":
    main()
