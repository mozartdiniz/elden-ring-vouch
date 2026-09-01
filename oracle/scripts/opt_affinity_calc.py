#!/usr/bin/env python3
"""Port of Build Planner Optimal Affinity Calc / OptimalAffinityCalcData.

For one weapon + stats, compute AP and absorbed damage for every affinity.
Tables come from extracted/Build-Planner-v1.19.1/csv/.
"""

from __future__ import annotations

import argparse
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
    WEAPON_BASE,
    WEAPON_CORRECT,
    WEAPON_CORRECT_TYPE,
    ApCalc,
    almost,
    clamp_stat,
    vlookup_graph,
)

AFFINITIES = (
    "Standard",
    "Heavy",
    "Keen",
    "Quality",
    "Fire",
    "Flame Art",
    "Lightning",
    "Sacred",
    "Magic",
    "Cold",
    "Poison",
    "Blood",
    "Occult",
)
PHYS_TYPES = ("Standard", "Strike", "Slash", "Pierce")
SORT_KEYS = (
    "Damage",
    "Physical AP",
    "Magic AP",
    "Fire AP",
    "Lightning AP",
    "Holy AP",
    "Total AP",
)
# OptimalAffinityCalcData B30:B37 / B38:B45 when Avg PvE Def/Neg is on
AVG_PVE_DEF = 109.542
AVG_PVE_NEG = {
    "physical": 1.697,
    "strike": -1.932,
    "slash": 1.253,
    "pierce": 3.613,
    "magic": 3.936,
    "fire": -1.192,
    "lightning": 0.501,
    "holy": 3.912,
}
DEFAULT_DEF = {
    "physical": 79.0,
    "strike": 79.0,
    "slash": 79.0,
    "pierce": 79.0,
    "magic": 93.0,
    "fire": 85.0,
    "lightning": 75.0,
    "holy": 89.0,
}
# Shared target from the Optimal Affinity Calc screenshots (Planner-linked Def/Neg).
SCREENSHOT_DEFENSE = {
    "physical": 162.0,
    "strike": 162.0,
    "slash": 162.0,
    "pierce": 162.0,
    "magic": 147.0,
    "fire": 189.0,
    "lightning": 129.0,
    "holy": 147.0,
}
SCREENSHOT_NEGATION = {
    "physical": 29.885,
    "strike": 24.446,
    "slash": 28.772,
    "pierce": 27.357,
    "magic": 24.199,
    "fire": 27.843,
    "lightning": 23.825,
    "holy": 26.014,
}


def _shot(**kwargs: Any) -> dict[str, Any]:
    inp = {
        "upgrade": 25,
        "intelligence": 9,
        "faith": 14,
        "arcane": 9,
        "two_hand": False,
        "attack_mv": 100.0,
        "sort_by": "Damage",
        "avg_pve": False,
        "defense": dict(SCREENSHOT_DEFENSE),
        "negation": dict(SCREENSHOT_NEGATION),
    }
    inp.update(kwargs)
    return inp

