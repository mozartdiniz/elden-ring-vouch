#!/usr/bin/env python3
"""Run the same questions through several OpenRouter models and compare what comes back.

Four things decide whether a model can drive this collection, and only the first is about
intelligence:

    finished      it reached an answer instead of erroring or running out of decisions
    attested      every numeral in that answer traced to a call
    right nodes   it reached for the nodes the recorded entry names
    cost          what the whole question cost, which is the reason this script exists

Every model's reply is kept in full, so a failure can be read rather than guessed at. That
matters more than the table: "gpt-5.6-luna scored 2/3" is not actionable, and "it invented a
parameter called `weapon_name` on the third decision" is.

    ./compare_models.py --questions 1.1                    every model, one question
    ./compare_models.py --models openai/gpt-5.6-luna       one model, the default questions
    ./compare_models.py --estimate                         what it would cost, without running

Costs real money. Nothing runs without --yes once the estimate is over a dollar.
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

import completeness  # noqa: E402
import engine  # noqa: E402
from llm import LLMError, ask_model  # noqa: E402

MODELS_FILE = os.path.join(ROOT, "web", "openrouter_models.txt")
RUNS = os.path.join(ROOT, "runs")

# Three shapes, chosen because they fail differently: one call, a three-call chain, and the
# long one that needed the decision budget raised.
DEFAULT_QUESTIONS = ["3.1", "1.1", "7.1"]

# Measured cost per decision over 28 runs, *including* the effect of prompt caching, which is
# most of the spread: kimi's headline rate is the highest here and it caches 87% of a 26k-token
# prompt, so it lands at a third of sol's cost. A first-call figure would overstate it by 4x.
SEEN_COST = {
    "openai/gpt-5.6-luna": 0.006,
    "moonshotai/kimi-k3": 0.021,
    "x-ai/grok-4.6": 0.044,
    "openai/gpt-5.6-sol": 0.048,
}
DECISIONS_PER_QUESTION = 9


def models():
    return [line.strip() for line in open(MODELS_FILE) if line.strip() and not line.startswith("#")]


def questions(wanted):
    """Pull the chosen questions, and the nodes their recorded entries name, out of the battery."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "battery", os.path.join(ROOT, "scripts", "run_battery.py")
    )
    battery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(battery)
    everything = {q["number"]: q for q in battery.battery()}
    return [everything[n] for n in wanted if n in everything]


class Recorder:
    """One model, one question: every prompt sent and every reply, plus what it all cost."""

    def __init__(self, model):
        self.model = model
        self.usage = {}
        self.exchanges = []

    async def __call__(self, prompt):
        started = time.monotonic()
        try:
            reply = await ask_model(prompt, model=self.model, usage=self.usage)
        except LLMError as failure:
            self.exchanges.append({"prompt_chars": len(prompt), "error": str(failure)})
            raise
        self.exchanges.append(
            {
                "prompt_chars": len(prompt),
                "reply": reply,
                "seconds": round(time.monotonic() - started, 1),
            }
        )
        return reply


NUMERAL = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numerals(text):
    """Every figure in an answer, as strings, so two answers can be compared without parsing
    prose. Trailing zeros and thousands separators are normalised, since 377 and 377.0 and
    "1,377" are the same claim written three ways."""
    found = set()
    for match in NUMERAL.finditer(text or ""):
        raw = match.group(0).replace(",", "")
        found.add(str(int(float(raw))) if float(raw) == int(float(raw)) else raw)
    return found


