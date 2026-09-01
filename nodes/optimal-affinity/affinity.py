#!/usr/bin/env python3
"""Rank every affinity a weapon can take, by the damage it would actually deal.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

The arithmetic is `oracle/scripts/opt_affinity_calc.py`, unmodified. It answers the question
players actually ask — "what should I infuse this with?" — which is thirteen comparisons
against a target's defences and absorptions, and is exactly the shape of question a model
answers from vibes.

Two things this node does that the oracle does not.

**It drops the affinities that do not exist.** The calculator returns thirteen rows whatever
it is given, with `null` damage for the twelve a non-infusable weapon cannot take. A null is
not a weak answer, it is the absence of one, and leaving it in a ranked list invites a caller
to read "Heavy: null" as a real comparison. Only affinities the weapon can actually take are
returned, and `infusable` says which case this is.

**It names the winner rather than leaving it to be read off.** `best` is the top row, and a
postcondition ties it to the maximum of the list — so "best" is a claim the runtime checked,
not a position in an array a caller might mis-index.

Damage is against a target: the default is the calculator's standard PvE reference, and a
caller can pass real defences instead. Which was used comes back as `target`, because the same
weapon ranks differently against different enemies and an answer that does not say which
target it assumed is not an answer.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "lib"))

import oracle  # noqa: E402

sys.path.insert(0, oracle.SCRIPTS)
import opt_affinity_calc as opt  # noqa: E402

ELEMENTS = ("physical", "magic", "fire", "lightning", "holy")


def main():
    request = json.load(sys.stdin)
    weapon = request["weapon"]

    catalog, _ = oracle.weapons()
    row = catalog.get(weapon)
    if row is None:
        print(
            f"no weapon named {weapon!r}; call weapon-lookup to resolve a name first",
            file=sys.stderr,
        )
        sys.exit(1)

    given_defense = request.get("defense") or {}
    inputs = opt.OptInputs(
        weapon_class=row["Weapon Class"],
        weapon=weapon,
        upgrade=request["upgrade"],
        strength=request["strength"],
        dexterity=request["dexterity"],
        intelligence=request["intelligence"],
        faith=request["faith"],
        arcane=request["arcane"],
        two_hand=request.get("two_hand", False),
        attack_mv=float(request.get("attack_mv", 100.0)),
        defense=dict(given_defense),
        avg_pve=request.get("avg_pve", False),
        counter_hit=request.get("counter_hit", False),
    )
    calc = opt.OptAffinityCalc()
    r = calc.calculate(inputs)

    # A row whose damage is None is an affinity this weapon cannot take. That is not a low
    # score to be ranked last; it is not a row at all.
    ranked = [
        {
            "affinity": row_.affinity,
            "damage": float(row_.damage),
            "total_ap": float(row_.total_ap),
            "split": row_.split or "",
            **{e: float(getattr(row_, e) or 0.0) for e in ELEMENTS},
        }
        for row_ in r.rows
        if row_.damage is not None
    ]
    print(f"{weapon}: {len(ranked)} affinities available", file=sys.stderr)

    infusable = bool(row["isInfuse"])
    best = max(ranked, key=lambda x: x["damage"])
    ranked.sort(key=lambda x: -x["damage"])

    result = {
        "weapon": weapon,
        "weapon_class": row["Weapon Class"],
        "upgrade": inputs.upgrade,
        "max_upgrade": oracle.max_upgrade(row),
        "two_hand": bool(inputs.two_hand),
        "infusable": infusable,
        "affinities_available": len(ranked),
        "best": best["affinity"],
        "best_damage": best["damage"],
        # The runner-up, so an answer can say whether the choice was close or obvious without
        # a caller subtracting two rows.
        "runner_up": ranked[1]["affinity"] if len(ranked) > 1 else "",
        "best_margin": round(best["damage"] - ranked[1]["damage"], 6) if len(ranked) > 1 else 0.0,
        "ranked": ranked,
        # Which target these numbers are about. The same weapon ranks differently against
        # different enemies, so an answer that omits this is not an answer.
        "target": "given" if given_defense else "default",
        "attack_mv": float(inputs.attack_mv),
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
