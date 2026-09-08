#!/usr/bin/env python3
"""Merge the extracted talismans into `data/BuffMult.csv`, widening it to the new hit kinds.

    python3 scripts/merge_talisman_buffs.py --dry-run    # say what would change
    python3 scripts/merge_talisman_buffs.py              # write it

Run `extract_talisman_buffs.py` first; this reads its draft.

**The part that would break silently.** `buffs.state_conditional` decides a buff is gated on a
state rather than a hit kind by asking whether its figure is above 1 on *every* hit kind — and
compares against `len(HIT_KINDS)`. Widening that tuple from eight values to twenty-three
without also widening the rows would leave nine existing buffs above 1 on only eight of
twenty-three, so they would stop being state-conditional, and `buff-stack` would stop asking
the caller to assert a bleed proc or full HP. It would quietly start applying Ritual Sword
Talisman's 1.1x to a build that is not at full HP. Nothing would fail; the answers would just
be wrong.

So every existing buff is extended, and how depends on which kind it is:

  * **state-gated** (above 1 everywhere today) — the new kinds get its multiplier too, because
    a bleed proc does not care whether the hit was a guard counter. It stays state-conditional.
  * **hit-kind-gated** — the new kinds get 1.0. Shard of Alexander is worth nothing extra on a
    horseback attack.

Where a talisman is in both the hand-built table and the draft, **the table wins.** Those ten
rows were assigned by hand from another source and are what the draft is checked against; the
extractor agreeing with them is the evidence it is right, not a licence to overwrite them.
"""

import argparse
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

import buffs  # noqa: E402

LIVE = os.path.join(ROOT, "data", "BuffMult.csv")
DRAFT = os.path.join(ROOT, "data", "BuffMult-talismans.draft.csv")
FIELDS = ["Name", "Kind", "Slot", "HitKind", "MultPve", "MultPvp", "Notes"]


def read(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def widen(rows, kinds):
    """Give every buff a row for every hit kind, preserving what each buff means."""
    by_name = {}
    for row in rows:
        by_name.setdefault(row["Name"], []).append(row)

    out = []
    for name, group in by_name.items():
        present = {r["HitKind"]: r for r in group}
        pve = {k: float(r["MultPve"]) for k, r in present.items()}
        # State-gated exactly as `buffs.state_conditional` reads it: above 1 on every kind it
        # currently has a row for. `none` is the unused product slot and is 1.0 throughout.
        everywhere = bool(pve) and all(v > 1.0 for v in pve.values())
        template = group[0]

        for kind in kinds:
            if kind in present:
                out.append({f: present[kind].get(f, "") for f in FIELDS})
                continue
            source = max(group, key=lambda r: float(r["MultPve"]))
            out.append({
                "Name": name,
                "Kind": template["Kind"],
                "Slot": template["Slot"],
                "HitKind": kind,
                "MultPve": source["MultPve"] if everywhere else "1.0",
                "MultPvp": source["MultPvp"] if everywhere else "1.0",
                "Notes": template.get("Notes", ""),
            })
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    live, draft = read(LIVE), read(DRAFT)
    kinds = list(dict.fromkeys([r["HitKind"] for r in draft]))
    existing = {r["Name"] for r in live}
    added = [r for r in draft if r["Name"] not in existing]

    widened = widen(live, kinds)
    merged = sorted(widened + added, key=lambda r: (r["Name"], kinds.index(r["HitKind"])))

    new_names = sorted({r["Name"] for r in added})
    print(f"{len(existing)} buffs in BuffMult.csv, widened from "
          f"{len(live) // max(len(existing), 1)} hit kinds to {len(kinds)}")
    print(f"{len(new_names)} talismans added: {', '.join(new_names[:6])}...")
    print(f"{len(merged)} rows total")

    # The check that matters: nothing that was state-conditional may stop being so.
    before = {n for n, e in buffs.table().items() if buffs.state_conditional(e)}
    after = set()
    for name in {r["Name"] for r in merged}:
        rows = [r for r in merged if r["Name"] == name]
        if all(float(r["MultPve"]) > 1.0 for r in rows):
            after.add(name)
    lost = before - after
    print(f"\nstate-conditional before: {len(before)}   after: {len(after)}")
    if lost:
        print(f"  LOST — buff-stack would stop asking the caller to assert these: {sorted(lost)}")
        return 1
    print("  none lost")

    if not args.dry_run:
        with open(LIVE, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(merged)
        print(f"\nwrote {os.path.relpath(LIVE, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
