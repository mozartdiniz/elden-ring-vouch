"""The agent loop, as a stream of events.

This is ~/Dev/vouch/examples/ask.py with its two I/O ends changed and its logic left alone.
The planning and narration prompts are copied verbatim, because they are the part that has
been exercised; if that file's prompts change, change these to match.

What is different here, and why:

  * it yields events instead of printing, so a browser can watch a question being answered;
  * the subprocesses are async, so several conversations can be in flight at once;
  * `VOUCH_SESSION` is set per conversation and never allowed to default. Left alone,
    `ledger::session_id()` falls back to today's date, and every visitor would attest against
    every other visitor's numbers. The stress test measured what that costs: in a day-sized
    ledger, 96 of the integers 1..99 are already present, so a fabricated small number
    attests clean. One ledger per conversation is both correct and a stricter check.
"""

import asyncio
import json
import os
import re

VOUCH = os.environ.get("VOUCH_BIN", "vouch")

# How many decisions the model may make before the loop gives up. Six was ask.py's figure and
# it is too few here: battery question 7.1 spent all six on calls — a weapon, three bosses, a
# build, an affinity — and never reached the narration, which needs a decision of its own. Ten
# leaves room for a chain that long plus a correction, and still cannot spin.
MAX_DECISIONS = int(os.environ.get("MAX_DECISIONS", "10"))

# A stop reason is one sentence. It is also the only text a model writes that reaches the page
# without passing through attestation, so it is bounded rather than trusted.
MAX_STOP = int(os.environ.get("MAX_STOP", "400"))

# How many times one node may refuse within a question before the loop calls it exhausted.
#
# A refusal is a correction and a model is meant to act on it — that is the whole point of the
# exit-code families. But acting on it can mean *retrying with a different argument*, and a
# node that refuses on a value the model is searching for invites an unbounded search. On
# battery question 10.3 a model called `matchmaking` eleven times with eleven different
# upgrade levels, hunting for the one that would not be refused, and spent the whole decision
# budget on it. The duplicate-call guard saw nothing, because no two calls were the same.
#
# Three is enough for a genuine correction sequence — wrong argument, fixed, wrong again — and
# short of a search.
MAX_REFUSALS_PER_NODE = int(os.environ.get("MAX_REFUSALS_PER_NODE", "3"))

# vouch's taxonomy, for reading the exit code of a call. Only DEFECT is branched on — the
# loop hands anything that is not a defect back to the model as a correction — but the
# refusal set is kept accurate because it is the documentation of what those numbers mean.
# 16 is a node refusing on its own data; 17 is a judgement the collection will not make,
# which the loop turns into an `ask` rather than a correction — see JUDGEMENT below.
JUDGEMENT = 17
REFUSAL = {11, 14, 15, 16, JUDGEMENT}
DEFECT = {12, 13, 20, 21}

# vouch rewrites anything outside this set when it names the ledger file, so a session id of
# "models-x-ai-grok-4.6" is written to session-models-x-ai-grok-4-6.jsonl. Building the path
# by interpolation therefore pointed at a file that did not exist, attestation exited 2, and
# the answer was shown as UNCHECKED — a silent downgrade of the one check that matters.
# Sanitising here means the name we pass and the name vouch writes are the same string.
UNSAFE = re.compile(r"[^a-z0-9-]+")


def safe_session(raw):
    return UNSAFE.sub("-", str(raw).lower()).strip("-") or "session"


class Defect(Exception):
    """A node violated its own contract. The loop stops and no answer is shown."""


# --------------------------------------------------------------------- the runtime


async def _vouch(collection, session, *args):
    env = dict(os.environ, VOUCH_SESSION=safe_session(session))
    proc = await asyncio.create_subprocess_exec(
        VOUCH,
        "-C",
        collection,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    out, err = await proc.communicate()
    return proc.returncode, out.decode(), err.decode()


def _report(stderr):
    """The structured JSON object vouch puts on stderr for every non-zero exit."""
    lines = stderr.strip().splitlines()
    try:
        return json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError):
        return {"outcome": "error", "reason": stderr.strip() or "no reason given"}


