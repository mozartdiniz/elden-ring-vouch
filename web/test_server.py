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


# ----------------------------------------------------------------------- what it costs


@check("the cacheable prefix is byte-identical as a question proceeds")
def _():
    """The whole saving rests on this and nothing checks it at runtime.

    A cache breakpoint is a claim that the text up to it is the same as last time. If
    anything volatile ever drifts above one — a timestamp, a re-serialised dict, a
    correction moved earlier — the claim silently becomes false, every call pays a cache
    *write* instead of a read, and the bill goes up rather than down. Nothing in the reply
    says so.
    """
    catalog = {"collection": "c", "notes": ["n"], "nodes": [{"node": "weapon-lookup"}]}
    first = engine.planning_prompt("how much AR?", catalog, [], None)
    later = engine.planning_prompt(
        "how much AR?",
        catalog,
        [{"node": "weapon-lookup", "input": {"query": "uchigatana"}, "result": {"ar": 229}}],
        {"node": "attack-power", "input": {}, "reason": "precondition failed"},
    )

    assert first.segments[0][1] and later.segments[0][1], "the catalog is the fixed prefix"
    assert first.segments[0][0] == later.segments[0][0], "the fixed prefix must not drift"
    # The second breakpoint only ever grows, so the earlier one stays a prefix of it.
    assert later.segments[1][0].startswith(first.segments[1][0])
    # And the correction, which is the one part that changes under a fixed prefix, is last
    # and is not claimed to be cacheable.
    assert later.segments[-1][1] is False
    assert "precondition failed" in later.segments[-1][0]
    # Whatever the segments say, the text a model sees is unchanged.
    assert str(later) == "".join(text for text, _ in later.segments)


@check("a prompt is still a string, and llm.py can place breakpoints on it")
def _():
    import llm

    catalog = {"collection": "c", "nodes": []}
    prompt = engine.planning_prompt("q?", catalog, [], None)
    assert isinstance(prompt, str) and len(prompt) == len(str(prompt))

    blocks = llm._content(prompt)
    assert [b["text"] for b in blocks] == [text for text, _ in prompt.segments]
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}

    # Narration is one uncacheable block, and goes out as a plain string as it always did.
    assert isinstance(llm._content(engine.narration_prompt("q?", [])), str)

    # CACHE_BREAKPOINTS=0 is a true no-op, so a comparison arm can turn this off and change
    # nothing else about the request.
    os.environ["CACHE_BREAKPOINTS"] = "0"
    try:
        assert llm._content(prompt) == str(prompt)
    finally:
        del os.environ["CACHE_BREAKPOINTS"]


@check("the compact pack carries what routing needs, and nothing that only a validator reads")
def _():
    """This replaced a `trimmed()` in engine.py that did the same job by hand.

    The runtime owns the trimming now, so what is worth checking here is not how it trims but
    that the collection this app ships against still publishes what the loop depends on —
    including the judgements map, which the hand-rolled version did not know existed.
    """
    catalog = asyncio.run(engine.load_catalog(COLLECTION))
    assert catalog["nodes"], "the pack has nodes"

    by_name = {n["node"]: n for n in catalog["nodes"]}
    allocate = by_name["build-allocate"]
    for needed in ("purpose", "use_when", "not_for", "input_schema", "examples", "judgements"):
        assert needed in allocate, f"routing needs {needed}"
    for absent in ("requires", "ensures", "output_schema", "params"):
        assert absent not in allocate, f"{absent} is not routing context"
    assert "$schema" not in allocate["input_schema"]
    assert len(allocate["examples"]) == 1, "one worked call is a shape to copy"


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


@check("an evicted conversation takes its ledger with it")
def _():
    """One file per visitor, kept forever, is how a box fills its disk overnight.

    The ledger is only read while the conversation is alive — it is what a follow-up is
    attested against — so the eviction that ends the thread is the right moment to drop it.
    """
    session = "web-evict-probe"
    ledger = engine.ledger_path(COLLECTION, session)
    os.makedirs(os.path.dirname(ledger), exist_ok=True)
    with open(ledger, "w") as handle:
        handle.write('{"node":"weapon-lookup","outcome":"ok"}\n')

    store = app.Conversations()
    store.remember(session, {"question": "q", "calls": [], "answer": "a"})
    store.touched[session] -= app.CONVERSATION_TTL + 1
    store.history("web-someone-else")

    assert session not in store.turns
    assert not os.path.exists(ledger), "the ledger outlived the conversation that needed it"

    # A conversation that never made a call has no ledger, and evicting it must not raise.
    store.remember("web-no-calls", {"question": "q", "calls": [], "answer": "a"})
    store.touched["web-no-calls"] -= app.CONVERSATION_TTL + 1
    store.history("web-someone-else")


