#!/usr/bin/env python3
"""Resolve a weapon name, and report the bounds every other node needs.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

Two jobs, and the second is the one that is easy to miss:

1. **Resolve the name.** 570 weapons, and a user types "rivers of blood" or "gs". An exact
   normalised match wins outright; otherwise every weapon whose name contains all of the
   query's tokens is a candidate. More than one candidate means the question has no single
   answer yet, so `resolved` stays empty and the caller has to ask which was meant. That is
   enforced by a postcondition, not merely requested.

2. **Report what the weapon can do**: its class, whether it takes affinities, and how far it
   can be upgraded. `attack-power` cannot check those itself — a CEL precondition sees only
   the call's own arguments, never the weapon table — so a caller that skips this step can ask
   for Moonveil +25 and the spreadsheet maths will answer with a number for an upgrade level
   the game does not have.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "lib"))

import oracle  # noqa: E402

# How many candidates to list when a query is ambiguous. A query like "sword" matches over a
# hundred weapons; a caller needs enough to recognise the one they meant, not all of them.
MAX_CANDIDATES = 20


def normalize(text):
    """Lowercase, apostrophe-free, single-spaced. Comparison happens only on this form."""
    text = text.lower().replace("'", "").replace("’", "")
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())


def resolve(query, names):
    target = normalize(query)

    # An exact name is unambiguous by construction, whatever else it is a substring of:
    # "Longsword" resolves even though "Lordsworn's Straight Sword" also contains it.
    exact = [name for name in names if normalize(name) == target]
    if exact:
        return exact

    tokens = target.split()
    if not tokens:
        return []
    return sorted(
        name for name in names if all(token in normalize(name) for token in tokens)
    )


def main():
    request = json.load(sys.stdin)
    affinity = (request.get("affinity") or "Standard").strip()
    query = request["query"]
    weapon_class = request.get("weapon_class", "")

    catalog, _ = oracle.weapons()
    names = [
        name
        for name, row in catalog.items()
        if not weapon_class or row["Weapon Class"] == weapon_class
    ]

    candidates = resolve(query, names)
    print(f"{query!r} matched {len(candidates)} of {len(names)}", file=sys.stderr)

    resolved = candidates[0] if len(candidates) == 1 else ""
    row = catalog[resolved] if resolved else None
    status_buffs = oracle.status_buffs(row, affinity) if row else []
    buffable = any(b["applies"] for b in status_buffs)

    result = {
        "query": query,
        # Empty rather than null: a caller reading this field gets a string either way, and an
        # empty one is never mistaken for a name.
        "resolved": resolved,
        "weapon_class": row["Weapon Class"] if row else "",
        "match_count": len(candidates),
        "candidates": candidates[:MAX_CANDIDATES],
        "candidates_truncated": len(candidates) > MAX_CANDIDATES,
        "ambiguous": len(candidates) > 1,
        "catalog_size": len(names),
        # What can be put on it: greases, armament buffs, the mist skills. Three conditions
        # decide it — the buff lists the class, the buff lists the affinity, and the weapon can
        # be buffed at all — and each is a different reason for a no. A somber weapon usually
        # refuses everything, and a Blood-affinity weapon loses every grease.
        "affinity_asked": affinity,
        "buffable": buffable,
        "status_buffs": status_buffs,
        "status_buffs_accepted": [b["buff"] for b in status_buffs if b["applies"]],
        # The bounds attack-power cannot check for itself.
        "infusable": bool(row["isInfuse"]) if row else False,
        "max_upgrade": oracle.max_upgrade(row) if row else 0,
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