async def load_catalog(collection):
    """The routing context a collection publishes about itself.

    Read once at startup and shared by every conversation: it is the same for all of them, and
    it is re-sent on every decision, six to sixteen per question.

    `--compact` is the runtime's own trimming, and this used to be a `trimmed()` in this file
    doing the same job by hand — dropping `$schema` and `title`, folding `params.*.guidance`
    into the schema description that duplicated it, one example per node, no whitespace. The
    two agreed to within 0.8% on this collection, so nothing was lost by deleting ours, and
    two things were gained: it stops being this app's problem to maintain, and the compact
    pack carries a `judgements` map that the hand-rolled version had no idea existed.
    """
    code, out, err = await _vouch(collection, "startup", "describe", "--all", "--compact")
    if code != 0:
        raise RuntimeError(f"cannot read the collection: {_report(err)['reason']}")
    return json.loads(out)


# ------------------------------------------------------------------------ the model


def chosen_text(option):
    """What the user is taken to have said when they pick an option from an `ask`.

    The label alone is not it. Models label their options "Padrão recomendado" and put the
    numbers in `value`, so sending the label back asks the same question again — which is
    exactly how one model spiralled into asking three times and then emitting `"vigor": fifty`
    as JSON. The values are the answer; the label is the caption.

    static/app.js does the same thing, so the chat shows precisely what was sent.
    """
    label = str(option.get("label", "")).strip()
    value = option.get("value")
    if value is None or value == "":
        return label or "the first option"
    if isinstance(value, dict):
        spelled = ", ".join(f"{k} {v}" for k, v in value.items())
    elif isinstance(value, list):
        spelled = ", ".join(str(v) for v in value)
    else:
        spelled = str(value)
    if not label:
        return spelled
    # "40 vigor (typical) (40)" helps nobody.
    return label if spelled in label else f"{label} ({spelled})"


def parse_json_reply(text):
    """Models sometimes wrap JSON in a fence or a sentence. Take the outermost object."""
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in the model's reply: {text[:200]}")
    return json.loads(text[start : end + 1])


PLANNING_RULES = """\
You are driving a set of verified functions, called nodes, to answer a question. You are NOT
answering it yourself.

Reply with ONLY a JSON object, in one of three shapes:

  {"call": {"node": "<name>", "input": {...}}}
      Run a node. `input` must satisfy that node's input_schema exactly. Build the arguments
      from the question and from the verified results of earlier calls — never from your own
      guesses. If you need a figure you do not have, call the node that produces it first.

  {"done": true}
      The verified results so far are enough to answer the question.

  {"ask": {"question": "<one sentence>",
           "parameter": "<the parameter you cannot fill>",
           "options": [{"label": "<what the user would pick>", "value": <the value>,
                        "note": "<why, one clause>"}]}}
      A node needs a judgement that is the user's to make, not yours — a floor like vigor, a
      weapon the question never named, which of two forms of a spell was meant. Ask for it.
      Offer two to four options with the conventional one first. This is not failure: it is
      the question the collection needs answered before it can compute anything.

      Ask ONCE, for everything you are missing. If a node needs three floors, one question
      offering three complete sets beats three questions in a row; each option's `value` may
      be an object carrying all of them. Nobody wants to be interviewed.

      NEVER offer an option you did not get from a node. An option you invented becomes an
      input, and inputs are the one thing in this loop nothing checks: a made-up name that the
      user clicks is laundered into an answer where every figure attests and the whole thing
      is about the wrong weapon.

      So GET THEM FIRST. If you do not know which weapon, spell or boss was meant, call the
      lookup and offer its `candidates` — asking is not the alternative to guessing, calling
      is. A lookup costs one decision and a blind question costs the user a turn and tells
      them nothing they did not already know. Only ask once a node has given you something to
      offer, or when what is missing is a judgement no lookup can settle.

      NEVER ask for a value the user's question already contains. If they wrote "VIG 55 /
      MND 30 / END 20", those are the floors — asking and then substituting your own is how
      an answer stops being about their build. Read the question again before asking.

      A parameter whose description says the collection has a default is not missing. Leave
      it out and let the collection fill it; it reports what it assumed and the answer will
      say so.

  {"stop": "<one sentence>"}
      No node can answer this, or a node has told you the answer does not exist. Say what you
      cannot answer and why.

Use `ask` when a value is missing and a person could supply it. Use `stop` only when no
answer exists at all — a weapon that is not in the game, a figure nothing computes. A missing
judgement is never a `stop`.

Stopping is a good answer when it is the true one. Never pick a node that is merely close,
and never fill a parameter with a number you invented — a wrong answer is worse than none.
"""