# Cached Optimal Affinity Calc view: Unarmed +0, starting stats, Strike MV 100
SCREENSHOT_INPUTS = {
    "weapon_class": "Fist",
    "weapon": "Unarmed",
    "upgrade": 0,
    "strength": 14,
    "dexterity": 13,
    "intelligence": 9,
    "faith": 9,
    "arcane": 7,
    "two_hand": False,
    "attack_mv": 100.0,
    "phys_atk_type": "Strike",
    "sort_by": "Damage",
    "avg_pve": False,
}
SCREENSHOT_CASES: list[dict[str, Any]] = [
    {
        "name": "Unarmed +0 Strike (cached sheet defaults)",
        "inp": {},
        "expect": {
            "order": ["Standard"],
            "rows": {
                "Standard": {
                    "damage": 2.617505281,
                    "total_ap": 23.45785443,
                    "physical": 23.45785443,
                    "magic": None,
                    "fire": None,
                    "lightning": None,
                    "holy": None,
                },
            },
            "missing": [
                "Heavy",
                "Keen",
                "Quality",
                "Fire",
                "Flame Art",
                "Lightning",
                "Sacred",
                "Magic",
                "Cold",
                "Poison",
                "Blood",
                "Occult",
            ],
        },
    },
    {
        "name": "Great Katana +25 Slash (STR 20 DEX 70)",
        "inp": _shot(
            weapon_class="Great Katana",
            weapon="Great Katana",
            strength=20,
            dexterity=70,
            phys_atk_type="Slash",
        ),
        "expect": {
            "places": 2,
            "order": [
                "Lightning", "Keen", "Cold", "Sacred", "Standard", "Quality",
                "Flame Art", "Magic", "Poison", "Blood", "Fire", "Heavy", "Occult",
            ],
            "rows": {
                "Lightning": {"damage": 419.949, "total_ap": 791.428, "physical": 395.895, "lightning": 395.533},
                "Keen": {"damage": 394.932, "total_ap": 687.347, "physical": 687.347},
                "Cold": {"damage": 350.186, "total_ap": 705.924, "physical": 465.749, "magic": 240.175},
                "Sacred": {"damage": 349.710, "total_ap": 696.688, "physical": 355.000, "holy": 341.688},
                "Standard": {"damage": 346.307, "total_ap": 619.572, "physical": 619.572},
                "Quality": {"damage": 339.389, "total_ap": 609.801, "physical": 609.801},
                "Flame Art": {"damage": 330.628, "total_ap": 696.688, "physical": 355.000, "fire": 341.688},
                "Magic": {"damage": 326.894, "total_ap": 654.062, "physical": 334.166, "magic": 319.896},
                "Poison": {"damage": 318.865, "total_ap": 580.589, "physical": 580.589},
                "Blood": {"damage": 318.865, "total_ap": 580.589, "physical": 580.589},
                "Fire": {"damage": 282.553, "total_ap": 625.596, "physical": 321.622, "fire": 303.974},
                "Heavy": {"damage": 244.321, "total_ap": 470.865, "physical": 470.865},
                "Occult": {"damage": 237.587, "total_ap": 460.600, "physical": 460.600},
            },
        },
    },
    {
        "name": "Black Steel Twinblade +25 2h (STR 80 DEX 20)",
        "inp": _shot(
            weapon_class="Twinblade",
            weapon="Black Steel Twinblade",
            strength=80,
            dexterity=20,
            two_hand=True,
            phys_atk_type="Standard",
        ),
        "expect": {
            "places": 2,
            "order": [
                "Heavy", "Fire", "Quality", "Sacred", "Standard", "Keen",
                "Lightning", "Flame Art", "Cold", "Magic", "Poison", "Blood", "Occult",
            ],
            "rows": {
                "Heavy": {"damage": 324.829, "total_ap": 665.082, "physical": 579.944, "holy": 85.138},
                "Fire": {"damage": 295.730, "total_ap": 698.816, "physical": 324.192, "fire": 315.597, "holy": 59.027},
                "Quality": {"damage": 286.532, "total_ap": 601.895, "physical": 527.626, "holy": 74.269},
                "Sacred": {"damage": 268.797, "total_ap": 577.349, "physical": 258.510, "holy": 318.840},
                "Standard": {"damage": 234.316, "total_ap": 530.562, "physical": 441.802, "holy": 88.761},
                "Keen": {"damage": 224.442, "total_ap": 513.027, "physical": 427.889, "holy": 85.138},
                "Lightning": {"damage": 222.016, "total_ap": 547.858, "physical": 247.031, "lightning": 237.789, "holy": 63.038},
                "Flame Art": {"damage": 219.481, "total_ap": 600.150, "physical": 258.510, "fire": 265.189, "holy": 76.452},
                "Cold": {"damage": 217.323, "total_ap": 558.885, "physical": 311.665, "magic": 182.008, "holy": 65.212},
                "Magic": {"damage": 214.128, "total_ap": 555.273, "physical": 236.629, "magic": 246.186, "holy": 72.458},
                "Poison": {"damage": 208.600, "total_ap": 483.706, "physical": 405.429, "holy": 78.278},
                "Blood": {"damage": 208.600, "total_ap": 483.706, "physical": 405.429, "holy": 78.278},
                "Occult": {"damage": 152.615, "total_ap": 388.045, "physical": 312.181, "holy": 75.864},
            },
        },
    },
    {
        "name": "Flail +25 Strike (STR 20 DEX 70)",
        "inp": _shot(
            weapon_class="Flail",
            weapon="Flail",
            strength=20,
            dexterity=70,
            phys_atk_type="Strike",
        ),
        "expect": {
            "places": 2,
            "order": [
                "Lightning", "Keen", "Quality", "Standard", "Cold", "Poison",
                "Blood", "Sacred", "Magic", "Flame Art", "Heavy", "Occult", "Fire",
            ],
            "rows": {
                "Lightning": {"damage": 317.895, "total_ap": 620.134, "physical": 307.277, "lightning": 312.857},
                "Keen": {"damage": 316.484, "total_ap": 551.028, "physical": 551.028},
                "Quality": {"damage": 279.176, "total_ap": 499.273, "physical": 499.273},
                "Standard": {"damage": 272.563, "total_ap": 489.942, "physical": 489.942},
                "Cold": {"damage": 251.178, "total_ap": 536.656, "physical": 362.041, "magic": 174.614},
                "Poison": {"damage": 248.705, "total_ap": 455.816, "physical": 455.816},
                "Blood": {"damage": 248.705, "total_ap": 455.816, "physical": 455.816},
                "Sacred": {"damage": 242.201, "total_ap": 526.832, "physical": 252.214, "holy": 274.618},
                "Magic": {"damage": 230.524, "total_ap": 506.594, "physical": 256.173, "magic": 250.421},
                "Flame Art": {"damage": 220.538, "total_ap": 526.832, "physical": 252.214, "fire": 274.618},
                "Heavy": {"damage": 195.310, "total_ap": 372.196, "physical": 372.196},
                "Occult": {"damage": 184.987, "total_ap": 355.980, "physical": 355.980},
                "Fire": {"damage": 182.170, "total_ap": 471.502, "physical": 234.596, "fire": 236.907},
            },
        },
    },
    {
        "name": "Warhawk's Talon +25 Standard (STR 60 DEX 20)",
        "inp": _shot(
            weapon_class="Straight Sword",
            weapon="Warhawk's Talon",
            strength=60,
            dexterity=20,
            phys_atk_type="Standard",
        ),
        "expect": {
            "places": 2,
            "order": [
                "Heavy", "Fire", "Quality", "Sacred", "Standard", "Lightning",
                "Magic", "Flame Art", "Cold", "Poison", "Blood", "Keen", "Occult",
            ],
            "rows": {
                "Heavy": {"damage": 228.997, "total_ap": 453.005, "physical": 453.005},
                "Fire": {"damage": 220.972, "total_ap": 539.136, "physical": 265.237, "fire": 273.899},
                "Quality": {"damage": 208.666, "total_ap": 420.899, "physical": 420.899},
                "Sacred": {"damage": 195.439, "total_ap": 471.609, "physical": 230.057, "holy": 241.552},
                "Standard": {"damage": 189.712, "total_ap": 387.405, "physical": 387.405},
                "Lightning": {"damage": 182.117, "total_ap": 436.541, "physical": 216.182, "lightning": 220.359},
                "Magic": {"damage": 179.713, "total_ap": 445.682, "physical": 219.485, "magic": 226.196},
                "Flame Art": {"damage": 175.139, "total_ap": 471.609, "physical": 230.057, "fire": 241.552},
                "Cold": {"damage": 175.034, "total_ap": 440.532, "physical": 283.724, "magic": 156.808},
                "Poison": {"damage": 170.583, "total_ap": 354.194, "physical": 354.194},
                "Blood": {"damage": 170.583, "total_ap": 354.194, "physical": 354.194},
                "Keen": {"damage": 167.788, "total_ap": 349.642, "physical": 349.642},
                "Occult": {"damage": 139.240, "total_ap": 305.610, "physical": 305.610},
            },
        },
    },
    {
        "name": "Iron Greatsword +25 2h (STR 80 DEX 20)",
        "inp": _shot(
            weapon_class="Greatsword",
            weapon="Iron Greatsword",
            strength=80,
            dexterity=20,
            two_hand=True,
            phys_atk_type="Standard",
        ),
        "expect": {
            "places": 2,
            "order": [
                "Heavy", "Standard", "Fire", "Poison", "Blood", "Cold", "Sacred",
                "Quality", "Flame Art", "Magic", "Lightning", "Keen", "Occult",
            ],
            "rows": {
                "Heavy": {"damage": 452.832, "total_ap": 776.296, "physical": 776.296},
                "Standard": {"damage": 427.498, "total_ap": 741.305, "physical": 741.305},
                "Fire": {"damage": 412.899, "total_ap": 833.230, "physical": 423.925, "fire": 409.306},
                "Poison": {"damage": 399.176, "total_ap": 701.920, "physical": 701.920},
                "Blood": {"damage": 399.176, "total_ap": 701.920, "physical": 701.920},
                "Cold": {"damage": 390.652, "total_ap": 775.305, "physical": 561.260, "magic": 214.045},
                "Sacred": {"damage": 371.805, "total_ap": 740.058, "physical": 392.233, "holy": 347.825},
                "Quality": {"damage": 362.827, "total_ap": 650.808, "physical": 650.808},
                "Flame Art": {"damage": 353.406, "total_ap": 740.058, "physical": 392.233, "fire": 347.825},
                "Magic": {"damage": 348.357, "total_ap": 692.315, "physical": 363.280, "magic": 329.035},
                "Lightning": {"damage": 333.243, "total_ap": 661.097, "physical": 343.187, "lightning": 317.911},
                "Keen": {"damage": 291.683, "total_ap": 548.053, "physical": 548.053},
                "Occult": {"damage": 262.537, "total_ap": 504.513, "physical": 504.513},
            },
        },
    },
    {
        "name": "Warhawk's Talon +25 Standard (STR 20 DEX 60)",
        "inp": _shot(
            weapon_class="Straight Sword",
            weapon="Warhawk's Talon",
            strength=20,
            dexterity=60,
            phys_atk_type="Standard",
        ),
        "expect": {
            "places": 2,
            "order": [
                "Lightning", "Keen", "Standard", "Quality", "Sacred", "Cold",
                "Poison", "Blood", "Magic", "Flame Art", "Heavy", "Occult", "Fire",
            ],
            "rows": {
                "Lightning": {"damage": 262.447, "total_ap": 551.822, "physical": 271.478, "lightning": 280.343},
                "Keen": {"damage": 246.602, "total_ap": 480.248, "physical": 480.248},
                "Standard": {"damage": 222.876, "total_ap": 443.416, "physical": 443.416},
                "Quality": {"damage": 208.666, "total_ap": 420.899, "physical": 420.899},
                "Sacred": {"damage": 206.432, "total_ap": 487.906, "physical": 246.354, "holy": 241.552},
                "Cold": {"damage": 205.107, "total_ap": 485.431, "physical": 328.623, "magic": 156.808},
                "Poison": {"damage": 202.818, "total_ap": 411.523, "physical": 411.523},
                "Blood": {"damage": 202.818, "total_ap": 411.523, "physical": 411.523},
                "Magic": {"damage": 187.531, "total_ap": 457.452, "physical": 231.256, "magic": 226.196},
                "Flame Art": {"damage": 186.132, "total_ap": 487.906, "physical": 246.354, "fire": 241.552},
                "Heavy": {"damage": 156.465, "total_ap": 331.722, "physical": 331.722},
                "Occult": {"damage": 150.437, "total_ap": 322.458, "physical": 322.458},
                "Fire": {"damage": 145.792, "total_ap": 426.505, "physical": 211.212, "fire": 215.293},
            },
        },
    },
]


