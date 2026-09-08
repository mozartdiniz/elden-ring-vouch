#!/usr/bin/env python3
"""Pull the damage talismans out of the oracle's prose, as a draft for `data/BuffMult.csv`.

    python3 scripts/extract_talisman_buffs.py            # write the draft, check it
    python3 scripts/extract_talisman_buffs.py --check    # check only, exit 1 on disagreement

`BuffMult.csv` carries ten talismans, hand-built. This finds **thirty-three**, and it finds
them in a place nobody had looked: `EffectData.csv`'s `Effects` column, which is prose and is
read by nothing — not by this collection, and not by the workbook it came from. See `DATA.md`
item 1 for why the Build Planner cannot use these numbers and left them as description text.

**This writes a draft and not the table.** Two columns are deliberately left empty, because
they are decisions rather than data:

  * `HitKind` — the prose has twenty-two distinct "with ..." clauses against the eight values
    `BuffMult.csv` uses. Extending that vocabulary is a schema decision, and guessing it here
    would bury the decision in a generated file.
  * `Condition` — the filterable form of "while at full HP", "for 20 seconds when bleed is
    triggered within 7m". `buff-stack` already has `assume` for asserting these; what is
    missing is a controlled vocabulary to select on.

The raw clause is carried through in `Clause` so whoever fills those in is reading what the
oracle said rather than a summary of it.

Nothing here goes near `data/BuffMult.csv`. That file is what `buff-stack` reads, and thirty
unreviewed rows in it would be exactly the well-formed answer about nothing this collection
exists to prevent — attested, because attestation checks that a figure came from a node and
cannot check the table underneath.
"""

import argparse
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFT = os.path.join(ROOT, "data", "BuffMult-talismans.draft.csv")


def oracle_csv(name):
    import glob

    found = glob.glob(os.path.join(ROOT, "oracle", "extracted", "*", "csv", name))
    if not found:
        sys.exit(f"no {name} under oracle/extracted/*/csv/")
    return found[0]


# "Increases damage by 1.15x" — and sometimes several, which is a stacking ramp rather than
# alternatives: Winged Sword Insignia is 1.03x then 1.05x then 1.1x as hits land.
MULTIPLIER = re.compile(r"ncreases damage by\s*([0-9.]+x(?:\s*/\s*[0-9.]+x)*)")
EACH = re.compile(r"([0-9.]+)x")

# A parenthetical is only a PvP figure when it says so. "(1.075x in PvP)" is one;
# "(holy bugged in PvP: 1x)" is a note about a bug in one damage type and reading it as the
# PvP multiplier would put 1.0 against every talisman that carries it — which is most of them.
PVP = re.compile(r"\(\s*([0-9.]+)x\s*in PvP\s*\)")
PVP_NOTE = re.compile(r"\([^)]*bugged[^)]*\)")

# What gates the multiplier: a hit kind, a state, or a proc.
CLAUSE = re.compile(
    r"\b(with|while|when|after|to)\b\s+(.{3,80}?)(?:\s*$|\s*[.;]|,\s*and increases)",
    re.I,
)
DURATION = re.compile(r"for\s+([0-9]+)\s+seconds")


def talismans():
    """Every accessory whose effect text carries a damage multiplier."""
    accessories = {}
    with open(oracle_csv("EquipParamAccessory.csv")) as handle:
        for row in list(csv.reader(handle))[1:]:
            if len(row) > 2 and row[1].strip():
                accessories[row[1].strip()] = row[2].strip()

    with open(oracle_csv("EffectData.csv")) as handle:
        rows = list(csv.reader(handle))[2:]

    found = []
    for row in rows:
        name, effect = row[0].strip(), row[1].strip()
        if name not in accessories:
            continue
        match = MULTIPLIER.search(effect)
        if not match:
            continue

        values = EACH.findall(match.group(1))
        pvp = PVP.search(effect)
        clause = CLAUSE.search(PVP_NOTE.sub("", effect))
        duration = DURATION.search(effect)

        found.append(
            {
                "Name": name,
                "Kind": "Talisman",
                "Slot": "Passive",
                "HitKind": "",
                "Condition": "",
                "MultPve": values[0],
                "MultPvp": pvp.group(1) if pvp else values[0],
                "Tiers": " ".join(values[1:]),
                "DurationSeconds": duration.group(1) if duration else "",
                "Clause": f"{clause.group(1)} {clause.group(2)}".strip() if clause else "",
                "Effect": effect,
                "refId": accessories[name],
            }
        )
    return sorted(found, key=lambda r: r["Name"])


