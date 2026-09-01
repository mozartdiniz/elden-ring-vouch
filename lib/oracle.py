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
    """How far this weapon can actually be upgraded.

    Not a column in the data — it follows from two flags. A weapon that cannot be reinforced
    at all sits at +0; an infusable (smithing-stone) weapon goes to +25; everything else is
    somber and stops at +10.

    This matters more than it looks. `ap_calc.py` will happily compute Moonveil +25 and return
    180.39, a number for an upgrade level the game does not have — lower than the 539.15 the
    weapon actually reaches at its +10 cap, so it does not even look wrong. Bounding it is the
    whole reason this function exists.
    """
    if not row["isReinforce"]:
        return 0
    return 25 if row["isInfuse"] else 10
