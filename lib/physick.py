"""The crystal tears, with what each one does.

`CrystalTearData.csv` in the extraction is a list of names and a few stat columns.
`data/PhysickEffect.csv` — the Prometheux workspace's compilation — is what each tear actually
does, in the form the game states it: `⌊MaxHP * 0.5⌋`, `Restores 7 HP/s`, a duration in
seconds, and a note where one is needed.

It also carries three tears the extraction's catalogue does not name the way a player does. The
catalogue holds `Crimson Crystal Tear 1` and `Crimson Crystal Tear 2` — the two copies you can
find — where everybody, this table included, says `Crimson Crystal Tear`.
"""

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PHYSICK_CSV = os.path.join(ROOT, "data", "PhysickEffect.csv")


def table():
    """`{name: {listed, effect, pvp_alter, duration, notes}}`, first row per name wins.

    The file has a blank continuation row after some tears; those carry nothing and are skipped
    rather than overwriting the row above them.
    """
    out = {}
    with open(PHYSICK_CSV, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("Name") or "").strip()
            if not name or name in out:
                continue
            if not (row.get("Effect") or "").strip() and not (row.get("Listed") or "").strip():
                continue
            out[name] = {
                "listed": (row.get("Listed") or "").strip(),
                "effect": (row.get("Effect") or "").strip(),
                "pvp_alter": (row.get("PvpAlter") or "").strip(),
                "duration": (row.get("Duration") or "").strip(),
                "notes": (row.get("Notes") or "").strip(),
            }
    return out
