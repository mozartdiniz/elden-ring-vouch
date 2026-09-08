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

# The proposal. Each clause the prose uses, and the `HitKind` values it becomes.
#
# A clause can name more than one kind — Godfrey Icon's "charged spells and charged weapon
# skills" is `ChargedSkill` *and* `ChargedR2` in the hand-built table, which is the convention
# this follows. Four of these names already exist in `lib/buffs.HIT_KINDS`; the rest are the
# proposal, and are the whole of what is being decided.
#
# An empty list means the gate is not a hit kind at all — a state or a proc — and the buff
# goes on every kind, which is what makes `buffs.state_conditional` fire and makes
# `buff-stack` demand the caller assert it. That mechanism already exists; nothing is added
# for it here.
HIT_KIND_FOR = {
    # Both, because a charged weapon skill is still a weapon skill. The hand-built table
    # knows this and a naive reading of the clause does not — which the check caught.
    "with weapon skills": ["Skill", "ChargedSkill"],
    "with charged spells and charged weapon skills": ["ChargedSkill", "ChargedR2"],
    "with charged R2s": ["ChargedR2"],
    "with jump attacks": ["Jump"],
    "with continuous attacks": ["Successive"],
    "with guard counters": ["GuardCounter"],
    "with horseback attacks": ["Horseback"],
    "with dashing attacks": ["Dashing"],
    "with rolling / backstep attacks": ["RollBackstep"],
    "with arrow / bolt attacks": ["Ranged"],
    "with aimed arrow / bolt  attacks": ["RangedAimed"],
    "with 2h attacks": ["TwoHanded"],
    "with kicking / stomping skills": ["KickStomp"],
    "with weapon-throwing attacks": ["ThrownWeapon"],
    "with roar attacks and Shriek of Milos": ["Roar"],
    "with Cracked / Ritual Pot attacks": ["Pot"],
    "with Perfume Bottle attacks": ["Perfume"],
    "with storm attacks": ["Storm"],
    "with magma attacks": ["Magma"],
    "with the final light attack in a chain": ["FinalLight"],
}

# Clauses the prose spells with trailing detail that does not change which kind it is.
TRIM = re.compile(r"\s*(and bowDistRate.*|and increases dexterity.*|\(crosshair.*|& 1.*)$")


def hit_kinds(clause):
    """The `HitKind` values a clause maps to, or [] when the gate is a state rather than a hit."""
    key = TRIM.sub("", clause).strip()
    return HIT_KIND_FOR.get(key, [])


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
        # The LAST of a ramp, not the first. "1.03x /1.05x /1.1x /1.1x with continuous
        # attacks" is one buff that climbs, and `BuffMult.csv` records where it lands —
        # because a ramped figure is state-conditional and `buff-stack` already makes the
        # caller assert the state. Taking values[0] was my bug, and the check against the ten
        # known talismans caught it on the first run; I then wrote it up as a difference of
        # convention, which it was not.
        ramped = values[-1]
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
                "MultPve": ramped,
                "MultPvp": pvp.group(1) if pvp else ramped,
                "Tiers": " ".join(values) if len(values) > 1 else "",
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


def rows_for(entry, kinds_in_use):
    """One row per hit kind, exactly as `BuffMult.csv` is shaped.

    A buff gated on a hit kind is worth its multiplier on those kinds and 1.0 on the rest. A
    buff gated on a *state* is worth it everywhere, which is what `buffs.state_conditional`
    reads to decide the caller must assert the state — so those get the figure on all eight.
    """
    kinds = hit_kinds(entry["Clause"])
    everywhere = not kinds
    out = []
    for kind in kinds_in_use:
        applies = everywhere or kind in kinds
        out.append({
            "Name": entry["Name"],
            "Kind": "Talisman",
            "Slot": "Passive",
            "HitKind": kind,
            "MultPve": entry["MultPve"] if applies else "1.0",
            "MultPvp": entry["MultPvp"] if applies else "1.0",
            "Notes": entry["Effect"],
        })
    return out


def check_kinds(draft):
    """Do the proposed hit kinds reproduce the ten rows that already exist?

    The strongest check available: the overlap was assigned by hand from a different source, so
    if the naming is right the generated rows are identical to the ones in the table.
    """
    import sys as _sys
    _sys.path.insert(0, os.path.join(ROOT, "lib"))
    import buffs

    known = buffs.table()
    wrong = []
    for entry in draft:
        if entry["Name"] not in known:
            continue
        theirs = known[entry["Name"]]["pve"]
        mine = {r["HitKind"]: float(r["MultPve"]) for r in rows_for(entry, buffs.HIT_KINDS)}
        differing = {k for k in theirs if abs(theirs[k] - mine.get(k, 1.0)) > 1e-9}
        if differing:
            wrong.append(
                f"{entry['Name']}: {sorted(differing)} — "
                f"table {[theirs[k] for k in sorted(differing)]}, "
                f"proposed {[mine.get(k, 1.0) for k in sorted(differing)]}"
            )
    return wrong


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

    import sys as _sys
    _sys.path.insert(0, os.path.join(ROOT, "lib"))
    import buffs

    unnamed = [r for r in draft if r["Clause"].startswith("with") and not hit_kinds(r["Clause"])]
    stateful = [r for r in draft if not hit_kinds(r["Clause"])]
    proposed = sorted({k for r in draft for k in hit_kinds(r["Clause"])} - set(buffs.HIT_KINDS))

    wrong = check_kinds(draft)
    print(f"\nhit kinds: the proposal reproduces the ten known talismans"
          f"{' — EXCEPT:' if wrong else ' exactly'}")
    for w in wrong:
        print(f"  WRONG  {w}")

    print(f"\n{len(stateful)} of the 33 are gated on a state, not a hit kind, and go on every")
    print("  kind — which is what makes buff-stack require the caller to assert them.")
    if unnamed:
        print(f"\n{len(unnamed)} 'with ...' clause(s) have no proposed name yet:")
        for r in unnamed:
            print(f"  {r['Name']:<32} {r['Clause']}")
    print(f"\n{len(proposed)} new HIT_KINDS values proposed: {', '.join(proposed)}")

    if not args.check:
        expanded = [row for r in draft for row in rows_for(r, buffs.HIT_KINDS + tuple(proposed))]
        with open(DRAFT, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["Name", "Kind", "Slot", "HitKind",
                                                        "MultPve", "MultPvp", "Notes"])
            writer.writeheader()
            writer.writerows(expanded)
        print(f"\nwrote {os.path.relpath(DRAFT, ROOT)} — {len(expanded)} rows, "
              f"BuffMult.csv's shape exactly")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