def earlier_turns(history):
    """The conversation so far, as context for routing — deliberately without its results.

    A follow-up is nearly always a change: *the same question with dexterity instead of
    strength*. Handing back the previous turn's raw results invites the model to narrate from
    them rather than call the nodes again with the new values, which is the one thing that
    would make an answer wrong while every contract still held.

    So each earlier turn carries what the user asked, the calls that were made **with their
    inputs** — which is where "the Longsword, at this spread" actually lives — and what was
    answered. Not the numbers. Those get recomputed.
    """
    if not history:
        return ""

    lines = [
        "\nEarlier in this conversation, oldest first. This is context for understanding what",
        "\nthe user is now asking, NOT results you may reuse. If they are changing a stat, a",
        "\nweapon or a level, call the nodes again with the new values.\n\n",
    ]
    for position, turn in enumerate(history, 1):
        lines.append(f'  {position}. asked: "{turn["question"]}"\n')
        for call in turn["calls"]:
            lines.append(f"     called: {call['node']}({json.dumps(call['input'])})\n")
        if turn.get("answer"):
            lines.append(f'     answered: "{turn["answer"]}"\n')
        elif turn.get("asked"):
            # The user's next message is very often the answer to this, and without it that
            # message is a bare number with nothing to attach to.
            lines.append(f'     asked the user: "{turn["asked"]}"\n')
        else:
            lines.append(f'     gave no answer: "{turn.get("outcome_reason", "")}"\n')
    return "".join(lines)


class Prompt(str):
    """The text of one prompt, plus where a provider may put a cache breakpoint.

    It **is** a `str`, so everything that logs, measures, slices or greps a prompt keeps
    working untouched — `test_server.py` reads them, `compare_models.py` records their
    length, and neither needs to know this exists.

    What `llm.py` needs on top of the text is two things it cannot recover from the string:

      * `segments` — (text, cacheable) pairs, in order. A cacheable segment means
        *everything up to and including this point is identical on the next call*, which is
        exactly the condition a prefix cache needs. The planning prompt is built so that is
        true twice: after the rules and the catalog, which never change at all, and after
        the calls made so far, which only ever grow.
      * `kind` — "planning" or "narration". They want different budgets. A routing decision
        is a fifty-token JSON object that needs no deliberation; the narration is the one
        reply a person actually reads.
    """

    def __new__(cls, segments, kind):
        prompt = super().__new__(cls, "".join(text for text, _ in segments))
        prompt.segments = [(text, cache) for text, cache in segments if text]
        prompt.kind = kind
        return prompt


def planning_prompt(question, catalog, steps, correction, history=()):
    # Ordered so that everything stable precedes everything that varies, which is what makes
    # the two breakpoints below legal: the rules and the catalog are the same for every
    # question ever asked; the history and the question are the same for every decision
    # within this question; the calls made so far only ever grow; and the correction — the
    # one part that can change while the prefix stays fixed — is last.
    fixed = [
        PLANNING_RULES,
        "\nThe collection you are working with:\n",
        # Not indented. Pretty-printing this cost 25,000 characters — about 6,000 tokens —
        # on every single decision, for whitespace no model needs.
        json.dumps(catalog, separators=(",", ":")),
    ]

    asked = [
        earlier_turns(history),
        f"\n\nThe user asked: {question}\n",
    ]

    if steps:
        asked.append("\nCalls made so far, and their verified results:\n")
        for step in steps:
            asked.append(
                f"  {step['node']}({json.dumps(step['input'])})\n"
                f"    → {json.dumps(step['result'])}\n"
            )

    varies = []
    if correction:
        varies.append(
            "\nYour last call was rejected by the runtime.\n"
            f"  you called: {correction['node']}({json.dumps(correction['input'])})\n"
            f"  the runtime said: {correction['reason']}\n\n"
            "That message is a correction you can act on. Fix the arguments, call a different "
            "node, or stop if there is genuinely no answer to be had.\n"
        )

    return Prompt(
        [
            # ~18k tokens, byte-identical on every decision of every question.
            ("".join(fixed), True),
            # This breakpoint moves forward as calls accumulate. Each decision's prefix is
            # the previous decision's prefix plus one more result, so the cache is read for
            # everything already seen and written only for what is new.
            ("".join(asked), True),
            ("".join(varies), False),
        ],
        "planning",
    )


