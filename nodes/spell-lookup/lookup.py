#!/usr/bin/env python3
"""Resolve a spell name, and report what casting it needs.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

`weapon-lookup` exists because a user types "rivers of blood" and a node needs
"Rivers of Blood". Spells had no equivalent: `spell-power` matched the display name exactly and
exited otherwise, so "Rellana's Twin Moons" — which the table stores as three hits, `[1]`, `[2]`
and `[3]` — came back as a crash rather than as three candidates. A user comparing three moon
spells hit that on the third one.

The rules are the same as the weapon lookup's, and for the same reasons:

- **An exact name beats the names that contain it.** "Comet" is a spell; it is also a prefix of
  Comet Azur and of two charged variants.
- **More than one candidate resolves to nothing**, and lists them. Choosing one silently is how
  a charged cast gets reported as an ordinary one.
- **The forms of a spell are named.** A charged cast is a different spell with a different
  attack, and so is each numbered hit of a multi-hit incantation.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "lib"))

import spells as spellbook  # noqa: E402

MAX_CANDIDATES = 20
MIN_QUERY = 3


def normalize(text):
    text = text.lower().replace("'", "").replace("’", "")
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())


def resolve(query, names):
    target = normalize(query)
    exact = [name for name in names if normalize(name) == target]
    if exact:
        return exact
    tokens = target.split()
    if not tokens:
        return []
    return sorted(name for name in names if all(t in normalize(name) for t in tokens))


def main():
    request = json.load(sys.stdin)
    query = request["query"]
    want_type = (request.get("spell_type") or "").strip()

    book = spellbook.book()
    names = list(book)
    if want_type:
        names = [n for n in names if (book[n].get("Type") or "") == want_type]

    candidates = resolve(query, names)
    resolved = candidates[0] if len(candidates) == 1 else ""
    print(f"{query!r} matched {len(candidates)} of {len(names)}", file=sys.stderr)

    row = book.get(resolved)
    base = spellbook.base_attack(row) if row else {d: 0.0 for d in spellbook.ATTACK_COLUMN}
    families = spellbook.families().get(resolved, []) if resolved else []

    result = {
        "query": query,
        "resolved": resolved,
        "match_count": len(candidates),
        "candidates": candidates[:MAX_CANDIDATES],
        "candidates_truncated": len(candidates) > MAX_CANDIDATES,
        "ambiguous": len(candidates) > 1,
        "catalog_size": len(names),
        "spell_type": (row.get("Type") or "") if row else "",
        # Every named form of the same spell. A charged cast and each numbered hit of a
        # multi-hit incantation are separate rows with separate attack values.
        "forms": spellbook.variants(book, row["Name"]) if row else [],
        "families": sorted(families),
        "base_attack": base,
        "damage_types": sorted(d for d, v in base.items() if v > 0) if row else [],
        "requirement": spellbook.requirement(row) if row else {
            "intelligence": 0, "faith": 0, "arcane": 0,
        },
        "fp_cost": spellbook.number(row.get("mp")) if row else 0.0,
        # Which kind of catalyst can cast it at all, so the next call is not an impossible one.
        "cast_from": (
            "Glintstone Staff" if (row.get("Type") if row else "") == "Sorcery"
            else "Sacred Seal" if row else ""
        ),
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
