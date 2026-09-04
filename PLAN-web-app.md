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

## Attestation was stress-tested before any of this was built

`vouch attest` needs no model, so it did not need the app to be exercised. `scripts/stress_attest.py`
runs three things for free, and they changed what this document asks for.

**The precision rule is exactly right.** Against a real attack rating of 853.1751…:

| quoted as | verdict |
|---|---|
| 853.18, 853.2, **853** | attested — a rounded or truncated quotation of a real figure |
| 850, 854 | rejected |

So the app can let the narrator quote the number the game shows without the check tripping,
and it still catches the adjacent integer.

**A mutation sweep caught 23 of 24.** Take a paragraph every numeral of which came from a node,
mutate each numeral four ways — adjacent digit, adjacent whole, extra decimal, +0.1% — and
attest each mutant. Twenty-three rejected.

**The one miss is the failure mode the app has to design around.** It was `faith 70 → 80`, and
80 slipped through *because the ledger contained an 80* from another call in the same session.
A numeral attests if **some** call in the session returned it, so a value that collides with
any other figure is invisible. Which leads to the measurement that matters:

| ledger | calls | distinct scalars | integers 1–99 that collide |
|---|---|---|---|
| one conversation | 2 | 29 | **19%** |
| a small run | 29 | 165 | 40% |
| **one day's work** | 238 | 1,186 | **96%** |
| **one day's work** | 277 | 989 | **99%** |

`ledger::session_id()` falls back to the **date** when `VOUCH_SESSION` is unset. So the default
configuration, for a single user with no concurrency at all, already accounts for essentially
every small integer: a fabricated *"you need 7 more points"* or *"go to 40 vigor"* attests
clean. Per-conversation sessions are not hygiene, they are the difference between the check
working and not, and the effect is quantified above.

**Two consequences for the app:**

1. **`VOUCH_SESSION` per conversation, enforced in code, never defaulted.** This was already the
   concurrency rule below; it turns out to matter single-threaded too.
2. **The narrator must be told to write no numeral it did not take from a result.** Ordinals
   and asides — "ranked 1st", "around 850" — are rejected, correctly, and would fail an
   otherwise good answer. Either forbid them in the prompt or pass `--question` so figures the
   user supplied are not counted as fabrication.

**And one thing worth knowing about the check's reach.** The paragraph first fed to the sweep
failed its baseline, on `97.73` — a figure this assistant produced by subtracting two node
results while writing the build evaluation, unprompted and without noticing. Nothing else in
the pipeline would have caught it. That is the whole argument for the last line existing.

## Concurrency, and the one thing that breaks quietly

Two places want it, and they want it for the same reason: almost all the wall time is spent
waiting on a model, not computing.

**In the app.** Several questions in flight at once. A question is two to four model calls —
call it eight to thirty seconds of network — wrapped around node calls that take between 0.02
and 2.77 seconds of CPU. Serving those serially would waste the machine entirely.

**In `vouch eval`.** It is serial today: no `-j`, no concurrency flag, cases × `-n` runs one
after another. That is why an early run went six silent minutes over eighteen model calls. A
refreshed suite covering all nineteen nodes is perhaps forty cases; at `-n 3` that is 120 model
calls, twenty minutes serially. At eight in flight it is two or three. **That is the difference
between running the evals before every change and running them once a month**, which is the
whole argument — the suite being stale is already the top item on the pending list, and part of
why it is stale is that running it hurts.

### The rule: one `VOUCH_SESSION` per unit of work

`ledger::session_id()` falls back to **today's date** when `VOUCH_SESSION` is unset, so
everything run on one day appends to one `session-YYYYMMDD.jsonl`. That is fine for a person at
a terminal and wrong for anything concurrent. Set it per conversation in the app, and per case
run in the eval harness.

Two hazards follow from not doing it, and they are not equally obvious:

**The loud one: interleaved writes.** Every `vouch call` appends a line to the session file.
The entries are large — one sampled here carried dozens of scalars and ran well past four
kilobytes — so an append is not atomic under the usual POSIX guarantee. Two processes writing
the same file can interleave mid-line and corrupt it. This one at least fails visibly.