async def run(model, question, collection, catalog, node_names, repeat=0):
    """One question, and if the model asks for a judgement, the first option it offered.

    A model that asks has not failed — it has done the thing the guidance tells it to do. But
    a comparison wants to know whether it can finish, so the harness plays the user: it takes
    the first option, which the rules tell the model to make the conventional one, and sends
    it as the next turn exactly as a click in the browser would.
    """
    recorder = Recorder(model)
    started = time.monotonic()
    outcome = {
        "model": model,
        "number": question["number"],
        "question": question["question"],
        "called": [],
        "outcome": "incomplete",
        "attestation": None,
        "answer": None,
        "detail": [],
        "asked": None,
        "answered_with": None,
        "results": [],
    }

    # The repeat index is in the session id on purpose. Repeats sharing a ledger would make
    # each run attest against the previous run's numbers, which is the collision the
    # attestation stress test measured — and it would make a consistency test meaningless.
    session = (
        f"models-{model.replace('/', '-')}-{question['number'].replace('.', '-')}-r{repeat}"
    )
    asking, history = question["question"], []

    try:
        # Three, because a model that asks for one floor at a time needs two rounds and
        # the rules now tell it not to. Any more and it is interviewing, not asking.
        for turn in range(3):
            request = None
            calls = []
            async for event in engine.answer(
                asking, collection, session, catalog, recorder, history
            ):
                if event["type"] == "call":
                    outcome["called"].append(event["node"])
                    calls.append({"node": event["node"], "input": event["input"]})
                elif event["type"] == "result":
                    outcome["results"].append((event["node"], event["result"]))
                elif event["type"] == "answer":
                    outcome["outcome"] = "answered"
                    outcome["attestation"] = event["attestation"]
                    outcome["answer"] = event["text"]
                    outcome["detail"] = event.get("detail") or []
                elif event["type"] == "ask":
                    request = event
                    outcome["outcome"] = "asked"
                    outcome["asked"] = event["question"]
                elif event["type"] in ("no_answer", "defect", "error"):
                    outcome["outcome"] = event["type"]
                    outcome["detail"] = [event.get("reason", "")]

            if not request or turn == 2:
                break

            options = request.get("options") or []
            if not options:
                outcome["detail"] = ["asked, but offered no options to pick from"]
                break

            history.append(
                {"question": asking, "calls": calls, "answer": None,
                 "asked": request["question"]}
            )
            asking = outcome["answered_with"] = engine.chosen_text(options[0])
    except LLMError as failure:
        outcome["outcome"] = "error"
        outcome["detail"] = [str(failure)]

    recorded = [n for n in question.get("recorded_nodes", []) if n in node_names]
    found = numerals(outcome["answer"])
    whole, omitted, owed = completeness.check(
        question["question"], outcome["results"], outcome["answer"]
    )
    outcome.update(
        repeat=repeat,
        complete=whole,
        omitted=omitted,
        owed=owed,
        figures=sorted(found, key=lambda n: float(n)),
        figures_shared=sorted(
            found & set(question.get("recorded_figures", [])), key=lambda n: float(n)
        ),
        seconds=round(time.monotonic() - started, 1),
        decisions=len(recorder.exchanges),
        usage=recorder.usage,
        cost=round(recorder.usage.get("cost", 0), 4),
        exchanges=recorder.exchanges,
        nodes_missed=sorted(set(recorded) - set(outcome["called"])),
    )
    return outcome


def verdict(outcome):
    if outcome["outcome"] == "answered":
        mark = {"attested": "ok", "unchecked": "UNCHECKED", "failed": "UNATTESTED"}[
            outcome["attestation"]
        ]
        # Attested but incomplete is the failure attestation cannot see, so it outranks the
        # attestation mark in the one word this column has room for.
        if not outcome.get("complete", True):
            mark = "OMITS"
        return f"{mark} (asked)" if outcome["asked"] else mark
    return outcome["outcome"].upper()