@dataclass
class OptInputs:
    weapon_class: str
    weapon: str
    upgrade: int
    strength: int
    dexterity: int
    intelligence: int
    faith: int
    arcane: int
    two_hand: bool = False
    attack_mv: float = 100.0
    phys_atk_type: Optional[str] = None
    sort_by: str = "Damage"
    avg_pve: bool = False
    defense: dict[str, float] = field(default_factory=dict)
    negation: dict[str, float] = field(default_factory=dict)
    dmg_mult: dict[str, float] = field(default_factory=dict)
    counter_hit: bool = False
    leo_counter: bool = False
    frost_debuff: bool = False
    rain: bool = False


@dataclass
class AffinityRow:
    affinity: str
    damage: Optional[float]
    total_ap: Optional[float]
    physical: Optional[float]
    magic: Optional[float]
    fire: Optional[float]
    lightning: Optional[float]
    holy: Optional[float]
    split: Optional[str]


@dataclass
class OptResult:
    weapon: str
    requirements: dict[str, Any]
    rows: list[AffinityRow]
    phys_atk_type: str = "Standard"


def defense_absorb(attack: float, defense: float) -> float:
    """Elden Ring PvE defense curve used by OptimalAffinityCalcData CI:CP."""
    x = attack
    d = defense
    if d > x * 8:
        return 0.1 * x
    if d > x:
        return (19.2 / 49 * (x / d - 0.125) ** 2 + 0.1) * x
    if d > x * 0.4:
        return (-0.4 / 3 * (x / d - 2.5) ** 2 + 0.7) * x
    if d > x * 0.125:
        return (-0.8 / 121 * (x / d - 8) ** 2 + 0.9) * x
    return x * 0.9


