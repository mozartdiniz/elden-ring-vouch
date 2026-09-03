# Serving this as a web app — a design conversation, not a decision

*3 September 2026. Nothing here is built.* This records a brainstorm: what it would take to put
the collection behind a public chat interface, what it would cost, and how to talk about it
afterwards. It exists so the reasoning survives, including the parts that argue against.

`HANDOFF.md` is where the work stands. This is where it might go next.

---

## The idea

A web page with a chat box. Someone asks an Elden Ring question in English; an LLM reached
through the OpenRouter API decides which nodes to call and with what arguments; the nodes run;
the model turns the verified results into a sentence. Where the question is under-specified the
app asks back rather than guessing.

Public, linked from Reddit, cheap to run.

## What already exists, and should not be rewritten

**`~/Dev/vouch/examples/ask.py` is this app's backend.** Two hundred and ninety-one lines:
`load_catalog` → `plan` (one node call at a time, each result fed back into the next decision)
→ `narrate` → `attest`. It is the reference implementation of the loop and it is already
correct about the hard part.

The hard part is that **the three exit-code families drive three different behaviours**, and
that mapping is the app's whole interaction design:

| family | codes | what the app does |
|---|---|---|
| success | 0 | narrate the numbers |
| **refusal** | 11, 14, 15 | correct course, then ask the user — this is where clarifying questions come from |
| **defect** | 12, 13, 20, 21 | stop. Never answer. Log it and page yourself |

The defect branch is not negotiable. A node that violated its own contract must not reach a
user at all — not as an error toast with a best guess underneath. That is the one behaviour
that distinguishes this from a chatbot with a database.

## Clarification is data the collection already emits

Do not prompt a model to "ask a clarifying question". The nodes produce them as structured
results, and the app should render them as buttons rather than prose:

- `weapon-lookup`, `spell-lookup`, `boss-lookup` → `ambiguous: true` with `candidates`. Ten
  weapons contain "knight sword"; nine Death Rite Birds differ only by `location`.
- `spell-lookup` → `forms`. Comet and Comet - Charged are different spells with different
  attack values, and picking one silently is how a charged cast gets reported as an ordinary
  one.
- `build-allocate` → **requires** vigor, mind and endurance floors and will not invent them.
  That is the one natural up-front question, with defaults pre-filled and labelled as chosen.
- `ash-rank` → `rank_on` is four questions with four different winners.

A chip-picker beats free text twice over: it is a better interaction and it costs no tokens.

## Attestation is the product

Everything upstream — schemas, contracts, exit codes — is enforced. The final narration is the
one place a number can still be invented, and `vouch attest` is the check:

```console
$ vouch attest --ledger <this conversation> --text "<the model's prose>" \
    --question "<what the user asked>" --json
```

Exit 0 every numeral traces to a node result; exit 1 one did not; exit 2 the check could not
run, and the answer must then be shown as **unchecked** rather than as verified. On exit 1 the
app does not show the answer.

There is a stronger version available and it is the demo: the ledger records every `result.*`
scalar per call, so each figure in the UI can be traced back to the call that produced it.
*"679.39 — attack-power, Treespear Standard +25, at your spread."* No other Elden Ring
assistant can offer that, and it is the reason to build this rather than fine-tune something.

**Set `VOUCH_SESSION` once per conversation.** `attest` defaults to the most recent session
file in `.vouch/ledger/`, so concurrent users would otherwise attest against each other's
numbers. A smaller ledger is also a stricter check.

## What it costs to run

### The box is cheap and flat

Measured, on this machine:

| node | wall time | peak RSS |
|---|---|---|
| `boss-coverage` | 0.02 s | 13 MB |
| `attack-power` | 0.33 s | 53 MB |
| `weapon-rank` (489 weapons × 13 affinities) | 0.56 s | 54 MB |
| `build-allocate` (worst realistic case) | 2.77 s | 79 MB |

Eighty megabytes and three seconds at the worst. A 2 vCPU / 4 GB VPS — Hetzner CX22 at about
€4/month, or the equivalent elsewhere — is comfortable.

**Serverless does not work here.** Cloudflare Workers cannot spawn subprocesses at all;
Vercel and Netlify hobby tiers cap execution around ten seconds and are not built to carry a
Rust binary plus Python. This needs a plain box with a writable filesystem, because `vouch
call` is a subprocess and the ledger is a file. Avoid free tiers that sleep: a cold start means
re-reading two megabytes of CSV on the first request.

Put a **concurrency cap and a queue** in front of the node calls. Reddit traffic is spiky, and
twenty simultaneous `build-allocate` calls on two cores is the only plausible way to fall over.

### The tokens are the real cost, and they are not flat

The routing context was measured properly for the first time in this conversation — the
handoff had it recorded as unmeasured:

| | tokens |
|---|---|
| `vouch describe --all --json`, everything | ~60,000 |
| **what `ask.py` actually sends** (drops output schemas and contracts) | **~21,300** |
| the preamble notes alone | 4,200 |
| median node | 845 |
| build-allocate, the largest node | 1,638 |
| a lean tool definition (name, purpose, use_when, input schema) | 8,500 total |

At ~21.3k tokens per model call and two to four calls per question, **call it 60k input tokens
a question**. At $P per million input tokens that is about `$0.06 × P` per question:

| model tier | per question | per 1,000 questions |
|---|---|---|
| ~$0.10/M | $0.006 | $6 |
| ~$0.50/M | $0.03 | $30 |
| ~$3.00/M | $0.18 | $180 |

A Reddit post that does moderately well is easily three thousand questions, so the spread is
roughly $18 to $540 — decided entirely by choices made before posting.

