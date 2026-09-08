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
#
# Stale, deliberately, until a run replaces them. They were measured against a 28k-token fixed
# prefix and no reasoning budget; that prefix is now 19k, and planning decisions ask for
# `reasoning: low`. So `--estimate` now reads high — the safe direction for a figure whose only
# job is to stop a run that would cost more than expected. Re-measure with one model on one
# question before trusting them again; `llm.py` documents the two environment variables that
# reproduce the configuration these came from.
SEEN_COST = {
    # Measured 7 September 2026, three questions each, with cache breakpoints and
    # `reasoning: low`. These four are per decision; divide a per-question figure by
    # DECISIONS_PER_QUESTION to add one.
    "openai/gpt-5.6-luna": 0.0007,
    "qwen/qwen3.8-27b": 0.0044,
    "openai/gpt-5.6-terra": 0.0106,
    # Not re-measured since the change; left at their old rates, which now read high.
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


# Questions whose right answer is not a figure.
#
# Every question in the first battery was answerable, so a model that answers everything
# scored full marks. The collection's whole value is refusing when refusing is true, and
# nothing measured whether a model relays a refusal or fabricates around it. These do.
#
# They are scored apart from the rest, and deliberately not auto-failed on "answered": for
# 4.1 an answer can be right (the recorded entry recovers), and for the others an answer is
# a claim the collection cannot support and wants reading. The table says which is which and
# leaves the judgement where it belongs.
EXPECT = {
    "4.1": ("recovery", "no such weapon; the skill names the real one"),
    # 11.3 was here and is not any more: `status-effect` answers it. The proc rule was in
    # StatusEffectData.csv the whole time, vendored and read by nothing. Leaving a question in
    # this arm after the collection learns to answer it scores a correct answer as a failure,
    # which is the failure mode this map exists to prevent in the other direction.
    "11.6": ("refusal", "poise figures exist, the stance-break rule does not"),
    "15.6": ("refusal", "no table carries range"),
    # Added 7 September, and the reason they were not here first is worth keeping.
    #
    # Both were scored as failures while the models were right about them: nothing in this
    # collection ranks talismans, which is DATA.md's first entry. VALIDATION.md marks 5.1 as
    # done, so the recorded answer disagrees with the code — and the scoring key inherited the
    # record's opinion rather than the collection's behaviour.
    #
    # That distinction only started to matter this week. Once refusing got easier, an honest
    # "no node does this" and a failure scored identically, and the difference was most of the
    # movement between runs. A key that cannot tell "couldn't" from "wouldn't" measures the
    # wrong thing at exactly the moment the tool gets better at saying which.
    # 5.1 was here for the same reason and leaves for the same reason: `item-rank` ranks
    # talismans now. This arm is about what the collection can do, not about whether a model
    # manages it — so if a model still fails 5.1 that is a real failure and should be scored
    # as one.
    # 14.4 was here too and should not have been. It asks how to get a fire buff without
    # Faith, and the model answers it by naming plausible items and pricing them through
    # item-effect and buff-stack — no ranking required, and it says which item it could not
    # verify. 5.1 asks which *four* talismans maximise something, which is a ranking and is
    # the gap. Being in the refusal arm scores a good answer as a failure, so the line between
    # "name some and price them" and "rank the whole table" has to be drawn where the data is,
    # not where the question sounds hard.
}

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
        "asks": 0,
        "answered_with": None,
        "expect": EXPECT.get(question["number"], ("answer", ""))[0],
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
                    # One ask is the guidance working. Three is a model interviewing the
                    # user, which is how luna spent all of 7.1 — visible until now only by
                    # reading the exchanges by hand.
                    outcome["asks"] += 1
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
    # On a question the collection cannot answer, stopping is the right outcome and
    # answering is the one worth reading. The marks are inverted here rather than in the
    # counting, so the word in the column always means "this is what you wanted".
    if outcome.get("expect") == "refusal":
        if outcome["outcome"] == "no_answer":
            return "ok (stopped)"
        if outcome["outcome"] == "answered":
            return "ANSWERED?"
        return outcome["outcome"].upper()

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
    # Grouped by model **and question**. Grouping by model alone compared the figures in an
    # answer about talismans against the figures in an answer about boss resistances, so the
    # line said DIFFERED for every multi-question run ever made and meant nothing.
    by = {}
    for outcome in results:
        by.setdefault((outcome["model"], outcome["number"]), []).append(outcome)

    repeated = {k: v for k, v in by.items() if len(v) > 1}
    if repeated:
        print(f"\nSame model, same question, across repeats:")
        for (model, number), runs in sorted(repeated.items()):
            answered = [r for r in runs if r["outcome"] == "answered"]
            sets = [set(r["figures"]) for r in answered]
            if not sets:
                print(f"  {model:<24} {number:<5} never answered")
                continue
            shared = set.intersection(*sets)
            varying = sorted(set.union(*sets) - shared, key=float)
            # Two very different things look identical in a set comparison, and only one of
            # them is a problem. A figure quoted in one run and left out of another is the
            # narrator choosing what to mention from the same verified result — the answer is
            # the same, the prose is shorter. A run that reached *different inputs* computed a
            # different answer, and that is the drift worth chasing.
            #
            # Asking is not the test for it. A question that genuinely does not state a floor
            # should be asked about, and 1.1 asks in every run and takes the same option every
            # time — stable inputs, five asks. What separates them is whether the runs agreed
            # on what they were told, so that is what is compared.
            asked = sum(r.get("asks", 0) for r in runs)
            chosen = {str(r.get("answered_with")) for r in runs}
            if not varying:
                print(f"  {model:<24} {number:<5} identical across {len(sets)} run(s)")
            else:
                kind = ("INPUTS DIFFERED" if len(chosen) > 1
                        else "same inputs, different subset quoted")
                print(f"  {model:<24} {number:<5} {len(shared)} held, {len(varying)} varied "
                      f"({kind}; {asked} ask(s)): {', '.join(varying[:8])}")
                if len(chosen) > 1:
                    for taken in sorted(chosen):
                        print(f"  {'':<24} {'':<5}   took: {taken[:80]}")

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

    # The two arms are counted apart because "answered" means opposite things in them.
    # Averaging a refusal question into an answered-rate is how a model that answers
    # everything comes out looking best.
    answerable = [r for r in results if r.get("expect") != "refusal"]
    if answerable:
        print(f"\n{'model':<24} {'answered':>9} {'attested':>9} {'complete':>9} {'asks':>6} {'cost/q':>9} {'cached':>8}")
        print("-" * 80)
        for model in dict.fromkeys(r["model"] for r in answerable):
            mine = [r for r in answerable if r["model"] == model]
            answered = sum(1 for r in mine if r["outcome"] == "answered")
            attested = sum(1 for r in mine if r["attestation"] == "attested")
            cost = sum(r["cost"] for r in mine) / len(mine)
            prompt_tokens = sum(r["usage"].get("prompt_tokens", 0) for r in mine)
            cached = sum(r["usage"].get("cached_tokens", 0) for r in mine)
            share = f"{100 * cached / prompt_tokens:.0f}%" if prompt_tokens else "-"
            whole = sum(1 for r in mine if r["outcome"] == "answered" and r.get("complete", True))
            asks = sum(r.get("asks", 0) for r in mine)
            print(
                f"{model:<24} {answered:>6}/{len(mine)} {attested:>6}/{len(mine)} "
                f"{whole:>6}/{len(mine)} {asks:>6} ${cost:>8.4f} {share:>8}"
            )

    refusing = [r for r in results if r.get("expect") == "refusal"]
    if refusing:
        print(f"\nQuestions the collection cannot answer — stopping is the right outcome:")
        print(f"{'model':<24} {'stopped':>9} {'answered':>9} {'cost/q':>9}")
        print("-" * 54)
        for model in dict.fromkeys(r["model"] for r in refusing):
            mine = [r for r in refusing if r["model"] == model]
            stopped = sum(1 for r in mine if r["outcome"] == "no_answer")
            said = sum(1 for r in mine if r["outcome"] == "answered")
            cost = sum(r["cost"] for r in mine) / len(mine)
            print(f"{model:<24} {stopped:>6}/{len(mine)} {said:>6}/{len(mine)} ${cost:>8.4f}")
        for outcome in refusing:
            if outcome["outcome"] == "answered":
                why = EXPECT.get(outcome["number"], ("", ""))[1]
                print(f"\n  {outcome['model']} r{outcome['repeat']} answered {outcome['number']} ({why}):")
                print(f"    {(outcome['answer'] or '')[:300]}")

    recovering = [r for r in results if r.get("expect") == "recovery"]
    if recovering:
        print(f"\nQuestions naming something that does not exist — recovery or an honest stop:")
        for outcome in recovering:
            print(f"  {outcome['model']:<24} r{outcome['repeat']} {outcome['number']} "
                  f"{outcome['outcome']} via {', '.join(dict.fromkeys(outcome['called'])) or '(no calls)'}")
            if outcome["answer"]:
                print(f"    {outcome['answer'][:250]}")

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
