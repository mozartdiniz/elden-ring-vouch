#!/usr/bin/env python3
"""The loop and the conversation store, with a scripted model.

    .venv/bin/python test_server.py

No model is called. The replies are canned, so what is under test is everything around them:
real `vouch call` subprocesses, real contracts, real attestation against a real ledger, and
the plumbing that carries one turn's context into the next. That makes this runnable as often
as you like, which the battery is not.
"""

import asyncio
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app  # noqa: E402
import engine  # noqa: E402

COLLECTION = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION = "test-server"
LEDGER = os.path.join(COLLECTION, ".vouch", "ledger", f"session-{SESSION}.jsonl")

checks = []
check = lambda name: lambda fn: checks.append((name, fn)) or fn  # noqa: E731


class Script:
    """A model that says what it is told to, and keeps every prompt it was shown."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

    async def __call__(self, prompt):
        self.prompts.append(prompt)
        if not self.replies:
            raise AssertionError(f"the script ran out; the loop asked again:\n{prompt[-400:]}")
        return self.replies.pop(0)


async def run(question, model, history=()):
    catalog = await engine.load_catalog(COLLECTION)
    return [
        event
        async for event in engine.answer(
            question, COLLECTION, SESSION, catalog, model, history
        )
    ]


# ------------------------------------------------------------------ the prompts carry a turn


@check("an earlier turn is context, and is labelled as not reusable")
def _():
    history = [
        {
            "question": "best weapons at STR 55 / FTH 60?",
            "calls": [{"node": "weapon-rank", "input": {"strength": 55, "faith": 60}}],
            "answer": "Shadow Sunflower Blossom at 931.",
        }
    ]
    written = engine.earlier_turns(history)
    assert "best weapons at STR 55" in written
    assert '"strength": 55' in written, "the inputs are the context; they must survive"
    assert "Shadow Sunflower Blossom at 931." in written
    assert "NOT results you may reuse" in written
    assert "call the nodes again with the new values" in written


@check("a turn that gave no answer is carried too, with its reason")
def _():
    written = engine.earlier_turns(
        [{"question": "is 40/40 worth it?", "calls": [], "answer": None,
          "outcome_reason": "no node can compare spreads without a weapon"}]
    )
    assert "gave no answer" in written
    assert "without a weapon" in written


@check("with no history, the prompt gains nothing at all")
def _():
    assert engine.earlier_turns([]) == ""
    assert engine.earlier_turns(()) == ""


@check("the narrator may quote earlier answers, and is told why")
def _():
    history = [{"question": "at STR?", "calls": [], "answer": "It comes to 229."}]
    written = engine.narration_prompt("and at DEX?", [], history)
    assert "It comes to 229." in written
    assert "came from a node call" in written
    # A turn with no answer has no quotable figures and must not appear here.
    assert "Answers already given" not in engine.narration_prompt(
        "x", [], [{"question": "q", "calls": [], "answer": None}]
    )


# ------------------------------------------------------------------------ the store


@check("the store keeps the last turns, and only the last turns")
def _():
    store = app.Conversations()
    for n in range(app.KEEP_TURNS + 4):
        store.remember("web-a", {"question": f"q{n}", "calls": [], "answer": f"a{n}"})
    kept = store.history("web-a")
    assert len(kept) == app.KEEP_TURNS, f"kept {len(kept)}"
    assert kept[-1]["question"] == f"q{app.KEEP_TURNS + 3}"
    assert kept[0]["question"] == "q4"


@check("conversations are separate, and an unknown one is empty")
def _():
    store = app.Conversations()
    store.remember("web-a", {"question": "mine", "calls": [], "answer": "x"})
    assert store.history("web-b") == []
    assert len(store.history("web-a")) == 1


@check("old conversations are evicted, by age and by count")
def _():
    store = app.Conversations()
    store.remember("web-old", {"question": "q", "calls": [], "answer": "a"})
    store.touched["web-old"] -= app.CONVERSATION_TTL + 1
    store.history("web-new")
    assert "web-old" not in store.turns, "a conversation past its TTL should be gone"

    store = app.Conversations()
    for n in range(app.KEEP_CONVERSATIONS + 5):
        store.remember(f"web-{n}", {"question": "q", "calls": [], "answer": "a"})
        store.touched[f"web-{n}"] = n  # oldest first, deterministically
    store.history("web-probe")
    assert len(store.turns) <= app.KEEP_CONVERSATIONS + 1, len(store.turns)
    assert "web-0" not in store.turns


# --------------------------------------------------- the loop, against real nodes


@check("a scripted turn makes a real call and attests against a real ledger")
def _():
    model = Script(
        json.dumps({"call": {"node": "weapon-lookup", "input": {"query": "Uchigatana"}}}),
        json.dumps({"done": True}),
        "The Uchigatana resolves to one weapon, upgradeable to +25.",
    )
    events = asyncio.run(run("what is an Uchigatana?", model))
    kinds = [e["type"] for e in events]
    assert "result" in kinds, kinds
    answer = events[-1]
    assert answer["type"] == "answer", answer
    assert answer["attestation"] == "attested", answer


@check("a fabricated figure is caught by attestation, and no answer is shown")
def _():
    model = Script(
        json.dumps({"call": {"node": "weapon-lookup", "input": {"query": "Uchigatana"}}}),
        json.dumps({"done": True}),
        "The Uchigatana resolves to one weapon and deals 1234.5 damage.",
    )
    events = asyncio.run(run("what is an Uchigatana?", model))
    answer = events[-1]
    assert answer["attestation"] == "failed", answer
    assert answer["text"] is None, "a failed answer must not carry its prose"
    assert any("1234.5" in line for line in answer["detail"]), answer["detail"]


@check("the second turn is planned with the first turn in front of the model")
def _():
    first = Script(
        json.dumps({"call": {"node": "weapon-lookup", "input": {"query": "Uchigatana"}}}),
        json.dumps({"done": True}),
        "It goes to +25.",
    )
    asyncio.run(run("what is an Uchigatana?", first))

    history = [
        {
            "question": "what is an Uchigatana?",
            "calls": [{"node": "weapon-lookup", "input": {"query": "Uchigatana"}}],
            "answer": "It goes to +25.",
        }
    ]
    second = Script(json.dumps({"stop": "nothing more to add"}))
    asyncio.run(run("and if I make it Blood?", second, history))

    planning = second.prompts[0]
    assert "what is an Uchigatana?" in planning, "the follow-up lost the earlier question"
    assert '"query": "Uchigatana"' in planning, "the follow-up lost the earlier call"
    assert "and if I make it Blood?" in planning


@check("a lookup miss comes back as data the model can decline on")
def _():
    # Not a defect and not a refusal: exit 0, with match_count 0. The runtime cannot express
    # "no such weapon" as a refusal — the open design question in ~/Dev/vouch/DECISIONS.md —
    # so the node reports the miss in its result and the model is expected to read it.
    #
    # Note what else is in that result: max_upgrade 0, for a weapon that does not exist. A
    # narrator that wrote "+0" would be quoting a real scalar about an unreal thing, and it
    # would attest. That is audit question 2 in BUGS.md, and this is an instance of it.
    model = Script(
        json.dumps({"call": {"node": "weapon-lookup", "input": {"query": "!!nonexistent!!"}}}),
        json.dumps({"stop": "there is no such weapon"}),
    )
    events = asyncio.run(run("what is a !!nonexistent!!?", model))
    found = next(e for e in events if e["type"] == "result")
    assert found["result"]["match_count"] == 0, found
    assert found["result"]["resolved"] == "", found
    assert events[-1]["type"] == "no_answer", events[-1]
    assert not any(e["type"] == "answer" for e in events)


def main():
    if os.path.exists(LEDGER):
        os.remove(LEDGER)

    failed = 0
    for name, fn in checks:
        try:
            fn()
            print(f"  ok    {name}")
        except Exception as failure:
            failed += 1
            print(f"  FAIL  {name}\n        {failure}")

    if os.path.exists(LEDGER):
        os.remove(LEDGER)
    print(f"\n{len(checks) - failed}/{len(checks)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
