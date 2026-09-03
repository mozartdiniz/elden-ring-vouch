#!/usr/bin/env python3
"""Run the 122 questions in VALIDATION.md through the live app, concurrently.

The recorded answers are prose with tables, so this is not a diff. Four things are
mechanical, and they are the four worth watching:

    routed        the loop reached an answer at all, rather than giving up
    no defect     no node violated its own contract
    attested      every numeral traced to a call in that question's own ledger
    same nodes    it reached for the nodes the recorded entry names

The figures are printed side by side — the numbers in the recorded entry against the numbers
in the fresh answer — because drift there is the thing a human should look at and no
comparison this script could make would be trustworthy.

Each question gets its own VOUCH_SESSION, which is what makes running them at once safe: a
shared ledger would have every question attesting against every other question's numbers.
That is the whole finding of scripts/stress_attest.py, exercised for real.

    ./run_battery.py --pattern 1 --concurrency 4
    ./run_battery.py --only 1.1,1.2,2.3
    ./run_battery.py --limit 6
    ./run_battery.py --resume runs/battery-20260903-1412.jsonl

Costs roughly three model calls per question. Nothing over --limit 20 runs without --yes.
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "web"))

import engine  # noqa: E402
from llm import LLMError, ask_model  # noqa: E402

VALIDATION = os.path.join(ROOT, "VALIDATION.md")
RUNS = os.path.join(ROOT, "runs")

QUESTION = re.compile(r"^- \[([ x~!])\] \*\*(\d+\.\d+)\*\* (.+)$")
ENTRY = re.compile(r"^### (\d+\.\d+) (.+)$")
# Thousands separators, so "3,081 spreads" is one figure and not an oddly specific 081.
NUMERAL = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numerals(text):
    return {found.group(0).replace(",", "") for found in NUMERAL.finditer(text)}


# ------------------------------------------------------------------ reading the battery


def battery():
    """Every question, paired with the entry recorded for it when it was first worked."""
    lines = open(VALIDATION, encoding="utf-8").read().splitlines()

    questions = {}
    for line in lines:
        found = QUESTION.match(line)
        if found:
            status, number, text = found.groups()
            questions[number] = {"number": number, "status": status, "question": text.strip()}

    # The Results section: one ### heading per question, body until the next heading.
    recorded, current = {}, None
    for line in lines:
        found = ENTRY.match(line)
        if found:
            current = found.group(1)
            recorded[current] = {"title": found.group(2), "body": []}
        elif current and line.startswith("## "):
            current = None
        elif current:
            recorded[current]["body"].append(line)

    for number, entry in recorded.items():
        if number in questions:
            body = "\n".join(entry["body"])
            questions[number]["recorded_title"] = entry["title"]
            questions[number]["recorded_nodes"] = sorted(set(re.findall(r"`([a-z-]+)`", body)))
            questions[number]["recorded_figures"] = sorted(numerals(body))

    return [questions[n] for n in sorted(questions, key=lambda n: [int(p) for p in n.split(".")])]


def select(items, args):
    if args.only:
        wanted = {n.strip() for n in args.only.split(",")}
        items = [q for q in items if q["number"] in wanted]
    if args.pattern:
        items = [q for q in items if q["number"].split(".")[0] == str(args.pattern)]
    if args.resume:
        # Only skip what actually finished. A question that errored — which is nearly always
        # the provider's limit rather than the question — must be retried, or resuming would
        # quietly bless the run that ran out of quota.
        done = set()
        for line in open(args.resume):
            if line.strip():
                outcome = json.loads(line)
                if outcome["outcome"] != "error":
                    done.add(outcome["number"])
        items = [q for q in items if q["number"] not in done]
    if args.limit:
        items = items[: args.limit]
    return items


# ----------------------------------------------------------------------- running one


async def run_one(question, collection, catalog, node_names):
    """One question, in its own ledger. Returns what the four checks saw."""
    session = f"battery-{question['number'].replace('.', '-')}"
    outcome = {
        **{k: question[k] for k in question if k != "recorded_figures"},
        "called": [],
        "refusals": [],
        "outcome": "incomplete",
        "attestation": None,
        "answer": None,
        "detail": [],
    }
    started = time.monotonic()

    try:
        async for event in engine.answer(
            question["question"], collection, session, catalog, ask_model
        ):
            kind = event["type"]
            if kind == "call":
                outcome["called"].append(event["node"])
            elif kind == "refusal":
                outcome["refusals"].append(f"{event['node']}: {event['reason']}")
            elif kind == "answer":
                outcome["outcome"] = "answered"
                outcome["attestation"] = event["attestation"]
                outcome["answer"] = event["text"]
                outcome["detail"] = event.get("detail") or []
            elif kind in ("no_answer", "defect", "error"):
                outcome["outcome"] = kind
                outcome["detail"] = [event.get("reason", "")]
    except LLMError as failure:
        outcome["outcome"] = "error"
        outcome["detail"] = [str(failure)]

    outcome["seconds"] = round(time.monotonic() - started, 1)

    # Only compare against nodes that still exist: the recorded entries predate two renames,
    # and a backtick in prose is not always a node name.
    recorded = [n for n in question.get("recorded_nodes", []) if n in node_names]
    outcome["nodes_expected"] = recorded
    outcome["nodes_missed"] = sorted(set(recorded) - set(outcome["called"]))
    outcome["nodes_extra"] = sorted(set(outcome["called"]) - set(recorded))

    figures = numerals(outcome["answer"] or "")
    outcome["figures_in_answer"] = sorted(figures)
    outcome["figures_recorded"] = question.get("recorded_figures", [])
    outcome["figures_shared"] = sorted(figures & set(outcome["figures_recorded"]))
    return outcome


# --------------------------------------------------------------------------- reporting

EXHAUSTED = ("limit", "quota", "429", "rate")


def out_of_quota(reason):
    """Did the model provider refuse us, rather than this question failing?

    Worth telling apart: pattern 1 once produced ten "errors" in fifteen seconds, all of them
    the same session limit, and each one looked like a question that had been tried.
    """
    lowered = reason.lower()
    return any(word in lowered for word in EXHAUSTED)


MARK = {
    ("answered", "attested"): "ok  ",
    ("answered", "unchecked"): "UNCH",
    ("answered", "failed"): "FAIL",
}


def line_for(outcome):
    mark = MARK.get((outcome["outcome"], outcome["attestation"]), outcome["outcome"].upper()[:4])
    nodes = f"{len(outcome['called'])} call(s)"
    if outcome["nodes_missed"]:
        nodes += f"  missed: {','.join(outcome['nodes_missed'])}"
    shared, recorded = len(outcome["figures_shared"]), len(outcome["figures_in_answer"])
    figures = f"{shared}/{recorded} figures also in the record" if recorded else "no figures"
    return f"  {outcome['number']:<5} {mark}  {outcome['seconds']:>5.1f}s  {nodes:<44} {figures}"


def summarise(results):
    print(f"\n{len(results)} question(s)\n")

    counted = {}
    for outcome in results:
        key = (outcome["outcome"], outcome["attestation"])
        counted[key] = counted.get(key, 0) + 1
    for (kind, attestation), count in sorted(counted.items(), key=lambda pair: -pair[1]):
        label = f"{kind}, {attestation}" if attestation else kind
        print(f"  {count:>3}  {label}")

    broken = [r for r in results if r["outcome"] == "defect"]
    if broken:
        print("\nDEFECTS — a node violated its own contract:")
        for outcome in broken:
            print(f"  {outcome['number']}  {'; '.join(outcome['detail'])}")

    unattested = [r for r in results if r["attestation"] == "failed"]
    if unattested:
        print("\nATTESTATION FAILED — a figure no call produced:")
        for outcome in unattested:
            print(f"  {outcome['number']}")
            for line in outcome["detail"]:
                print(f"      {line}")

    quiet = [r for r in results if r["outcome"] == "no_answer"]
    if quiet:
        print("\nNo answer — check whether the record says the same:")
        for outcome in quiet:
            print(f"  {outcome['number']}  {'; '.join(outcome['detail'])[:120]}")


# -------------------------------------------------------------------------------- main


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pattern", type=int, help="only questions from this pattern")
    parser.add_argument("--only", help="comma-separated question numbers")
    parser.add_argument("--limit", type=int, default=0, help="stop after N questions")
    parser.add_argument("--resume", help="skip questions already in this run file")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--yes", action="store_true", help="run more than 20 questions")
    args = parser.parse_args()

    chosen = select(battery(), args)
    if not chosen:
        sys.exit("nothing selected")

    if len(chosen) > 20 and not args.yes:
        sys.exit(
            f"{len(chosen)} questions is roughly {len(chosen) * 3} model calls. "
            "Pass --yes, or narrow it with --pattern / --limit."
        )

    catalog = await engine.load_catalog(ROOT)
    node_names = {n["node"] for n in catalog["nodes"]}
    print(
        f"{len(chosen)} question(s), {args.concurrency} at a time, "
        f"one ledger each, against {len(node_names)} nodes"
    )

    os.makedirs(RUNS, exist_ok=True)
    path = os.path.join(RUNS, f"battery-{time.strftime('%Y%m%d-%H%M')}.jsonl")
    gate = asyncio.Semaphore(args.concurrency)
    results = []

    halted = asyncio.Event()

    async def guarded(question):
        if halted.is_set():
            return
        async with gate:
            if halted.is_set():
                return
            outcome = await run_one(question, ROOT, catalog, node_names)
        if outcome["outcome"] == "error" and out_of_quota(" ".join(outcome["detail"])):
            if not halted.is_set():
                halted.set()
                print(f"\n  stopping: {'; '.join(outcome['detail'])}", flush=True)
            return
        results.append(outcome)
        print(line_for(outcome), flush=True)
        with open(path, "a", encoding="utf-8") as out:
            out.write(json.dumps(outcome) + "\n")

    await asyncio.gather(*(guarded(q) for q in chosen))

    results.sort(key=lambda r: [int(p) for p in r["number"].split(".")])
    summarise(results)
    print(f"\nfull runs in {os.path.relpath(path, ROOT)}")
    if halted.is_set():
        skipped = len(chosen) - len(results)
        print(
            f"{skipped} question(s) never ran. When the quota is back:\n"
            f"  ./scripts/run_battery.py --resume {os.path.relpath(path, ROOT)} "
            + (f"--pattern {args.pattern}" if args.pattern else "")
        )


if __name__ == "__main__":
    asyncio.run(main())