def narration_prompt(question, steps, history=()):
    verified = "\n".join(
        f"From {step['node']}:\n{json.dumps(step['result'], indent=2)}" for step in steps
    )

    # Figures in an earlier answer are quotable: they came from node calls in this same
    # conversation, so they are in this conversation's ledger and will attest. That is the
    # whole reason a follow-up can say "229 before, 245 now" without the check rejecting it.
    previous = ""
    answered = [turn for turn in history if turn.get("answer")]
    if answered:
        previous = (
            "\nAnswers already given in this conversation. Every figure in them came from a "
            "node call, so you may quote them when the user is asking what changed:\n\n"
            + "".join(f'  asked: "{t["question"]}"\n  answered: {t["answer"]}\n\n' for t in answered)
        )

    # The text is left exactly as it was. This is the one prompt where a model writes figures
    # of its own accord, it is the prompt the whole battery was worked against, and it is one
    # call in seven to seventeen — so there is very little to save here and a great deal to
    # confound. `Prompt` is only wrapped around it so `llm.py` can tell the two kinds apart.
    return Prompt(
        [
            (
                previous
                + f"""\
Answer the user's question in one to three plain sentences, using ONLY the values in the
verified results below.

Do not calculate anything. Do not introduce any number that does not appear below. If the
results do not contain what was asked for, say so plainly.

Numbers written inside a name or a sentence — a label like "Seppuku (only bleed; +30 phys AP)"
— are text, not computed figures. Describe them in words or leave them out; do not quote them
as numbers. Only a value that stands on its own in the results is a figure you may repeat.

Write in the language the user asked in. Weapon, spell, boss, talisman and Ash of War names
are proper nouns and stay exactly as the results spell them, whatever language you answer in.

The user asked: {question}

{verified}
""",
                False,
            )
        ],
        "narration",
    )


def declined(said, refused, steps):
    """A stop, said in the runtime's words where there are any, and with what was reached.

    Three things are wrong with relaying the model's sentence as-is.

    It is **the only model-authored prose the page renders**, and therefore the whole surface
    for anyone trying to use this as a free language model. Everything else the planner emits
    is a node name and an argument object, and the narrator never sees anything but verified
    results. Capping it closes that at no cost to a real answer, which is one sentence anyway.

    Where a node refused, the runtime already said why, in words written to be acted on — and
    those are better than a paraphrase of them. Quoting the paraphrase also loses which node
    said it.

    And a bare no throws away the work. Thirty-one of 122 question shapes end here, so this is
    a quarter of what a user sees, and by the time the loop stops it usually knows something:
    the honest answer to "how does stance-break work" is not "no", it is "no rule for that, but
    these nodes answered on the way and the arithmetic is yours".
    """
    said = " ".join(str(said).split())[:MAX_STOP]
    reached = list(dict.fromkeys(step["node"] for step in steps))

    out = {"reason": said, "reached": reached}
    if refused:
        out["reason"] = f"{refused['node']}: {refused['reason']}"
        out["relayed"] = said
    return out


# --------------------------------------------------------------------- attestation


def ledger_path(collection, session):
    return os.path.join(collection, ".vouch", "ledger", f"session-{safe_session(session)}.jsonl")