**The quiet one, which is worse: attestation silently loosens.** `attest` accounts for a
numeral if *some call in the session* produced it. Share a session across two conversations and
a figure fabricated in one can be accounted for by a call made in the other. Nothing errors.
The check does not fail — **it stops checking**, and the report still says the answer was
attested. For a system whose entire claim is "every number came from a node", that is the
failure mode to design against first.

A smaller ledger is a stricter check. Concurrency makes that a correctness requirement rather
than a nicety.

### The shape: wide on the model, narrow on the nodes

A request is I/O-bound with short CPU bursts, so the two limits are different by an order of
magnitude:

- **Model calls: many in flight.** Bounded by the provider's rate limit, not by the box. Needs
  backoff on 429s; a burst of parallel evals is exactly what trips them.
- **Node calls: a semaphore at roughly the core count.** Measured, `build-allocate` is 2.77 s
  and 79 MB at its worst. On two cores, three of those at once is already queueing, and twenty
  is how the box falls over.

Same rule for both the app and a parallel eval harness.

### Parallel results must equal serial results

Nodes are pure functions of their input plus read-only CSVs. Nothing is shared but the ledger,
and per-session ledgers remove even that. So concurrency must not change a single figure, and
that is testable rather than assumed: run the suite once serially, once at `-j 8`, and diff.
If they differ, something is sharing state that should not be.

The same property is what makes the 122 questions in `VALIDATION.md` usable as a parallel
regression suite — the answers are already written down, and they cannot legitimately move.

### Where it lands is a fork

**In the runtime** as `vouch eval -j N`: everyone gets it, it belongs next to the serial
implementation, and the session-per-case rule can be enforced there rather than remembered by
each harness. It is also a change to a tool that is otherwise stable, and the runtime has never
served concurrent work — see `DECISIONS.md`.

**In the app's own harness**, ported from `examples/ask.py`: no runtime change, and the app
needs its own concurrency control anyway for live traffic. The cost is that the eval suite and
the app then run two different loops, which is precisely what `ask.py`'s own docstring warns
against — "building a second, eval-only description would measure a context nobody ships".

Leaning towards the runtime for `eval -j`, because the session-per-case rule is the kind of
thing that should be impossible to forget rather than documented.

## The first slice — built, 3 September

`web/`, four files and a static page. `app.py` is one endpoint streaming NDJSON; `engine.py`
is `ask.py` with its I/O ends changed and its prompts copied verbatim; `llm.py` puts the
Claude CLI and OpenRouter behind one signature; `static/` has no build step. `VOUCH_SESSION`
is set per conversation and the ledger named explicitly, as the stress test required.

**Three questions through it found two things, and both are about attestation's edges.**

1. *"Does Bloodflame Blade stack with a Blood affinity?"* produced a correct answer that was
   **withheld**. `weapon-lookup` returns `buff: "Seppuku (only bleed; +30 phys AP)"` — the 30
   is inside a label, the ledger holds scalars, so `attest` exited 1 on a true figure. The
   large version of this is `item-effect`, whose whole payload is effect prose full of
   numbers, none of them traceable. Now in `BUGS.md`; the app works around the small case in
   its narration prompt, which is a guard living in one place again.
2. *"What levels for a level 125 Zweihander build?"* produced an answer that **attested and
   should not have**. The model invented `vigor 40, mind 12, endurance 20` and
   `starting_class: "Wretch"`, and `build-allocate` returned them in `stats`, so they traced.
   Attestation cannot tell a computed figure from a guess a node echoed back.

Neither is a bug in the runtime and neither would have shown up in a fixture. They are the
boundary of what "every number came from a node" actually buys, and the app is where you find
it, because the app is the first thing that lets a model choose parameters unsupervised.

## Follow-up questions, and what the ledger was already doing

Each question was planned from scratch, so *"and if I moved those points to dexterity?"* had
nothing to refer to. The fix turned out to be smaller than expected, because **the ledger was
already per-conversation** — only the prompts were not. Adding the memory to the prompts made
multi-turn comparison attest for free:

