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

### Reaching it from another machine

The default is `127.0.0.1`, so nothing off the box can see it. To open it up:

```console
$ ACCESS_TOKEN=$(openssl rand -hex 16) HOST=0.0.0.0 ./run.sh
$ sudo firewall-cmd --add-port=8000/tcp        # this boot only; add --permanent to keep it
```

then visit `http://<the box's LAN address>:8000/?k=<the token>`. `run.sh` refuses to bind
anything but the loopback without `ACCESS_TOKEN`, because this endpoint spends model calls on
somebody's account and has no other authentication; the page carries the key through to `/ask`,
so one link is enough to share and a bare `/ask` is still 403.

That is a LAN, not the internet. From another network the honest options are an SSH tunnel
(`ssh -L 8000:localhost:8000 <the box>`, which needs no server change and no open port) or a
tunnelling service such as Cloudflare Tunnel or Tailscale. Do not port-forward this.

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

## Follow-up questions

A conversation is carried forward, so *"and if I moved those points to dexterity instead?"*
works. What gets carried is deliberately partial:

- **the earlier questions, and the calls with their inputs** — which is where *"the Longsword,
  at this spread"* actually lives;
- **the answers that were given**, including the turns that gave none, since a node refusing
  for want of a weapon is usually followed by the user naming one;
- **not the earlier results.** A follow-up is nearly always a change, and handing back the
  previous turn's numbers invites the model to narrate from them instead of calling again with
  the new values — the one way an answer could be wrong while every contract still held.

The narrator *may* quote figures from an earlier answer, and is told why it may: those came
from node calls in this same conversation, so they are in this conversation's ledger and will
attest. That is what lets a follow-up say *"820 before, 694 now"* and pass the check.

**The cost is that attestation gets looser as a conversation grows.** A numeral attests if any
call in the ledger returned it, so a longer ledger accounts for more numbers by accident —
`scripts/stress_attest.py` measured 19% of the integers 1–99 at two calls and 40% at
twenty-nine. `KEEP_TURNS` bounds the prompt; starting a new conversation is what bounds the
ledger, and the button in the header is therefore a real reset rather than a cosmetic one.

Conversations live in memory, capped by `KEEP_TURNS`, `KEEP_CONVERSATIONS` and
`CONVERSATION_TTL`, and are gone on restart. The durable half is the ledger on disk, which is
what answers are checked against; losing the rest costs a user their thread, not correctness.

## What is checked, and what is not

```console
$ node test_client.mjs           # the client, against a stub DOM. No browser, no network.
$ .venv/bin/python test_server.py  # the loop and the store, with a scripted model.
```

`test_server.py` cans the model's replies and lets everything else be real: real `vouch call`
subprocesses, real contracts, real attestation against a real ledger. So it checks that a
fabricated figure is caught and that the second turn is planned with the first in front of the
model, and it costs nothing to run as often as you like — which the battery does not.

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
- **No static answers.** `VALIDATION.md` holds 122 questions with verified answers that could
  be served with no model in the loop at all.
- **Nothing durable behind the rate limit.** It is a dict in memory and resets on restart.
