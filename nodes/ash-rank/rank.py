#!/usr/bin/env python3
"""Rank the ashes of war a weapon can take, by hits, status buildup, poise damage or motion.

Reads one JSON object on stdin, writes one JSON object on stdout. Logs go to stderr.

"Qual Ash aceita Blood e dá mais hits?" is two lookups and a sort, and the collection could do
none of it: `weapon-skill` resolves one ash by name, and `AshCompat` carries only the affinity
an ash *comes with*. `data/AshAffinity.csv` and `data/AshClass.csv` carry what an ash accepts,
which is the question.

**The four rankings are four different questions**, and which one is right depends on what the
user is after:

- `status` — total status motion value over the ash's hits. This is the bleed- or frost-proc
  question, and it is not the same as hit count: two hits at 60 beat five at 20.
- `poise` — total poise motion value. Stance-breaking.
- `hits` — how many times it connects, which is what a *per-hit* effect keys on.
- `motion` — total motion value, which is closest to raw damage and is the one to be most
  careful with, because a skill's damage also depends on the weapon it is on.

**The "(Lacking FP)" rows are excluded.** They are what the ash does when the FP ran out, and
counting them would double every ash's hits.

Nothing here is damage. `weapon-skill` gives a hit's motion value and `optimal-affinity` prices
it on a specific weapon; this node is about which ash to put on in the first place.
"""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "lib"))

import ashes  # noqa: E402

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
RANK_ON = ("status", "poise", "hits", "motion")
NO_OVERRIDE = "-"


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def main():
    request = json.load(sys.stdin)
    weapon_class = (request["weapon_class"] or "").strip()
    affinity = (request.get("affinity") or "").strip()
    rank_on = request.get("rank_on", "status")
    limit = int(request.get("limit", 10))

    accepted = ashes.affinities()
    fits_class = ashes.classes()

    with open(ATTACK_CSV, newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("SkillFamily")]
    with open(COMPAT_CSV, newline="", encoding="utf-8") as handle:
        compat = {r["Skill"]: r for r in csv.DictReader(handle) if r.get("Skill")}

    families = {}
    for row in rows:
        families.setdefault(row["SkillFamily"], []).append(row)

    considered = 0
    ranked = []
    for skill, listed in sorted(fits_class.items()):
        if affinity and affinity not in accepted.get(skill, set()):
            continue
        if weapon_class and not ashes.fits(listed, weapon_class):
            continue
        considered += 1

        # On one weapon class, and without the "(Lacking FP)" rows. Both matter: Sword Dance's
        # table carries a set of hits per class, and summing them made it 48 hits and 4,400
        # status motion value where on a reaper it is three hits and 275.
        family_rows = families.get(skill, [])
        hits = ashes.hits_for(family_rows, weapon_class)
        damaging = [
            row for row in hits
            if any(number(row[MV_COLUMN[d]]) for d in MV_COLUMN)
            or any(number(row[ATK_COLUMN[d]]) for d in ATK_COLUMN)
        ]
        status = sum(number(row["StatusMv"]) for row in hits)
        poise = sum(number(row["PoiseMv"]) for row in hits)
        motion = sum(max(number(row[MV_COLUMN[d]]) for d in MV_COLUMN) for row in hits)
        overrides = sorted({
            (row.get("OverwriteScaling") or NO_OVERRIDE).strip()
            for row in hits
            if (row.get("OverwriteScaling") or NO_OVERRIDE).strip() != NO_OVERRIDE
        })
        entry = compat.get(skill, {})

        ranked.append({
            "skill": skill,
            "hits": len(damaging),
            "rows": len(hits),
            "total_status_motion_value": status,
            "total_poise_motion_value": poise,
            "total_motion_value": motion,
            "highest_motion_value": max(
                (max(number(row[MV_COLUMN[d]]) for d in MV_COLUMN) for row in hits),
                default=0.0,
            ),
            "total_stamina_cost": sum(number(row["StaminaCost"]) for row in hits),
            "default_affinity": (entry.get("DefaultAffinity") or "").strip(),
            "affinities": sorted(accepted.get(skill, set())),
            "weapon_classes": sorted(listed),
            "scaling_overrides": overrides,
            "overrides_weapon_scaling": bool(overrides),
            "priced": len(hits) > 0,
            # True when this ash hits differently depending on the weapon it is on, so the
            # figures above are for `weapon_class` and not for the ash in general.
            "variants": ashes.variants(family_rows),
            "varies_by_variant": bool(ashes.variants(family_rows)),
        })

    key = {
        "status": lambda r: (-r["total_status_motion_value"], r["skill"]),
        "poise": lambda r: (-r["total_poise_motion_value"], r["skill"]),
        "hits": lambda r: (-r["hits"], r["skill"]),
        "motion": lambda r: (-r["total_motion_value"], r["skill"]),
    }[rank_on]
    ranked.sort(key=key)
    truncated = len(ranked) > limit
    out = ranked[:limit]
    print(
        f"{considered} ashes fit; ranked on {rank_on}",
        file=sys.stderr,
    )

    result = {
        "ranked": out,
        "rank_on": rank_on,
        "rank_on_note": {
            "status": "Total status motion value over one full use of the ash, every press included — the proc-speed question. Not hit count: two hits at 60 beat five at 20.",
            "poise": "Total poise motion value — stance breaking.",
            "hits": "How many times it connects, which is what a per-hit effect keys on.",
            "motion": "Total motion value, the closest thing here to damage — and it still depends on the weapon it goes on.",
        }[rank_on],
        "weapon_class": weapon_class,
        "affinity": affinity,
        "catalog_size": len(fits_class),
        "considered": considered,
        "limit": limit,
        "returned": len(out),
        "truncated": truncated,
        "best": out[0]["skill"] if out else "",
    }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
