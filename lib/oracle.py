"""Shared entry point to the vendored Build Planner oracle.

`oracle/` is a verbatim copy of `elden-ring-wiki/` — the scripts and the extracted
spreadsheet CSVs, unmodified, so it can be re-vendored from upstream by copying rather than
by merging. Nothing in this repository edits it. Every node reaches it through here, so there
is one place that knows where it lives.

The maths in those scripts is the extracted Build Planner spreadsheet logic and is treated as
given. What this collection adds is the part the scripts do not have: contracts that say when
an answer is meaningful, and a record of where each number came from.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "oracle", "scripts")

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def weapons():
    """`{name: row}` for all 570 weapons, and the affinity offset table."""
    import ap_calc

    return ap_calc.load_weapon_data()


def max_upgrade(row):
    """How far this weapon can actually be upgraded, read from the reinforce table.

    Not a column in the data, and **not** derivable from `isInfuse` either. That shortcut —
    +25 if infusable, else +10 — is right for 569 of the 570 weapons and wrong for the
    Academy Glintstone Staff, which takes no affinity and still goes to +25. It was caught by
    a spell figure disagreeing with the Prometheux implementation: Comet from an Academy staff
    is 1009.444 there, which is the +25 number, and the shortcut had capped it at +10.

    The honest source is which reinforce rows exist. A weapon's `reinforceTypeId` indexes a
    band in `ReinforceParamWeapon`, one row per upgrade level, so the cap is how far that band
    runs. `isReinforce` false means no band at all: +0 only, as for the Meteorite Staff.

    Bounding this matters more than it looks. `ap_calc.py` will happily compute Moonveil +25
    and return 180.39, a number for an upgrade level the game does not have — lower than the
    539.15 the weapon actually reaches at its +10 cap, so it does not even look wrong.
    """
    if not row["isReinforce"]:
        return 0

    import ap_calc

    equip = ap_calc.load_table("EquipParamWeapon").get(float(row["ID"]))
    if not equip:
        return 0
    base = int(float(equip["reinforceTypeId"]))
    levels = set(int(k) for k in ap_calc.load_table("ReinforceParamWeapon"))

    cap = 0
    while base + cap + 1 in levels:
        cap += 1
    return cap
