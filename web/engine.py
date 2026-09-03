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

# How many decisions the model may make before the loop gives up. Enough for a couple of
# chained calls plus a correction, and low enough that a confused model cannot spin.
MAX_DECISIONS = int(os.environ.get("MAX_DECISIONS", "6"))

REFUSAL = {11, 14, 15}
DEFECT = {12, 13, 20, 21}


class Defect(Exception):
    """A node violated its own contract. The loop stops and no answer is shown."""


# --------------------------------------------------------------------- the runtime


async def _vouch(collection, session, *args):
    env = dict(os.environ, VOUCH_SESSION=session)
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

    Read once at startup and shared by every conversation: it is the same for all of them,
    and it is 4,000-odd tokens that would otherwise be re-read per question.
    """
    code, out, err = await _vouch(collection, "startup", "describe", "--all", "--json")
    if code != 0:
        raise RuntimeError(f"cannot read the collection: {_report(err)['reason']}")

    described = json.loads(out)
    return {
        "collection": described["collection"],
        "about": described.get("description"),
        "notes": described.get("notes", []),
        "nodes": [
            {
                "node": node["name"],
                "purpose": node["purpose"],
                "use_when": node["use_when"],
                "not_for": node["not_for"],
                "parameters": node["params"],
                "input_schema": node["input_schema"],
                "examples": node["examples"],
            }
            for node in described["nodes"]
        ],
    }


# ------------------------------------------------------------------------ the model


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

  {"stop": "<one sentence>"}
      No node can answer this, or a node has told you the answer does not exist. Say what you
      cannot answer and why.

Stopping is a good answer when it is the true one. Never pick a node that is merely close,
and never fill a parameter with a number you invented — a wrong answer is worse than none.
"""


def planning_prompt(question, catalog, steps, correction):
    prompt = [
        PLANNING_RULES,
        "\nThe collection you are working with:\n",
        json.dumps(catalog, indent=2),
        f"\n\nThe user asked: {question}\n",
    ]

    if steps:
        prompt.append("\nCalls made so far, and their verified results:\n")
        for step in steps:
            prompt.append(
                f"  {step['node']}({json.dumps(step['input'])})\n"
                f"    → {json.dumps(step['result'])}\n"
            )

    if correction:
        prompt.append(
            "\nYour last call was rejected by the runtime.\n"
            f"  you called: {correction['node']}({json.dumps(correction['input'])})\n"
            f"  the runtime said: {correction['reason']}\n\n"
            "That message is a correction you can act on. Fix the arguments, call a different "
            "node, or stop if there is genuinely no answer to be had.\n"
        )

    return "".join(prompt)


def narration_prompt(question, steps):
    verified = "\n".join(
        f"From {step['node']}:\n{json.dumps(step['result'], indent=2)}" for step in steps
    )
    return f"""\
Answer the user's question in one to three plain sentences, using ONLY the values in the
verified results below.

Do not calculate anything. Do not introduce any number that does not appear below. If the
results do not contain what was asked for, say so plainly.

Numbers written inside a name or a sentence — a label like "Seppuku (only bleed; +30 phys AP)"
— are text, not computed figures. Describe them in words or leave them out; do not quote them
as numbers. Only a value that stands on its own in the results is a figure you may repeat.

The user asked: {question}

{verified}
"""


# --------------------------------------------------------------------- attestation


async def attest(collection, session, prose, question):
    """Check the model's sentences against this conversation's ledger.

    Everything upstream is enforced by the runtime. This is the one step where the model
    writes figures of its own accord, and so the one place a number can still be invented.
    The ledger is named explicitly rather than defaulted, so the check is against this
    conversation's calls and nothing else.

    Returns one of "attested", "failed", "unchecked", plus the lines explaining a failure.
    """
    ledger = os.path.join(collection, ".vouch", "ledger", f"session-{session}.jsonl")
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


async def answer(question, collection, session, catalog, ask_model):
    """Yield events for one question. The caller decides how to render them.

    Event types:
        thinking   the model is deciding what to call, or writing the answer
        call       a node call is going out
        result     it came back verified
        refusal    a precondition said no — a correction, fed back to the model
        answer     prose, with `attestation` set to attested | failed | unchecked
        no_answer  the honest out: nothing computed, or the model declined
        defect     a node broke its own contract; nothing is shown
        error      the loop itself could not continue
    """
    steps = []
    correction = None

    for _ in range(MAX_DECISIONS):
        yield {"type": "thinking", "what": "choosing a node"}
        reply = await ask_model(planning_prompt(question, catalog, steps, correction))
        correction = None

        try:
            decision = parse_json_reply(reply)
        except (ValueError, json.JSONDecodeError) as failure:
            yield {"type": "error", "reason": str(failure)}
            return

        # The model declined. This is the honest out-of-scope path — and when it follows a
        # refusal, it is the model relaying a "no" the runtime established.
        if "stop" in decision:
            yield {"type": "no_answer", "reason": decision["stop"]}
            return

        if decision.get("done"):
            if not steps:
                yield {"type": "no_answer", "reason": "Nothing was computed to answer this."}
                return

            yield {"type": "thinking", "what": "writing the answer from verified results"}
            prose = await ask_model(narration_prompt(question, steps))

            verdict, detail = await attest(collection, session, prose, question)
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

        # A defect means the node is broken. Retrying is pointless and answering anyway would
        # be dishonest, so the loop stops here rather than working around it.
        if code in DEFECT or report.get("outcome") == "defect":
            yield {"type": "defect", "node": node, "reason": reason, "code": code}
            return

        # A refusal, or an input the schema rejected, is a correction. Hand it back.
        yield {"type": "refusal", "node": node, "reason": reason, "code": code}
        correction = {"node": node, "input": node_input, "reason": reason}

    yield {"type": "no_answer", "reason": "I ran out of attempts before reaching a verified answer."}