> **turn 1** — *"best weapons at STR 55 / DEX 14?"* → Great Club, 820 total AR.
> **turn 2** — *"and if I moved those points to dexterity?"* → weapon-rank called again at
> STR 14 / DEX 55; Rakshasa's Great Katana at 694, *"a lower ceiling than the strength
> build's 820"*. **Attested** — 820 came from turn 1's call, in the same ledger.

What is carried is the earlier questions, the calls **with their inputs**, and the answers.
Deliberately **not** the earlier results: a follow-up is almost always a change, and handing
back the previous numbers invites narration from stale results instead of a fresh call, which
is the one way an answer could be wrong while every contract still held. Turns that gave *no*
answer are carried too, and are the more useful half — a node refusing for want of a weapon is
usually followed by the user naming one, which is the clarification loop arriving early.

**The trade is real and measurable.** A numeral attests if any call in the ledger returned it,
so a longer conversation accounts for more numbers by accident: 19% of the integers 1–99 at
two calls, 40% at twenty-nine. `KEEP_TURNS` bounds the prompt; only starting a new conversation
bounds the ledger. That makes the reset button part of the correctness story rather than a
convenience, which is worth saying out loud in the UI eventually.

## Which models can drive this, and what they cost

The suspicion was that only Anthropic models could work the collection. The suspicion was
wrong, and what it was hiding is more useful.

**The protocol is not the problem.** All four of `openai/gpt-5.6-sol`, `openai/gpt-5.6-luna`,
`x-ai/grok-4.6` and `moonshotai/kimi-k3` return clean, correct JSON on the first decision.

**The problem was that the collection offered a move the app could not make.** `build-allocate`'s
vigor guidance reads *"This is a judgement and the node will not make it: **ask the user**, or
state the figure you assumed and why."* Two legal moves. kimi and grok assumed and disclosed;
both OpenAI models chose to ask — and the app had no way to ask, so their correct behaviour
arrived as a shrug. The same sentence explains battery questions 2.8, 1.4 and 1.2.

So `ask` is now a fourth decision shape alongside `call`, `done` and `stop`, carrying a
parameter and two to four options with the conventional one first, rendered as chips. It is
not an error path: it is the question the collection needs answered before it can compute
anything, and every model that was failing now reaches an attested answer through it.

### Three bugs found by pointing other vendors' models at it

1. **The ledger path was built by string interpolation.** `x-ai/grok-4.6` contains a dot;
   vouch rewrites that when it names the file; `attest` then looked for a ledger that did not
   exist, exited 2, and the answer was shown as **UNCHECKED**. A silent downgrade of the only
   check that matters, and no Anthropic-only run would ever have produced it. Sessions are now
   sanitised at the source, and a missing ledger is a loud error rather than a shrug.
2. **Picking an option sent its caption, not its values.** Models label options *"Padrão
   recomendado"* and put `{vigor: 40, mind: 20, endurance: 25}` in `value`. Sending the caption
   back asks the same question again — which is how `gpt-5.6-luna` asked three times and then
   emitted `"vigor": fifty` as JSON. Both the harness and the browser now send the values.
3. **Reasoning tokens come out of `max_tokens`.** `kimi-k3` spent 663 of 707 completion tokens
   thinking and returned empty `content`, which read downstream as "the model said nothing".
   The budget is now 6,000, and an empty reply is an explicit error rather than an empty string
   flowing into the parser.

A malformed reply is also no longer fatal. The loop already knew how to say *"that was
rejected, try again"* for runtime refusals; a parser complaint now goes back the same way,
costing one decision instead of the whole question.

### With `ask` available, all four work — and two reproduce the record exactly

Question 1.1, Rivers of Blood at RL150, after the fixes: **4 of 4 answered, 4 of 4 attested.**
The interesting part is that they did not give the same answer, and every difference traces to
the judgement each model made at the `ask` — which it then disclosed.

