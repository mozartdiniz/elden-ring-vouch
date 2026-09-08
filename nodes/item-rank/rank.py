#!/usr/bin/env python3
"""Rank the buffs that are worth something on one kind of hit.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

This is the node question 5.1 asks for and the collection could not answer: *which four
talismans maximise the damage of X*. `buff-stack` prices a set the caller already chose;
nothing selected the set, so a model asked to pick four either invented them or — once it
stopped inventing — said no node does this. Both shipping candidates said exactly that, across
all six runs, and they were right.

**It ranks, it does not choose.** The result is every buff worth more than 1.0 on the hit
kind asked about, in order, with what each is worth. Picking four out of it is still the
caller's, because "best" depends on what the user can actually hold: a talisman slot count
this node does not know, a physick already spent, a condition the player cannot meet.

**Conditional buffs are ranked and flagged, never silently counted.** Lord of Blood's
Exultation is worth 1.2 after a bleed proc and 1.0 the rest of the time, and the difference is
a fact about the fight rather than the build. They appear with `conditional: true` and are left
out of `best_unconditional`, which is the figure a caller can quote without asserting anything.
`buff-stack --assume` is where an assertion belongs, and this node points at it.
"""

import json
import os
import sys

# The status a node exits with to refuse: it understood the question and there is no answer.
REFUSE = 3

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "lib"))

import buffs  # noqa: E402


def main():
    request = json.load(sys.stdin)
    hit_kind = request["hit_kind"]
    pvp = bool(request.get("pvp", False))
    want_slot = (request.get("slot") or "").strip()
    want_kind = (request.get("kind") or "").strip()
    limit = int(request.get("limit", 10))
    # A conditional buff is worth more than an unconditional one only when its condition holds,
    # and a ranking that sorts 1.8x-after-a-proc above 1.15x-always would have a caller quote
    # the first without noticing. The flag on every row says which is which; this says "do not
    # show me the ones I would have to assert", which is the question behind most askings of
    # "what should I wear".
    unconditional_only = bool(request.get("unconditional_only", False))

    if hit_kind not in buffs.HIT_KINDS:
        print(
            f"{hit_kind!r} is not a hit kind; the table knows "
            f"{', '.join(buffs.HIT_KINDS)}",
            file=sys.stderr,
        )
        sys.exit(REFUSE)

    table = buffs.table()
    rules = buffs.slot_rules()

    ranked = []
    for name, entry in table.items():
        if name == "none":
            continue
        if want_kind and entry["kind"] != want_kind:
            continue
        if want_slot and entry["slot"] != want_slot:
            continue

        value = buffs.multiplier(entry, hit_kind, pvp)
        if value <= 1.0:
            continue

        conditional = buffs.state_conditional(entry, pvp)
        if conditional and unconditional_only:
            continue
        ranked.append(
            {
                "buff": name,
                "kind": entry["kind"],
                "slot": entry["slot"],
                "multiplier": round(value, 6),
                # What the caller would have to be true. `buff-stack` takes these in `assume`.
                "conditional": conditional,
                "note": entry["note"],
            }
        )

    # Highest first, then by name so a tie is not decided by dictionary order — two buffs worth
    # 1.15 have to come back in the same order on every call or the same question gives two
    # different answers.
    ranked.sort(key=lambda row: (-row["multiplier"], row["buff"]))
    shown = ranked[:limit]

    unconditional = [row for row in ranked if not row["conditional"]]
    print(
        f"{len(ranked)} buff(s) above 1.0 on {hit_kind}"
        f"{' in PvP' if pvp else ''}; showing {len(shown)}",
        file=sys.stderr,
    )

    result = {
        "hit_kind": hit_kind,
        "pvp": pvp,
        "unconditional_only": unconditional_only,
        "ranked": shown,
        "count": len(ranked),
        "returned": len(shown),
        "truncated": len(ranked) > len(shown),
        # The best a caller can quote without asserting anything about the fight.
        "best_unconditional": round(unconditional[0]["multiplier"], 6) if unconditional else 1.0,
        "conditional_count": sum(1 for row in ranked if row["conditional"]),
        # Slots decide whether two of these can be worn together, and this node does not
        # combine anything. Handed over so a caller does not have to guess which node does.
        "slot_rules": {slot: rule for slot, (rule, _) in sorted(rules.items())},
        "stack_with": "buff-stack",
        "catalog_size": len(table) - 1,
        "hit_kinds": list(buffs.HIT_KINDS),
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