class OptAffinityCalc:
    def __init__(self) -> None:
        self.ap = ApCalc()

    def _stats(self, inp: OptInputs, wmeta: dict) -> dict[str, int]:
        # B9: TRUNC(clamp(TRUNC(STR),1,99) * 1.5) when 2h and bothHandsAtkBonus.
        # Unlike AP Calc, this is not re-clamped to 99 after the 1.5x.
        strength = min(max(int(math.trunc(inp.strength)), 1), 99)
        if inp.two_hand and wmeta.get("bothHandsAtkBonus"):
            strength = int(math.trunc(strength * 1.5))
        return {
            "strength": strength,
            "dexterity": clamp_stat(inp.dexterity),
            "intelligence": clamp_stat(inp.intelligence),
            "faith": clamp_stat(inp.faith),
            "arcane": clamp_stat(inp.arcane),
        }

    def _cut_rate(self, inp: OptInputs, kind: str) -> float:
        if inp.avg_pve:
            neg = AVG_PVE_NEG[kind]
        else:
            neg = float(inp.negation.get(kind, 0.0))
        rate = 1 - neg * 0.01
        if inp.frost_debuff:
            rate *= 1.200000048
        if kind == "pierce":
            if inp.leo_counter:
                rate *= 1.495000005
            elif inp.counter_hit:
                rate *= 1.299999952
        if kind == "fire" and inp.rain:
            rate *= 0.899999976
        if kind == "lightning" and inp.rain:
            rate *= 1.100000024
        return rate

    def _defense(self, inp: OptInputs, kind: str) -> float:
        if inp.avg_pve:
            return AVG_PVE_DEF
        return float(inp.defense.get(kind, DEFAULT_DEF[kind]))

    def _mult(self, inp: OptInputs, kind: str) -> float:
        return float(inp.dmg_mult.get(kind, 1.0))

    def _overwrite(self, aec: dict, stat: str, dmg: str) -> float:
        # Match OptimalAffinityCalcData headers exactly. Thunder uses
        # overwrite…_ByThunder (capital B); AttackElementCorrectParam uses
        # _byThunder, so MATCH fails and the sheet treats Lightning overwrite as -1.
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

    def _element_ap(
        self,
        dmg: str,
        equip: dict,
        reinf: dict,
        aec: dict,
        stats: dict[str, int],
    ) -> float:
        base = float(equip.get(WEAPON_BASE[dmg]) or 0) * float(
            reinf.get(REINFORCE_ATK[dmg]) or 1
        )
        if base == 0:
            return 0.0
        ctype = float(equip.get(WEAPON_CORRECT_TYPE[dmg]) or 0)
        aec_elem = DAMAGE_AEC[dmg]
        scale = 0.0
        for stat in STATS:
            aec_stat = AEC_STAT[stat]
            flag = aec.get(f"is{aec_stat}Correct_by{aec_elem}")
            if not flag:
                continue
            sat = vlookup_graph(self.ap.graph, ctype, stats[stat])
            rate = float(reinf.get(REINFORCE_CORRECT[stat]) or 1)
            correct = float(equip.get(WEAPON_CORRECT[stat]) or 0) * rate
            ow = self._overwrite(aec, stat, dmg)
            coeff = ow * rate if ow != -1 else correct
            scale += coeff * 0.01 * sat * 0.01
        return base + base * scale

    def _hit_damage(self, inp: OptInputs, ap: float, kind: str) -> float:
        mv = inp.attack_mv * 0.01
        incoming = ap * mv
        absorbed = defense_absorb(incoming, self._defense(inp, kind))
        return self._cut_rate(inp, kind) * absorbed * self._mult(inp, kind)

    def _max_upgrade(self, wmeta: dict) -> int:
        if not wmeta.get("isReinforce"):
            return 0
        return 10 if wmeta.get("isUnique") else 25

    def _affinity_row(
        self, inp: OptInputs, wmeta: dict, affinity: str, stats: dict[str, int]
    ) -> AffinityRow:
        offset = self.ap.affinity_offset.get(affinity, 0.0)
        weapon_id = float(wmeta["ID"]) + offset
        equip = self.ap.equip.get(weapon_id)
        if not equip:
            return AffinityRow(affinity, None, None, None, None, None, None, None, None)
        upgrade = min(max(int(inp.upgrade), 0), self._max_upgrade(wmeta))
        reinf = self.ap.reinforce.get(
            float(equip.get("reinforceTypeId") or 0) + upgrade
        ) or {}
        aec = self.ap.aec.get(float(equip.get("attackElementCorrectId") or 0), {})
        aps = {d: self._element_ap(d, equip, reinf, aec, stats) for d in DAMAGE}
        phys_type = inp.phys_atk_type or wmeta.get("defaultPhysType") or "Standard"
        if phys_type not in PHYS_TYPES:
            phys_type = "Standard"
        dmg = {
            "physical": 0.0,
            "strike": 0.0,
            "slash": 0.0,
            "pierce": 0.0,
            "magic": self._hit_damage(inp, aps["magic"], "magic"),
            "fire": self._hit_damage(inp, aps["fire"], "fire"),
            "lightning": self._hit_damage(inp, aps["lightning"], "lightning"),
            "holy": self._hit_damage(inp, aps["holy"], "holy"),
        }
        phys_kind = {
            "Standard": "physical",
            "Strike": "strike",
            "Slash": "slash",
            "Pierce": "pierce",
        }[phys_type]
        dmg[phys_kind] = self._hit_damage(inp, aps["physical"], phys_kind)
        total_dmg = sum(dmg.values())
        total_ap = sum(aps.values())

        def pos(v: float) -> Optional[float]:
            return v if v > 0 else None

        return AffinityRow(
            affinity=affinity,
            damage=total_dmg,
            total_ap=total_ap,
            physical=pos(aps["physical"]),
            magic=pos(aps["magic"]),
            fire=pos(aps["fire"]),
            lightning=pos(aps["lightning"]),
            holy=pos(aps["holy"]),
            split="/".join(str(math.trunc(aps[d])) for d in DAMAGE),
        )

    def _sort_key(self, row: AffinityRow, inp: OptInputs, wmeta: dict, idx: int):
        if not wmeta.get("isInfuse"):
            return (0, idx)
        metric = {
            "Damage": row.damage,
            "Physical AP": row.physical,
            "Magic AP": row.magic,
            "Fire AP": row.fire,
            "Lightning AP": row.lightning,
            "Holy AP": row.holy,
            "Total AP": row.total_ap,
        }.get(inp.sort_by, row.damage)
        if metric is None:
            metric = float("-inf")
        return (1, -float(metric), idx)

    def calculate(self, inp: OptInputs) -> OptResult:
        wmeta = self.ap.weapons.get(inp.weapon)
        if not wmeta:
            raise SystemExit(f"Unknown weapon: {inp.weapon}")
        if (
            inp.weapon_class
            and inp.weapon != "Unarmed"
            and wmeta.get("Weapon Class") != inp.weapon_class
        ):
            raise SystemExit(
                f"Weapon {inp.weapon!r} is class {wmeta.get('Weapon Class')!r}, "
                f"not {inp.weapon_class!r}"
            )
        stats = self._stats(inp, wmeta)
        phys_type = inp.phys_atk_type or wmeta.get("defaultPhysType") or "Standard"
        if phys_type not in PHYS_TYPES:
            phys_type = "Standard"
        resolved = OptInputs(**{**inp.__dict__, "phys_atk_type": phys_type})
        rows = [
            self._affinity_row(resolved, wmeta, affinity, stats) for affinity in AFFINITIES
        ]
        rows.sort(key=lambda r: self._sort_key(r, resolved, wmeta, AFFINITIES.index(r.affinity)))
        standard = next((r for r in rows if r.affinity == "Standard"), None)
        req = {}
        if standard and wmeta:
            equip = self.ap.equip.get(float(wmeta["ID"]))
            if equip:
                req = {
                    "strength": int(equip.get("properStrength") or 0) or None,
                    "dexterity": int(equip.get("properAgility") or 0) or None,
                    "intelligence": int(equip.get("properMagic") or 0) or None,
                    "faith": int(equip.get("properFaith") or 0) or None,
                    "arcane": int(equip.get("properLuck") or 0) or None,
                }
        return OptResult(
            weapon=inp.weapon,
            requirements=req,
            rows=rows,
            phys_atk_type=phys_type,
        )