def consistency(results, expect):
    """Two questions the table cannot answer: does a model repeat itself, and do models agree?

    Both are judged on the figures in the answer rather than its wording, because the wording
    is in whatever language the question was asked in and the figures are the claim.
    """
    by_model = {}
    for outcome in results:
        by_model.setdefault(outcome["model"], []).append(outcome)

    if any(len(runs) > 1 for runs in by_model.values()):
        print(f"\nSame model, same question, {max(len(r) for r in by_model.values())} runs:")
        for model, runs in by_model.items():
            sets = [frozenset(r["figures"]) for r in runs if r["outcome"] == "answered"]
            if not sets:
                print(f"  {model:<24} never answered")
            elif len(set(sets)) == 1:
                print(f"  {model:<24} identical across {len(sets)} run(s)")
            else:
                shared = set.intersection(*(set(s) for s in sets))
                drifted = sorted(set.union(*(set(s) for s in sets)) - shared, key=float)
                print(f"  {model:<24} DIFFERED — {len(shared)} figure(s) held, "
                      f"{len(drifted)} moved: {', '.join(drifted[:10])}")

    dropped = [r for r in results if r["outcome"] == "answered" and not r.get("complete", True)]
    if dropped:
        print("\nAttested, but did not name something the question asked about:")
        for outcome in dropped:
            print(f"  {outcome['model']:<24} r{outcome['repeat']}  omits {', '.join(outcome['omitted'])}")
            print(f"  {'':<24}      {(outcome['answer'] or '')[:150]}")

    answered = [r for r in results if r["outcome"] == "answered"]
    if len(answered) > 1:
        everyones = set.intersection(*(set(r["figures"]) for r in answered))
        print(f"\nFigures every answer contains: {', '.join(sorted(everyones, key=float)) or '(none)'}")

    if expect:
        print(f"\nAgainst the recorded answer ({', '.join(expect)}):")
        for outcome in results:
            if outcome["outcome"] != "answered":
                print(f"  {outcome['model']:<24} r{outcome['repeat']}  {outcome['outcome']}")
                continue
            hit = [figure for figure in expect if figure in outcome["figures"]]
            mark = "ALL" if len(hit) == len(expect) else f"{len(hit)}/{len(expect)}"
            missing = [f for f in expect if f not in hit]
            note = f"  missing {', '.join(missing)}" if missing else ""
            print(f"  {outcome['model']:<24} r{outcome['repeat']}  {mark}{note}")


def report(results, chosen, expect):
    print(f"\n{'model':<24} {'q':<5} {'verdict':<18} {'calls':>5} {'dec':>4} {'cost':>8}  {'s':>5}")
    print("-" * 81)
    for outcome in results:
        print(
            f"{outcome['model']:<24} {outcome['number']:<5} {verdict(outcome):<18} "
            f"{len(outcome['called']):>5} {outcome['decisions']:>4} "
            f"${outcome['cost']:>7.4f} {outcome['seconds']:>5.0f}"
        )

    print(f"\n{'model':<24} {'answered':>9} {'attested':>9} {'complete':>9} {'cost/q':>9} {'cached':>8}")
    print("-" * 73)
    for model in dict.fromkeys(r["model"] for r in results):
        mine = [r for r in results if r["model"] == model]
        answered = sum(1 for r in mine if r["outcome"] == "answered")
        attested = sum(1 for r in mine if r["attestation"] == "attested")
        cost = sum(r["cost"] for r in mine) / len(mine)
        prompt_tokens = sum(r["usage"].get("prompt_tokens", 0) for r in mine)
        cached = sum(r["usage"].get("cached_tokens", 0) for r in mine)
        share = f"{100 * cached / prompt_tokens:.0f}%" if prompt_tokens else "-"
        whole = sum(1 for r in mine if r["outcome"] == "answered" and r.get("complete", True))
        print(
            f"{model:<24} {answered:>6}/{len(mine)} {attested:>6}/{len(mine)} "
            f"{whole:>6}/{len(mine)} ${cost:>8.4f} {share:>8}"
        )

    consistency(results, expect)

    print("\nWhere a model asked before answering, and what it offered first:")
    for outcome in (r for r in results if r["asked"]):
        print(f"  {outcome['model']:<24} {outcome['asked'][:90]}")
        print(f"  {'':<24} -> took: {outcome['answered_with']}")

    broken = [r for r in results if r["outcome"] != "answered" or r["attestation"] != "attested"]
    if broken:
        print("\nWhat went wrong, in the model's own words:")
        for outcome in broken:
            print(f"\n  {outcome['model']} on {outcome['number']} — {verdict(outcome)}")
            for line in outcome["detail"]:
                print(f"    {line[:300]}")
            last = outcome["exchanges"][-1] if outcome["exchanges"] else {}
            if "reply" in last:
                print(f"    last reply: {last['reply'][:300]}")