| model | chose | answered | against the record |
|---|---|---|---|
| `x-ai/grok-4.6` | 40/20/25, attack | STR 12 · DEX 56 · ARC 59, **675** AR, 76 bleed | the attack row: 675.826 / 76.4 |
| `moonshotai/kimi-k3` | 40/20/25, **bleed** | STR 12 · DEX 18 · ARC 97, **644** AR, 79 bleed | the bleed row: 644.748 / 79.5 |
| `openai/gpt-5.6-sol` | vigor **50**, attack | 662 AR at a different spread | correct for its own premise |
| `openai/gpt-5.6-luna` | 40/20/25 | 396 physical / 279 fire / 76 bleed | grok's build, narrated without the spread |

The recorded entry for 1.1 has **two** rows, one per focus, and two different models reproduced
one each to the digit. Neither is wrong; they answered different readings of a question that
did not say which it meant. That is the whole argument for `ask` in one table — and it is also
the sharpest evidence yet for the caveat now sitting under `VALIDATION.md`'s status legend,
that a `[x]` records a question someone had already settled.

`luna`'s answer is the weak one, and not because a number is wrong: it never states the spread
the user asked for. Cheapest is not free.

### The stress test: one hard question, four models, twice each

Question 7.1 was the right one to pick because it **states its own stats** — *"my bleed build
on the Gargoyle's Twinblade (STR 40 / DEX 23 / ARC 12) doesn't work on Radagon and the Elden
Beast, which affinity do I switch to?"* — so there is no judgement to make and the answers are
directly comparable. It needs seven to ten calls across `weapon-lookup`, `boss-lookup` twice
and `optimal-affinity` twice.

**8 of 8 answered. 8 of 8 attested. 8 of 8 gave the same answer: Fire for Radagon, Heavy for
the Elden Beast** — which is what the record says too.

The numbers behind that agreement did not agree, and every difference traces to a parameter
the question never supplied:

| model | repeats | what it did |
|---|---|---|
| `x-ai/grok-4.6` | **identical** | filled int/faith at 10, one-handed, never asked |
| `moonshotai/kimi-k3` | **identical** | the same, byte for byte — 342 and 357 |
| `openai/gpt-5.6-sol` | **differed** | asked about class and grip; took *"Vagabond, two-handed"* in one run and not the other, giving 383 / 423 once and no figures at all the second time |
| `openai/gpt-5.6-luna` | **differed** | asked for a starting class, got Wretch, and passed `faith: 1, intelligence: 1` on one call before correcting itself |

Two of the four are **bit-identical across repeats**, with byte-identical inputs to
`optimal-affinity`. The two that drifted are the two that used `ask` — and the drift is not in
which option was chosen (the harness always takes the first) but in **which options the model
offered**. So `ask` buys honesty about a missing parameter and spends determinism to get it.
That is the right trade for a person at a keyboard and the wrong one for a regression suite,
which is worth knowing before the 122 questions are run this way.

Every figure produced was reproducible: 342.18 one-handed and 383.50 two-handed, straight from
the node. `two_hand` is now demonstrably a parameter that changes the answer by 12% and that a
model will fill in silently — the same shape as `starting_class` in bug 17.

### And the record was wrong

None of the eight produced the recorded 377 and 394. Neither does the collection, at the stats
the question states, and neither does **the code at the commit that recorded the entry** — so
it is not a since-fixed bug. A sweep of strength 46–57 against dexterity 24–35 finds no spread
producing both; `STR 50 / DEX 30` yields Heavy 394.6 and Fire 369.7, reproducing one and not
the other. The entry was almost certainly priced at a re-allocated spread rather than the
question's, with its two rows not even priced at the same one.

`VALIDATION.md` 7.1 is corrected and annotated. The general point is the uncomfortable one:
**nothing in the suite checks the record against the code.** 247 fixtures check the nodes, the
spreadsheet checks the oracle, attestation checks the prose — and the file that says what the
right answers are has never been re-run since the day each entry was written. Eight model runs
found that in one question.

### Cost is the real differentiator, and it is not subtle

Measured per decision on the same 26k-token planning prompt:

