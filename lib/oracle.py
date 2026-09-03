"""Shared entry point to the vendored Build Planner oracle.

`oracle/` is a verbatim copy of `elden-ring-wiki/` — the scripts and the extracted
spreadsheet CSVs, unmodified, so it can be re-vendored from upstream by copying rather than
by merging. Nothing in this repository edits it. Every node reaches it through here, so there
is one place that knows where it lives.

The maths in those scripts is the extracted Build Planner spreadsheet logic and is treated as
given. What this collection adds is the part the scripts do not have: contracts that say when
an answer is meaningful, and a record of where each number came from.
"""

import functools
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


@functools.lru_cache(maxsize=None)
def _table(name):
    """One table, loaded once.

    `ap_calc.load_table` re-reads and re-parses the CSV on every call — a tenth of a second
    for `EquipParamWeapon`, which is 1.3 MB. That is invisible when a node prices one weapon
    and fatal when `weapon-rank` prices 489: two lookups each turned a one-second ranking into
    a two-minute one that hit the node timeout. Caching here rather than in `oracle/` keeps
    the vendored copy byte-identical.
    """
    import ap_calc

    return ap_calc.load_table(name)


@functools.lru_cache(maxsize=None)
def _reinforce_levels():
    return set(int(k) for k in _table("ReinforceParamWeapon"))


def max_upgrade(row):
    """How far this weapon can actually be upgraded, read from the reinforce table.

    Not a column in the data, and **not** derivable from `isInfuse` either. That shortcut —
    +25 if infusable, else +10 — is wrong for 69 of the 489 weapons in the catalogue: 58 that
    take no affinity and still reach +25, among them the Academy and Carian Glintstone staves,
    Great Club, Serpentbone Blade and the Perfume Bottles, and 11 more that cannot be
    reinforced at all. It was caught by a spell figure disagreeing with the Prometheux
    implementation: Comet from an Academy staff is 1009.444 there, which is the +25 number,
    and the shortcut had capped it at +10.

    The honest source is which reinforce rows exist. A weapon's `reinforceTypeId` indexes a
    band in `ReinforceParamWeapon`, one row per upgrade level, so the cap is how far that band
    runs. `isReinforce` false means no band at all: +0 only, as for the Meteorite Staff.

    Bounding this matters more than it looks. `ap_calc.py` will happily compute Moonveil +25
    and return 180.39, a number for an upgrade level the game does not have — lower than the
    539.15 the weapon actually reaches at its +10 cap, so it does not even look wrong.
    """
    if not row["isReinforce"]:
        return 0

    equip = _table("EquipParamWeapon").get(float(row["ID"]))
    if not equip:
        return 0
    base = int(float(equip["reinforceTypeId"]))
    levels = _reinforce_levels()

    cap = 0
    while base + cap + 1 in levels:
        cap += 1
    return cap


def casts(row):
    """What this weapon can cast: "Sorcery", "Incantation", both, or nothing.

    A staff casts sorceries and a seal casts incantations, and the two are not
    interchangeable — but nothing in the maths says so. `planner.py` computes a spell buff for
    any catalyst and the multiply that turns it into a spell's attack does not ask what kind
    of spell it is, so `spell-power` would happily price Comet cast from an Erdtree Seal at
    798.766. There is no such cast. The figure was arithmetically correct and about nothing.

    `enableMagic` and `enableMiracle` in `EquipParamWeapon` are the game's own answer, so the
    check reads them rather than assuming the weapon class settles it.
    """
    if row.get("ID") is None:
        return []

    equip = _table("EquipParamWeapon").get(float(row["ID"]))
    if not equip:
        return []

    def flag(name):
        value = equip.get(name)
        return str(value).strip().upper() in ("TRUE", "1", "1.0")

    out = []
    if flag("enableMagic"):
        out.append("Sorcery")
    if flag("enableMiracle"):
        out.append("Incantation")
    return out


def status_buffs(row, affinity="Standard"):
    """Which greases and armament buffs this weapon can take, with the reason when it cannot.

    The rule is `ap_calc`'s own — `_status_buff_effect_id`, ported from the spreadsheet — and it
    is three conditions, not one: the buff has to list the weapon's class, it has to list the
    affinity, and the weapon has to be buffable at all (`isEnhance`), unless the buff ignores
    that (`isEnhanceIgnore`) in which case the weapon must not block it (`disableGemAttr`).

    That is the whole of Pattern 12. Two results are worth knowing before anyone asks:
    **Bloodflame Blade lists only Standard, Heavy, Keen and Quality**, so it cannot go on a
    Blood-affinity weapon — they do not stack, the buff simply does not apply — and a somber
    weapon usually has `isEnhance` false, which is why greases slide off most unique weapons.
    """
    import ap_calc

    if row.get("ID") is None:
        return []
    equip = _table("EquipParamWeapon").get(float(row["ID"])) or {}
    weapon_class = str(row.get("Weapon Class") or "")
    can_enhance = bool(equip.get("isEnhance"))
    blocks_gem = bool(equip.get("disableGemAttr"))

    out = []
    for name, buff in ap_calc.load_by_name("StatusBuffData").items():
        if name == "None":
            continue
        class_ok = bool(buff.get(weapon_class))
        affinity_ok = bool(buff.get(affinity))
        ignores = bool(buff.get("isEnhanceIgnore"))
        applies = (
            (class_ok and affinity_ok and not blocks_gem) if ignores
            else (can_enhance and class_ok and affinity_ok)
        )
        why = ""
        if not applies:
            if not class_ok:
                why = f"not for a {weapon_class}"
            elif not affinity_ok:
                why = f"not on a {affinity} weapon"
            elif ignores and blocks_gem:
                why = "this weapon blocks it"
            else:
                why = "this weapon cannot be buffed"
        out.append({
            "buff": name,
            "applies": applies,
            "reason": why,
            "ignores_enhance": ignores,
        })
    return out
