# The web app

A chat box in front of the collection. A question goes in; the model chooses nodes and builds
their arguments; `vouch` runs them and checks their contracts; the model writes a sentence from
the results; `vouch attest` checks every numeral in that sentence against the ledger before
anyone sees it. If a figure cannot be traced, the answer is not shown.

The model never does arithmetic. That is the whole point, and it is the only claim here worth
making.

## Layout

```
web/
  app.py        one endpoint, rate limits, static files
  engine.py     the loop — plan → call → narrate → attest — as a stream of events
  llm.py        two backends behind one signature: the Claude CLI, or OpenRouter
  static/       index.html, app.js, style.css. No build step, no bundler, no framework.
```

`engine.py` is `~/Dev/vouch/examples/ask.py` with its I/O ends changed and its logic left
alone. **The planning and narration prompts are copied verbatim** because they are the part
that has been exercised; if that file's prompts change, change these to match.

The collection itself is the parent directory. Nothing in `web/` is imported by a node, and
nothing in `web/` writes to `data/`, `nodes/` or `oracle/`.

## Running it

```console
$ python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
$ cp .env.example .env          # optional; the defaults work locally
$ .venv/bin/uvicorn app:app --reload --port 8000
```

`vouch` must be on `PATH`, or `VOUCH_BIN` must point at it.

With `LLM_BACKEND=claude` it shells out to the Claude CLI session already on this machine,
which costs nothing extra and is how it was developed. That is not a deployment: on a public
box every visitor would be sharing one logged-in account. Deployed, it is
`LLM_BACKEND=openrouter` with a spend limit set **on the key itself**, not in application code.

## The three outcomes are the interaction design

| exit codes | what the user sees |
|---|---|
| 0 | the answer, with an attestation badge |
| 11, 14, 15 — **refusal** | a step in the trace. The runtime's reason is written to be acted on, so it goes back to the model and the turn continues |
| 12, 13, 20, 21 — **defect** | the turn ends with no answer at all. Not a hedged one, not a best guess |

The defect branch is not negotiable. A node that violated its own contract must not reach a
user, and an app that quietly works around one has given up the only thing it had.

## One ledger per conversation

`engine.py` sets `VOUCH_SESSION` for every subprocess and `attest` names the ledger file
explicitly. Neither is a tidiness preference.

Left alone, `ledger::session_id()` falls back to **today's date**, so every visitor would
attest against every other visitor's numbers. The stress test in `scripts/stress_attest.py`
measured the cost: a numeral attests if *any* call in the ledger returned it, and in a
day-sized ledger 96 of the integers 1–99 are already present. A fabricated *"you need 7 more
points"* would attest clean. A ledger per conversation is both the correct scope and a
strictly better check.

## What is checked, and what is not

```console
$ node test_client.mjs      # the client, against a stub DOM. No browser, no network.
```

Nine checks, one per event branch plus the fragile one: a JSON event split across two network
chunks, and again at one byte per chunk. Two of them exist to hold a line rather than to catch
a typo — **a failed attestation must show no answer text**, and **a defect must end the turn** —
because those are the behaviours that would be easiest to soften later and are the only reason
any of this is worth more than a chatbot with a database.

The server's request path is checked by hand with `LLM_BACKEND` set to a nonsense value, which
exercises rejection, rate limiting and the streaming error branch without spending a model
call. Conversation ids are checked against traversal, since they become ledger filenames.

**Not checked: how the page looks.** Nothing here has ever run in a browser — no layout, no
textarea autosize, no scrolling. Open it and see.

## What this slice does not do

- **No clarification chips.** `weapon-lookup` and `spell-lookup` already return `ambiguous`
  with `candidates`, and `ash-rank` returns `rank_on` — four questions with four different
  winners. Rendering those as buttons is a better interaction than free text *and* costs no
  tokens. It is the next thing to build.
- **No conversation history.** Each question is planned from scratch. The ledger persists per
  conversation, the transcript does not.
- **No static answers.** `VALIDATION.md` holds 122 questions with verified answers that could
  be served with no model in the loop at all.
- **Nothing durable behind the rate limit.** It is a dict in memory and resets on restart.
