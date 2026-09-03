"""Stress `vouch attest` without a model, because it does not need one.

Attestation is the last line: everything upstream is enforced by schemas and contracts, and
this is the one step where a model writes figures of its own accord. It is also the least
exercised part of the collection — building nineteen nodes and answering 122 questions never
ran it once.

No model is involved in the check, so it can be stressed for free. Three things are measured:

1. **The behaviour matrix.** Correct prose, a transposed digit, an invented total, a figure
   quoted from the question, a truncated display figure.
2. **A mutation sweep.** Take a paragraph every numeral of which came from a node, mutate each
   numeral four ways, and count how many mutations are caught.
3. **Collision against ledger size.** A numeral attests if *some* call in the session returned
   it. The larger the session, the more small integers collide with something — which is what
   turns "set VOUCH_SESSION per conversation" from hygiene into correctness.

    python3 scripts/stress_attest.py
"""

import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION = "stress-attest"


def vouch(*args, session=SESSION):
    env = dict(os.environ, VOUCH_SESSION=session)
    return subprocess.run(["vouch", *args], capture_output=True, text=True, cwd=ROOT, env=env)


def call(node, payload, session=SESSION):
    return vouch("call", node, "--input", json.dumps(payload), session=session)


def attest(text, session=SESSION, extra=()):
    return vouch("attest", "--text", text, *extra, session=session)


def build_ledger(session, calls):
    path = os.path.join(ROOT, ".vouch", "ledger", f"session-{session}.jsonl")
    if os.path.exists(path):
        os.remove(path)
    for node, payload in calls:
        call(node, payload, session=session)
    return path


# --------------------------------------------------------------- 1. behaviour matrix

def matrix():
    build_ledger(SESSION, [
        ("attack-power", {"weapon": "Greatsword", "affinity": "Heavy", "upgrade": 25,
                          "strength": 66, "dexterity": 14, "intelligence": 9, "faith": 15,
                          "arcane": 7, "two_hand": True}),
        ("character-build", {"starting_class": "Vagabond", "vigor": 60, "mind": 10,
                             "endurance": 35, "strength": 66, "dexterity": 14,
                             "intelligence": 9, "faith": 15, "arcane": 7,
                             "target_level": 150}),
    ])
    cases = [
        (0, "every figure came from a node",
         "Two-handed the Heavy Greatsword +25 reaches 853.18 attack rating, and the spread "
         "lands at rune level 137 with 1900 HP.", ()),
        (1, "one digit transposed",
         "Two-handed the Heavy Greatsword +25 reaches 853.19 attack rating.", ()),
        (1, "a total the model computed itself",
         "The Greatsword hits 853.18 and the seal 349.65, so together 1202.83.", ()),
        (0, "the figure as the game displays it, truncated",
         "The Greatsword shows 853 attack rating in the menu.", ()),
        (0, "rounded to one decimal", "The Greatsword reaches 853.2.", ()),
        (1, "rounded to the nearest ten", "The Greatsword reaches 850.", ()),
        (1, "the adjacent integer", "The Greatsword reaches 854.", ()),
    ]
    print("1. behaviour matrix\n")
    bad = 0
    for want, label, text, extra in cases:
        got = attest(text, extra=extra).returncode
        ok = got == want
        bad += not ok
        print(f"   {'ok  ' if ok else 'FAIL'} exit {got} (want {want})  {label}")
    return bad


# ------------------------------------------------------------------ 2. mutation sweep

PROSE = ("Faith on the Erdtree Seal does not bend until 80. At faith 70 Black Flame is 765.18 "
         "and the Blasphemous Blade reads 736.59; at faith 80 the spell is 862.91.")


def mutations():
    session = SESSION + "-mutate"
    build_ledger(session, [
        ("spell-power", {"spell": "Black Flame", "catalyst": "Erdtree Seal", "upgrade": 10,
                         "starting_class": "Confessor", "strength": 22, "dexterity": 15,
                         "intelligence": 9, "faith": 70, "arcane": 9}),
        ("spell-power", {"spell": "Black Flame", "catalyst": "Erdtree Seal", "upgrade": 10,
                         "starting_class": "Confessor", "strength": 22, "dexterity": 15,
                         "intelligence": 9, "faith": 80, "arcane": 9}),
        ("attack-power", {"weapon": "Blasphemous Blade", "affinity": "Standard", "upgrade": 10,
                          "strength": 22, "dexterity": 15, "intelligence": 9, "faith": 70,
                          "arcane": 9}),
    ])
    print("\n2. mutation sweep\n")
    base = attest(PROSE, session=session).returncode
    print(f"   baseline: {'PASS' if base == 0 else 'FAIL — fix the paragraph first'}")
    if base != 0:
        return 1

    caught = total = 0
    missed = []
    for m in re.finditer(r"\d+(?:\.\d+)?", PROSE):
        original = m.group(0)
        if "." in original:
            whole, frac = original.split(".")
            muts = [f"{whole}.{int(frac) + 1:0{len(frac)}d}", f"{int(whole) + 1}.{frac}",
                    f"{whole}.{frac}9", str(round(float(original) * 1.001, 3))]
        else:
            muts = [str(int(original) + 1), str(int(original) - 1),
                    str(int(original) + 10), str(int(original) * 2)]
        for mutant in muts:
            text = PROSE[:m.start()] + mutant + PROSE[m.end():]
            total += 1
            if attest(text, session=session).returncode != 0:
                caught += 1
            else:
                missed.append(f"{original} → {mutant}")
    print(f"   {caught} of {total} mutations caught ({100 * caught // total}%)")
    for miss in missed:
        print(f"   MISSED  {miss}  — the mutant value is itself in the ledger")
    return 0


# ------------------------------------------------- 3. collision against ledger size

def collisions():
    print("\n3. how many integers 1..99 collide with something in the ledger\n")
    print(f"   {'ledger':<40} {'entries':>7} {'scalars':>8}  {'collide':>8}")
    for path in sorted(glob.glob(os.path.join(ROOT, ".vouch", "ledger", "*.jsonl")),
                       key=os.path.getsize):
        values, entries = set(), 0
        for line in open(path):
            entries += 1
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            for value in (entry.get("scalars") or {}).values():
                if isinstance(value, (int, float)):
                    values.add(float(value))
        hits = sum(1 for i in range(1, 100) if float(i) in values)
        print(f"   {os.path.basename(path):<40} {entries:>7} {len(values):>8}  {hits:>6}/99")
    print("\n   A numeral attests if some call in the session returned it, so a session that")
    print("   spans a day accounts for nearly every small integer. Set VOUCH_SESSION per")
    print("   conversation: a smaller ledger is a stricter check.")


if __name__ == "__main__":
    failures = matrix() + mutations()
    collisions()
    sys.exit(1 if failures else 0)
