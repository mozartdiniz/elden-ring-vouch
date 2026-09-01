#!/usr/bin/env python3
"""Port of Build Planner AP Calc / ApCalcData for one weapon.

Default inputs and expected outputs match the Longsword +25 Standard
screenshot (STR 20). Success is: same inputs → same numbers as the sheet.

Tables come from extracted/Build-Planner-v1.19.1/csv/ (the spreadsheet
engine), not from a cell-by-cell clone of the 40-sheet workbook.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "extracted" / "Build-Planner-v1.19.1" / "csv"

STATS = ("strength", "dexterity", "intelligence", "faith", "arcane")
SHEET_STAT = {
    "strength": "Strength",
    "dexterity": "Dexterity",
    "intelligence": "Intelligence",
    "faith": "Faith",
    "arcane": "Arcane",
}
# ApCalcData N2:R2 labels used to build AttackElementCorrectParam column names
AEC_STAT = {
    "strength": "Strength",
    "dexterity": "Dexterity",
    "intelligence": "Magic",
    "faith": "Faith",
    "arcane": "Luck",
}
DAMAGE = ("physical", "magic", "fire", "lightning", "holy")
DAMAGE_AEC = {
    "physical": "Physics",
    "magic": "Magic",
    "fire": "Fire",
    "lightning": "Thunder",
    "holy": "Dark",
}
WEAPON_BASE = {
    "physical": "attackBasePhysics",
    "magic": "attackBaseMagic",
    "fire": "attackBaseFire",
    "lightning": "attackBaseThunder",
    "holy": "attackBaseDark",
}
WEAPON_CORRECT = {
    "strength": "correctStrength",
    "dexterity": "correctAgility",
    "intelligence": "correctMagic",
    "faith": "correctFaith",
    "arcane": "correctLuck",
}
WEAPON_CORRECT_TYPE = {
    "physical": "correctType_Physics",
    "magic": "correctType_Magic",
    "fire": "correctType_Fire",
    "lightning": "correctType_Thunder",
    "holy": "correctType_Dark",
}
REINFORCE_ATK = {
    "physical": "physicsAtkRate",
    "magic": "magicAtkRate",
    "fire": "fireAtkRate",
    "lightning": "thunderAtkRate",
    "holy": "darkAtkRate",
}
REINFORCE_CORRECT = {
    "strength": "correctStrengthRate",
    "dexterity": "correctAgilityRate",
    "intelligence": "correctMagicRate",
    "faith": "correctFaithRate",
    "arcane": "correctLuckRate",
}
STATUS = ("poison", "scarlet_rot", "bleed", "frost", "sleep", "madness")
STATUS_FIELD = {
    "poison": "poizonAttackPower",
    "scarlet_rot": "diseaseAttackPower",
    "bleed": "bloodAttackPower",
    "frost": "freezeAttackPower",
    "sleep": "sleepAttackPower",
    "madness": "madnessAttackPower",
}
# AP-Calc J41/J43: scarlet rot and frost scaling is always 0 when base is numeric.
STATUS_NO_SCALING = {"scarlet_rot", "frost"}
STATUS_LABEL = {
    "poison": "Poison",
    "scarlet_rot": "Scarlet Rot",
    "bleed": "Bleed",
    "frost": "Frost",
    "sleep": "Sleep",
    "madness": "Madness",
}

# Default CLI values: first verified screenshot (Longsword +25 Standard, STR 20)
SCREENSHOT_INPUTS = {
    "weapon_class": "Straight Sword",
    "weapon": "Longsword",
    "affinity": "Standard",
    "upgrade": 25,
    "strength": 20,
    "dexterity": 13,
    "intelligence": 80,
    "faith": 7,
    "arcane": 9,
    "two_hand": False,
    "ignore_require": False,
    "status_buff": "None",
}

# Spreadsheet screenshots used as regression fixtures.
SCREENSHOT_CASES = [
    {
        "name": "Longsword +25 Standard (STR 20)",
        "inp": dict(SCREENSHOT_INPUTS),
        "expect": {
            "letters": {"strength": "C", "dexterity": "D", "intelligence": "-", "faith": "-", "arcane": "-"},
            "pct": {"strength": 0.75, "dexterity": 0.495},
            "req": {"strength": 10, "dexterity": 10},
            "base": {"physical": 269.5},
            "scaling": {"physical": 78.23588679},
            "total": {"physical": 347.7358868},
            "rounded": {"physical": 347},
            "sub": {"physical": {"strength": 56.278, "dexterity": 21.957}},
            "ar": 347.7358868,
            "ar_round": 347,
            "guard": {"physical": 45.0, "magic": 30.0},
            "gb": 36,
            "resist": 15,
        },
    },
    {
        "name": "Godslayer's Greatsword +10 (unmet DEX req)",
        "inp": {
            "weapon_class": "Colossal Sword",
            "weapon": "Godslayer's Greatsword",
            "affinity": "Standard",
            "upgrade": 10,
            "strength": 60,
            "dexterity": 13,
            "intelligence": 10,
            "faith": 60,
            "arcane": 9,
        },
        "expect": {
            "letters": {"strength": "D", "dexterity": "B", "faith": "C"},
            "pct": {"strength": 0.558, "dexterity": 1.008, "faith": 0.72},
            "req": {"strength": 20, "dexterity": 22, "faith": 20},
            "req_met": {"dexterity": False},
            "base": {"physical": 291.55, "fire": 188.65},
            "scaling": {"physical": -116.62, "fire": 115.4538},
            "total": {"physical": 174.93, "fire": 304.1038},
            "rounded": {"physical": 174, "fire": 304},
            "sub": {"physical": {"strength": 0, "dexterity": 0}, "fire": {"faith": 115.454}},
            "ar": 479.0338,
            "ar_round": 479,
            "guard": {"physical": 63, "fire": 49},
            "gb": 49,
            "resist": 22,
        },
    },
    {
        "name": "Siluria's Tree +10",
        "inp": {
            "weapon_class": "Great Spear",
            "weapon": "Siluria's Tree",
            "affinity": "Standard",
            "upgrade": 10,
            "strength": 60,
            "dexterity": 13,
            "intelligence": 10,
            "faith": 60,
            "arcane": 9,
        },
        "expect": {
            "letters": {"strength": "B", "dexterity": "D", "faith": "C"},
            "pct": {"strength": 1.044, "dexterity": 0.27, "faith": 0.81},
            "base": {"physical": 220.5, "holy": 220.5},
            "scaling": {"physical": 182.4507121, "holy": 151.81425},
            "total": {"physical": 402.9507121, "holy": 372.31425},
            "rounded": {"physical": 402, "holy": 372},
            "sub": {"physical": {"strength": 172.652, "dexterity": 9.799}, "holy": {"faith": 151.814}},
            "ar": 775.2649621,
            "ar_round": 775,
            "guard": {"physical": 51, "holy": 55},
            "gb": 50,
            "resist": 22,
        },
    },
    {
        "name": "Ordovis's Greatsword +10",
        "inp": {
            "weapon_class": "Greatsword",
            "weapon": "Ordovis's Greatsword",
            "affinity": "Standard",
            "upgrade": 10,
            "strength": 60,
            "dexterity": 13,
            "intelligence": 10,
            "faith": 60,
            "arcane": 9,
        },
        "expect": {
            "letters": {"strength": "A", "dexterity": "E", "faith": "C"},
            "pct": {"strength": 1.422, "dexterity": 0.18, "faith": 0.63},
            "base": {"physical": 262.15, "holy": 169.05},
            "scaling": {"physical": 287.3497579, "holy": 90.526275},
            "total": {"physical": 549.4997579, "holy": 259.576275},
            "rounded": {"physical": 549, "holy": 259},
            "sub": {"physical": {"strength": 279.583, "dexterity": 7.767}, "holy": {"faith": 90.526}},
            "ar": 809.0760329,
            "ar_round": 809,
            "guard": {"physical": 69, "holy": 50},
            "gb": 51,
            "resist": 22,
        },
    },
    {
        "name": "Claymore +25 Standard (STR 55)",
        "inp": {
            "weapon_class": "Greatsword",
            "weapon": "Claymore",
            "affinity": "Standard",
            "upgrade": 25,
            "strength": 55,
            "dexterity": 13,
            "intelligence": 80,
            "faith": 7,
            "arcane": 9,
        },
        "expect": {
            "letters": {"strength": "C", "dexterity": "D"},
            "pct": {"strength": 0.735, "dexterity": 0.51},
            "base": {"physical": 338.1},
            "scaling": {"physical": 205.0948141},
            "total": {"physical": 543.1948141},
            "rounded": {"physical": 543},
            "sub": {"physical": {"strength": 176.713, "dexterity": 28.381}},
            "ar": 543.1948141,
            "ar_round": 543,
            "guard": {"physical": 65, "magic": 35},
            "gb": 50,
            "resist": 20,
        },
    },
    {
        "name": "Estoc +25 Standard (STR 60 / DEX 13)",
        "inp": {
            "weapon_class": "Thrusting Sword",
            "weapon": "Estoc",
            "affinity": "Standard",
            "upgrade": 25,
            "strength": 60,
            "dexterity": 13,
            "intelligence": 80,
            "faith": 7,
            "arcane": 9,
        },
        "expect": {
            "letters": {"strength": "E", "dexterity": "B"},
            "pct": {"strength": 0.21, "dexterity": 0.90},
            "req": {"strength": 11, "dexterity": 13},
            "sat": {"physical": {"strength": 0.75, "dexterity": 0.1646}},
            "base": {"physical": 262.15},
            "scaling": {"physical": 80.12253946},
            "total": {"physical": 342.2725395},
            "rounded": {"physical": 342},
            "sub": {"physical": {"strength": 41.289, "dexterity": 38.834}},
            "ar": 342.2725395,
            "ar_round": 342,
            "guard": {"physical": 54, "magic": 36},
            "gb": 28,
            "resist": 12,
        },
    },
    {
        "name": "Estoc +25 Standard (STR 20 / DEX 60)",
        "inp": {
            "weapon_class": "Thrusting Sword",
            "weapon": "Estoc",
            "affinity": "Standard",
            "upgrade": 25,
            "strength": 20,
            "dexterity": 60,
            "intelligence": 80,
            "faith": 7,
            "arcane": 9,
        },
        "expect": {
            "letters": {"strength": "E", "dexterity": "B"},
            "pct": {"strength": 0.21, "dexterity": 0.90},
            "sat": {"physical": {"strength": 0.2784, "dexterity": 0.75}},
            "base": {"physical": 262.15},
            "scaling": {"physical": 192.2794378},
            "total": {"physical": 454.4294378},
            "rounded": {"physical": 454},
            "sub": {"physical": {"strength": 15.328, "dexterity": 176.951}},
            "ar": 454.4294378,
            "ar_round": 454,
            "guard": {"physical": 54},
            "gb": 28,
            "resist": 12,
        },
    },
    {
        "name": "Estoc +25 Standard Frozen Armament (STR 20 / DEX 80)",
        "inp": {
            "weapon_class": "Thrusting Sword",
            "weapon": "Estoc",
            "affinity": "Standard",
            "upgrade": 25,
            "strength": 20,
            "dexterity": 80,
            "intelligence": 60,
            "faith": 7,
            "arcane": 9,
            "status_buff": "Frozen Armament",
        },
        "expect": {
            "letters": {"strength": "E", "dexterity": "B"},
            "pct": {"strength": 0.21, "dexterity": 0.90},
            "sat": {"physical": {"strength": 0.2784, "dexterity": 0.90}},
            "base": {"physical": 262.15, "frost": 63},
            "scaling": {"physical": 227.6696878, "frost": 0},
            "total": {"physical": 489.8196878, "frost": 63},
            "rounded": {"physical": 489, "frost": 63},
            "sub": {"physical": {"strength": 15.328, "dexterity": 212.342}},
            "ar": 489.8196878,
            "ar_round": 489,
            "guard": {"physical": 54},
            "gb": 28,
            "resist": 12,
        },
    },
]


def _to_number(value: str) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    if text.upper() == "TRUE":
        return True
    if text.upper() == "FALSE":
        return False
    try:
        n = float(text)
    except ValueError:
        return text
    if math.isfinite(n) and n == int(n) and abs(n) < 1e15:
        # Keep IDs like 2000000.0 as float so lookups stay consistent
        return n
    return n


def _is_comment_row(row: dict) -> bool:
    name = str(row.get("Name") or row.get("Weapon") or "")
    return name.startswith("(")


def load_table(name: str, id_field: str = "ID") -> dict[float, dict]:
    path = CSV / f"{name}.csv"
    out: dict[float, dict] = {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = {k: _to_number(v) if k != "Name" else (v or "") for k, v in raw.items()}
            if _is_comment_row(row):
                continue
            key = row.get(id_field)
            if key in (None, ""):
                continue
            out[float(key)] = row
    return out


def load_by_name(name: str, key_field: str = "Name") -> dict[str, dict]:
    path = CSV / f"{name}.csv"
    out: dict[str, dict] = {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = {
                k: _to_number(v) if k != key_field else (v or "")
                for k, v in raw.items()
            }
            if _is_comment_row(row):
                continue
            key = row.get(key_field)
            if key in (None, ""):
                continue
            out[str(key)] = row
    return out


def load_weapon_data() -> tuple[dict[str, dict], dict[str, float]]:
    path = CSV / "WeaponData.csv"
    weapons: dict[str, dict] = {}
    affinity_offset: dict[str, float] = {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = {k: _to_number(v) if k not in ("Weapon Class", "Weapon", "Infusion") else (v or "") for k, v in raw.items()}
            name = row.get("Weapon")
            if name:
                weapons[str(name)] = row
            infusion = row.get("Infusion")
            if infusion not in (None, ""):
                affinity_offset[str(infusion)] = float(row.get("Offset") or 0)
    return weapons, affinity_offset


def load_calc_graph() -> dict[int, dict[int, float]]:
    path = CSV / "CalcCorrectGraphEz.csv"
    graph: dict[int, dict[int, float]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        stats = [int(float(h)) for h in header[1:] if h]
        for parts in reader:
            if not parts or parts[0] == "":
                continue
            gid = int(float(parts[0]))
            graph[gid] = {
                stat: float(raw)
                for stat, raw in zip(stats, parts[1:])
                if raw != ""
            }
    return graph


def vlookup_graph(graph: dict[int, dict[int, float]], correct_type: float, stat: int) -> float:
    # ApCalcData: VLOOKUP(correctType, CalcCorrectGraphEz, stat+1)
    row = graph.get(int(correct_type), {})
    return float(row.get(int(stat), 0.0))


def clamp_stat(value: float) -> int:
    return int(min(max(int(value), 1), 99))


def scaling_letter(percent: float) -> str:
    # AP-Calc O12: IFS(ROUND(percent,4) >= thresholds)
    x = round(percent, 4)
    if x >= 1.75:
        return "S"
    if x >= 1.4:
        return "A"
    if x >= 0.9:
        return "B"
    if x >= 0.6:
        return "C"
    if x >= 0.25:
        return "D"
    if x >= 0.01:
        return "E"
    return "-"


def fmt(value, pct: bool = False, dash: bool = False) -> str:
    if value is None or (dash and (value == 0 or value == 0.0)):
        return "-"
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if pct:
        return f"{value * 100:.2f}%"
    if isinstance(value, int) or (isinstance(value, float) and value == int(value) and abs(value) < 1e12):
        if isinstance(value, float) and not value.is_integer():
            return f"{value}"
        return str(int(value)) if float(value).is_integer() and abs(value - round(value)) < 1e-9 and abs(value) >= 1 else f"{value}"
    return f"{value}"


@dataclass
class Inputs:
    weapon_class: str
    weapon: str
    affinity: str
    upgrade: int
    strength: int
    dexterity: int
    intelligence: int
    faith: int
    arcane: int
    two_hand: bool = False
    ignore_require: bool = False
    status_buff: str = "None"
    overwrite_aec_id: Optional[float] = None
    overwrite_base: dict[str, Optional[float]] = field(default_factory=dict)
    change_points: dict[str, float] = field(default_factory=dict)
    base_atk_rate: bool = False


@dataclass
class ApResult:
    weapon_label: str
    stats: dict[str, int]
    requirements: dict[str, Any]
    scaling_percent: dict[str, float]
    scaling_letter: dict[str, str]
    saturation: dict[str, dict[str, float]]
    status_saturation: dict[str, float]
    base: dict[str, Any]
    scaling: dict[str, Any]
    total: dict[str, Any]
    rounded: dict[str, Any]
    subtotals: dict[str, dict[str, Any]]
    total_ar: float
    total_ar_rounded: int
    guard_negation: dict[str, float]
    guard_boost: int
    guard_resist: dict[str, int]
    req_met: dict[str, bool]


class ApCalc:
    def __init__(self) -> None:
        self.weapons, self.affinity_offset = load_weapon_data()
        self.equip = load_table("EquipParamWeapon")
        self.reinforce = load_table("ReinforceParamWeapon")
        self.aec = load_table("AttackElementCorrectParam")
        self.graph = load_calc_graph()
        self.player = load_table("PlayerCommonParam")
        self.status_buffs = load_by_name("StatusBuffData")
        self.status_effects = load_table("StatusEffectData", id_field="SpEffectId")
        low = self.player.get(0.0, {})
        self.low_status_atk_pow_down = float(low.get("lowStatus_AtkPowDown") or 0.4)

    def _status_from_effect(self, speffect_id: Any) -> dict[str, float]:
        zeros = {name: 0.0 for name in STATUS}
        try:
            sid = float(speffect_id)
        except (TypeError, ValueError):
            return zeros
        if sid in (-1.0, 0.0):
            return zeros
        row = self.status_effects.get(sid)
        if not row:
            return zeros
        return {name: float(row.get(STATUS_FIELD[name]) or 0) for name in STATUS}

    def _status_buff_effect_id(self, inp: Inputs, equip: dict) -> float:
        # ApCalcData E39: valid buff → StatusBuffData SpEffectId, else -1
        row = self.status_buffs.get(inp.status_buff or "None")
        if not row:
            return -1.0
        class_ok = bool(row.get(inp.weapon_class))
        affinity_ok = bool(row.get(inp.affinity))
        if bool(row.get("isEnhanceIgnore")):
            valid = class_ok and affinity_ok and not bool(equip.get("disableGemAttr"))
        else:
            valid = bool(equip.get("isEnhance")) and class_ok and affinity_ok
        if not valid:
            return -1.0
        try:
            return float(row.get("SpEffectId") or -1)
        except (TypeError, ValueError):
            return -1.0

    def calculate(self, inp: Inputs) -> ApResult:
        wmeta = self.weapons.get(inp.weapon)
        if not wmeta:
            raise SystemExit(f"Unknown weapon: {inp.weapon}")
        if inp.weapon_class and wmeta.get("Weapon Class") != inp.weapon_class:
            raise SystemExit(
                f"Weapon {inp.weapon!r} is class {wmeta.get('Weapon Class')!r}, "
                f"not {inp.weapon_class!r}"
            )

        offset = 0.0
        if wmeta.get("isInfuse"):
            if inp.affinity not in self.affinity_offset:
                raise SystemExit(f"Unknown affinity: {inp.affinity}")
            offset = self.affinity_offset[inp.affinity]
        weapon_id = float(wmeta["ID"]) + offset
        equip = self.equip.get(weapon_id)
        if not equip:
            raise SystemExit(f"No EquipParamWeapon row for ID {weapon_id}")

        reinforce_id = float(equip.get("reinforceTypeId") or 0) + inp.upgrade
        reinf = self.reinforce.get(reinforce_id) or {}

        aec_id = inp.overwrite_aec_id
        if aec_id is None:
            aec_id = float(equip.get("attackElementCorrectId") or 0)
        aec = self.aec.get(float(aec_id), {})

        two_hand_bonus = bool(wmeta.get("bothHandsAtkBonus"))
        str_for_scaling = clamp_stat(inp.strength)
        if inp.two_hand and two_hand_bonus:
            str_for_scaling = int(math.trunc(str_for_scaling * 1.5))
            str_for_scaling = min(max(str_for_scaling, 1), 99)

        stats = {
            "strength": str_for_scaling,
            "dexterity": clamp_stat(inp.dexterity),
            "intelligence": clamp_stat(inp.intelligence),
            "faith": clamp_stat(inp.faith),
            "arcane": clamp_stat(inp.arcane),
        }
        req = {
            "strength": float(equip.get("properStrength") or 0),
            "dexterity": float(equip.get("properAgility") or 0),
            "intelligence": float(equip.get("properMagic") or 0),
            "faith": float(equip.get("properFaith") or 0),
            "arcane": float(equip.get("properLuck") or 0),
        }
        # B26 uses 1.5 whenever 2h is checked, even if the weapon has no 2h bonus
        str_for_req = clamp_stat(inp.strength)
        if inp.two_hand:
            str_for_req = int(math.trunc(min(max(str_for_req, 1), 99) * 1.5))
        req_stat = dict(stats)
        req_stat["strength"] = str_for_req if inp.two_hand else stats["strength"]
        req_met = {}
        for stat in STATS:
            if inp.ignore_require:
                req_met[stat] = True
            else:
                req_met[stat] = req_stat[stat] >= req[stat]

        change = {s: 0.01 * float(inp.change_points.get(s) or 0) for s in STATS}

        scaling_percent = {}
        for stat in STATS:
            correct = float(equip.get(WEAPON_CORRECT[stat]) or 0) * 0.01
            rate = float(reinf.get(REINFORCE_CORRECT[stat]) or 1)
            scaling_percent[stat] = correct * rate + change[stat]

        def aec_flag(stat: str, dmg: str) -> bool:
            col = f"is{AEC_STAT[stat]}Correct_by{DAMAGE_AEC[dmg]}"
            return bool(aec.get(col))

        def aec_overwrite(stat: str, dmg: str) -> float:
            col = f"overwrite{AEC_STAT[stat]}CorrectRate_by{DAMAGE_AEC[dmg]}"
            raw = aec.get(col)
            if raw is None:
                return -1.0
            val = float(raw)
            if val >= 0:
                return val * 0.01
            return -1.0

        def aec_influence(stat: str, dmg: str) -> float:
            col = f"Influence{AEC_STAT[stat]}CorrectRate_by{DAMAGE_AEC[dmg]}"
            raw = aec.get(col)
            if raw in (None, ""):
                return 1.0
            return float(raw) * 0.01

        saturation: dict[str, dict[str, float]] = {d: {} for d in DAMAGE}
        for dmg in DAMAGE:
            ctype = float(equip.get(WEAPON_CORRECT_TYPE[dmg]) or 0)
            for stat in STATS:
                sat = vlookup_graph(self.graph, ctype, stats[stat]) * 0.01
                saturation[dmg][stat] = sat if aec_flag(stat, dmg) else 0.0

        status_types = {
            "poison": float(equip.get("correctType_Poison") or 0),
            "bleed": float(equip.get("correctType_Blood") or 0),
            "sleep": float(equip.get("correctType_Sleep") or 0),
            "madness": float(equip.get("correctType_Madness") or 0),
        }
        status_saturation = {
            name: vlookup_graph(self.graph, ctype, stats["arcane"]) * 0.01
            for name, ctype in status_types.items()
        }

        def penalty(dmg: str) -> bool:
            return any(
                (not req_met[stat]) and aec_flag(stat, dmg) for stat in STATS
            )

        def penalty_value(dmg: str) -> float:
            infs = [aec_influence(s, dmg) for s in STATS]
            return min(0.6 * (inf - 1) - self.low_status_atk_pow_down for inf in infs)

        contrib: dict[str, dict[str, float]] = {d: {} for d in DAMAGE}
        for dmg in DAMAGE:
            hit = penalty(dmg)
            for stat in STATS:
                if aec_flag(stat, dmg) and not hit:
                    inf = aec_influence(stat, dmg)
                    ow = aec_overwrite(stat, dmg)
                    scale = ow if ow >= 0 else scaling_percent[stat]
                    sat = vlookup_graph(
                        self.graph,
                        float(equip.get(WEAPON_CORRECT_TYPE[dmg]) or 0),
                        stats[stat],
                    ) * 0.01
                    contrib[dmg][stat] = inf - 1 + scale * sat * inf
                else:
                    contrib[dmg][stat] = 0.0

        base: dict[str, Any] = {}
        scaling: dict[str, Any] = {}
        total: dict[str, Any] = {}
        rounded: dict[str, Any] = {}
        subtotals: dict[str, dict[str, Any]] = {}
        for dmg in DAMAGE:
            raw_base = inp.overwrite_base.get(dmg)
            if raw_base in (None, ""):
                raw_base = float(equip.get(WEAPON_BASE[dmg]) or 0)
            atk_rate = float(reinf.get(REINFORCE_ATK[dmg]) or 1)
            if inp.base_atk_rate:
                atk_rate = float(reinf.get("baseAtkRate") or atk_rate)
            shown_base = raw_base * atk_rate
            if raw_base == 0:
                base[dmg] = None
                scaling[dmg] = None
                total[dmg] = None
                rounded[dmg] = None
                subtotals[dmg] = {s: None for s in STATS}
                continue
            parts = contrib[dmg]
            scale_sum = sum(parts.values())
            if penalty(dmg):
                scale_sum = penalty_value(dmg)
            elif any(v < 0 for v in parts.values()):
                scale_sum = min(list(parts.values()) + [0])
            sc = shown_base * scale_sum
            tot = shown_base + sc
            base[dmg] = shown_base
            scaling[dmg] = sc
            total[dmg] = tot
            rounded[dmg] = math.trunc(tot)
            subtotals[dmg] = {s: round(shown_base * parts[s], 3) for s in STATS}

        totals = [total[d] for d in DAMAGE if isinstance(total[d], (int, float))]
        total_ar = sum(totals)
        total_ar_rounded = math.trunc(total_ar)

        slot0 = self._status_from_effect(
            float(equip.get("spEffectBehaviorId0") or -1)
            + float(reinf.get("spEffectId1") or 0)
        )
        slot1 = self._status_from_effect(
            float(equip.get("spEffectBehaviorId1") or -1)
            + float(reinf.get("spEffectId2") or 0)
        )
        buff = self._status_from_effect(self._status_buff_effect_id(inp, equip))
        for name in STATUS:
            innate = slot1[name] if slot0[name] == 0 else slot0[name]
            shown = innate + buff[name]
            if shown == 0:
                base[name] = None
                scaling[name] = None
                total[name] = None
                rounded[name] = None
                continue
            if name in STATUS_NO_SCALING:
                sc = 0.0
            else:
                sc = shown * scaling_percent["arcane"] * status_saturation.get(name, 0.0)
            base[name] = shown
            scaling[name] = sc
            total[name] = shown + sc
            rounded[name] = math.trunc(shown + sc)

        guard_negation = {
            "physical": min(float(equip.get("physGuardCutRate") or 0) * float(reinf.get("physicsGuardCutRate") or 1), 100),
            "magic": min(float(equip.get("magGuardCutRate") or 0) * float(reinf.get("magicGuardCutRate") or 1), 100),
            "fire": min(float(equip.get("fireGuardCutRate") or 0) * float(reinf.get("fireGuardCutRate") or 1), 100),
            "lightning": min(float(equip.get("thunGuardCutRate") or 0) * float(reinf.get("thunderGuardCutRate") or 1), 100),
            "holy": min(float(equip.get("darkGuardCutRate") or 0) * float(reinf.get("darkGuardCutRate") or 1), 100),
        }
        guard_boost = int(math.trunc(float(equip.get("staminaGuardDef") or 0) * float(reinf.get("staminaGuardDefRate") or 1)))
        guard_resist = {
            "poison": int(math.trunc(float(equip.get("poisonGuardResist") or 0) * float(reinf.get("poisonGuardResistRate") or 1))),
            "scarlet_rot": int(math.trunc(float(equip.get("diseaseGuardResist") or 0) * float(reinf.get("diseaseGuardResistRate") or 1))),
            "bleed": int(math.trunc(float(equip.get("bloodGuardResist") or 0) * float(reinf.get("bloodGuardResistRate") or 1))),
            "frost": int(math.trunc(float(equip.get("freezeGuardResist") or 0) * float(reinf.get("freezeGuardDefRate") or 1))),
            "sleep": int(math.trunc(float(equip.get("sleepGuardResist") or 0) * float(reinf.get("sleepGuardDefRate") or 1))),
            "madness": int(math.trunc(float(equip.get("madnessGuardResist") or 0) * float(reinf.get("madnessGuardDefRate") or 1))),
            "death": int(math.trunc(float(equip.get("curseGuardResist") or 0) * float(reinf.get("curseGuardResistRate") or 1))),
        }

        upgrade = inp.upgrade
        label = str(equip.get("Name") or inp.weapon)
        if upgrade:
            label = f"{label} +{upgrade}"

        return ApResult(
            weapon_label=label,
            stats=stats,
            requirements={s: (int(req[s]) if req[s] else None) for s in STATS},
            scaling_percent=scaling_percent,
            scaling_letter={s: scaling_letter(scaling_percent[s]) for s in STATS},
            saturation=saturation,
            status_saturation=status_saturation,
            base=base,
            scaling=scaling,
            total=total,
            rounded=rounded,
            subtotals=subtotals,
            total_ar=total_ar,
            total_ar_rounded=total_ar_rounded,
            guard_negation=guard_negation,
            guard_boost=guard_boost,
            guard_resist=guard_resist,
            req_met=req_met,
        )


def print_result(inp: Inputs, r: ApResult) -> None:
    print(f"{r.weapon_label} Scaling")
    print(f"  {'':<14}{'Str':>10}{'Dex':>10}{'Int':>10}{'Fth':>10}{'Arc':>10}")
    print(
        "  Letter      "
        + "".join(f"{r.scaling_letter[s]:>10}" for s in STATS)
    )
    print(
        "  Percent     "
        + "".join(f"{r.scaling_percent[s] * 100:9.2f}%" for s in STATS)
    )
    print(
        "  Require     "
        + "".join(f"{fmt(r.requirements[s], dash=True):>10}" for s in STATS)
    )
    print()
    print("Attribute Saturation")
    print(f"  {'':<14}{'Str':>10}{'Dex':>10}{'Int':>10}{'Fth':>10}{'Arc':>10}")
    for dmg in DAMAGE:
        print(
            f"  {dmg.capitalize():<14}"
            + "".join(f"{r.saturation[dmg][s] * 100:9.2f}%" for s in STATS)
        )
    for name in ("poison", "bleed", "sleep", "madness"):
        print(f"  {name.capitalize():<14}{'-':>10}{'-':>10}{'-':>10}{'-':>10}{r.status_saturation[name] * 100:9.2f}%")
    print()
    print("Attack Power")
    print(f"  {'':<16}{'Base':>14}{'Scaling':>16}{'Total':>16}{'Rounded':>10}")
    for dmg in DAMAGE:
        label = f"{dmg.capitalize()} AP"
        if r.base[dmg] is None:
            print(f"  {label:<16}{'-':>14}{'-':>16}{'-':>16}{'-':>10}")
        else:
            print(
                f"  {label:<16}{r.base[dmg]:14.4f}{r.scaling[dmg]:16.8f}"
                f"{r.total[dmg]:16.8f}{r.rounded[dmg]:10d}"
            )
    for name in STATUS:
        if r.base.get(name) is None:
            continue
        print(
            f"  {STATUS_LABEL[name]:<16}{r.base[name]:14.4f}{r.scaling[name]:16.8f}"
            f"{r.total[name]:16.8f}{r.rounded[name]:10d}"
        )
    print(
        f"  {'Total AR':<16}{'':>14}{'':>16}{r.total_ar:16.8f}{r.total_ar_rounded:10d}"
    )
    print()
    print("Scaling Sub Totals (Physical AP)")
    print(f"  {'':<14}{'Str':>10}{'Dex':>10}{'Int':>10}{'Fth':>10}{'Arc':>10}")
    phys = r.subtotals["physical"]
    print(
        "  Physical AP "
        + "".join(
            f"{(phys[s] if phys[s] is not None else 0):10.3f}" if phys[s] is not None else f"{'-':>10}"
            for s in STATS
        )
    )
    print()
    print("Guard Damage Negations")
    g = r.guard_negation
    print(
        f"  Phys {g['physical']:.3f}  Mag {g['magic']:.3f}  Fire {g['fire']:.3f}  "
        f"Ltng {g['lightning']:.3f}  Holy {g['holy']:.3f}"
    )
    print(f"  Guard Boost {r.guard_boost}")
    print("Guard Resistances")
    rs = r.guard_resist
    print(
        f"  Poison {rs['poison']}  Rot {rs['scarlet_rot']}  Bleed {rs['bleed']}  "
        f"Frost {rs['frost']}  Sleep {rs['sleep']}  Madness {rs['madness']}  Death {rs['death']}"
    )
    print()
    print("Inputs")
    print(
        f"  {inp.weapon_class} / {inp.weapon} / {inp.affinity} +{inp.upgrade}  "
        f"STR {inp.strength} DEX {inp.dexterity} INT {inp.intelligence} "
        f"FTH {inp.faith} ARC {inp.arcane}  2h={inp.two_hand} "
        f"ignore_req={inp.ignore_require} buff={inp.status_buff}"
    )


def almost(a: float, b: float, places: int = 6) -> bool:
    return abs(a - b) <= 0.5 * 10 ** (-places)


def check_case(r: ApResult, expect: dict) -> list[str]:
    errors: list[str] = []

    def eq(name, got, expected, places=6):
        if expected is None:
            if got not in (None, 0, "-"):
                errors.append(f"{name}: expected empty/-, got {got}")
            return
        if isinstance(expected, str) or isinstance(got, str):
            if got != expected:
                errors.append(f"{name}: got {got}, expected {expected}")
            return
        if got is None:
            got = 0
        if not almost(float(got), float(expected), places):
            errors.append(f"{name}: got {got}, expected {expected}")

    for stat, letter in expect.get("letters", {}).items():
        eq(f"letter.{stat}", r.scaling_letter[stat], letter)
    for stat, pct in expect.get("pct", {}).items():
        eq(f"pct.{stat}", r.scaling_percent[stat], pct, 4)
    for stat, req in expect.get("req", {}).items():
        eq(f"req.{stat}", r.requirements[stat], req, 0)
    for stat, met in expect.get("req_met", {}).items():
        eq(f"req_met.{stat}", r.req_met[stat], met)
    for dmg, parts in expect.get("sat", {}).items():
        for stat, val in parts.items():
            eq(f"sat.{dmg}.{stat}", r.saturation[dmg][stat], val, 4)
    for dmg, val in expect.get("base", {}).items():
        eq(f"base.{dmg}", r.base.get(dmg), val, 4)
    for dmg, val in expect.get("scaling", {}).items():
        eq(f"scaling.{dmg}", r.scaling[dmg], val, 4)
    for dmg, val in expect.get("total", {}).items():
        eq(f"total.{dmg}", r.total[dmg], val, 4)
    for dmg, val in expect.get("rounded", {}).items():
        eq(f"rounded.{dmg}", r.rounded[dmg], val, 0)
    for dmg, parts in expect.get("sub", {}).items():
        for stat, val in parts.items():
            eq(f"sub.{dmg}.{stat}", r.subtotals[dmg].get(stat), val, 3)
    if "ar" in expect:
        eq("ar", r.total_ar, expect["ar"], 4)
    if "ar_round" in expect:
        eq("ar.round", r.total_ar_rounded, expect["ar_round"], 0)
    for dmg, val in expect.get("guard", {}).items():
        eq(f"guard.{dmg}", r.guard_negation[dmg], val, 3)
    if "gb" in expect:
        eq("guard.boost", r.guard_boost, expect["gb"], 0)
    if "resist" in expect:
        eq("resist.poison", r.guard_resist["poison"], expect["resist"], 0)
    return errors


def inputs_to_dict(inp: Inputs) -> dict[str, Any]:
    return {
        "weapon_class": inp.weapon_class,
        "weapon": inp.weapon,
        "affinity": inp.affinity,
        "upgrade": inp.upgrade,
        "strength": inp.strength,
        "dexterity": inp.dexterity,
        "intelligence": inp.intelligence,
        "faith": inp.faith,
        "arcane": inp.arcane,
        "two_hand": inp.two_hand,
        "ignore_require": inp.ignore_require,
        "status_buff": inp.status_buff,
    }


def result_to_dict(inp: Inputs, r: ApResult) -> dict[str, Any]:
    def block(name: str) -> Optional[dict[str, Any]]:
        if r.base.get(name) is None:
            return None
        return {
            "base": r.base[name],
            "scaling": r.scaling[name],
            "total": r.total[name],
            "rounded": r.rounded[name],
        }

    return {
        "inputs": inputs_to_dict(inp),
        "weapon_label": r.weapon_label,
        "scaling": {
            stat: {
                "letter": r.scaling_letter[stat],
                "percent": r.scaling_percent[stat],
                "requirement": r.requirements[stat],
                "req_met": r.req_met[stat],
            }
            for stat in STATS
        },
        "saturation": r.saturation,
        "status_saturation": r.status_saturation,
        "attack_power": {dmg: block(dmg) for dmg in DAMAGE},
        "status": {name: block(name) for name in STATUS},
        "subtotals": {
            dmg: {stat: r.subtotals[dmg][stat] for stat in STATS}
            for dmg in DAMAGE
        },
        "total_ar": r.total_ar,
        "total_ar_rounded": r.total_ar_rounded,
        "guard_negation": r.guard_negation,
        "guard_boost": r.guard_boost,
        "guard_resist": r.guard_resist,
    }


def check_all(calc: ApCalc) -> int:
    failed = 0
    for case in SCREENSHOT_CASES:
        kwargs = dict(SCREENSHOT_INPUTS)
        kwargs.update(case["inp"])
        inp = Inputs(**kwargs)
        result = calc.calculate(inp)
        errors = check_case(result, case["expect"])
        if errors:
            failed += 1
            print(f"FAIL  {case['name']}")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"PASS  {case['name']}  AR {result.total_ar_rounded}")
    if failed:
        print(f"\nCHECK FAILED: {failed}/{len(SCREENSHOT_CASES)} cases")
        return 1
    print(f"\nCHECK OK — {len(SCREENSHOT_CASES)} spreadsheet screenshots match.")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Elden Ring AP Calc (Build Planner port)")
    p.add_argument("--weapon-class", default=SCREENSHOT_INPUTS["weapon_class"])
    p.add_argument("--weapon", default=SCREENSHOT_INPUTS["weapon"])
    p.add_argument("--affinity", default=SCREENSHOT_INPUTS["affinity"])
    p.add_argument("--upgrade", type=int, default=SCREENSHOT_INPUTS["upgrade"])
    p.add_argument("--strength", type=int, default=SCREENSHOT_INPUTS["strength"])
    p.add_argument("--dexterity", type=int, default=SCREENSHOT_INPUTS["dexterity"])
    p.add_argument("--intelligence", type=int, default=SCREENSHOT_INPUTS["intelligence"])
    p.add_argument("--faith", type=int, default=SCREENSHOT_INPUTS["faith"])
    p.add_argument("--arcane", type=int, default=SCREENSHOT_INPUTS["arcane"])
    p.add_argument("--two-hand", action="store_true")
    p.add_argument("--ignore-require", action="store_true")
    p.add_argument("--status-buff", default="None")
    p.add_argument(
        "--check",
        action="store_true",
        help="Verify all spreadsheet screenshot fixtures",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Print one result as JSON (oracle contract for another implementation)",
    )
    p.add_argument(
        "--export-oracle",
        metavar="PATH",
        help="Write screenshot fixtures as JSONL oracle records and exit",
    )
    return p.parse_args()


def export_oracle(calc: ApCalc, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for case in SCREENSHOT_CASES:
            kwargs = dict(SCREENSHOT_INPUTS)
            kwargs.update(case["inp"])
            inp = Inputs(**kwargs)
            record = result_to_dict(inp, calc.calculate(inp))
            record["name"] = case["name"]
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()
    calc = ApCalc()
    if args.check:
        return check_all(calc)
    if args.export_oracle:
        export_oracle(calc, Path(args.export_oracle))
        print(f"Wrote {len(SCREENSHOT_CASES)} oracle records to {args.export_oracle}")
        return 0
    inp = Inputs(
        weapon_class=args.weapon_class,
        weapon=args.weapon,
        affinity=args.affinity,
        upgrade=args.upgrade,
        strength=args.strength,
        dexterity=args.dexterity,
        intelligence=args.intelligence,
        faith=args.faith,
        arcane=args.arcane,
        two_hand=args.two_hand,
        ignore_require=args.ignore_require,
        status_buff=args.status_buff,
    )
    result = calc.calculate(inp)
    if args.json:
        json.dump(result_to_dict(inp, result), sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print_result(inp, result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