| model | cost per decision | note |
|---|---|---|
| **openai/gpt-5.6-luna** | **$0.0065** | ten times cheaper than anything else here |
| x-ai/grok-4.6 | $0.056 | |
| openai/gpt-5.6-sol | $0.065 | |
| moonshotai/kimi-k3 | $0.088 | but cached 73–100% of the prompt on later calls |

Per *question*, once the `ask` round trip is included: **luna $0.040**, kimi $0.143, sol
$0.315, grok $0.325. On the heavier question 7.1, per run: **luna $0.044**, kimi $0.126, grok
$0.232, sol $0.366 — and kimi cached 93% of its prompt against sol's 0%, which is most of why
the gap narrows. Luna is eight times cheaper than either frontier option and answered in
41 seconds against grok's 126 and kimi's 274.

**The prompt is 26,000 tokens and it is re-sent on every decision.** Six decisions is a
question, so the catalog dominates everything: 61 notes and nineteen nodes with full schemas
and examples. Two levers follow directly, and both are worth more than any model choice —
prompt caching, which kimi already gets 73–100% of and the OpenAI models get 41% of, and
pruning the preamble, which has been the top item in `BUGS.md` for weeks.

## The battery, pointed at the running app

`scripts/run_battery.py` reads all 122 questions out of `VALIDATION.md`, runs them through the
same `engine.answer` the web app uses, and checks the four things that are mechanical: it
routed, nothing broke a contract, it attested, and it reached for the nodes the recorded entry
names. Figures are printed side by side rather than compared, because the recorded answers are
prose and tables and no automatic comparison would be trustworthy.

**Each question gets its own `VOUCH_SESSION`, which is what makes running them at once safe.**
This is the concurrency requirement, exercised for real rather than argued about: a shared
ledger would have every question attesting against every other question's numbers, which is
exactly what `scripts/stress_attest.py` measured the cost of.

### What the first questions through it showed

**1.1 reproduced exactly.** Rivers of Blood RL150 came back DEX 56 / ARC 59, AR 675, bleed 76,
against a record of 675.826 and 76.4. That is the regression suite working.

**Three of seven questions returned no answer, and all three are recorded `[x]` done.** This is
the finding, and it is not a bug:

- **2.8** — *"is 40/40 worth it or should I commit to one?"* The model declined: no node can
  compare stat spreads without knowing the weapon, and it would not invent one. The recorded
  answer is *"40/40 quality loses to committing, 416 against 458 on a Longsword"* — and the
  Longsword is a weapon **I chose** while working the question by hand.
- **1.4** — a pure Faith build needs an incantation named before `build-allocate` can maximise
  for one; with none named, `focus: attack` would have optimised the seal's *melee* rating.
- **1.2** — Transient Moonlight resolves to two skills, R1 and R2, and the model would not pick.

In every case the model was **more honest than the hand-working was.** The difference between a
done answer and no answer is a parameter a human chose without noticing they had chosen it.
That re-reads the 91 `[x]` answers in a harsher light and it makes the clarification chips the
next thing to build rather than a nicety: these are not failures, they are the collection
asking a question, and the app currently renders that as a shrug.

**`MAX_DECISIONS` was too low.** Question 7.1 spent all six of `ask.py`'s decisions on calls —
a weapon, three bosses, a build, an affinity — and never reached the narration, which needs a
decision of its own. Ten, and it answers in seven calls, attested.

### The ceiling is the provider, not the box

The Claude CLI backend manages four or five questions before the session limit, and at
concurrency 4 it burns quota four times faster. Two runs of pattern 1 ended that way, the
second after four questions. **The 122-question run needs OpenRouter**, where the cost is
money rather than a wall.

The runner now treats that properly: a limit stops the whole run instead of failing every
remaining question in turn — pattern 1 once produced ten "errors" in fifteen seconds, all the
same session limit, each looking like a question that had been tried — and `--resume` retries
errored questions while skipping only what finished.

This is also the first thing that made `llm.py`'s error handling matter. The Claude CLI reports
a session limit on *stdout* with an empty stderr, so the original message was the entirely
useless `claude exited 1:`. It now says *"You've hit your session limit · resets 5pm."*

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