def result_to_dict(inp: OptInputs, r: OptResult) -> dict[str, Any]:
    def pack(row: AffinityRow) -> dict[str, Any]:
        return {
            "affinity": row.affinity,
            "damage": row.damage,
            "total_ap": row.total_ap,
            "physical": row.physical,
            "magic": row.magic,
            "fire": row.fire,
            "lightning": row.lightning,
            "holy": row.holy,
            "split": row.split,
        }

    return {
        "inputs": {
            "weapon_class": inp.weapon_class,
            "weapon": inp.weapon,
            "upgrade": inp.upgrade,
            "strength": inp.strength,
            "dexterity": inp.dexterity,
            "intelligence": inp.intelligence,
            "faith": inp.faith,
            "arcane": inp.arcane,
            "two_hand": inp.two_hand,
            "attack_mv": inp.attack_mv,
            "phys_atk_type": r.phys_atk_type,
            "sort_by": inp.sort_by,
            "avg_pve": inp.avg_pve,
        },
        "requirements": r.requirements,
        "rows": [pack(row) for row in r.rows],
    }


def print_result(inp: OptInputs, r: OptResult) -> None:
    print(f"{r.weapon}  +{inp.upgrade}  MV {inp.attack_mv:g}  {r.phys_atk_type}")
    print(
        f"  STR {inp.strength} DEX {inp.dexterity} INT {inp.intelligence} "
        f"FTH {inp.faith} ARC {inp.arcane}  2h={inp.two_hand}  sort={inp.sort_by}"
    )
    print(
        f"  {'Affinity':<14}{'Damage':>14}{'Total AP':>14}{'Phys':>12}"
        f"{'Magic':>12}{'Fire':>12}{'Ltng':>12}{'Holy':>12}"
    )
    for row in r.rows:
        def fmt(v: Optional[float], places: int = 4) -> str:
            if v is None:
                return "-"
            return f"{v:.{places}f}"

        print(
            f"  {row.affinity:<14}{fmt(row.damage, 8):>14}{fmt(row.total_ap, 8):>14}"
            f"{fmt(row.physical):>12}{fmt(row.magic):>12}{fmt(row.fire):>12}"
            f"{fmt(row.lightning):>12}{fmt(row.holy):>12}"
        )


