#!/usr/bin/env python3
"""Generate `nodes/attack-power/cases.toml` from the oracle's own screenshot fixtures.

`ap_calc.SCREENSHOT_CASES` is eight inputs whose expected outputs were read off the Build
Planner spreadsheet by hand. They are the only figures in this repository that trace back to
the game rather than to code, so they are the right thing for `vouch test` to pin — and
generating the file means the expectations are the oracle's, not ones written from the same
head as the node.

Run it again after re-vendoring `oracle/`; the diff is then the spreadsheet's, not a rewrite.

    python3 scripts/generate_cases.py
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

import oracle  # noqa: E402

sys.path.insert(0, oracle.SCRIPTS)
import ap_calc  # noqa: E402

NODE = os.path.join(ROOT, "nodes", "attack-power")

DAMAGE = ("physical", "magic", "fire", "lightning", "holy")

HEADER = """\
# Node fixtures (§7.1) — GENERATED, do not edit.
#
# Every expectation below comes from `ap_calc.SCREENSHOT_CASES`: inputs whose outputs were
# read off the Build Planner spreadsheet by hand. They are the only numbers here that trace
# back to the game rather than to code. Regenerate with:
#
#     python3 scripts/generate_cases.py
#
# The first block of cases pins the maths. The hand-written block at the end pins the things
# the oracle has no opinion about, because they are what this collection adds: bounds,
# affinity substitution, and the refusals.
"""

HAND_WRITTEN = '''
# --- what the oracle does not check -------------------------------------------------

# `ap_calc.py` computes this happily and returns 180.39 — an attack rating for an upgrade
# level Moonveil does not have, and lower than the 643 it really reaches at its +10 cap, so it
# does not even look wrong. With the cap declared it is a refusal that says what to do.
[[case]]
name = "an upgrade past the weapon's cap is refused when the cap is declared"
input = { weapon = "Moonveil", affinity = "Standard", upgrade = 25, max_upgrade = 10, strength = 20, dexterity = 20, intelligence = 60, faith = 10, arcane = 10 }
expect_code = 11

# And a caller who declares a generous cap to get past that refusal is caught by the
# postcondition, which uses the cap the node looked up itself. No value reaches stdout.
[[case]]
name = "a wrong declared cap is caught after the fact instead"
input = { weapon = "Moonveil", affinity = "Standard", upgrade = 25, max_upgrade = 25, strength = 20, dexterity = 20, intelligence = 60, faith = 10, arcane = 10 }
expect_code = 13

[[case]]
name = "an affinity on a non-infusable weapon is applied as Standard, and says so"
input = { weapon = "Moonveil", affinity = "Heavy", upgrade = 10, strength = 20, dexterity = 20, intelligence = 60, faith = 10, arcane = 10 }
expect = { "result.affinity_applied" = "Standard", "result.affinity_ignored" = true, "result.infusable" = false }

[[case]]
name = "an unknown affinity is refused with the thirteen names"
input = { weapon = "Longsword", affinity = "Frostbite", upgrade = 25, strength = 20, dexterity = 20, intelligence = 10, faith = 10, arcane = 10 }
expect_code = 11

[[case]]
name = "a stat above 99 is refused rather than computed"
input = { weapon = "Longsword", affinity = "Standard", upgrade = 25, strength = 150, dexterity = 20, intelligence = 10, faith = 10, arcane = 10 }
expect_code = 11

[[case]]
name = "a weapon that cannot be reinforced reports a cap of zero"
input = { weapon = "Meteorite Staff", affinity = "Standard", upgrade = 0, strength = 20, dexterity = 20, intelligence = 60, faith = 10, arcane = 10 }
expect = { "result.max_upgrade" = 0, "result.infusable" = false }
'''


def toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return json.dumps(v)
    return repr(v)


def main():
    calc = ap_calc.ApCalc()
    lines = [HEADER]

    for case in ap_calc.SCREENSHOT_CASES:
        inputs = case["inp"]
        sheet = case["expect"]
        r = calc.calculate(ap_calc.Inputs(**inputs))

        # Ask the node itself, so the fixture pins the shape the node returns rather than the
        # oracle's internal one. Any disagreement between them shows up here, at generation
        # time, rather than as a mystery later.
        node_input = {k: v for k, v in inputs.items() if k != "weapon_class"}
        proc = subprocess.run(
            [sys.executable, os.path.join(NODE, "ap.py")],
            input=json.dumps(node_input),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            sys.exit(f"node failed on {case['name']}: {proc.stderr}")
        produced = json.loads(proc.stdout)

        if abs(produced["total_ar"] - r.total_ar) > 1e-9:
            sys.exit(
                f"node and oracle disagree on {case['name']}: "
                f"{produced['total_ar']} vs {r.total_ar}"
            )

        pairs = " ".join(f"{k} = {toml_value(v)}," for k, v in node_input.items()).rstrip(",")

        # Expectations come from the sheet's own recorded values wherever it has one. Only
        # `total_ar` at full precision is taken from the run, because the screenshot recorded
        # it to seven places; `ar_round` below is the figure a player actually reads.
        expect = {"result.total_ar_rounded": sheet["ar_round"]}
        for stat, letter in sheet.get("letters", {}).items():
            expect[f"result.scaling.{stat}.letter"] = letter
        for stat, pct in sheet.get("pct", {}).items():
            expect[f"result.scaling.{stat}.percent"] = pct
        # The sheet's `total` mixes damage types and status buildup in one dict; they land in
        # different fields on the node, so route each by name rather than by position.
        for key, value in sheet.get("total", {}).items():
            field = "attack" if key in DAMAGE else "status"
            expect[f"result.{field}.{key}"] = value
        if "gb" in sheet:
            expect["result.guard_boost"] = sheet["gb"]
        for damage, value in sheet.get("guard", {}).items():
            expect[f"result.guard_negation.{damage}"] = float(value)
        expect_pairs = ", ".join(f'"{k}" = {toml_value(v)}' for k, v in expect.items())

        lines.append(
            f"\n[[case]]\nname = {json.dumps(case['name'])}\n"
            f"input = {{ {pairs} }}\n"
            f"expect = {{ {expect_pairs} }}\n"
        )

    lines.append(HAND_WRITTEN)
    path = os.path.join(NODE, "cases.toml")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("".join(lines))
    print(f"wrote {path}: {len(ap_calc.SCREENSHOT_CASES)} generated cases", file=sys.stderr)


if __name__ == "__main__":
    main()