@check("the daily ceiling is money, not a count of questions")
def _():
    """200 questions is $1.28 on one model and $19 on another, so a count bounds nothing.

    This is what lets the endpoint be public without an account system: the worst case is a
    number the operator chose.
    """
    was = (app.SPENT.copy(), app.DAILY_SPEND, app.DAILY_BUDGET)
    try:
        app.DAILY_SPEND, app.DAILY_BUDGET = 0.10, 0
        app.SPENT.update(day=None, count=0, cost=0.0)

        assert not app.over_budget(), "nothing spent yet"
        app.record_spend({"cost": 0.04})
        assert not app.over_budget(), "under the ceiling"
        app.record_spend({"cost": 0.07})
        assert app.over_budget(), "over the ceiling and still admitting questions"

        # A new day starts clean.
        app.SPENT["day"] = "19700101"
        assert not app.over_budget()

        # The claude backend reports no cost, so the money cap must never fire on it rather
        # than blocking every question after the first.
        app.SPENT.update(day=None, count=0, cost=0.0)
        for _ in range(50):
            app.record_spend({})
        assert not app.over_budget()
    finally:
        app.SPENT.clear()
        app.SPENT.update(was[0])
        app.DAILY_SPEND, app.DAILY_BUDGET = was[1], was[2]


@check("a stop quotes the runtime, caps the model, and says what it reached")
def _():
    """The stop path is the only model-authored prose the page renders.

    So it is bounded, it prefers the words the runtime already wrote — which were written to
    be acted on, and name the node that said them — and it carries the nodes that did answer,
    because a quarter of real question shapes end here and a bare no throws that away.
    """
    plain = engine.declined("  no  figure   for that ", None, [{"node": "boss-lookup"}])
    assert plain["reason"] == "no figure for that", plain
    assert plain["reached"] == ["boss-lookup"]
    assert "relayed" not in plain

    refused = {"node": "buff-stack", "reason": "no buff named 'Bloodboil Aromatic'"}
    quoted = engine.declined("I could not find it.", refused,
                             [{"node": "weapon-lookup"}, {"node": "weapon-lookup"}])
    assert quoted["reason"] == "buff-stack: no buff named 'Bloodboil Aromatic'", quoted
    assert quoted["relayed"] == "I could not find it."
    # A node reached twice is one thing reached, in the order it was first reached.
    assert quoted["reached"] == ["weapon-lookup"]

    long = engine.declined("x" * 5000, None, [])
    assert len(long["reason"]) == engine.MAX_STOP


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


@check("the same call twice runs once, and the model is told it already has it")
def _():
    call = json.dumps({"call": {"node": "weapon-lookup", "input": {"query": "Uchigatana"}}})
    model = Script(
        call,
        call,  # the same node with the same arguments: nothing new can come of it
        json.dumps({"done": True}),
        "The Uchigatana resolves to one weapon, upgradeable to +25.",
    )
    events = asyncio.run(run("what is an Uchigatana?", model))

    assert [e["type"] for e in events].count("call") == 1, "the node must not run twice"
    repeat = next(e for e in events if e["type"] == "refusal")
    assert "already called that node" in repeat["reason"]

    # A duplicate result would otherwise be carried in every remaining decision's prompt.
    planning = [p for p in model.prompts if getattr(p, "kind", None) == "planning"]
    assert planning[-1].count("→ ") == 1, "one call, one result, however often it was asked for"
    assert events[-1]["attestation"] == "attested", events[-1]


@check("a node that cannot answer refuses, and the turn survives it")
def _():
    """The difference between a refusal and a defect, from the user's side.

    Nineteen places in this collection said "no weapon named X; call weapon-lookup first" by
    exiting 1, which vouch read as a crash — so a mistyped weapon name ended the turn and
    showed nothing, including nothing about the rest of the question. They exit 3 now, and the
    reason comes back as the correction it was always written as.
    """
    model = Script(
        json.dumps({"call": {"node": "attack-power", "input": {
            "weapon": "Distinguished Greatsword", "affinity": "Standard", "upgrade": 10,
            "strength": 40, "dexterity": 23, "intelligence": 10, "faith": 10, "arcane": 12}}}),
        json.dumps({"call": {"node": "weapon-lookup", "input": {"query": "Uchigatana"}}}),
        json.dumps({"done": True}),
        "The Uchigatana resolves to one weapon, upgradeable to +25.",
    )
    events = asyncio.run(run("how much AR on a Distinguished Greatsword?", model))
    kinds = [e["type"] for e in events]

    assert "defect" not in kinds, "a name that is not in the game is not a broken node"
    refusal = next(e for e in events if e["type"] == "refusal")
    assert refusal["code"] == 16, refusal
    assert "call weapon-lookup" in refusal["reason"], refusal
    # And the turn carried on to an answer, which is the whole point.
    assert events[-1]["type"] == "answer", kinds


