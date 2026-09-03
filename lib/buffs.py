"""What a buff multiplies, per kind of hit, and whether two of them stack.

`data/BuffMult.csv` is 21 items across eight hit kinds — All, Skill, ChargedSkill, Crit, Jump,
ChargedR2, Successive, Physical — with separate PvE and PvP figures. `data/BuffSlot.csv` is the
rule for combining them.

Both matter, and the second one more than it looks. **Not every buff multiplies.** Golden Vow
as a spell, as an ash and as a tool all occupy the `Aura` slot: the last one applied wins, and
a node that multiplied all three would produce a figure for a stack the game does not allow.
`Passive` (talismans) and `Tear` multiply; `Aura`, `Unique` and `Body` overwrite.

**The condition an item needs falls out of the table rather than being guessed.** An item whose
figure is above 1 on *one* hit kind is conditional on the hit — Shard of Alexander is 1.15 on a
`Skill` and 1.0 on everything else, so naming the hit kind is the whole assertion. An item
whose figure is above 1 on *every* hit kind is conditional on a state the table cannot see —
Lord of Blood's Exultation is 1.2 whenever its bleed aura is up — and those have to be asserted
by the caller, because nothing here knows whether a bleed has procced.
"""

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MULT_CSV = os.path.join(ROOT, "data", "BuffMult.csv")
SLOT_CSV = os.path.join(ROOT, "data", "BuffSlot.csv")

HIT_KINDS = (
    "All", "Skill", "ChargedSkill", "Crit", "Jump", "ChargedR2", "Successive", "Physical",
)


def number(value, default=1.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def slot_rules():
    """`{slot: (rule, note)}` — Multiply, Overwrite or Identity."""
    with open(SLOT_CSV, newline="", encoding="utf-8") as handle:
        return {
            row["Slot"]: (row["Rule"], row["Notes"])
            for row in csv.DictReader(handle)
            if row.get("Slot")
        }


def table():
    """`{name: {kind, slot, note, pve: {hit: mult}, pvp: {hit: mult}}}`."""
    out = {}
    with open(MULT_CSV, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("Name") or "").strip()
            if not name or name == "none":
                continue
            entry = out.setdefault(name, {
                "kind": row.get("Kind") or "",
                "slot": row.get("Slot") or "",
                "note": (row.get("Notes") or "").strip(),
                "pve": {}, "pvp": {},
            })
            hit = (row.get("HitKind") or "").strip()
            entry["pve"][hit] = number(row.get("MultPve"))
            entry["pvp"][hit] = number(row.get("MultPvp"))
    return out


def applies_on(entry, pvp=False):
    """The hit kinds this buff is worth more than 1.0 on."""
    figures = entry["pvp" if pvp else "pve"]
    return sorted(hit for hit, value in figures.items() if value > 1.0)


def state_conditional(entry, pvp=False):
    """True when the figure is above 1 on every hit kind.

    Then the condition is not the kind of hit but a state — a bleed proc, full HP, a successive
    hit tier — which nothing here can observe, so the caller has to assert it.
    """
    hits = applies_on(entry, pvp)
    return len(hits) == len(HIT_KINDS)


def multiplier(entry, hit_kind, pvp=False):
    figures = entry["pvp" if pvp else "pve"]
    return figures.get(hit_kind, 1.0)


def stack(factors, rules):
    """Combine per slot: multiply where the rule says so, keep the largest where it does not.

    Returns `(total, applied, shadowed)`. A shadowed factor is one the game would have
    overwritten — two Golden Vows are not 1.15 x 1.15.
    """
    by_slot = {}
    for factor in factors:
        by_slot.setdefault(factor["slot"], []).append(factor)

    total = 1.0
    applied, shadowed = [], []
    for slot, group in sorted(by_slot.items()):
        rule = rules.get(slot, ("Multiply", ""))[0]
        if rule == "Multiply":
            for factor in group:
                total *= factor["multiplier"]
                applied.append(factor)
        elif rule == "Identity":
            shadowed.extend(group)
        else:
            group = sorted(group, key=lambda f: (-f["multiplier"], f["item"]))
            total *= group[0]["multiplier"]
            applied.append(group[0])
            shadowed.extend(group[1:])
    return round(total, 9), applied, shadowed


# The other axis a buff can be conditional on. `BuffMult` is about *how you hit* — a skill, a
# critical, a jump — and says nothing about *what the damage is*: Graven-Mass multiplies
# sorceries, Fire Scorpion Charm multiplies fire, and neither is a hit kind. Eleven talismans
# state one of these in their description, in one shape, and the figure is the extraction's own.
import csv as _csv
import re as _re

EFFECT_CSV = os.path.join(
    ROOT, "oracle", "extracted", "Build-Planner-v1.19.1", "csv", "EffectData.csv"
)
TALISMAN_CSV = os.path.join(
    ROOT, "oracle", "extracted", "Build-Planner-v1.19.1", "csv", "TalismanData.csv"
)

SOURCE = _re.compile(
    r"^Increases (?P<source>[a-z ]+?) damage by (?P<rate>\d+(?:\.\d+)?)x"
    r"(?:\s*\((?P<paren>[^)]*)\))?(?P<rest>.*)$"
)
SOURCE_PVP = _re.compile(r"^(?P<rate>\d+(?:\.\d+)?)x in PvP$")
# "stamina damage" is not damage to a health bar and does not belong in a damage multiplier.
NOT_DAMAGE = {"stamina"}


def _talisman_names():
    names = set()
    with open(TALISMAN_CSV, newline="", encoding="utf-8") as handle:
        for row in _csv.reader(handle):
            if row and row[0] and row[0] != "Talisman" and not row[0].startswith("//"):
                names.add(row[0])
    return names


def source_table():
    """`{name: {source, multiplier, pvp_multiplier, cost, note}}` for the school and element
    talismans — the ones whose condition is what the damage *is* rather than how it was dealt.

    Kept apart from `BuffMult` because it is a different axis and a different provenance: these
    figures are read out of `EffectData`'s own description column, and `source` is the word that
    description uses. Anything that does not match the shape exactly is left out; a miss costs
    an unquantified talisman, a wrong parse would cost a wrong number.
    """
    talismans = _talisman_names()
    with open(EFFECT_CSV, newline="", encoding="utf-8") as handle:
        rows = list(_csv.reader(handle))
    header = rows[1]
    out = {}
    for row in rows[2:]:
        record = dict(zip(header, row))
        name = (record.get("Name") or "").strip()
        if not name or name not in talismans or name in out:
            continue
        text = (record.get("Effects") or "").strip()
        match = SOURCE.match(text)
        if not match:
            continue
        source = match.group("source").strip()
        if source in NOT_DAMAGE:
            continue
        paren = (match.group("paren") or "").strip()
        pvp_match = SOURCE_PVP.match(paren)
        rest = (match.group("rest") or "").strip(" ,")
        out[name] = {
            "source": source,
            "multiplier": float(match.group("rate")),
            "pvp_multiplier": float(pvp_match.group("rate")) if pvp_match else None,
            # What it costs. The Scorpion Charms buy their 1.12 with worse negation, and an
            # answer that quotes the bonus without the cost is half an answer.
            "cost": rest.lstrip("but ").strip() if rest.startswith("but") else "",
            "note": paren if not pvp_match else "",
            "source_text": text,
        }
    return out