def check_case(r: OptResult, expect: dict) -> list[str]:
    errors: list[str] = []
    by_name = {row.affinity: row for row in r.rows}

    places = int(expect.get("places", 4))

    def eq(name: str, got: Any, expected: Any, places: int = places) -> None:
        if expected is None:
            if got not in (None, 0):
                errors.append(f"{name}: expected empty/-, got {got}")
            return
        if got is None:
            errors.append(f"{name}: got empty, expected {expected}")
            return
        if not almost(float(got), float(expected), places):
            errors.append(f"{name}: got {got}, expected {expected}")

    if "order" in expect:
        present = [row.affinity for row in r.rows if row.total_ap is not None]
        if present[: len(expect["order"])] != expect["order"]:
            errors.append(f"order: got {present}, expected {expect['order']}")
    rows_expect = dict(expect.get("rows") or {})
    if expect.get("standard"):
        rows_expect.setdefault("Standard", expect["standard"])
    for aff, parts in rows_expect.items():
        row = by_name.get(aff)
        if not row:
            errors.append(f"missing {aff}")
            continue
        for key, val in parts.items():
            eq(f"{aff}.{key}", getattr(row, key), val)
    for aff in expect.get("missing", []):
        row = by_name.get(aff)
        if row and row.total_ap not in (None, 0):
            errors.append(f"{aff}: expected empty, got AP {row.total_ap}")
    return errors