### Four levers, roughly multiplicative

1. **Prompt caching.** The catalog is byte-identical every turn. Biggest cut for no design
   change; check which OpenRouter providers honour it.
2. **Two-stage routing.** A cheap model picks two or three nodes from a ~1.5k-token index of
   names and purposes; the better model then gets only those nodes' full guidance at ~845
   tokens each. 21k → ~4k.
3. **A cheap model, deliberately.** Routing is "pick a node and fill a JSON schema"; narration
   is "read these numbers back". Neither is frontier work — and the contracts and attestation
   catch the mistakes, which is the point. **A cheap model is affordable here precisely because
   the system does not trust it.**
4. **Cache normalised questions.** Reddit asks the same thing fifty times.

### Hard caps, before anything is public

- A **spend limit on the OpenRouter key itself**, set to what is acceptable to lose. Not a soft
  check in application code.
- An **app-level daily budget** that degrades rather than fails: "today's budget is spent, here
  are the answers already computed."
- **Per-IP and per-session rate limits.** A public LLM endpoint is a free token faucet, and an
  off-topic question still costs tokens even when it fails to route.
- **Optional bring-your-own-key**, so the heaviest users pay for themselves.

### The free move

`VALIDATION.md` holds 122 real questions with verified answers. Ship them as **static pages
with no model in the loop** — an FAQ that costs nothing, doubles as something to link, and
covers the questions most likely to be asked. Reach for the model only when the question is new.

## Two decisions still open

**Native tool-calling, or `ask.py`'s JSON protocol?** OpenRouter offers OpenAI-style function
calling, and every node already has an `input.schema.json`. Going native buys structured
arguments and parallel calls for free. The thing not to lose in the translation is
`params.*.guidance` — *"pass `max_upgrade` from weapon-lookup, or an impossible upgrade is only
caught after the fact"* — which is where the traps are recorded. Fold each guidance string into
the corresponding JSON Schema `description`, which is where a function-calling model reads.

**How much of the preamble survives.** Sixty notes, 4,200 tokens, carried on every call. Some
of them are per-node advice that belongs in a tool description; some are collection-level rules
that have nowhere else to live. Pruning it is already the top open item in `BUGS.md`, and this
is the forcing function.

## What not to do

**Do not bypass `vouch call`.** The nodes are Python and importing them directly would be
faster. `vouch call` *is* the contract boundary: without it there is no schema check, no
postcondition, no exit-code taxonomy and no ledger — and therefore nothing to attest against.
What is left is a chatbot with CSVs. If process start-up hurts, use a warm subprocess pool.

## The first slice

One endpoint, no chat history, no accounts: question in, then plan → call → narrate → attest,
and out comes the answer plus the trace of calls behind it.

Point it at the 122 questions in `VALIDATION.md` as a live regression suite — the correct
answers are already written down. That also finally does the thing at the top of the pending
list: it puts the eight nodes that have never been in front of a live model in front of one.

---

## Talking about it afterwards

The collection is a second implementation of an ontology built at Prometheux, and there is a
real question about how to say so without the whole thing reading as marketing. The conclusion
was: **split it into two posts with different audiences, and let neither do both jobs.**

**The gaming post has essentially no Prometheux in it.** r/Eldenring wants the tool. A company
name in a gaming post is exactly what gets it read as an advert, and the tool is more
persuasive on its own. The material there is the findings, which are genuinely interesting:
Bloodflame Blade does not stack with a Blood affinity because it does not apply at all; 84 of
238 boss phases are immune to bleed; 40/40 quality loses to committing, 416 against 458 on a
Longsword; Lusat's is +10.2% damage for +50% FP; vigor 40 → 41 is the most valuable single
level in the game at 48 HP.

**The engineering post is where the connection belongs, as a fact rather than a pitch.** "I
built a domain ontology at work, then rebuilt it from scratch on a different runtime to find
out what two independent implementations would catch" is accurate, contains the employer, and
reads as credentials because it is load-bearing to the story. The same information appended as
a positioning statement reads as copy. The difference is whether the company is *in* the story
or *attached to* it.

Three things keep it from reading as promotion:

1. **Lead with what the method got wrong.** Two independent implementations are supposed to
   catch each other's bugs; ours did not. Every incantation in the game priced at zero because
   both implementations read the same wrong column and agreed with each other perfectly. Bug 17
   survived 122 questions and was found by three PDFs of the source spreadsheet. Bug 22 is a
   guard that already existed, missing from two nodes written after it was written. None of
   that appears in an advert, and it is the most interesting material in the project.
2. **Give the technique away whole.** The two audit questions in `BUGS.md` found five bugs
   between them and can be applied by anyone tomorrow without buying anything. Advice that is
   useful to a non-customer is not advertising.
3. **Disclose once, plainly, at the bottom.** Undisclosed promotion is what gets punished;
   disclosed, it stops being an issue and cannot be framed by somebody else first.

**Do not overclaim the bridge.** The transferable finding is narrow, and stating it narrowly is
what makes it credible: *an LLM fabricates precisely where you leave it one small sum.*
`HANDOFF.md` has fourteen documented instances, each fixed upstream of where it appeared rather
than by prompting harder. That generalises to any domain and requires no one to care about
Elden Ring. "And therefore enterprise knowledge graphs" is a jump the reader can make
unassisted, and will trust more for not being told.

**Talk to Prometheux before it goes up.** This is a public reimplementation of work built
there, so it needs a word regardless — and the useful part is that a blessing converts the
problem from "how do I mention this subtly" into "we both post it", which is a better position
than the one the question started from.