def disagreements(draft):
    """Check the draft against the ten talismans `BuffMult.csv` already has.

    They were built by hand from a different source, so agreement is a real check on this
    parse and not a tautology — the same shape of differential check that found the upgrade-cap
    bug and the FireAtk bug. Disagreement means one of the two is wrong and both are in use.
    """
    path = os.path.join(ROOT, "data", "BuffMult.csv")
    with open(path) as handle:
        known = {}
        for row in csv.DictReader(handle):
            if row["Kind"] != "Talisman":
                continue
            # The highest figure the hand-built table gives this buff on any hit kind: the
            # prose states one multiplier and the table spreads it across the kinds it applies
            # to, leaving 1.0 on the rest.
            best = known.get(row["Name"], 0.0)
            known[row["Name"]] = max(best, float(row["MultPve"]))

    problems, conventions = [], []
    for row in draft:
        if row["Name"] not in known:
            continue
        theirs, ours = known[row["Name"]], float(row["MultPve"])
        if abs(theirs - ours) <= 1e-9:
            continue

        # A ramp is not a disagreement about the number, it is a disagreement about which
        # number. Winged Sword Insignia is "1.03x /1.05x /1.1x /1.1x with continuous attacks":
        # the prose leads with the first hit and BuffMult recorded the fully-ramped 1.1. Both
        # are right about the game and the schema has no way to hold both, which is the whole
        # reason `Tiers` is in this draft. Reporting it as an error would train a reader to
        # ignore the check that found it.
        tiers = [float(t) for t in row["Tiers"].split()] if row["Tiers"] else []
        if any(abs(theirs - t) <= 1e-9 for t in tiers):
            conventions.append(
                f"{row['Name']}: a ramp — the prose leads with {ours}, "
                f"BuffMult recorded the ramped {theirs} (tiers: {ours} {row['Tiers']})"
            )
        else:
            problems.append(f"{row['Name']}: BuffMult says {theirs}, the prose says {ours}")
    return problems, conventions, known


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="check only, write nothing")
    args = parser.parse_args()

    draft = talismans()
    problems, conventions, known = disagreements(draft)

    overlap = sum(1 for row in draft if row["Name"] in known)
    print(f"{len(draft)} damage talismans found in EffectData.csv's prose")
    print(f"{overlap} of them are also in BuffMult.csv, and are the check on this parse")
    for problem in problems:
        print(f"  DISAGREES  {problem}")
    for note in conventions:
        print(f"  ramp       {note}")
    if not problems:
        print(f"  {overlap - len(conventions)} agree exactly, and no figure disagrees")

    blank_hitkind = sum(1 for r in draft if not r["Clause"])
    tiered = sum(1 for r in draft if r["Tiers"])
    timed = sum(1 for r in draft if r["DurationSeconds"])
    print(f"\nleft for a person: {len(draft)} HitKind and Condition values")
    print(f"  {tiered} carry stacking tiers, which the schema has no column for")
    print(f"  {timed} are timed procs")
    print(f"  {blank_hitkind} produced no clause and need reading by hand")

    if not args.check:
        with open(DRAFT, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(draft[0]))
            writer.writeheader()
            writer.writerows(draft)
        print(f"\nwrote {os.path.relpath(DRAFT, ROOT)}")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