async def attest(collection, session, prose, question):
    """Check the model's sentences against this conversation's ledger.

    Everything upstream is enforced by the runtime. This is the one step where the model
    writes figures of its own accord, and so the one place a number can still be invented.
    The ledger is named explicitly rather than defaulted, so the check is against this
    conversation's calls and nothing else.

    Returns one of "attested", "failed", "unchecked", plus the lines explaining a failure.
    """
    ledger = ledger_path(collection, session)

    # If calls were made, this file exists. Its absence means our idea of where the ledger
    # lives disagrees with vouch's, which is a bug here and must not pass as "unchecked".
    if not os.path.exists(ledger):
        return "missing-ledger", [f"no ledger at {ledger}"]

    code, _, err = await _vouch(
        collection,
        session,
        "attest",
        "--ledger",
        ledger,
        "--text",
        prose,
        "--question",
        question,
    )
    if code == 0:
        return "attested", []
    if code == 1:
        return "failed", err.strip().splitlines()[1:]
    # Exit 2: the check could not run. Refusing on a technicality would be worse than saying
    # so, but the answer must not be presented as checked either.
    return "unchecked", [err.strip()]


# ------------------------------------------------------------------------- the loop


async def answer(question, collection, session, catalog, ask_model, history=()):
    """Yield events for one question. The caller decides how to render them.

    Event types:
        thinking   the model is deciding what to call, or writing the answer
        call       a node call is going out
        result     it came back verified
        refusal    a precondition said no — a correction, fed back to the model
        answer     prose, with `attestation` set to attested | failed | unchecked
        ask        a judgement is needed that belongs to the user; options come with it
        malformed  the model's reply would not parse; it is being told so and asked again
        no_answer  the honest out: nothing computed, or the model declined
        defect     a node broke its own contract; nothing is shown
        error      the loop itself could not continue
    """
    steps = []
    correction = None
    refusals = {}
    # The last thing the runtime actually said no about. `correction` is cleared as soon as it
    # has been shown to the model, and a stop usually arrives a decision later than the
    # refusal that caused it, so the reason worth quoting has to be kept separately.
    refused = None

    for _ in range(MAX_DECISIONS):
        yield {"type": "thinking", "what": "choosing a node"}
        reply = await ask_model(planning_prompt(question, catalog, steps, correction, history))
        correction = None

        try:
            decision = parse_json_reply(reply)
        except (ValueError, json.JSONDecodeError) as failure:
            # Not fatal. Models do emit near-JSON — `{"vigor": fifty}` was a real reply — and
            # the loop already has a way to say "that was rejected, try again". Handing the
            # parser's complaint back costs one decision and recovers the question, where
            # giving up costs the whole question and everything already spent on it.
            trouble = str(failure)
            yield {"type": "malformed", "reason": trouble}
            correction = {
                "node": "(your last reply)",
                "input": {},
                "reason": (
                    f"that was not valid JSON: {trouble}. Reply with one JSON object and "
                    "nothing else. Every number must be a numeral — 40, not 'forty'."
                ),
            }
            continue

        # A judgement the nodes will not make. Distinct from `stop`, because there is an
        # answer here — it is waiting on one value that belongs to the person asking. This is
        # the branch that lets a model obey "ask the user, or state what you assumed" without
        # the app turning the first half of that sentence into a dead end.
        if "ask" in decision:
            request = decision["ask"]
            if isinstance(request, str):
                request = {"question": request}
            yield {
                "type": "ask",
                "question": request.get("question", "I need one more detail."),
                "parameter": request.get("parameter"),
                "options": [o for o in request.get("options", []) if isinstance(o, dict)][:4],
            }
            return

        # The model declined. This is the honest out-of-scope path — and when it follows a
        # refusal, it is the model relaying a "no" the runtime established.
        if "stop" in decision:
            yield {"type": "no_answer", **declined(decision["stop"], refused, steps)}
            return

        if decision.get("done"):
            if not steps:
                yield {"type": "no_answer", "reason": "Nothing was computed to answer this."}
                return

            yield {"type": "thinking", "what": "writing the answer from verified results"}
            prose = await ask_model(narration_prompt(question, steps, history))

            verdict, detail = await attest(collection, session, prose, question)
            if verdict == "missing-ledger":
                yield {"type": "error", "reason": f"attestation could not find its ledger: {detail[0]}"}
                return
            if verdict == "failed":
                yield {"type": "answer", "attestation": "failed", "text": None, "detail": detail}
                return
            yield {
                "type": "answer",
                "attestation": verdict,
                "text": prose,
                "detail": detail,
            }
            return

        call = decision.get("call") or {}
        node, node_input = call.get("node"), call.get("input", {})
        if not node:
            yield {"type": "error", "reason": f"the model replied with no decision: {reply[:200]}"}
            return

        # A call this question has already made costs twice: the subprocess, and then a
        # second identical result carried in every remaining decision's prompt. Neither buys
        # anything — the node is deterministic, and its result is already in front of the
        # model. Hand back a correction instead, which is also the only thing that breaks the
        # model out of asking for it again.
        already = next(
            (s for s in steps if s["node"] == node and s["input"] == node_input), None
        )
        if already is not None:
            reason = (
                "you have already called that node with exactly those arguments in this "
                "question, and its result is listed above. Use it, call something else, or "
                "say you are done."
            )
            yield {"type": "refusal", "node": node, "reason": reason, "code": 0}
            correction = {"node": node, "input": node_input, "reason": reason}
            continue

        yield {"type": "call", "node": node, "input": node_input}
        code, out, err = await _vouch(
            collection, session, "call", node, "--input", json.dumps(node_input)
        )

        if code == 0:
            result = json.loads(out)
            steps.append({"node": node, "input": node_input, "result": result})
            yield {"type": "result", "node": node, "result": result}
            continue

        report = _report(err)
        reason = report.get("reason", "")
        details = report.get("details") or {}

        # A judgement the collection will not make is a question for the person, not a
        # correction for the model — and the options come from the manifest, so the model
        # never authors them.
        #
        # That distinction is not cosmetic. On question 4.1 a model looked up a weapon that
        # does not exist, invented a list of plausible-sounding weapons, and asked which was
        # meant; the harness took the first and the run produced an attested, complete answer
        # about a weapon nobody had asked about. Every figure in it traced to a real call. The
        # premise was fabricated one layer above where any check runs, because an `ask` the
        # model writes is the only text in this loop that becomes an *input* — and inputs are
        # deliberately outside attestation.
        if code == JUDGEMENT and details.get("judgement"):
            yield {
                "type": "ask",
                "question": details.get("guidance") or reason,
                "parameter": details["judgement"],
                "options": [
                    {"label": option.get("label") or "this one",
                     "value": {k: v for k, v in option.items() if k != "label"}}
                    for option in (details.get("options") or [])
                    if isinstance(option, dict)
                ][:4],
                "from": "collection",
            }
            return

        # A defect means the node is broken. Retrying is pointless and answering anyway would
        # be dishonest, so the loop stops here rather than working around it.
        if code in DEFECT or report.get("outcome") == "defect":
            yield {"type": "defect", "node": node, "reason": reason, "code": code}
            return

        # A refusal, or an input the schema rejected, is a correction. Hand it back.
        yield {"type": "refusal", "node": node, "reason": reason, "code": code}
        refusals[node] = refusals.get(node, 0) + 1

        # Refused this many times, it is not going to answer this question. Saying so is
        # better than letting the decision budget run out, because the reason a caller gets
        # then is "I ran out of attempts", which is true of the loop and tells them nothing
        # about their question.
        if refusals[node] >= MAX_REFUSALS_PER_NODE:
            yield {
                "type": "no_answer",
                **declined(
                    f"{node} refused {refusals[node]} times; it cannot answer this",
                    {"node": node, "reason": reason},
                    steps,
                ),
            }
            return

        correction = refused = {"node": node, "input": node_input, "reason": reason}
        if refusals[node] > 1:
            correction["reason"] = (
                f"{reason}\n\nThat is {node}'s {refusals[node]} refusal for this question. "
                "Trying it again with a different argument is a search, and this node is not "
                "a search. Call a different node, or stop."
            )

    yield {"type": "no_answer", "reason": "I ran out of attempts before reaching a verified answer."}
