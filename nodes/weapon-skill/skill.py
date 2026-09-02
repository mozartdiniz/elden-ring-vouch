#!/usr/bin/env python3
"""What an ash of war does: its hits, their motion values, and whether it changes the scaling.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

Both tables come from the Prometheux ontology; the Build Planner publishes no skill data at
all. `data/AshAttack.csv` is one row per *hit* — a skill is several — and `data/AshCompat.csv`
says which affinity a skill defaults to and whether it fits any weapon.

The column that matters most is the scaling override. 173 of the 2,643 hits replace the
weapon's scaling with a single stat, which means **a build optimised for the weapon can be the
wrong build for its ash**. Most hits do not override anything, and saying which case a skill is
in is more useful than any single number: it tells a caller whether `build-allocate`'s answer
applies to the skill they actually intend to use.

Motion values are percentages on the scale `optimal-affinity`'s `attack_mv` expects, so a hit
can be priced through the same maths as an ordinary swing. This node does not price anything
itself — it reports what the skill is, and the damage nodes do the rest.
"""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ATTACK_CSV = os.path.join(ROOT, "data", "AshAttack.csv")
COMPAT_CSV = os.path.join(ROOT, "data", "AshCompat.csv")

MV_COLUMN = {
    "physical": "PhysMv", "magic": "MagicMv", "fire": "FireMv",
    "lightning": "LtngMv", "holy": "HolyMv",
}
ATK_COLUMN = {
    "physical": "AtkPhys", "magic": "AtkMag", "fire": "AtkFire",
    "lightning": "AtkLtng", "holy": "AtkHoly",
}
DAMAGE = tuple(MV_COLUMN)
MAX_CANDIDATES = 20
NO_OVERRIDE = "-"


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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

    with open(ATTACK_CSV, newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("SkillFamily")]
    with open(COMPAT_CSV, newline="", encoding="utf-8") as handle:
        compat = {r["Skill"]: r for r in csv.DictReader(handle) if r.get("Skill")}

    families = {}
    for row in rows:
        families.setdefault(row["SkillFamily"], []).append(row)

    candidates = resolve(query, list(families))
    resolved = candidates[0] if len(candidates) == 1 else ""
    print(f"{query!r} matched {len(candidates)} of {len(families)}", file=sys.stderr)

    hits = []
    for row in families.get(resolved, []):
        hits.append(
            {
                "hit": row["Hit"],
                "motion_value": {d: number(row[MV_COLUMN[d]]) for d in DAMAGE},
                "status_motion_value": number(row["StatusMv"]),
                "poise_motion_value": number(row["PoiseMv"]),
                "stamina_cost": number(row["StaminaCost"]),
                "flat_attack": {d: number(row[ATK_COLUMN[d]]) for d in DAMAGE},
                # `-` means the weapon's own scaling applies; anything else replaces it.
                "scaling_override": (row.get("OverwriteScaling") or NO_OVERRIDE).strip(),
            }
        )

    overrides = sorted(
        {h["scaling_override"] for h in hits if h["scaling_override"] != NO_OVERRIDE}
    )
    weapons = sorted({r["UniqueWeapon"] for r in families.get(resolved, [])}) if resolved else []
    # "Any" in that column means the skill is not tied to one weapon.
    unique_to = [w for w in weapons if w and w != "Any"]

    entry = compat.get(resolved, {})
    result = {
        "query": query,
        "skill": resolved,
        "match_count": len(candidates),
        "candidates": candidates[:MAX_CANDIDATES],
        "candidates_truncated": len(candidates) > MAX_CANDIDATES,
        "ambiguous": len(candidates) > 1,
        "catalog_size": len(families),
        "hits": hits,
        "hit_count": len(hits),
        # The headline motion value: the biggest single hit, which is what a caller comparing
        # skills wants. Summing them would describe a full combo nobody necessarily lands.
        "highest_motion_value": max(
            (max(h["motion_value"].values()) for h in hits), default=0.0
        ),
        "total_stamina_cost": round(sum(h["stamina_cost"] for h in hits), 6),
        # Whether a build optimised for the weapon is a build optimised for this skill.
        "overrides_weapon_scaling": bool(overrides),
        "scaling_overrides": overrides,
        "unique_to": unique_to,
        "any_weapon": bool(resolved) and not unique_to,
        "default_affinity": (entry.get("DefaultAffinity") or "").strip(),
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
