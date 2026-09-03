"""Check the collection against the spreadsheet the whole thing came from.

Three of the Build Planner's own saved builds, exported to PDF from the workbook and read off
by hand. Every `sheet` figure below is the spreadsheet's; every `got` figure is a node's.

This is a different check from `vouch test`. The fixtures pin the collection against the
*extraction* — the CSVs in `oracle/` — and they cannot catch a mistake in how the collection
uses them. These figures come from upstream of the extraction, which is why this found the one
bug 122 real questions did not: `planner.py` floors every stat at the starting class's, and
four nodes were defaulting that class to Wretch.

Run it after touching anything that reaches `planner.py` or `ap_calc.py`:

    python3 scripts/check_spreadsheet.py

The builds are the sheet's three defaults — PvP Faith RL150, PvE Strength RL150, PvP
Intelligence RL150 — all from a Confessor. Two of their figures are *not* comparable and are
handled here rather than pretended away: sheets 1 and 3 wear HP and equip-load talismans, which
nothing in this collection applies, and sheet 2's dexterity is 17 because of Millicent's
Prosthesis rather than because it was levelled there.
"""
import json, subprocess, sys

ROOT = "/home/mozartdiniz/Dev/elden-ring-vouch"

def call(node, payload):
    out = subprocess.run(["vouch", "-C", ROOT, "call", node, "--input", json.dumps(payload)],
                         capture_output=True, text=True)
    try:
        return json.loads(out.stdout)
    except Exception:
        return {"_error": out.stdout[:200] or out.stderr[:200]}

rows = []
def check(label, got, want, tol=0.005):
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        ok = abs(got - want) <= tol
    else:
        ok = got == want
    rows.append((ok, label, got, want))

BUILDS = {
    "sheet1 PvP-Faith": dict(starting_class="Confessor", vigor=60, mind=13, endurance=25,
                             strength=15, dexterity=24, intelligence=9, faith=79, arcane=9),
    "sheet2 PvE-Strength": dict(starting_class="Confessor", vigor=60, mind=13, endurance=27,
                                strength=79, dexterity=12, intelligence=9, faith=27, arcane=9),
    "sheet3 PvP-Intelligence": dict(starting_class="Confessor", vigor=60, mind=25, endurance=24,
                                    strength=12, dexterity=13, intelligence=80, faith=14, arcane=9),
}

# --- rune level, from character-build
for name, level in (("sheet1 PvP-Faith", 155), ("sheet2 PvE-Strength", 157),
                    ("sheet3 PvP-Intelligence", 158)):
    r = call("character-build", BUILDS[name])
    check(f"{name}: rune level", r.get("level"), level)

# --- vitals. Sheets 1 and 3 wear HP and stamina talismans, which nothing here applies, so the
# figures to compare are the sheet's with the multipliers undone.
r = call("character-build", BUILDS["sheet2 PvE-Strength"])
check("sheet2: HP at vigor 60", r.get("hp"), 1900)
check("sheet2: FP at mind 13", r.get("fp"), 88)
check("sheet2: stamina at endurance 27", r.get("stamina"), 125)
check("sheet2: equip load at endurance 27", round(r.get("equip_load", 0), 1), 74.1)

r = call("character-build", BUILDS["sheet3 PvP-Intelligence"])
check("sheet3: FP at mind 25", r.get("fp"), 147)
check("sheet3: HP before the two medallions", r.get("hp"), 1900)

# --- weapons
r = call("attack-power", dict(weapon="Treespear", affinity="Standard", upgrade=25,
                              **{k: v for k, v in BUILDS["sheet1 PvP-Faith"].items()
                                 if k in ("strength", "dexterity", "intelligence", "faith", "arcane")}))
check("sheet1: Treespear +25 physical", round(r.get("attack", {}).get("physical", 0), 2), 387.07)
check("sheet1: Treespear +25 holy", round(r.get("attack", {}).get("holy", 0), 2), 292.32)
check("sheet1: Treespear +25 total", round(r.get("total_ar", 0), 2), 679.39)

# Sheet 2's dexterity is 17 on the sheet: 12 levelled plus 5 from Millicent's Prosthesis. The
# collection does not apply talisman stats, so the 17 is passed in by hand — which is the
# deliberate gap showing up in a real build.
r = call("attack-power", dict(weapon="Broadsword", affinity="Heavy", upgrade=25,
                              strength=79, dexterity=17, intelligence=9, faith=27, arcane=9))
check("sheet2: Heavy Broadsword +25 (dex 17, Millicent's applied by hand)",
      round(r.get("total_ar", 0), 2), 572.31)

r = call("attack-power", dict(weapon="Lusat's Glintstone Staff", affinity="Standard", upgrade=10,
                              strength=12, dexterity=13, intelligence=80, faith=14, arcane=9))
check("sheet3: Lusat's +10 attack rating", round(r.get("total_ar", 0), 2), 243.14)
r = call("attack-power", dict(weapon="Azur's Glintstone Staff", affinity="Standard", upgrade=10,
                              strength=12, dexterity=13, intelligence=80, faith=14, arcane=9))
check("sheet3: Azur's +10 attack rating", round(r.get("total_ar", 0), 2), 212.97)
r = call("attack-power", dict(weapon="Frenzied Flame Seal", affinity="Standard", upgrade=10,
                              strength=12, dexterity=13, intelligence=80, faith=14, arcane=9))
check("sheet3: Frenzied Flame Seal +10 attack rating", round(r.get("total_ar", 0), 2), 107.75)
check("sheet3: Frenzied Flame Seal madness", r.get("status", {}).get("madness"), 55.0)

# --- spell buffs, through spell-power
for label, catalyst, build, want in (
    ("sheet1: Erdtree Seal +10 spell buff", "Erdtree Seal", "sheet1 PvP-Faith", 349.65),
    ("sheet3: Lusat's +10 spell buff", "Lusat's Glintstone Staff", "sheet3 PvP-Intelligence", 413.50),
    ("sheet3: Azur's +10 spell buff", "Azur's Glintstone Staff", "sheet3 PvP-Intelligence", 362.20),
    ("sheet3: Frenzied Flame Seal +10 spell buff", "Frenzied Flame Seal", "sheet3 PvP-Intelligence", 175.91),
    ("sheet2: Frenzied Flame Seal +10 spell buff", "Frenzied Flame Seal", "sheet2 PvE-Strength", 222.87),
):
    b = BUILDS[build]
    spell = "Comet" if "Glintstone" in catalyst else "Black Flame"
    stats = {k: v for k, v in b.items()
             if k in ("strength", "dexterity", "intelligence", "faith", "arcane")}
    # Sheet 2's dexterity is 17 on the sheet: 12 levelled plus Millicent's +5, and the
    # Frenzied Flame Seal is one of the two catalysts whose spell buff takes dexterity.
    if build == "sheet2 PvE-Strength":
        stats["dexterity"] = 17
    r = call("spell-power", dict(spell=spell, catalyst=catalyst, upgrade=10,
                                 starting_class="Confessor", **stats))
    # Excel rounds half away from zero for display; the sheet shows two places.
    import decimal
    got = float(decimal.Decimal(str(r.get("spell_buff", 0))).quantize(
        decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_UP))
    check(label, got, want)

print(f"{sum(1 for ok, *_ in rows if ok)} of {len(rows)} match\n")
for ok, label, got, want in rows:
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<62} got {got!r:<12} sheet {want!r}")
