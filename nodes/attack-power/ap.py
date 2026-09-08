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

**The gap, not just the verdict.** `req_met` says a requirement is missed; `shortfall` says by
how much. An eval run answered "you'd need 2 more points" off a requirement of 12 and a
strength of 10, and attestation refused the 2 — a subtraction is arithmetic, and arithmetic a
caller does is arithmetic a model does. The stats it is measured against are the *effective*
ones, so two-handing is already accounted for.

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
import math
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
import ap_calc  # noqa: E402

DAMAGE = ("physical", "magic", "fire", "lightning", "holy")
STATUS = ("poison", "scarlet_rot", "bleed", "frost", "sleep", "madness")
STATS = ("strength", "dexterity", "intelligence", "faith", "arcane")


def number(value):
    """The oracle's `null` means "this weapon deals none of that". Report it as zero."""
    return 0.0 if value is None else float(value)


def main():
    request = json.load(sys.stdin)
    # two_hand is not a neutral default: two-handing multiplies effective strength by 1.5,
    # and on question 7.1 it moved a real answer from 342 to 383 — internally consistent,
    # attested, and answering a question nobody asked. False asserts the least, and `assumed`
    # is what stops it asserting silently.
    chosen, assumed = judgement.applied(request, "two_hand")
    weapon = request["weapon"]
    affinity = request["affinity"]

    calc = ap_calc.ApCalc()
    catalog, _ = oracle.weapons()
    row = catalog.get(weapon)
    if row is None:
        # Reachable only when the caller skipped weapon-lookup. Nothing is broken and there
        # is no answer either — and the runtime can now say the second, which it could not
        # when this comment ended "so this is a crash".
        print(
            f"no weapon named {weapon!r}; call weapon-lookup to resolve a name first",
            file=sys.stderr,
        )
        sys.exit(REFUSE)

    infusable = bool(row["isInfuse"])
    # A non-infusable weapon is priced as Standard whatever it was asked for. Recording which
    # affinity was actually used is what keeps the caller from quoting the other one.
    applied = affinity if infusable else "Standard"

    # A buff a weapon cannot take is silently dropped by the oracle: `_status_buff_effect_id`
    # returns -1 and the figures come back unbuffed, identical to a call that named no buff at
    # all. Blood Grease on a Rivers of Blood is 76 bleed either way, and a caller quoting that
    # as a greased figure would be wrong in the same way quoting an ignored affinity is.
    status_buff = request.get("status_buff", "None")
    buff_applies = status_buff == "None" or any(
        b["buff"] == status_buff and b["applies"]
        for b in oracle.status_buffs(row, applied)
    )
    buff_reason = ""
    if not buff_applies:
        buff_reason = next(
            (b["reason"] for b in oracle.status_buffs(row, applied)
             if b["buff"] == status_buff),
            f"{status_buff!r} is not one of the buffs in the table",
        )

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
        two_hand=chosen["two_hand"],
        ignore_require=request.get("ignore_require", False),
        status_buff=request.get("status_buff", "None"),
    )
    print(f"{weapon} {applied} +{inputs.upgrade}", file=sys.stderr)
    r = calc.calculate(inputs)

    attack = {d: number((r.total or {}).get(d)) for d in DAMAGE}
    status = {s: number((r.total or {}).get(s)) for s in STATUS}

    # What the game shows, and it is not the truncated total.
    #
    # The equipment screen prints a damage type as two numbers — "291 + 281" — and truncates
    # **each** before adding them. Truncating the sum instead gives a figure up to one point
    # higher per damage type, which is what this did: Godslayer's Greatsword at 291.550 base
    # and 281.914 scaling is 573.464, and the game shows 572.
    #
    # Caught by photographs of three real characters. Every base and scaling figure here
    # matched the screen exactly, to three decimals, on all six damage types — the arithmetic
    # was never wrong. Only the rounding was, and only in the field whose whole purpose is to
    # be the number a player sees and quotes back.
    # `math.floor` and not `int`, which truncates toward zero. When a requirement is unmet the
    # scaling term is negative — Godslayer's Greatsword at ten dexterity is 291.550 base and
    # -116.620 scaling — and `int(-116.620)` is -116, which would make the shown figure 175
    # against a true 174.930. Overstating a penalised weapon is the wrong direction to be
    # wrong in, and it breaks the invariant that the shown figure never exceeds the real one.
    #
    # No screenshot here has an unmet requirement, so the game's own handling of a negative
    # component is unverified. Flooring is the choice that cannot overstate.
    def as_shown(figures, key):
        base = number((r.base or {}).get(key))
        scale = number((r.scaling or {}).get(key))
        if base or scale:
            return math.floor(base) + math.floor(scale)
        return math.floor(figures[key])

    shown = {d: as_shown(attack, d) for d in DAMAGE}
    status_shown = {s: as_shown(status, s) for s in STATUS}

    # Guard negation is a percentage and the screen gives it to one decimal, truncated: 46.55
    # reads as 46.5, 23.75 as 23.7. Publishing only full precision is what bug 2 was about —
    # a reader with 46.55 in front of them writes 46.55, and the game never showed that.
    #
    # The rounding to six places first is for float representation, not for the game: the
    # magic figure arrives as 43.699999999999996, and truncating that directly gives 43.6.
    def to_one_decimal(value):
        return math.floor(round(value, 6) * 10) / 10

    result = {
        "weapon": weapon,
        "weapon_class": row["Weapon Class"],
        "label": r.weapon_label,
        "affinity_requested": affinity,
        "affinity_applied": applied,
        "affinity_ignored": applied != affinity,
        "status_buff": status_buff,
        # False means the figures below are unbuffed however the call was written. Quoting them
        # as buffed is the same mistake as quoting an affinity that was ignored.
        "status_buff_applied": buff_applies,
        "status_buff_ignored_because": buff_reason,
        "infusable": infusable,
        "upgrade": inputs.upgrade,
        "max_upgrade": oracle.max_upgrade(row),
        "two_hand": bool(inputs.two_hand),
        # What the collection decided because nobody else did.
        "assumed": assumed,
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
                # Against the effective stat, which already includes the two-handed strength
                # bonus, so "two more points" means two more points of the raw stat only when
                # the weapon is held one-handed. Zero whenever the requirement is met.
                "effective": int(number(r.stats.get(stat))),
                "shortfall": max(
                    0,
                    int(number(r.requirements.get(stat))) - int(number(r.stats.get(stat))),
                )
                if not r.req_met.get(stat, True)
                else 0,
            }
            for stat in STATS
        },
        "requirements_met": all(r.req_met.get(s, True) for s in STATS),
        "guard_boost": int(r.guard_boost),
        "guard_negation": {d: number(r.guard_negation.get(d)) for d in DAMAGE},
        # The same figures as the screen prints them. See `to_one_decimal`.
        "guard_negation_shown": {
            d: to_one_decimal(number(r.guard_negation.get(d))) for d in DAMAGE
        },
        # What blocking with this weapon resists. Left out until now, which made the guard
        # half of the answer incomplete: a shield's status resistance is most of why one is
        # chosen over another.
        "guard_resist": {s: int(number(r.guard_resist.get(s))) for s in STATUS},
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
