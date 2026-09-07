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

# The status a node exits with to refuse: it understood the question and there is no answer.
# vouch turns it into exit 16, a refusal, with this node's stderr as the reason — where every
# non-zero exit used to become exit 20, a defect, which tells the caller the node is broken
# and throws away the rest of their question along with the part that had none.
REFUSE = 3

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
    sources = buffs.source_table()
    rules = buffs.slot_rules()
    # A cast is more than one thing at once: Comet is a *sorcery* and it deals *magic*, and
    # Graven-Mass keys on the first while Magic Scorpion Charm keys on the second. One string
    # here would make the two talismans exclusive when the game stacks them.
    damage_sources = [s.strip().lower() for s in (request.get("damage_sources") or [])]

    known = sorted(set(table) | set(sources))
    unknown = [name for name in names if name not in table and name not in sources]
    if unknown:
        # A name the tables do not carry used to exit 1, which the runtime reads as exit 20 —
        # a defect. That tells the caller the node is broken when the node is fine and the
        # name is not, and it ends the conversation instead of correcting it. Cragblade found
        # this: a real Ash of War, present in four other tables the collection ships, absent
        # from BuffMult because it is not modelled as a multiplier.
        #
        # So the miss comes back as data, the way weapon-lookup reports match_count 0. What
        # does NOT come back is a stack: with a buff unaccounted for, a product over the
        # remaining ones is a well-formed number for a combination nobody asked about, and it
        # would attest. `multiplier` stays 1.0 and `applied` stays empty on purpose.
        print(
            json.dumps(
                {
                    "buffs": names,
                    "hit_kind": hit_kind,
                    "damage_sources": damage_sources,
                    "pvp": pvp,
                    "assumed": assumed,
                    "unknown": unknown,
                    "known_buffs": known,
                    "multiplier": 1.0,
                    "damage_multiplier": {kind: 1.0 for kind in DAMAGE_KINDS},
                    "applied": [],
                    # Every buff given has to appear in applied or not_counted — the node's
                    # own postcondition says so, and it is right to. An unrecognised name is
                    # not counted, and saying that explicitly is better than the list being
                    # short by one.
                    "not_counted": [
                        {
                            "buff": name,
                            "kind": "",
                            "slot": "None",
                            "multiplier": 1.0,
                            "applies_on": [],
                            "state_conditional": False,
                            "note": "",
                            "excluded_because": "no such buff in the tables"
                            if name in unknown
                            else "no product is computed while another name is unrecognised",
                        }
                        for name in names
                    ],
                    "slot_rules": {slot: rule for slot, (rule, _) in sorted(rules.items())},
                    "hit_kinds": list(buffs.HIT_KINDS),
                    "catalog_size": len(table),
                }
            )
        )
        return
    not_held = [name for name in assumed if name not in names]
    if not_held:
        print(f"asserted but not among the buffs given: {', '.join(not_held)}", file=sys.stderr)
        sys.exit(REFUSE)

    factors, not_counted = [], []
    for name in names:
        # The other axis: a talisman conditional on what the damage *is* rather than on how it
        # was dealt. Graven-Mass multiplies sorceries and Fire Scorpion Charm multiplies fire,
        # and neither is a hit kind — `BuffMult` has nothing to say about either.
        if name in sources and name not in table:
            entry = sources[name]
            rate = entry["multiplier"]
            if pvp and entry["pvp_multiplier"] is not None:
                rate = entry["pvp_multiplier"]
            row = {
                "buff": name,
                "kind": "Talisman",
                "slot": "Passive",
                "multiplier": rate,
                "applies_on": [entry["source"]],
                "state_conditional": False,
                "note": entry["source_text"],
                "cost": entry["cost"],
            }
            if entry["source"] not in damage_sources:
                row["excluded_because"] = (
                    f"it multiplies {entry['source']} damage"
                    + (f", and this hit is " + " and ".join(damage_sources)
                       if damage_sources else " and no damage_sources were given")
                )
                row["multiplier"] = 1.0
                not_counted.append(row)
            else:
                factors.append(dict(row, item=name))
            continue

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
        "damage_sources": damage_sources,
        "pvp": pvp,
        "assumed": assumed,
        "multiplier": total,
        "unknown": [],
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