@check("a judgement the collection will not make is asked with the collection's own options")
def _():
    """The one place a model's words become an *input*, and inputs are outside attestation.

    On battery question 4.1 a model looked up a weapon that does not exist, invented a list of
    plausible-sounding weapons, asked which was meant, and the harness took the first — giving
    an attested, complete answer about a weapon nobody asked about. Every figure in it traced
    to a real call; the premise was fabricated one layer above where any check runs.

    So the options for a judgement come from the manifest, through the runtime's exit 17, and
    the model never writes them.
    """
    model = Script(
        json.dumps({"call": {"node": "build-allocate", "input": {
            "weapon": "Rivers of Blood", "affinity": "Standard",
            "upgrade": 10, "max_upgrade": 10, "focus": "bleed"}}}),
    )
    events = asyncio.run(run("build me a Rivers of Blood build", model))

    ask = events[-1]
    assert ask["type"] == "ask", [e["type"] for e in events]
    assert ask["from"] == "collection", "not authored by the model"
    assert ask["parameter"] in ("vigor", "mind", "endurance"), ask
    # The values are the collection's, spelled out, and travel together because they are
    # chosen together.
    first = ask["options"][0]
    assert first["value"] == {"vigor": 40, "mind": 20, "endurance": 25}, first
    assert "balanced" in first["label"], first
    # And the model was asked once, not asked and then asked again.
    assert len(model.prompts) == 1, model.prompts


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


# ------------------------------------------------------- did it answer the question


@check("an answer that drops one of two named bosses is flagged")
def _():
    import completeness

    question = ("Meu build na Gargoyle's Twinblade nao funciona no Radagon e na Elden Beast. "
                "Qual affinity eu troco pra esses dois?")
    results = [
        ("weapon-lookup", {"query": "Gargoyle's Twinblade", "resolved": "Gargoyle's Twinblade",
                           "ambiguous": False}),
        ("boss-lookup", {"query": "Radagon", "resolved": "Radagon of the Golden Order",
                         "ambiguous": False}),
        ("boss-lookup", {"query": "Elden Beast", "resolved": "Elden Beast", "ambiguous": False}),
    ]
    # The real failure: attested, and about one boss out of two.
    whole, omitted, _ = completeness.check(question, results, "Fire is optimal, 342 damage.")
    assert not whole
    assert "Elden Beast" in omitted

    whole, omitted, _ = completeness.check(
        question, results, "Contra Radagon use Fire; contra a Elden Beast, Heavy."
    )
    assert whole, omitted


@check("the one weapon in a question need not be named again")
def _():
    import completeness

    # A single entity of a kind is the subject and can be left implicit. Demanding it back
    # would flag good answers, and a check that cries wolf gets switched off.
    question = "What is the attack power of the Uchigatana at 40 dexterity?"
    results = [("weapon-lookup", {"query": "Uchigatana", "resolved": "Uchigatana",
                                  "ambiguous": False})]
    whole, omitted, owed = completeness.check(question, results, "It comes to 229 physical.")
    assert whole, omitted
    assert owed == []


@check("an entity the model looked up but the user never named is not owed")
def _():
    import completeness

    question = "What is the best affinity for the Uchigatana?"
    results = [
        ("weapon-lookup", {"query": "Uchigatana", "resolved": "Uchigatana", "ambiguous": False}),
        # The model went looking for these; the user did not ask about them.
        ("weapon-lookup", {"query": "Nagakiba", "resolved": "Nagakiba", "ambiguous": False}),
    ]
    assert completeness.check(question, results, "Blood, at 229.")[2] == []


@check("an ambiguous or missed lookup is owed nothing")
def _():
    import completeness

    question = "How does the Uchigatana compare to the Nagakiba?"
    results = [
        ("weapon-lookup", {"query": "Uchigatana", "resolved": "", "ambiguous": True}),
        ("weapon-lookup", {"query": "Nagakiba", "resolved": "", "ambiguous": False}),
    ]
    assert completeness.check(question, results, "")[2] == []


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
