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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "lib"))

import ashes  # noqa: E402

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
    """Lower-cased words, with the question mark kept as a word of its own.

    Seven families in the table are a name plus " ?" — the source marking a hit it could not
    confirm, each a single row with zero motion values beside a real family of the same name.
    Folding the "?" away made those seven skills unresolvable: "Loretta's Slash" matched both
    its own 24 hits and the one unverified row, and came back ambiguous between a name and
    itself. Keeping the mark as a token lets the plain name resolve and leaves the flagged row
    reachable by asking for it.
    """
    text = text.lower().replace("'", "").replace("’", "")
    text = "".join(c if (c.isalnum() or c == "?") else " " for c in text)
    return " ".join(text.replace("?", " ? ").split())


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
    weapon_class = (request.get("weapon_class") or "").strip()

    with open(ATTACK_CSV, newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("SkillFamily")]
    with open(COMPAT_CSV, newline="", encoding="utf-8") as handle:
        compat = {r["Skill"]: r for r in csv.DictReader(handle) if r.get("Skill")}

    families = {}
    for row in rows:
        families.setdefault(row["SkillFamily"], []).append(row)
    # An ash that deals no damage has no rows in AshAttack and was invisible: Seppuku is a
    # self-buff and question 6.2 names it alongside two ashes that do hit. The catalogue is the
    # union of the three tables, and an ash with no damaging hits comes back with none rather
    # than not at all.
    for name in list(compat) + list(ashes.affinities()):
        families.setdefault(name, [])

    candidates = resolve(query, list(families))
    resolved = candidates[0] if len(candidates) == 1 else ""
    print(f"{query!r} matched {len(candidates)} of {len(families)}", file=sys.stderr)

    # A family's rows come in variant groups and they are alternatives, not a sequence: most
    # are weapon classes, and adding two together describes a use nobody makes. Sword Dance
    # summed across classes was 48 hits where on a reaper it is three.
    family_rows = families.get(resolved, [])
    variants = ashes.variants(family_rows)
    chosen = ashes.hits_for(family_rows, weapon_class)
    # What the same ash does with the FP gone. Not further hits of it, so out of the count —
    # but a real thing a player sees, so counted separately rather than dropped.
    lacking_fp = [
        row for row in ashes.hits_for(family_rows, weapon_class, lacking_fp=True)
        if "(Lacking FP)" in row["Hit"]
    ]
    variant_used = ""
    if variants:
        variant_used = weapon_class if weapon_class in variants else (
            "" if any(not ashes._prefix(r["Hit"]) for r in family_rows) else sorted(variants)[0]
        )

    hits = []
    for row in chosen:
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
                # optimal-affinity's `attack_mv` is one number for the whole hit, so passing a
                # hit whose motion values differ per damage type multiplies the wrong ones.
                # Establish Order's big hit is 300 holy and 0 physical: handing 300 to a
                # scalar triples a physical attack rating the skill does not use.
                "motion_value_uniform": len(
                    {number(row[MV_COLUMN[d]]) for d in DAMAGE}
                ) == 1,
            }
        )

    overrides = sorted(
        {h["scaling_override"] for h in hits if h["scaling_override"] != NO_OVERRIDE}
    )
    weapons = sorted({r["UniqueWeapon"] for r in family_rows}) if resolved else []
    # "Any" in that column means the skill is not tied to one weapon.
    unique_to = [w for w in weapons if w and w != "Any"]

    entry = compat.get(resolved, {})
    result = {
        "query": query,
        "skill": resolved,
        # The source marks a hit it could not confirm by appending " ?" to the family name.
        # Seven skills have one, each a single row of zeros beside the real family. Saying so
        # keeps a zero from being read as a measurement.
        "uncertain": resolved.rstrip().endswith("?"),
        "match_count": len(candidates),
        "candidates": candidates[:MAX_CANDIDATES],
        "candidates_truncated": len(candidates) > MAX_CANDIDATES,
        "ambiguous": len(candidates) > 1,
        "catalog_size": len(families),
        # Which affinities the ash accepts and which weapons it goes on. `AshCompat`'s
        # `default_affinity` is only the one it arrives with; "does this take Blood?" is a
        # different question and `data/AshAffinity.csv` is what answers it.
        "affinities": sorted(ashes.affinities().get(resolved, set())) if resolved else [],
        "weapon_classes": sorted(ashes.classes().get(resolved, set())) if resolved else [],
        "weapon_class": weapon_class,
        # The variant these hits are for, and the ones they are not. Empty means the ash hits
        # the same whatever it is on.
        "variants": variants,
        "variant_used": variant_used,
        "hits": hits,
        "hit_count": len(hits),
        "hit_count_lacking_fp": len(lacking_fp),
        # False means at least one hit's motion values differ by damage type, and
        # optimal-affinity's single `attack_mv` cannot express it. Pricing such a hit with the
        # highest figure inflates the damage types the skill does not deal.
        "motion_values_uniform": all(h["motion_value_uniform"] for h in hits),
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