BROKE = ("402", "insufficient", "exceed your available credits", "quota")


def out_of_credit(reason):
    """Did the account run dry, rather than this question failing?

    Worth telling apart, and worth stopping on: a run that keeps going after 402 turns every
    remaining question into a "failure" that was never attempted, which is exactly what makes
    a results file untrustworthy later.
    """
    lowered = reason.lower()
    return any(word in lowered for word in BROKE)


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", help="comma-separated; default is openrouter_models.txt")
    parser.add_argument("--questions", help=f"comma-separated; default {','.join(DEFAULT_QUESTIONS)}")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--repeat", type=int, default=1, help="run each pairing N times")
    parser.add_argument(
        "--expect",
        help="comma-separated figures the right answer contains, e.g. 377,394",
    )
    parser.add_argument("--estimate", action="store_true", help="print the likely cost and stop")
    parser.add_argument("--yes", action="store_true", help="run even if the estimate is over $1")
    args = parser.parse_args()

    chosen_models = args.models.split(",") if args.models else models()
    chosen = questions((args.questions or ",".join(DEFAULT_QUESTIONS)).split(","))
    if not chosen:
        sys.exit("no such question in VALIDATION.md")

    likely = sum(
        SEEN_COST.get(m, 0.05) * DECISIONS_PER_QUESTION * len(chosen) * args.repeat
        for m in chosen_models
    )
    print(
        f"{len(chosen_models)} model(s) x {len(chosen)} question(s) x {args.repeat} run(s) "
        f"~ ${likely:.2f} at roughly {DECISIONS_PER_QUESTION} decisions each"
    )
    if args.estimate:
        return 0
    if likely > 1 and not args.yes:
        sys.exit("over $1 — pass --yes, or narrow it with --models / --questions")

    catalog = await engine.load_catalog(ROOT)
    node_names = {n["node"] for n in catalog["nodes"]}

    os.makedirs(RUNS, exist_ok=True)
    path = os.path.join(RUNS, f"models-{time.strftime('%Y%m%d-%H%M')}.jsonl")
    gate = asyncio.Semaphore(args.concurrency)
    results = []

    halted = asyncio.Event()

    async def guarded(model, question, repeat):
        if halted.is_set():
            return
        async with gate:
            if halted.is_set():
                return
            outcome = await run(model, question, ROOT, catalog, node_names, repeat)
        if outcome["outcome"] == "error" and out_of_credit(" ".join(outcome["detail"])):
            if not halted.is_set():
                halted.set()
                print(f"\n  stopping: {'; '.join(outcome['detail'])[:200]}", flush=True)
            return
        results.append(outcome)
        print(
            f"  {outcome['model']:<24} {outcome['number']:<5} r{outcome['repeat']} "
            f"{verdict(outcome):<18} ${outcome['cost']:.4f}",
            flush=True,
        )
        with open(path, "a", encoding="utf-8") as out:
            out.write(json.dumps({k: v for k, v in outcome.items() if k != "results"}) + "\n")

    await asyncio.gather(
        *(
            guarded(m, q, r)
            for m in chosen_models
            for q in chosen
            for r in range(args.repeat)
        )
    )

    results.sort(key=lambda r: (chosen_models.index(r["model"]), r["number"], r["repeat"]))
    report(results, chosen, [f.strip() for f in (args.expect or "").split(",") if f.strip()])
    print(f"\nevery prompt and reply in {os.path.relpath(path, ROOT)}")
    if halted.is_set():
        print(
            f"{len(chosen_models) * len(chosen) * args.repeat - len(results)} pairing(s) never "
            "ran — the account ran out of credit, which is not a result about any model."
        )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