def make_inputs(overrides: Optional[dict[str, Any]] = None) -> OptInputs:
    kwargs = dict(SCREENSHOT_INPUTS)
    if overrides:
        kwargs.update(overrides)
    allowed = set(OptInputs.__dataclass_fields__)
    return OptInputs(**{k: v for k, v in kwargs.items() if k in allowed})


def check_all(calc: OptAffinityCalc) -> int:
    failed = 0
    for case in SCREENSHOT_CASES:
        inp = make_inputs(case["inp"])
        result = calc.calculate(inp)
        errors = check_case(result, case["expect"])
        if errors:
            failed += 1
            print(f"FAIL  {case['name']}")
            for err in errors:
                print(f"  - {err}")
        else:
            std = next(row for row in result.rows if row.affinity == "Standard")
            print(f"PASS  {case['name']}  dmg {std.damage:.4f}  AR {std.total_ap:.4f}")
    if failed:
        print(f"\nCHECK FAILED: {failed}/{len(SCREENSHOT_CASES)} cases")
        return 1
    print(f"\nCHECK OK — {len(SCREENSHOT_CASES)} spreadsheet fixtures match.")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Elden Ring Optimal Affinity Calc port")
    p.add_argument("--weapon-class", default=SCREENSHOT_INPUTS["weapon_class"])
    p.add_argument("--weapon", default=SCREENSHOT_INPUTS["weapon"])
    p.add_argument("--upgrade", type=int, default=SCREENSHOT_INPUTS["upgrade"])
    p.add_argument("--strength", type=int, default=SCREENSHOT_INPUTS["strength"])
    p.add_argument("--dexterity", type=int, default=SCREENSHOT_INPUTS["dexterity"])
    p.add_argument("--intelligence", type=int, default=SCREENSHOT_INPUTS["intelligence"])
    p.add_argument("--faith", type=int, default=SCREENSHOT_INPUTS["faith"])
    p.add_argument("--arcane", type=int, default=SCREENSHOT_INPUTS["arcane"])
    p.add_argument("--two-hand", action="store_true")
    p.add_argument("--attack-mv", type=float, default=SCREENSHOT_INPUTS["attack_mv"])
    p.add_argument("--phys-atk-type", default=None, choices=PHYS_TYPES)
    p.add_argument("--sort-by", default=SCREENSHOT_INPUTS["sort_by"], choices=SORT_KEYS)
    p.add_argument("--avg-pve", action="store_true")
    p.add_argument("--counter-hit", action="store_true")
    p.add_argument("--leo-counter", action="store_true")
    p.add_argument("--frost-debuff", action="store_true")
    p.add_argument("--rain", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument("--export-oracle", metavar="PATH")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    calc = OptAffinityCalc()
    if args.check:
        return check_all(calc)
    if args.export_oracle:
        path = Path(args.export_oracle)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for case in SCREENSHOT_CASES:
                inp = make_inputs(case["inp"])
                rec = result_to_dict(inp, calc.calculate(inp))
                rec["name"] = case["name"]
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"Wrote {len(SCREENSHOT_CASES)} oracle records to {path}")
        return 0
    inp = OptInputs(
        weapon_class=args.weapon_class,
        weapon=args.weapon,
        upgrade=args.upgrade,
        strength=args.strength,
        dexterity=args.dexterity,
        intelligence=args.intelligence,
        faith=args.faith,
        arcane=args.arcane,
        two_hand=args.two_hand,
        attack_mv=args.attack_mv,
        phys_atk_type=args.phys_atk_type,
        sort_by=args.sort_by,
        avg_pve=args.avg_pve,
        counter_hit=args.counter_hit,
        leo_counter=args.leo_counter,
        frost_debuff=args.frost_debuff,
        rain=args.rain,
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
