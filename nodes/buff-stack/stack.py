#!/usr/bin/env python3
"""What a set of buffs multiplies your damage by, for one kind of hit.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

This is the arithmetic every "me mostra o multiplicador total" question ends on, and the one a
caller left holding would do in prose. Two facts decide the answer and neither is a judgement:

**Which hit it is.** Shard of Alexander is 1.15 on a weapon skill and 1.0 on everything else;
Dagger Talisman is 1.17 on a critical and 1.0 elsewhere; Claw Talisman is 1.15 on a jump. So
`hit_kind` is the assertion, and for those items there is nothing left for a caller to claim.

**Which slot each buff occupies.** Talismans multiply. Auras do not: Golden Vow as a spell, as
an ash and as a tool all occupy one slot, the last one applied wins, and multiplying them would
be a figure for a stack the game does not allow. `shadowed` names what was overwritten.

What is left for the caller is the third kind of condition — a *state* the tables cannot see. A
buff worth more than 1.0 on **every** hit kind is not conditional on the hit at all: Lord of
Blood's Exultation needs a bleed to have procced, Ritual Sword Talisman needs full HP,
Millicent's Prosthesis needs a run of successive hits. Those are asserted with `assume`, and
that distinction is read off the table rather than guessed at.

`item-effect` is the node for what a talisman is worth in stats, weight and resistances. This
one is only about multipliers, and it takes buffs that are not items at all — an ash, a spell,
a physick tear.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "lib"))

import buffs  # noqa: E402

DAMAGE_KINDS = ("physical", "strike", "slash", "pierce", "magic", "fire", "lightning", "holy")


def main():
    request = json.load(sys.stdin)
    names = list(request["buffs"])
    hit_kind = request.get("hit_kind", "All")
    pvp = bool(request.get("pvp", False))
    assumed = list(request.get("assume", []))

    table = buffs.table()
    rules = buffs.slot_rules()

    unknown = [name for name in names if name not in table]
    if unknown:
        print(
            "not in BuffMult.csv: " + ", ".join(unknown)
            + f"; the {len(table)} it knows are: " + ", ".join(sorted(table)),
            file=sys.stderr,
        )
        sys.exit(1)
    not_held = [name for name in assumed if name not in names]
    if not_held:
        print(f"asserted but not among the buffs given: {', '.join(not_held)}", file=sys.stderr)
        sys.exit(1)

    factors, not_counted = [], []
    for name in names:
        entry = table[name]
        rate = buffs.multiplier(entry, hit_kind, pvp)
        state = buffs.state_conditional(entry, pvp)
        row = {
            "buff": name,
            "kind": entry["kind"],
            "slot": entry["slot"],
            "multiplier": rate,
            "applies_on": buffs.applies_on(entry, pvp),
            "state_conditional": state,
            "note": entry["note"],
        }
        if rate <= 1.0:
            row["excluded_because"] = f"worth 1.0 on a {hit_kind} hit"
            not_counted.append(row)
        elif state and name not in assumed:
            row["excluded_because"] = "its condition is a state you did not assert"
            not_counted.append(row)
        else:
            factors.append(dict(row, item=name))

    total, applied, shadowed = buffs.stack(factors, rules)
    for row in shadowed:
        row["excluded_because"] = f"the {row['slot']} slot overwrites rather than multiplies"

    print(
        f"{hit_kind}{' PvP' if pvp else ''}: {len(applied)} of {len(names)} buffs, x{total}",
        file=sys.stderr,
    )

    result = {
        "buffs": names,
        "hit_kind": hit_kind,
        "pvp": pvp,
        "assumed": assumed,
        "multiplier": total,
        "applied": [
            {k: v for k, v in row.items() if k != "item"} for row in applied
        ],
        # What the game would have overwritten, and what this hit kind does not qualify for.
        # Listing them is what makes the answer actionable: it is the change a player makes.
        "not_counted": [
            {k: v for k, v in row.items() if k != "item"}
            for row in not_counted + list(shadowed)
        ],
        "slot_rules": {slot: rule for slot, (rule, _) in sorted(rules.items())},
        # Shaped for optimal-affinity's `damage_multiplier`, so nothing reshapes it downstream.
        "damage_multiplier": {kind: total for kind in DAMAGE_KINDS},
        "hit_kinds": list(buffs.HIT_KINDS),
        "catalog_size": len(table),
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
