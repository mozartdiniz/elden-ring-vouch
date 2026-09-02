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
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "lib"))

import oracle  # noqa: E402
import spells as spellbook  # noqa: E402

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
# How many spreads the exhaustive sweep will price before falling back to the coarse-to-fine
# search. The oracle prices about seven thousand a second, so this is around twenty seconds at
# worst — slow for a node, and worth it: below this line the answer is the optimum rather than
# a good spread, and every case that has actually come up sits under it.
SWEEP_CAP = 40000


def sweep_cost(live, budget):
    """How many spreads of `budget` points across `live` stats an exhaustive sweep prices."""
    return math.comb(budget + live - 1, live - 1) if live else 1


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

    # `focus = "spell"` maximises what a spell hits for out of this catalyst, not what the
    # catalyst hits for. They are different questions with different answers: an Erdtree Seal's
    # own attack rating and the incantation it casts do not scale the same way, and building
    # for the first was the only thing this node could do until now.
    spell_name = request.get("spell", "")
    spell_row = None
    if focus == "spell":
        if not spell_name:
            print("focus 'spell' needs a spell to maximise", file=sys.stderr)
            sys.exit(1)
        spell_row = spellbook.book().get(spell_name)
        if spell_row is None:
            print(f"no spell named {spell_name!r}; call spell-power to resolve it",
                  file=sys.stderr)
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

    # A weapon that takes no affinity is priced as Standard whatever was asked for. Searching
    # for the spread that maximises "Lightning Dragon Halberd" and reporting the affinity back
    # unchanged would hand the caller a number for a weapon that cannot exist — Dragon Halberd
    # is somber, and every figure below is the Standard one.
    infusable = bool(row["isInfuse"])
    affinity_requested = request["affinity"]
    affinity = affinity_requested if infusable else "Standard"

    def evaluate(stats):
        return calc.calculate(
            ap_calc.Inputs(
                weapon_class=row["Weapon Class"],
                weapon=weapon,
                affinity=affinity,
                upgrade=request["upgrade"],
                two_hand=two_hand,
                **{s: stats[s] for s in COMBAT},
            )
        )

    # --- the spell objective. The catalyst's spell buff comes from `planner.py` unmodified;
    # the multiply that turns it into a spell's attack is `lib/spells.py`, the same one
    # spell-power uses.
    spell_families = spellbook.families().get(spell_name, []) if spell_row else []
    spell_bonus, spell_bonus_applied, spell_bonus_family = (
        spellbook.bonus(row, spell_name, spell_families) if spell_row else (1.0, False, "")
    )
    spell_base = spellbook.base_attack(spell_row) if spell_row else {}
    spell_requirement = spellbook.requirement(spell_row) if spell_row else {}
    spell_planner = planner.Planner()

    def spell_buff_at(stats):
        build = planner.PlannerInputs(
            starting_class=starting_class,
            rh1=planner.WeaponSlotIn(
                weapon=weapon, affinity=affinity, upgrade=request["upgrade"]
            ),
            **{s: stats[s] for s in COMBAT},
        )
        result = spell_planner.calculate(build)
        return float(next(w for w in result.weapons if w.slot == "RH1").spell_buff)

    def spell_attack_at(stats):
        buff = spell_buff_at(stats)
        return sum(spellbook.attack_by_type(spell_base, buff, spell_bonus).values()), buff

    def score(stats):
        """The figure the search maximises, for whichever focus was asked for."""
        if focus == "spell":
            return spell_attack_at(stats)[0]
        return objective(evaluate(stats), focus)

    # --- the floor: class minimums, then the caller's survivability floors, then the
    # weapon's own requirements. Everything here is forced; nothing is a choice.
    stats = dict(minimums)
    floors = {stat: int(request[stat]) for stat in FLOOR_STATS}
    for stat, floor in floors.items():
        stats[stat] = max(stats[stat], min(floor, MAX_STAT))

    # A character carries more than the weapon being optimised. A greatshield needing 48
    # strength, a second katana needing 22 dexterity, a seal needing faith: those are
    # requirements of the build, and a spread that ignores them is a spread that cannot hold
    # the gear it was asked for. Unlike the survivability floors these are not a judgement —
    # they come from attack-power or weapon-lookup on the other piece — so they are echoed
    # separately and the answer can name what each one is paying for.
    stat_floors = {stat: 0 for stat in COMBAT}
    for stat, floor in (request.get("stat_floors") or {}).items():
        stat_floors[stat] = int(floor)
        stats[stat] = max(stats[stat], min(int(floor), MAX_STAT))

    at_floor = evaluate(stats)
    requirements = at_floor.requirements
    # The weapon's scaling coefficients, which do not depend on the spread: a stat at zero
    # here cannot change the answer, so the sweep leaves it at its floor.
    requirements_scaling = at_floor.scaling_percent
    for stat in COMBAT:
        need = requirements.get(stat)
        if need:
            # Two-handing multiplies strength by 1.5, so the raw stat needed is lower.
            if stat == "strength" and two_hand:
                need = -(-int(need) * 2 // 3)
            stats[stat] = max(stats[stat], min(int(need), MAX_STAT))

    # A spell has its own requirements, and a build that cannot cast it is not an answer to
    # "make me a Comet Azur build".
    for stat, need in spell_requirement.items():
        if need:
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
    at_minimum = score(stats)
    best = at_minimum
    if feasible and budget:
        searched += 1

        # The stats that can move the answer at all: a stat the weapon does not scale off
        # buys nothing but its own requirement, and sweeping it multiplies the search for
        # no gain. `floor_stats` is where each of them starts, and no search goes below it.
        floor_stats = {stat: stats[stat] for stat in COMBAT}
        if focus == "spell":
            # A catalyst's spell buff does not follow its attack scaling — an Erdtree Seal's
            # AR is a faith weapon's and its spell buff is a seal's — so liveness is measured
            # rather than read off the table: spend a few points and see whether the spell
            # got stronger.
            live = []
            for stat in COMBAT:
                if stats[stat] >= MAX_STAT:
                    continue
                for step in (1, 10, 30):
                    trial = dict(stats)
                    trial[stat] = min(MAX_STAT, trial[stat] + step)
                    searched += 1
                    if score(trial) > at_minimum:
                        live.append(stat)
                        break
        else:
            live = [
                stat for stat in COMBAT
                if float((requirements_scaling or {}).get(stat) or 0.0) > 0
                and stats[stat] < MAX_STAT
            ]

        # A greedy climb finds a local optimum and a one-point swap cannot always leave it:
        # Moonveil at RL150 stalls at dexterity 59 / intelligence 57 when dexterity 66 /
        # intelligence 50 is worth more, because every single point moved between them costs
        # more than it buys and only the seventh pays off. So when few enough stats are live,
        # sweep every spread instead of climbing. Spending the whole budget is never worse
        # than spending part of it — scaling curves only rise — so the sweep fixes the sum
        # and a trim pass afterwards gives back whatever bought nothing.
        if live and sweep_cost(len(live), budget) <= SWEEP_CAP:
            caps = [MAX_STAT - stats[stat] for stat in live]

            def spreads(remaining, idx):
                if idx == len(live) - 1:
                    # The last stat takes what is left, or as much of it as fits under 99;
                    # the trim pass and the spare-points rule deal with any remainder.
                    yield (min(remaining, caps[idx]),)
                    return
                for value in range(0, min(remaining, caps[idx]) + 1):
                    for rest in spreads(remaining - value, idx + 1):
                        yield (value,) + rest

            best_stats = dict(stats)
            for extra in spreads(budget, 0):
                trial = dict(stats)
                for stat, spend in zip(live, extra):
                    trial[stat] += spend
                searched += 1
                value = score(trial)
                if value > best:
                    best, best_stats = value, trial
            stats = best_stats

            # Give back every point that bought nothing. A status that does not scale is the
            # case this exists for: the sweep spends the budget, finds no spread better than
            # the floor, and the points belong in vigor rather than in a stat that did not
            # move the objective.
            for stat in live:
                floor = max(floor_stats[stat], requirement_floor(requirements, stat, two_hand))
                while stats[stat] > floor:
                    trial = dict(stats)
                    trial[stat] -= 1
                    searched += 1
                    if score(trial) < best:
                        break
                    stats = trial
        elif live:
            # Too many live stats to price every spread. Sweep coarsely — every spread whose
            # points come in multiples of `grain` — and then refine around the winner at
            # finer and finer grain. It is not a proof of optimality the way the full sweep
            # is, but it does not stall the way a greedy climb does: the Frenzied Flame Seal
            # casting Frenzied Burst is 845.4 at strength 26 / dexterity 30 / intelligence 30
            # / faith 43, and a climb with one-point swaps stops at 828.33 because no single
            # point moved between any two of those four stats pays for itself.
            caps = [MAX_STAT - stats[stat] for stat in live]

            def sweep(bounds, grain, ceiling):
                """Every combination on `bounds`, at `grain`, spending at most `ceiling`."""
                def walk(idx, remaining, taken):
                    lo, hi = bounds[idx]
                    if idx == len(bounds) - 1:
                        top = min(hi, lo + (remaining // grain) * grain)
                        if top >= lo:
                            yield taken + (top,)
                        return
                    value = lo
                    while value <= hi and value - lo <= remaining:
                        yield from walk(idx + 1, remaining - (value - lo), taken + (value,))
                        value += grain
                walk_floor = sum(lo for lo, _ in bounds)
                if walk_floor <= ceiling:
                    yield from walk(0, ceiling - walk_floor, ())

            # The floor the search starts from stays fixed; only the winner moves.
            base = dict(stats)

            def price(extra):
                trial = dict(base)
                for stat, spend in zip(live, extra):
                    trial[stat] += spend
                return score(trial), trial

            grain = 1
            while sweep_cost(len(live), budget // grain) > SWEEP_CAP:
                grain *= 2

            center = tuple(0 for _ in live)
            bounds = [(0, cap) for cap in caps]
            while True:
                for extra in sweep(bounds, grain, budget):
                    searched += 1
                    value, trial = price(extra)
                    if value > best:
                        best, stats, center = value, trial, extra
                if grain == 1:
                    break
                grain = max(1, grain // 2)
                bounds = [
                    (max(0, c - 2 * grain), min(cap, c + 2 * grain))
                    for c, cap in zip(center, caps)
                ]

            for stat in live:
                floor = max(floor_stats[stat], requirement_floor(requirements, stat, two_hand))
                while stats[stat] > floor:
                    trial = dict(stats)
                    trial[stat] -= 1
                    searched += 1
                    if score(trial) < best:
                        break
                    stats = trial

        # `live` empty means nothing the caller could level moves the objective at all — a
        # status that does not scale, or a spell with no attack, like Terra Magica. There is
        # no search to run, and the points below go to vigor, which is the honest answer.

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

    # What the spell is worth out of this catalyst at the spread that was chosen. Reported
    # whenever a spell was named, whether or not it was the thing maximised, so a weapon
    # build that also casts can see what it casts for.
    if spell_row is not None:
        spell_attack, spell_buff = spell_attack_at(stats)
        spell_by_type = spellbook.attack_by_type(spell_base, spell_buff, spell_bonus)
        spell_castable = all(stats[stat] >= need for stat, need in spell_requirement.items())
        spell_damage_types = sorted(d for d, v in spell_base.items() if v > 0)
    else:
        spell_attack, spell_buff, spell_by_type = 0.0, 0.0, {}
        spell_castable, spell_damage_types = False, []

    result = {
        "weapon": weapon,
        "weapon_class": row["Weapon Class"],
        "affinity": affinity,
        "affinity_requested": affinity_requested,
        "affinity_ignored": affinity != affinity_requested,
        "infusable": infusable,
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
        # The other gear's requirements, echoed so an answer can say which stat is paying for
        # what. Zero means nothing else asked for that stat.
        "stat_floors": stat_floors,
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
        "spell": spell_name,
        "spell_attack": spell_attack,
        "spell_attack_shown": int(spell_attack),
        "spell_buff": spell_buff,
        "spell_damage_types": spell_damage_types,
        "spell_castable": spell_castable,
        "spell_bonus": spell_bonus,
        "spell_bonus_applied": spell_bonus_applied,
        "spell_bonus_family": spell_bonus_family,
        "objective_value": spell_attack if focus == "spell" else objective(final, focus),
        "objective_at_minimum": at_minimum,
        "objective_gain": round(
            (spell_attack if focus == "spell" else objective(final, focus)) - at_minimum, 9
        ),
        # False means the focus does not respond to levelling at all: the spread below is the
        # floor plus points that had nowhere useful to go. Say so rather than presenting it as
        # an optimised build.
        "objective_responds_to_stats": (
            spell_attack if focus == "spell" else objective(final, focus)
        ) > at_minimum,
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
