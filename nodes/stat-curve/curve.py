#!/usr/bin/env python3
"""What each point in a stat actually buys, and where the curve bends.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

"Onde estão os breakpoints de vigor?" and "quanto ganho por ponto de INT depois de 60?" are the
two most-repeated questions in Pattern 11, and both are answered everywhere by folk knowledge —
"soft cap at 40", "60 then 80" — which is the kind of number a model will produce whether or
not it is true. It is computable: walk the stat one point at a time and ask the oracle.

Three things it can walk, because they are three different curves:

- `vitals` — vigor to HP, mind to FP, endurance to stamina and equip load, from `planner.py`.
- `weapon` — a stat against one weapon's attack rating, from `ap_calc.py`.
- `spell` — a stat against what a spell hits for out of a catalyst, which is the spell buff
  curve and is *not* the same shape as the catalyst's own attack rating.

**A soft cap here is measured, not named.** It is a point where the gain from the next level
drops against the one before it, and the node reports every such bend with the figures either
side. Nobody has to trust "40 and 60".
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "lib"))

import judgement  # noqa: E402
import oracle  # noqa: E402
import spells as spellbook  # noqa: E402

sys.path.insert(0, oracle.SCRIPTS)
import ap_calc  # noqa: E402
import planner  # noqa: E402

COMBAT = ("strength", "dexterity", "intelligence", "faith", "arcane")
VITALS = {"vigor": "hp", "mind": "fp", "endurance": "stamina"}


def main():
    request = json.load(sys.stdin)
    # Every judgement this node makes, decided in one place and before anything reads them.
    # They were previously read at their point of use, which put one of them above its own
    # definition the moment a second parameter joined it.
    chosen, assumed = judgement.applied(request, "starting_class", "two_hand")
    stat = request["stat"]
    subject = request.get("subject", "vitals")
    low = int(request.get("from", 1))
    high = int(request.get("to", 99))
    starting_class = chosen["starting_class"]

    stats = {s: int(request.get(s, 10)) for s in COMBAT}
    for name in VITALS:
        stats[name] = int(request.get(name, 10))

    if subject == "vitals" and stat not in VITALS:
        print(f"vitals curves are vigor, mind and endurance; {stat!r} is not one",
              file=sys.stderr)
        sys.exit(1)
    if subject != "vitals" and stat not in COMBAT:
        print(f"{stat!r} is not one of the five the oracle scales damage from", file=sys.stderr)
        sys.exit(1)

    catalog, _ = oracle.weapons()
    row = None
    if subject in ("weapon", "spell"):
        weapon = request["weapon"]
        row = catalog.get(weapon)
        if row is None:
            print(f"no weapon named {weapon!r}; call weapon-lookup first", file=sys.stderr)
            sys.exit(1)

    spell_row = None
    catalyst_casts = oracle.casts(row) if row else []
    if subject == "spell":
        spell_row = spellbook.book().get(request["spell"])
        if spell_row is None:
            print(f"no spell named {request['spell']!r}; call spell-lookup first",
                  file=sys.stderr)
            sys.exit(1)
        # A curve for a cast that cannot happen is a curve about nothing: a staff walked
        # through faith for an incantation climbs perfectly smoothly and means nothing.
        if (spell_row.get("Type") or "") not in catalyst_casts:
            print(
                f"{request['weapon']} casts {', '.join(catalyst_casts) or 'nothing'}, "
                f"and {request['spell']} is a {spell_row.get('Type')}",
                file=sys.stderr,
            )
            sys.exit(1)
        families = spellbook.families().get(request["spell"], [])
        bonus, _, _ = spellbook.bonus(row, request["spell"], families)
        base = spellbook.base_attack(spell_row)

    calc = ap_calc.ApCalc()
    engine = planner.Planner()

    unmet_at = {}

    def value_at(level):
        here = dict(stats)
        here[stat] = level
        if subject == "vitals":
            build = planner.PlannerInputs(
                starting_class=starting_class,
                **{s: here[s] for s in COMBAT},
                vigor=here["vigor"], mind=here["mind"], endurance=here["endurance"],
            )
            result = engine.calculate(build)
            return float(getattr(result, VITALS[stat]))
        if subject == "weapon":
            result = calc.calculate(ap_calc.Inputs(
                weapon_class=row["Weapon Class"], weapon=request["weapon"],
                affinity=request.get("affinity", "Standard"),
                upgrade=int(request.get("upgrade", oracle.max_upgrade(row))),
                two_hand=bool(chosen["two_hand"]),
                **{s: here[s] for s in COMBAT},
            ))
            unmet_at[level] = sorted(
                stat_name for stat_name in COMBAT if not result.req_met.get(stat_name, True)
            )
            return float(result.total_ar)
        build = planner.PlannerInputs(
            starting_class=starting_class,
            **{s: here[s] for s in COMBAT},
            vigor=here["vigor"], mind=here["mind"], endurance=here["endurance"],
            rh1=planner.WeaponSlotIn(
                weapon=request["weapon"], affinity=request.get("affinity", "Standard"),
                upgrade=int(request.get("upgrade", oracle.max_upgrade(row))),
            ),
        )
        result = engine.calculate(build)
        buff = float(next(w for w in result.weapons if w.slot == "RH1").spell_buff)
        return sum(spellbook.attack_by_type(base, buff, bonus).values())

    points = []
    previous = None
    for level in range(low, high + 1):
        here = value_at(level)
        gain = None if previous is None else round(here - previous, 6)
        points.append({
            "level": level, "value": here, "gain": gain,
            # A curve that does not move because a *different* stat's requirement is unmet is
            # the trap here: a flat line reads as "this stat does nothing". A Zweihander at
            # dexterity 10 is 191.76 at every strength from 16 to 99, and the reason is the
            # dexterity.
            "requirements_unmet": unmet_at.get(level, []),
        })
        previous = here

    # A bend is where the next point buys materially less than the last one did. "Materially"
    # is the whole trick: these curves step down by a point here and there from rounding, and
    # calling every one of those a soft cap gives twenty-two of them for vigor. A quarter of the
    # gain lost is the threshold, and it finds vigor 40 and 60 — the two everybody names,
    # arrived at rather than recited.
    threshold = float(request.get("bend_threshold", 0.75))
    # Compared over a window rather than point to point. HP and stamina step in whole numbers,
    # so a single point of rounding noise looks like a cliff: endurance produced twenty-five
    # "soft caps" that way. Averaging three points either side leaves the bends that are real.
    window = int(request.get("window", 3))

    def mean_gain(start, stop):
        gains = [p["gain"] for p in points[start:stop] if p["gain"] is not None]
        return sum(gains) / len(gains) if gains else None

    bends = []
    for i in range(1, len(points)):
        before = mean_gain(max(0, i - window), i)
        after = mean_gain(i, min(len(points), i + window))
        if before is None or after is None or before <= 0:
            continue
        if after < before * threshold:
            if bends and points[i]["level"] - 1 - bends[-1]["level"] <= window:
                # One bend smeared over a few levels by the window is still one bend; keep the
                # steepest of them rather than reporting the same soft cap five times.
                if after / before < bends[-1]["kept"]:
                    bends[-1] = {
                        "level": points[i]["level"] - 1,
                        "gain_before": round(before, 4),
                        "gain_after": round(after, 4),
                        "kept": round(after / before, 4),
                        "value": points[i - 1]["value"],
                    }
                continue
            bends.append({
                "level": points[i]["level"] - 1,
                "gain_before": round(before, 4),
                "gain_after": round(after, 4),
                "kept": round(after / before, 4),
                "value": points[i - 1]["value"],
            })

    best = max((p for p in points if p["gain"] is not None),
               key=lambda p: p["gain"], default=None)
    print(
        f"{stat} {low}..{high} on {subject}: {len(bends)} bends",
        file=sys.stderr,
    )

    stats_raised = oracle.class_floor(
        starting_class, {s: stats[s] for s in COMBAT}
    )[1] if subject != "weapon" else []

    result = {
        "stat": stat,
        "subject": subject,
        "from": low,
        "to": high,
        "points": points,
        # Every level where the next point buys less than the one before it did.
        "bends": bends,
        "soft_caps": [b["level"] for b in bends],
        "bend_threshold": threshold,
        "window": window,
        "total_gain": round(points[-1]["value"] - points[0]["value"], 6) if points else 0.0,
        "best_point": best["level"] if best else 0,
        "best_point_gain": best["gain"] if best else 0.0,
        "value_at_from": points[0]["value"] if points else 0.0,
        "value_at_to": points[-1]["value"] if points else 0.0,
        "weapon": request.get("weapon", ""),
        "spell": request.get("spell", ""),
        # A curve is for a weapon at an upgrade and an affinity, and saying which is the
        # difference between a figure somebody can check and a figure they cannot.
        "affinity": request.get("affinity", "Standard") if row else "",
        "upgrade": int(request.get("upgrade", oracle.max_upgrade(row))) if row else None,
        "two_hand": bool(chosen["two_hand"]),
        "held_stats": {s: stats[s] for s in COMBAT},
        "catalyst_casts": catalyst_casts,
        "starting_class": starting_class,
        # What the collection decided because nobody else did.
        "assumed": assumed,
        # Stats the class floor lifted above what was asked for. planner.py treats a class's
        # stats as a minimum, so a vitals or spell curve for a Wretch never dips below ten.
        "stats_raised_by_class": stats_raised,
        # Stats whose requirement is unmet somewhere in the range. While one is, the curve is
        # flat for a reason that has nothing to do with the stat being walked.
        "requirements_unmet": sorted({
            name for row in points for name in row["requirements_unmet"]
        }),
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
