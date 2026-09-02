#!/usr/bin/env python3
"""Attack power for one weapon at one upgrade level with one stat spread.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

The arithmetic is `oracle/scripts/ap_calc.py`, the extracted Build Planner spreadsheet logic,
used unmodified. This node adds the three things that code does not have.

**Bounds.** `ap_calc` answers whatever it is asked. Moonveil +25 returns 180.39 — a number for
an upgrade level the game does not have, and lower than the 539.15 the weapon really reaches
at its +10 cap, so it does not even look wrong. The weapon's real cap cannot be checked by a
precondition, because a CEL contract sees only the call's own arguments and never the weapon
table. So this node returns the cap alongside the answer and a postcondition compares them:
an out-of-range upgrade produces no value at all.

**Silent substitutions, made loud.** A non-infusable weapon ignores the affinity it is given:
ask for a Heavy Moonveil and the sheet quietly prices a Standard one. That is reported here as
`affinity_ignored`, so a caller cannot repeat the requested affinity as though it applied.

**No nulls.** The oracle uses `null` for elements a weapon does not deal. A null would make
every contract mentioning that field unevaluable, which fails closed and refuses the call, so
absent damage is reported as `0.0`. `elements` names the ones the weapon actually has.

**Both the precise figure and the displayed one.** `attack` carries full precision, as §8.3
asks; `attack_shown` carries what the game puts on the screen, truncated. Returning only the
first sounds stricter and is how a caller ends up doing the truncation itself: an eval run
quoted "259 holy" off a `259.576275`, and attestation refused it, because rounding 259.576275
to zero decimals is 260. A figure a reader will quote has to exist as a return value.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "lib"))

import oracle  # noqa: E402

sys.path.insert(0, oracle.SCRIPTS)
import ap_calc  # noqa: E402

DAMAGE = ("physical", "magic", "fire", "lightning", "holy")
STATUS = ("poison", "scarlet_rot", "bleed", "frost", "sleep", "madness")
STATS = ("strength", "dexterity", "intelligence", "faith", "arcane")


def number(value):
    """The oracle's `null` means "this weapon deals none of that". Report it as zero."""
    return 0.0 if value is None else float(value)


def main():
    request = json.load(sys.stdin)
    weapon = request["weapon"]
    affinity = request["affinity"]

    calc = ap_calc.ApCalc()
    catalog, _ = oracle.weapons()
    row = catalog.get(weapon)
    if row is None:
        # Reachable only when the caller skipped weapon-lookup. Nothing is broken and there is
        # no answer either; the runtime has no way to say the second, so this is a crash.
        print(
            f"no weapon named {weapon!r}; call weapon-lookup to resolve a name first",
            file=sys.stderr,
        )
        sys.exit(1)

    infusable = bool(row["isInfuse"])
    # A non-infusable weapon is priced as Standard whatever it was asked for. Recording which
    # affinity was actually used is what keeps the caller from quoting the other one.
    applied = affinity if infusable else "Standard"

    inputs = ap_calc.Inputs(
        weapon_class=row["Weapon Class"],
        weapon=weapon,
        affinity=applied,
        upgrade=request["upgrade"],
        strength=request["strength"],
        dexterity=request["dexterity"],
        intelligence=request["intelligence"],
        faith=request["faith"],
        arcane=request["arcane"],
        two_hand=request.get("two_hand", False),
        ignore_require=request.get("ignore_require", False),
        status_buff=request.get("status_buff", "None"),
    )
    print(f"{weapon} {applied} +{inputs.upgrade}", file=sys.stderr)
    r = calc.calculate(inputs)

    attack = {d: number((r.total or {}).get(d)) for d in DAMAGE}
    status = {s: number((r.total or {}).get(s)) for s in STATUS}
    # What the game shows: truncated toward zero, never rounded up.
    shown = {d: int(attack[d]) for d in DAMAGE}
    status_shown = {s: int(status[s]) for s in STATUS}

    result = {
        "weapon": weapon,
        "weapon_class": row["Weapon Class"],
        "label": r.weapon_label,
        "affinity_requested": affinity,
        "affinity_applied": applied,
        "affinity_ignored": applied != affinity,
        "infusable": infusable,
        "upgrade": inputs.upgrade,
        "max_upgrade": oracle.max_upgrade(row),
        "two_hand": bool(inputs.two_hand),
        "total_ar": float(r.total_ar),
        "total_ar_rounded": int(r.total_ar_rounded),
        "attack": attack,
        "attack_shown": shown,
        # The damage types this weapon actually deals, so a caller can see at a glance which
        # of the five zeros above are real.
        "elements": [d for d in DAMAGE if attack[d] > 0],
        "status": status,
        "status_shown": status_shown,
        "status_effects": [s for s in STATUS if status[s] > 0],
        "scaling": {
            stat: {
                "letter": r.scaling_letter.get(stat, "-"),
                "percent": number(r.scaling_percent.get(stat)),
                "requirement": int(number(r.requirements.get(stat))),
                "req_met": bool(r.req_met.get(stat, True)),
            }
            for stat in STATS
        },
        "requirements_met": all(r.req_met.get(s, True) for s in STATS),
        "guard_boost": int(r.guard_boost),
        "guard_negation": {d: number(r.guard_negation.get(d)) for d in DAMAGE},
        # What blocking with this weapon resists. Left out until now, which made the guard
        # half of the answer incomplete: a shield's status resistance is most of why one is
        # chosen over another.
        "guard_resist": {s: int(number(r.guard_resist.get(s))) for s in STATUS},
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
