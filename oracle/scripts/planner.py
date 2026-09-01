#!/usr/bin/env python3
"""Port of Build Planner / PlannerData.

Core stats, vitals, armor, roll, and weapon AR. EffectData_Active is stubbed
as empty-gear (multipliers 1, stat adds 0) so talisman/tear/great-rune *effects*
are not applied yet; armor/talisman weight, absorption, and resists are.

Spell AP (MagicApData) is not included: that sheet reads PlannerData outputs.

Tables come from extracted/Build-Planner-v1.19.1/csv/.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ap_calc import (
    AEC_STAT,
    DAMAGE,
    DAMAGE_AEC,
    REINFORCE_ATK,
    REINFORCE_CORRECT,
    STATS,
    STATUS,
    STATUS_FIELD,
    STATUS_LABEL,
    WEAPON_BASE,
    WEAPON_CORRECT,
    WEAPON_CORRECT_TYPE,
    ApCalc,
    almost,
    clamp_stat,
    load_table,
    vlookup_graph,
)

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "extracted" / "Build-Planner-v1.19.1" / "csv"

CORE_STATS = (
    "vigor",
    "mind",
    "endurance",
    "strength",
    "dexterity",
    "intelligence",
    "faith",
    "arcane",
)
SLOT_NAMES = ("RH1", "RH2", "RH3", "LH1", "LH2", "LH3")
EMPTY_GEAR = ("", "Empty", "empty", None)
ABSORB_FIELD = {
    "physical": "neutralDamageCutRate",
    "strike": "blowDamageCutRate",
    "slash": "slashDamageCutRate",
    "pierce": "thrustDamageCutRate",
    "magic": "magicDamageCutRate",
    "fire": "fireDamageCutRate",
    "lightning": "thunderDamageCutRate",
    "holy": "darkDamageCutRate",
}
RESIST_FIELD = {
    "immunity": "resistPoison",
    "robustness": "resistBlood",
    "focus": "resistSleep",
    "vitality": "resistCurse",
}
BULL_GOAT = "Bull-Goat's Talisman"


@dataclass
class WeaponSlotIn:
    weapon: str = "Unarmed"
    affinity: str = "Standard"
    upgrade: int = 0


@dataclass
class PlannerInputs:
    starting_class: str = "Vagabond"
    vigor: Optional[int] = None
    mind: Optional[int] = None
    endurance: Optional[int] = None
    strength: Optional[int] = None
    dexterity: Optional[int] = None
    intelligence: Optional[int] = None
    faith: Optional[int] = None
    arcane: Optional[int] = None
    rh1: WeaponSlotIn = field(default_factory=WeaponSlotIn)
    rh2: WeaponSlotIn = field(default_factory=WeaponSlotIn)
    rh3: WeaponSlotIn = field(default_factory=WeaponSlotIn)
    lh1: WeaponSlotIn = field(default_factory=WeaponSlotIn)
    lh2: WeaponSlotIn = field(default_factory=WeaponSlotIn)
    lh3: WeaponSlotIn = field(default_factory=WeaponSlotIn)
    two_hand: bool = False
    ignore_require: bool = False
    head: str = "Empty"
    chest: str = "Empty"
    arms: str = "Empty"
    legs: str = "Empty"
    talisman1: str = "Empty"
    talisman2: str = "Empty"
    talisman3: str = "Empty"
    talisman4: str = "Empty"


@dataclass
class WeaponSlotOut:
    slot: str
    weapon: str
    weapon_class: str
    affinity: str
    upgrade: int
    invalid: bool
    weight: float
    ap: dict[str, Optional[float]]
    ap_display: dict[str, Any]
    total_ap: float
    total_display: Any
    scaling_percent: dict[str, float]
    scaling_letter: dict[str, str]
    requirements: dict[str, float]
    req_met: dict[str, bool]
    spell_buff: float
    status: dict[str, int]


@dataclass
class PlannerResult:
    starting_class: str
    class_stats: dict[str, int]
    allocated: dict[str, int]
    alter: dict[str, int]
    final_stats: dict[str, int]
    level: int
    hp: int
    fp: int
    stamina: int
    equip_load: float
    equipped_weight: float
    discovery: float
    discovery_display: int
    defenses: dict[str, int]
    absorb: dict[str, float]
    negation: dict[str, float]
    resists: dict[str, int]
    poise: float
    roll: str
    weight_left: float
    weight_left_display: str
    equip_load_display: str
    encumbrance_pct: str
    end_for_mid_roll: Any
    end_for_light_roll: Any
    weapons: list[WeaponSlotOut]
    optimal_class: str
    extra_levels: int


def excel_round(value: float, digits: int) -> float:
    p = 10 ** digits
    if value >= 0:
        return math.floor(value * p + 0.5) / p
    return math.ceil(value * p - 0.5) / p


def excel_rounddown(value: float, digits: int) -> float:
    p = 10 ** digits
    return math.trunc(value * p) / p


def sheet_one_decimal(value: float) -> str:
    rounded = excel_round(value, 1)
    if rounded == math.trunc(rounded):
        return f"{rounded:.1f}"
    text = f"{rounded:.10f}".rstrip("0").rstrip(".")
    return text if "." in text else f"{float(text):.1f}"


def dash_round(value: float, digits: int = 2) -> Any:
    if value > 0:
        return excel_round(value, digits)
    return "-"


def planner_letter(percent: Any) -> str:
    if percent == "-" or percent in (None, 0, 0.0):
        return "-"
    x = float(percent)
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
    if x > 0.01:
        return "E"
    return "-"


def _blank(name: Optional[str]) -> bool:
    return name is None or str(name).strip() in EMPTY_GEAR


def load_starting_classes() -> dict[str, dict[str, int]]:
    path = CSV / "StartingClassData.csv"
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [next(reader) for _ in CORE_STATS]
    out: dict[str, dict[str, int]] = {}
    for col, name in enumerate(header):
        if not name:
            continue
        out[name] = {
            stat: int(float(rows[i][col]))
            for i, stat in enumerate(CORE_STATS)
        }
    return out


def load_armor_by_name() -> dict[str, float]:
    path = CSV / "ArmorData.csv"
    out: dict[str, float] = {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Armor PIece") or row.get("Armor Piece") or ""
            if name:
                out[name] = float(row["ID"])
    return out


def load_talisman_by_name() -> dict[str, dict]:
    path = CSV / "TalismanData.csv"
    out: dict[str, dict] = {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Talisman") or ""
            if name:
                out[name] = {
                    "id": float(row["ID"]),
                    "group": row.get("accessoryGroup"),
                }
    return out


def load_roll_loads() -> list[tuple[int, float]]:
    path = CSV / "RollTypeData.csv"
    rows: list[tuple[int, float]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for parts in reader:
            if len(parts) < 2 or parts[0] == "" or parts[1] == "":
                continue
            try:
                rows.append((int(float(parts[0])), float(parts[1])))
            except ValueError:
                continue
    return rows


def xlookup_next_larger_last(
    lookup: float, pairs: list[tuple[int, float]], missing: str = "Not Possible"
) -> Any:
    # XLOOKUP(..., match_mode=1, search_mode=-1): exact or next larger,
    # last-to-first so duplicate loads resolve to the last endurance.
    candidates = [pair for pair in pairs if pair[1] >= lookup]
    if not candidates:
        return missing
    min_load = min(pair[1] for pair in candidates)
    matches = [pair for pair in candidates if pair[1] == min_load]
    return matches[-1][0]


class Planner:
    def __init__(self) -> None:
        self.ap = ApCalc()
        self.classes = load_starting_classes()
        self.armor_ids = load_armor_by_name()
        self.protectors = load_table("EquipParamProtector")
        self.talismans = load_talisman_by_name()
        self.accessories = load_table("EquipParamAccessory")
        self.status_effects = load_table("StatusEffectData", id_field="SpEffectId")
        self.roll_loads = load_roll_loads()
        low = self.ap.player.get(0.0, {})
        self.low_status_atk_pow_down = float(low.get("lowStatus_AtkPowDown") or 0.4)

    def calculate(self, inp: PlannerInputs) -> PlannerResult:
        class_stats = self.classes.get(inp.starting_class)
        if not class_stats:
            raise SystemExit(f"Unknown starting class: {inp.starting_class}")

        allocated = {}
        for stat in CORE_STATS:
            user = getattr(inp, stat)
            class_val = class_stats[stat]
            raw = class_val if user is None else max(float(user), class_val)
            allocated[stat] = clamp_stat(math.trunc(raw))
        alter = {stat: 0 for stat in CORE_STATS}
        final_stats = {
            stat: min(allocated[stat] + alter[stat], 99) for stat in CORE_STATS
        }
        level = sum(allocated.values()) - 79
        total_for_def = sum(final_stats.values())

        hp = int(math.trunc(vlookup_graph(self.ap.graph, 100, final_stats["vigor"])))
        fp = int(math.trunc(vlookup_graph(self.ap.graph, 101, final_stats["mind"])))
        stamina = int(
            math.trunc(vlookup_graph(self.ap.graph, 104, final_stats["endurance"]))
        )
        equip_load = vlookup_graph(self.ap.graph, 220, final_stats["endurance"])
        discovery = vlookup_graph(self.ap.graph, 140, final_stats["arcane"])

        graph102 = vlookup_graph(self.ap.graph, 102, total_for_def)
        defenses = {
            "physical": int(
                math.trunc(
                    graph102 + vlookup_graph(self.ap.graph, 130, final_stats["strength"])
                )
            ),
            "magic": int(
                math.trunc(
                    graph102
                    + vlookup_graph(self.ap.graph, 132, final_stats["intelligence"])
                )
            ),
            "fire": int(
                math.trunc(
                    graph102 + vlookup_graph(self.ap.graph, 133, final_stats["vigor"])
                )
            ),
            "lightning": int(math.trunc(graph102)),
            "holy": int(
                math.trunc(
                    graph102 + vlookup_graph(self.ap.graph, 135, final_stats["arcane"])
                )
            ),
        }
        resist_base = {
            "immunity": int(
                math.trunc(
                    vlookup_graph(self.ap.graph, 110, total_for_def)
                    + vlookup_graph(self.ap.graph, 120, final_stats["vigor"])
                )
            ),
            "robustness": int(
                math.trunc(
                    vlookup_graph(self.ap.graph, 112, total_for_def)
                    + vlookup_graph(self.ap.graph, 122, final_stats["endurance"])
                )
            ),
            "focus": int(
                math.trunc(
                    vlookup_graph(self.ap.graph, 114, total_for_def)
                    + vlookup_graph(self.ap.graph, 124, final_stats["mind"])
                )
            ),
            "vitality": int(
                math.trunc(
                    vlookup_graph(self.ap.graph, 116, total_for_def)
                    + vlookup_graph(self.ap.graph, 126, final_stats["arcane"])
                )
            ),
        }

        armor_rows = [
            self._protector(name)
            for name in (inp.head, inp.chest, inp.arms, inp.legs)
        ]
        absorb = {
            kind: math.prod(row[field] for row in armor_rows)
            for kind, field in ABSORB_FIELD.items()
        }
        armor_resist = {
            kind: sum(row[field] for row in armor_rows)
            for kind, field in RESIST_FIELD.items()
        }
        resists = {
            kind: int(resist_base[kind] + armor_resist[kind]) for kind in resist_base
        }
        poise_armor = sum(row["toughnessCorrectRate"] for row in armor_rows)
        talisman_names = (inp.talisman1, inp.talisman2, inp.talisman3, inp.talisman4)
        poise_mod = 0.75 if any(name == BULL_GOAT for name in talisman_names) else 1.0
        poise = (0.0 + poise_armor) / poise_mod

        armor_weight = sum(row["weight"] for row in armor_rows)
        talisman_weight = sum(self._talisman_weight(name) for name in talisman_names)

        slots_in = (inp.rh1, inp.rh2, inp.rh3, inp.lh1, inp.lh2, inp.lh3)
        weapons = [
            self._weapon_slot(name, slot, final_stats, inp)
            for name, slot in zip(SLOT_NAMES, slots_in)
        ]
        weapon_weight = sum(w.weight for w in weapons)
        equipped_weight = armor_weight + talisman_weight + weapon_weight

        max_load = equip_load  # K5 stubbed as 1
        if equipped_weight < max_load * 0.3:
            roll = "Light Load"
            left = max_load * 0.3 - equipped_weight
        elif equipped_weight < max_load * 0.7:
            roll = "Med. Load"
            left = max_load * 0.7 - equipped_weight
        elif equipped_weight < max_load:
            roll = "Heavy Load"
            left = max_load - equipped_weight
        else:
            roll = "Overloaded"
            left = max_load - equipped_weight

        load_mod = 1.0  # EffectData_Active BC6 stub
        end_for_mid = xlookup_next_larger_last(
            equipped_weight / load_mod / 0.7, self.roll_loads
        )
        end_for_light = xlookup_next_larger_last(
            equipped_weight / load_mod / 0.3, self.roll_loads
        )

        optimal_class, extra_levels = self._optimal_class(inp)

        return PlannerResult(
            starting_class=inp.starting_class,
            class_stats=class_stats,
            allocated=allocated,
            alter=alter,
            final_stats=final_stats,
            level=level,
            hp=hp,
            fp=fp,
            stamina=stamina,
            equip_load=equip_load,
            equipped_weight=equipped_weight,
            discovery=discovery,
            discovery_display=int(excel_round(100 * discovery, 0)),
            defenses=defenses,
            absorb=absorb,
            negation={k: 1.0 - v for k, v in absorb.items()},
            resists=resists,
            poise=poise,
            roll=roll,
            weight_left=left,
            weight_left_display=sheet_one_decimal(excel_rounddown(left, 1)),
            equip_load_display=(
                f"{sheet_one_decimal(equipped_weight)} / "
                f"{sheet_one_decimal(max_load)}"
            ),
            encumbrance_pct=f"{sheet_one_decimal((equipped_weight / max_load) * 100)}%",
            end_for_mid_roll=end_for_mid,
            end_for_light_roll=end_for_light,
            weapons=weapons,
            optimal_class=optimal_class,
            extra_levels=extra_levels,
        )

    def _protector(self, name: Optional[str]) -> dict[str, float]:
        empty = {
            "weight": 0.0,
            "toughnessCorrectRate": 0.0,
            **{field: 1.0 for field in ABSORB_FIELD.values()},
            **{field: 0.0 for field in RESIST_FIELD.values()},
        }
        if _blank(name):
            return empty
        pid = self.armor_ids.get(str(name))
        row = self.protectors.get(pid) if pid is not None else None
        if not row:
            return empty
        out = dict(empty)
        out["weight"] = float(row.get("weight") or 0)
        out["toughnessCorrectRate"] = float(row.get("toughnessCorrectRate") or 0)
        for field in ABSORB_FIELD.values():
            raw = row.get(field)
            out[field] = 1.0 if raw in (None, "") else float(raw)
        for field in RESIST_FIELD.values():
            out[field] = float(row.get(field) or 0)
        return out

    def _talisman_weight(self, name: Optional[str]) -> float:
        if _blank(name):
            return 0.0
        meta = self.talismans.get(str(name))
        if not meta:
            return 0.0
        row = self.accessories.get(meta["id"]) or {}
        return float(row.get("weight") or 0)

    def _overwrite(self, aec: dict, stat: str, dmg: str) -> float:
        # PlannerData headers use _ByThunder; AttackElementCorrectParam uses
        # _byThunder, so MATCH fails and Lightning overwrite is -1.
        aec_stat = AEC_STAT[stat]
        aec_elem = DAMAGE_AEC[dmg]
        if dmg == "lightning":
            name = f"overwrite{aec_stat}CorrectRate_By{aec_elem}"
        else:
            name = f"overwrite{aec_stat}CorrectRate_by{aec_elem}"
        raw = aec.get(name)
        if raw in (None, ""):
            return -1.0
        return float(raw)

    def _aec_flag(self, aec: dict, stat: str, dmg: str) -> bool:
        col = f"is{AEC_STAT[stat]}Correct_by{DAMAGE_AEC[dmg]}"
        return bool(aec.get(col))

    def _element_ap(
        self,
        dmg: str,
        equip: dict,
        reinf: dict,
        aec: dict,
        stats: dict[str, int],
        two_hand_str: bool,
        req_met: dict[str, bool],
        atk_rate: float,
    ) -> float:
        base = float(equip.get(WEAPON_BASE[dmg]) or 0) * float(
            reinf.get(REINFORCE_ATK[dmg]) or 1
        )
        if base == 0:
            return 0.0
        ctype = float(equip.get(WEAPON_CORRECT_TYPE[dmg]) or 0)
        penalty = any(
            (not req_met[stat]) and self._sat(aec, equip, stats, stat, dmg, two_hand_str) > 0
            for stat in STATS
        )
        if penalty:
            return (base + base * (-self.low_status_atk_pow_down)) * atk_rate
        scale = 0.0
        for stat in STATS:
            sat = self._sat(aec, equip, stats, stat, dmg, two_hand_str)
            rate = float(reinf.get(REINFORCE_CORRECT[stat]) or 1)
            correct = float(equip.get(WEAPON_CORRECT[stat]) or 0) * rate
            ow = self._overwrite(aec, stat, dmg)
            coeff = ow * rate if ow != -1 else correct
            scale += coeff * 0.01 * sat * 0.01
        return (base + base * scale) * atk_rate

    def _sat(
        self,
        aec: dict,
        equip: dict,
        stats: dict[str, int],
        stat: str,
        dmg: str,
        two_hand_str: bool,
    ) -> float:
        if not self._aec_flag(aec, stat, dmg):
            return 0.0
        ctype = float(equip.get(WEAPON_CORRECT_TYPE[dmg]) or 0)
        value = stats[stat]
        if stat == "strength" and two_hand_str:
            value = int(math.trunc(value * 1.5))
        return vlookup_graph(self.ap.graph, ctype, value)

    def _status_base(self, equip: dict, reinf: dict) -> dict[str, float]:
        id1 = float(equip.get("spEffectBehaviorId0") or -1)
        id2 = float(equip.get("spEffectBehaviorId1") or -1)
        off1 = float(reinf.get("spEffectId1") or 0)
        off2 = float(reinf.get("spEffectId2") or 0)
        out = {name: 0.0 for name in STATUS}
        for sid in (id1 + off1, id2 + off2):
            row = self.status_effects.get(sid)
            if not row:
                continue
            for name in STATUS:
                val = float(row.get(STATUS_FIELD[name]) or 0)
                out[name] = max(out[name], val)
        return out

    def _weapon_slot(
        self,
        slot_name: str,
        slot: WeaponSlotIn,
        final_stats: dict[str, int],
        inp: PlannerInputs,
    ) -> WeaponSlotOut:
        name = slot.weapon if slot.weapon else "Unarmed"
        wmeta = self.ap.weapons.get(name)
        if not wmeta:
            return WeaponSlotOut(
                slot=slot_name,
                weapon=name,
                weapon_class="Invalid",
                affinity=slot.affinity,
                upgrade=slot.upgrade,
                invalid=True,
                weight=0.0,
                ap={d: None for d in DAMAGE},
                ap_display={d: "-" for d in DAMAGE},
                total_ap=0.0,
                total_display="-",
                scaling_percent={s: 0.0 for s in STATS},
                scaling_letter={s: "-" for s in STATS},
                requirements={s: 0.0 for s in STATS},
                req_met={s: True for s in STATS},
                spell_buff=0.0,
                status={n: 0 for n in STATUS},
            )

        offset = 0.0
        affinity = slot.affinity or "Standard"
        if wmeta.get("isInfuse"):
            offset = self.ap.affinity_offset.get(affinity, 0.0)
        else:
            affinity = "Standard"
        weapon_id = float(wmeta["ID"]) + offset
        equip = self.ap.equip.get(weapon_id) or {}
        max_up = 0
        if wmeta.get("isReinforce"):
            max_up = 10 if wmeta.get("isUnique") else 25
        upgrade = min(max(int(slot.upgrade or 0), 0), max_up)
        reinf = self.ap.reinforce.get(
            float(equip.get("reinforceTypeId") or 0) + upgrade
        ) or {}
        aec = self.ap.aec.get(float(equip.get("attackElementCorrectId") or 0), {})

        two_hand_str = bool(inp.two_hand and wmeta.get("bothHandsAtkBonus"))
        scale_stats = {stat: final_stats[stat] for stat in STATS}
        req = {
            "strength": float(equip.get("properStrength") or 0),
            "dexterity": float(equip.get("properAgility") or 0),
            "intelligence": float(equip.get("properMagic") or 0),
            "faith": float(equip.get("properFaith") or 0),
            "arcane": float(equip.get("properLuck") or 0),
        }
        str_for_req = final_stats["strength"]
        if two_hand_str:
            str_for_req = int(math.trunc(str_for_req * 1.5))
        req_met = {}
        for stat in STATS:
            used = str_for_req if stat == "strength" else final_stats[stat]
            req_met[stat] = True if inp.ignore_require else used >= req[stat]

        atk_rate = 1.0  # DX11 EffectData_Active stub
        ap = {
            dmg: self._element_ap(
                dmg, equip, reinf, aec, scale_stats, two_hand_str, req_met, atk_rate
            )
            for dmg in DAMAGE
        }
        total = sum(ap.values())
        scaling_percent = {}
        for stat in STATS:
            correct = float(equip.get(WEAPON_CORRECT[stat]) or 0)
            rate = float(reinf.get(REINFORCE_CORRECT[stat]) or 1)
            scaling_percent[stat] = correct * rate
        letters = {
            stat: planner_letter(excel_round(scaling_percent[stat] * 0.01, 3))
            for stat in STATS
        }

        status_base = self._status_base(equip, reinf)
        arc_correct = scaling_percent["arcane"]
        status_penalty = not req_met["arcane"]
        status_out: dict[str, int] = {}
        status_graphs = {
            "poison": float(equip.get("correctType_Poison") or 0),
            "bleed": float(equip.get("correctType_Blood") or 0),
            "sleep": float(equip.get("correctType_Sleep") or 0),
            "madness": float(equip.get("correctType_Madness") or 0),
        }
        for status_name in STATUS:
            base = status_base[status_name]
            if status_name in ("scarlet_rot", "frost"):
                status_out[status_name] = int(math.trunc(base))
                continue
            sat = vlookup_graph(
                self.ap.graph, status_graphs[status_name], final_stats["arcane"]
            )
            if status_penalty:
                status_out[status_name] = int(
                    math.trunc(base + base * (-self.low_status_atk_pow_down))
                )
            else:
                status_out[status_name] = int(
                    math.trunc(base + base * (arc_correct * 0.01 * sat * 0.01))
                )

        is_catalyst = bool(equip.get("enableMagic") or equip.get("enableMiracle"))
        if is_catalyst:
            any_pen = any(not req_met[s] for s in STATS)
            if any_pen:
                spell_buff = 100 + 100 * (-self.low_status_atk_pow_down)
            else:
                sb_scale = 0.0
                for stat, dmg in (
                    ("strength", "magic"),
                    ("dexterity", "magic"),
                    ("intelligence", "magic"),
                    ("faith", "magic"),
                    ("arcane", "magic"),
                ):
                    sat = self._sat(aec, equip, scale_stats, stat, dmg, two_hand_str)
                    sb_scale += scaling_percent[stat] * 0.01 * sat * 0.01
                spell_buff = 100 + 100 * sb_scale
        else:
            spell_buff = 0.0

        wclass = str(wmeta.get("Weapon Class") or "")
        weight = 0.0
        if wclass not in ("Consumable", "Reusable"):
            weight = float(equip.get("weight") or 0)

        return WeaponSlotOut(
            slot=slot_name,
            weapon=name,
            weapon_class=wclass,
            affinity=affinity,
            upgrade=upgrade,
            invalid=False,
            weight=weight,
            ap=ap,
            ap_display={d: dash_round(ap[d], 2) for d in DAMAGE},
            total_ap=total,
            total_display=dash_round(total, 2),
            scaling_percent=scaling_percent,
            scaling_letter=letters,
            requirements=req,
            req_met=req_met,
            spell_buff=spell_buff,
            status=status_out,
        )

    def _optimal_class(self, inp: PlannerInputs) -> tuple[str, int]:
        # StartingClassData A11:A18 = MAX(Planner!Istat, class_base); blank I = 0.
        desired = {}
        for stat in CORE_STATS:
            user = getattr(inp, stat)
            desired[stat] = 0 if user is None else int(user)
        best_name = ""
        best_extra = None
        for name, bases in self.classes.items():
            extra = sum(max(desired[stat], bases[stat]) for stat in CORE_STATS) - 79
            if best_extra is None or extra < best_extra:
                best_extra = extra
                best_name = name
        return best_name, int(best_extra or 0)


def print_result(inp: PlannerInputs, r: PlannerResult) -> None:
    print(f"{r.starting_class}  Level {r.level}")
    print(
        "  "
        + "  ".join(
            f"{stat[:3].upper()} {r.final_stats[stat]}" for stat in CORE_STATS
        )
    )
    print(
        f"  HP {r.hp}  FP {r.fp}  Stamina {r.stamina}  "
        f"Equip {r.equip_load_display}  {r.encumbrance_pct}"
    )
    print(f"  {r.weight_left_display} | {r.roll}  Discovery {r.discovery_display}")
    print(
        f"  Def Phys {r.defenses['physical']}  Mag {r.defenses['magic']}  "
        f"Fire {r.defenses['fire']}  Ltng {r.defenses['lightning']}  "
        f"Holy {r.defenses['holy']}"
    )
    print(
        "  Neg "
        + "  ".join(
            f"{k[:4]} {excel_round(100 * r.negation[k], 3)}"
            for k in (
                "physical",
                "strike",
                "slash",
                "pierce",
                "magic",
                "fire",
                "lightning",
                "holy",
            )
        )
    )
    print(
        f"  Imm {r.resists['immunity']}  Rob {r.resists['robustness']}  "
        f"Foc {r.resists['focus']}  Vit {r.resists['vitality']}  "
        f"Poise {excel_round(1000 * r.poise, 0)}"
    )
    print(
        f"  End for Mid Roll {r.end_for_mid_roll}  "
        f"End for Light Roll {r.end_for_light_roll}"
    )
    print(f"  Optimal class {r.optimal_class}  extra {r.extra_levels}")
    print()
    for w in r.weapons:
        if w.invalid:
            print(f"  {w.slot}: Invalid")
            continue
        letters = " ".join(
            f"{w.scaling_letter[s]}" for s in STATS if w.scaling_letter[s] != "-"
        )
        print(
            f"  {w.slot} {w.weapon} {w.affinity} +{w.upgrade}  "
            f"AR {w.total_display}  {letters or '-'}"
        )
        parts = [
            f"{d[:4]} {w.ap_display[d]}"
            for d in DAMAGE
            if w.ap_display[d] != "-"
        ]
        if parts:
            print("    " + "  ".join(parts))


def slot_to_dict(w: WeaponSlotOut) -> dict[str, Any]:
    return {
        "slot": w.slot,
        "weapon": w.weapon,
        "weapon_class": w.weapon_class,
        "affinity": w.affinity,
        "upgrade": w.upgrade,
        "invalid": w.invalid,
        "weight": w.weight,
        "ap": w.ap,
        "ap_display": w.ap_display,
        "total_ap": w.total_ap,
        "total_display": w.total_display,
        "scaling_percent": w.scaling_percent,
        "scaling_letter": w.scaling_letter,
        "requirements": w.requirements,
        "req_met": w.req_met,
        "spell_buff": w.spell_buff,
        "status": w.status,
    }


def result_to_dict(inp: PlannerInputs, r: PlannerResult) -> dict[str, Any]:
    return {
        "starting_class": r.starting_class,
        "level": r.level,
        "class_stats": r.class_stats,
        "allocated": r.allocated,
        "alter": r.alter,
        "final_stats": r.final_stats,
        "hp": r.hp,
        "fp": r.fp,
        "stamina": r.stamina,
        "equip_load": r.equip_load,
        "equipped_weight": r.equipped_weight,
        "equip_load_display": r.equip_load_display,
        "encumbrance_pct": r.encumbrance_pct,
        "discovery": r.discovery,
        "discovery_display": r.discovery_display,
        "defenses": r.defenses,
        "absorb": r.absorb,
        "negation": r.negation,
        "resists": r.resists,
        "poise": r.poise,
        "roll": r.roll,
        "weight_left": r.weight_left,
        "weight_left_display": r.weight_left_display,
        "end_for_mid_roll": r.end_for_mid_roll,
        "end_for_light_roll": r.end_for_light_roll,
        "optimal_class": r.optimal_class,
        "extra_levels": r.extra_levels,
        "weapons": [slot_to_dict(w) for w in r.weapons],
        "two_hand": inp.two_hand,
        "ignore_require": inp.ignore_require,
    }


# Cached Planner.csv / PlannerData default: Vagabond, all Unarmed +0 Standard,
# empty armor/talismans. EffectData_Active is empty (multipliers 1, adds 0).
CACHED_DEFAULT = {
    "name": "cached Vagabond Unarmed +0 empty gear",
    "inp": {},
    "expect": {
        "starting_class": "Vagabond",
        "level": 9,
        "final_stats": {
            "vigor": 15,
            "mind": 10,
            "endurance": 11,
            "strength": 14,
            "dexterity": 13,
            "intelligence": 9,
            "faith": 9,
            "arcane": 7,
        },
        "hp": 522,
        "fp": 78,
        "stamina": 97,
        "equip_load": 49.76470588,
        "equipped_weight": 0.0,
        "equip_load_display": "0.0 / 49.8",
        "encumbrance_pct": "0.0%",
        "discovery_display": 107,
        "defenses": {
            "physical": 79,
            "magic": 93,
            "fire": 85,
            "lightning": 75,
            "holy": 89,
        },
        "negation": {
            "physical": 0.0,
            "strike": 0.0,
            "slash": 0.0,
            "pierce": 0.0,
            "magic": 0.0,
            "fire": 0.0,
            "lightning": 0.0,
            "holy": 0.0,
        },
        "resists": {
            "immunity": 92,
            "robustness": 92,
            "focus": 92,
            "vitality": 99,
        },
        "poise": 0.0,
        "roll": "Light Load",
        "weight_left_display": "14.9",
        "end_for_mid_roll": 8,
        "end_for_light_roll": 8,
        "optimal_class": "Wretch",
        "extra_levels": 1,
        "rh1": {
            "weapon": "Unarmed",
            "total_ap": 23.45785443,
            "total_display": 23.46,
            "ap": {"physical": 23.45785443},
            "letters": {"strength": "D", "dexterity": "D"},
        },
    },
}

SCREENSHOT_CASES = [CACHED_DEFAULT]


def check_case(r: PlannerResult, expect: dict) -> list[str]:
    errors: list[str] = []

    def eq(name: str, got: Any, expected: Any, places: int = 6) -> None:
        if expected is None:
            if got not in (None, 0, 0.0, "-"):
                errors.append(f"{name}: expected empty, got {got}")
            return
        if isinstance(expected, str) or isinstance(got, str):
            if str(got) != str(expected):
                errors.append(f"{name}: got {got!r}, expected {expected!r}")
            return
        if got is None:
            errors.append(f"{name}: got empty, expected {expected}")
            return
        if isinstance(expected, bool) or isinstance(got, bool):
            if bool(got) != bool(expected):
                errors.append(f"{name}: got {got}, expected {expected}")
            return
        if not almost(float(got), float(expected), places):
            errors.append(f"{name}: got {got}, expected {expected}")

    for key in (
        "starting_class",
        "level",
        "hp",
        "fp",
        "stamina",
        "discovery_display",
        "roll",
        "weight_left_display",
        "equip_load_display",
        "encumbrance_pct",
        "end_for_mid_roll",
        "end_for_light_roll",
        "optimal_class",
        "extra_levels",
    ):
        if key in expect:
            eq(key, getattr(r, key), expect[key], 0 if key != "equip_load" else 6)
    if "equip_load" in expect:
        eq("equip_load", r.equip_load, expect["equip_load"], 6)
    if "equipped_weight" in expect:
        eq("equipped_weight", r.equipped_weight, expect["equipped_weight"], 4)
    if "poise" in expect:
        eq("poise", r.poise, expect["poise"], 6)
    for stat, val in (expect.get("final_stats") or {}).items():
        eq(f"stat.{stat}", r.final_stats[stat], val, 0)
    for kind, val in (expect.get("defenses") or {}).items():
        eq(f"def.{kind}", r.defenses[kind], val, 0)
    for kind, val in (expect.get("negation") or {}).items():
        eq(f"neg.{kind}", r.negation[kind], val, 6)
    for kind, val in (expect.get("resists") or {}).items():
        eq(f"res.{kind}", r.resists[kind], val, 0)

    by_slot = {w.slot: w for w in r.weapons}
    for slot_key, parts in expect.items():
        if slot_key not in SLOT_NAMES and slot_key.lower() not in {
            s.lower() for s in SLOT_NAMES
        }:
            continue
        slot = slot_key.upper()
        w = by_slot.get(slot)
        if not w:
            errors.append(f"missing {slot}")
            continue
        if "weapon" in parts:
            eq(f"{slot}.weapon", w.weapon, parts["weapon"])
        if "total_ap" in parts:
            eq(f"{slot}.ar", w.total_ap, parts["total_ap"], 6)
        if "total_display" in parts:
            eq(f"{slot}.ar_display", w.total_display, parts["total_display"], 2)
        for dmg, val in (parts.get("ap") or {}).items():
            eq(f"{slot}.{dmg}", w.ap.get(dmg), val, 6)
        for stat, letter in (parts.get("letters") or {}).items():
            eq(f"{slot}.letter.{stat}", w.scaling_letter[stat], letter)
    return errors


def make_inputs(overrides: Optional[dict[str, Any]] = None) -> PlannerInputs:
    kwargs: dict[str, Any] = {}
    if overrides:
        kwargs.update(overrides)
    for key in SLOT_NAMES:
        low = key.lower()
        if low in kwargs and isinstance(kwargs[low], dict):
            kwargs[low] = WeaponSlotIn(**kwargs[low])
        elif key in kwargs and isinstance(kwargs[key], dict):
            kwargs[key.lower()] = WeaponSlotIn(**kwargs.pop(key))
    allowed = set(PlannerInputs.__dataclass_fields__)
    return PlannerInputs(**{k: v for k, v in kwargs.items() if k in allowed})


def check_all(calc: Planner) -> int:
    failed = 0
    for case in SCREENSHOT_CASES:
        result = calc.calculate(make_inputs(case.get("inp")))
        errors = check_case(result, case["expect"])
        if errors:
            failed += 1
            print(f"FAIL  {case['name']}")
            for err in errors:
                print(f"  - {err}")
        else:
            rh1 = result.weapons[0]
            print(
                f"PASS  {case['name']}  lv {result.level}  "
                f"HP {result.hp}  AR {rh1.total_display}"
            )
    if failed:
        print(f"\nCHECK FAILED: {failed}/{len(SCREENSHOT_CASES)} cases")
        return 1
    print(f"\nCHECK OK — {len(SCREENSHOT_CASES)} spreadsheet fixtures match.")
    return 0


def parse_slot(name: str, args: argparse.Namespace) -> WeaponSlotIn:
    return WeaponSlotIn(
        weapon=getattr(args, name) or "Unarmed",
        affinity=getattr(args, f"{name}_affinity") or "Standard",
        upgrade=int(getattr(args, f"{name}_upgrade") or 0),
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Elden Ring Build Planner port")
    p.add_argument("--class", dest="starting_class", default="Vagabond")
    for stat in CORE_STATS:
        p.add_argument(f"--{stat}", type=int, default=None)
    for slot in SLOT_NAMES:
        low = slot.lower()
        p.add_argument(f"--{low}", default="Unarmed")
        p.add_argument(f"--{low}-affinity", default="Standard")
        p.add_argument(f"--{low}-upgrade", type=int, default=0)
    p.add_argument("--two-hand", action="store_true")
    p.add_argument("--ignore-require", action="store_true")
    p.add_argument("--head", default="Empty")
    p.add_argument("--chest", default="Empty")
    p.add_argument("--arms", default="Empty")
    p.add_argument("--legs", default="Empty")
    p.add_argument("--talisman1", default="Empty")
    p.add_argument("--talisman2", default="Empty")
    p.add_argument("--talisman3", default="Empty")
    p.add_argument("--talisman4", default="Empty")
    p.add_argument("--json", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument("--export-oracle", metavar="PATH")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    calc = Planner()
    if args.check:
        return check_all(calc)
    if args.export_oracle:
        path = Path(args.export_oracle)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for case in SCREENSHOT_CASES:
                inp = make_inputs(case.get("inp"))
                rec = result_to_dict(inp, calc.calculate(inp))
                rec["name"] = case["name"]
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"Wrote {len(SCREENSHOT_CASES)} oracle records to {path}")
        return 0
    inp = PlannerInputs(
        starting_class=args.starting_class,
        vigor=args.vigor,
        mind=args.mind,
        endurance=args.endurance,
        strength=args.strength,
        dexterity=args.dexterity,
        intelligence=args.intelligence,
        faith=args.faith,
        arcane=args.arcane,
        rh1=parse_slot("rh1", args),
        rh2=parse_slot("rh2", args),
        rh3=parse_slot("rh3", args),
        lh1=parse_slot("lh1", args),
        lh2=parse_slot("lh2", args),
        lh3=parse_slot("lh3", args),
        two_hand=args.two_hand,
        ignore_require=args.ignore_require,
        head=args.head,
        chest=args.chest,
        arms=args.arms,
        legs=args.legs,
        talisman1=args.talisman1,
        talisman2=args.talisman2,
        talisman3=args.talisman3,
        talisman4=args.talisman4,
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
