# elden-ring-vouch — handoff

Read this to resume after a fresh chat. It records what is built, what it rests on, what is
known to be missing, and the traps that have already cost time.

`README.md` says how to use the collection. This file says where the work stands.

*Last worked on 7 September 2026. Both repositories clean.*

**The shipping configuration is `openai/gpt-5.6-luna` on the 18-question battery: 32 of 39
answerable runs answered, every one attested, 30 complete, and 9 of 12 refusal-arm runs
stopping correctly.** `DATA.md` holds what is blocked on a table; `~/Dev/vouch/FEEDBACK.md`
holds what is blocked on the runtime, six of its ten items now done.

---

## What this is

A [`vouch`](https://github.com/mozartdiniz/vouch) collection: Elden Ring build maths an agent
can be held to. It is a **second implementation** of the Prometheux *Elden Ring Brain*
ontology (`24bee49209c`), built for the same reason — give an LLM real computed numbers
instead of predicted ones — on a different runtime.

Having two implementations is not redundancy, it is the point. Where the ontology has a
recorded figure, the fixtures here are pinned against it, and the first comparison found a
real bug (see *Findings*).

## Layout

```
elden-ring-vouch/
  .vouch/registry.toml     routing rules an agent reads; the preamble is load-bearing
  .vouch/evals.toml        natural-language evals, 16 cases
  oracle/                  VENDORED VERBATIM from elden-ring-wiki/. Never edited.
    scripts/               ap_calc.py, planner.py, opt_affinity_calc.py
    extracted/             the Build Planner CSV tables and their formulas
  data/                    tables the Build Planner does NOT publish, from the ontology
    MagicFamily.csv        spell → family, for catalyst bonuses
    BossResist.csv         boss health/defences/negations/resistances, per encounter
    AshAttack.csv          2643 skill hits: motion values, scaling overrides
    AshCompat.csv          ash default affinity and weapon compatibility
    AshAffinity.csv        which affinities each ash accepts — not the same question
    AshClass.csv           which weapon classes each ash goes on
    BuffMult.csv           what a buff multiplies, per hit kind, PvE and PvP
    BuffSlot.csv           whether two buffs stack or overwrite each other
    PhysickEffect.csv      the forty crystal tears, and what each does
    AreaLevel.csv          the level band each area is built for — the softest table here
  lib/oracle.py            the one place that knows where the oracle lives
  lib/spells.py            the spell tables, and the one multiply that is not the oracle's
  lib/buffs.py             what a buff multiplies per hit kind, and whether two of them stack
  lib/ashes.py             which affinities an ash accepts, and its hits on one weapon class
  nodes/                   nineteen nodes
  scripts/generate_cases.py  regenerates attack-power fixtures from the oracle
  scripts/check_spreadsheet.py  22 figures read off the workbook itself — run after any
                            change reaching planner.py or ap_calc.py
  scripts/stress_attest.py  exercises `vouch attest` without a model: behaviour matrix,
                            mutation sweep, and collision against ledger size
  scripts/run_battery.py    the 122 questions through the live loop, concurrently, one
                            ledger each — costs model calls, stops on a provider limit
  scripts/compare_models.py the same questions across OpenRouter models: answered,
                            attested, complete, cost. --estimate before --yes
  web/                     the chat app. Four files and a static page, no build step
    app.py                 one endpoint streaming NDJSON, rate limit, two daily ceilings
    engine.py              the loop — ask.py with its I/O ends changed, prompts verbatim.
                           `Prompt` marks where a cache breakpoint is legal; `trimmed`
                           is why the catalog is 18,900 tokens and not 28,000
    llm.py                 Claude CLI or OpenRouter behind one signature, with retries,
                           cache breakpoints, and a per-call-kind token budget
    completeness.py        did the answer name what the user asked about — no model
    test_server.py         20 checks, model replies canned, everything else real
    test_client.mjs        14 checks of static/app.js against a stub DOM, via node
  VALIDATION.md            122 questions, worked one at a time — read this next
  BUGS.md                  what the questions found, open and fixed — the work list
  DATA.md                  the questions blocked on a missing table, and nothing else
  PLAN-web-app.md          serving this publicly: the loop, the costs, the model results
```

**The `oracle/` vs `data/` split is the important one.** `oracle/` is a byte-identical copy of
the wiki extraction and is re-vendored by copying, never merging. `data/` holds tables that
came from the Prometheux workspace, which is a different provenance and is declared as such in
`data/README.md`. Anything new from that workspace goes in `data/`, never in `oracle/`.

## The nodes

| Node | Answers | Cases |
|---|---|---|
| `weapon-lookup` | resolve a name; class, infusability, upgrade cap, and what can be put on it | 15 |
| `weapon-rank` | a stat spread → the weapons it can use, ranked | 9 |
| `spell-lookup` | resolve a spell name; type, forms, families, requirements | 7 |
| `spell-rank` | a catalyst + a build → the spells it can cast, ranked | 6 |
| `ash-rank` | a weapon class + an affinity → the ashes that fit, ranked four ways | 7 |
| `boss-lookup` | an encounter's every phase: health, poise, defences, negations, immunities | 14 |
| `boss-coverage` | many fights at once: which element covers them, which are immune | 7 |
| `weapon-skill` | an ash's hits, motion values, affinities, and whether it replaces the scaling | 16 |
| `item-effect` | talismans, tears and runes: stats, weight, resistances, what a tear does | 14 |
| `buff-stack` | what a set of buffs multiplies for one kind of hit — and which do not stack | 15 |
| `character-build` | class + named stats → full spread, rune level, HP/FP/stamina/load | 14 |
| `build-allocate` | weapon or spell + class + level → the spread | 23 |
| `attack-power` | one weapon at one spread → AR, scaling, requirements, status, guard | 23 |
| `optimal-affinity` | all thirteen infusions ranked against a target | 13 |
| `spell-power` | one spell from one catalyst → attack per type, family bonus, FP charged | 23 |
| `defence` | a build and armour → defences, negation, status resistances | 14 |
| `equip-load` | a loadout → weight, roll type, endurance to change it | 9 |
| `matchmaking` | who a character can play with, and the upgrade bracket that keeps them there | 9 |
| `stat-curve` | what each point in a stat buys, and where the curve bends | 9 |

`vouch -C . test` → **267 cases, 267 passed**.

`python3 scripts/check_spreadsheet.py` → **22 of 22 match**, against the Build Planner workbook
itself rather than against the extraction. Run it after touching anything that reaches
`planner.py` or `ap_calc.py`; it found the one bug 122 real questions did not.

## How this is checked, and what each check cannot catch

Three layers, and the point is that they fail differently.

**Four photographed characters** are the only figures here that come from the game rather than
from an extraction of it, and they are the last word when anything disagrees. They live as
fixtures in `attack-power`, `character-build` and `equip-load`, and between them they cover a
somber weapon and an infusion, one-handed and two-handed, physical, fire, holy and magic
damage, a status buildup, guard negation, and four different mind values. They confirmed the
rule everything rests on — three stat points to a level, `sum - 79`, on four independent
builds all summing to 229 at level 150 — and they found bugs 26 and 27, both of which were
wrong roundings in the fields that exist to be the number a player reads off the screen.

**296 fixtures** (`vouch test`) pin every node against the extraction in `oracle/`. They are
fast, they run on every change, and *by construction they cannot catch a mistake in how the
collection uses the extraction* — which is what bug 17 was. Worse, a fixture can pin the wrong
behaviour, and it has now happened twice. One asserted that `buff-stack` exiting 20 on an
unknown name was correct. The other was *named* for what it was protecting — "an item not in
the effect tables is a defect, not a silent zero" — and half of that was right while the other
half pinned bug 23 for as long as the node existed. **A fixture expecting exit 20 or 21 is
nearly always pinning a defect.** There are none left here; grep before adding one.

**122 questions** (`VALIDATION.md`) are the outside view: what a player actually types, worked
one at a time in fourteen patterns. They found seventeen bugs, four of which returned a
well-formed number rather than an error. They are the only check that finds a *missing*
capability, because a fixture cannot fail for a question nobody can ask.

**22 spreadsheet figures** (`scripts/check_spreadsheet.py`) come from three of the Build
Planner's own saved builds, read off PDFs of the workbook. This is the only check that sits
upstream of the oracle, and it found the one bug 122 questions did not.

**The attestation stress test** (`scripts/stress_attest.py`) exercises the last line, which
needs no model and so had never been run. It catches 23 of 24 mutations of a real answer, and
the one it misses shows the shape of the hole: **a numeral attests if *some* call in the
session returned it**, so a wrong value that collides with another figure is invisible. That
degrades fast with session size — 19% of integers 1–99 collide in a two-call ledger, 96% in a
day's. `VOUCH_SESSION` defaults to the *date*, so the default is the loose end of that range.
Set it per conversation.

**The web app** (`web/`, and `scripts/compare_models.py`) is the newest layer and the only one
where a model chooses the parameters. That is what it catches. In roughly forty runs across
four models it found: `buff-stack` crashing where it should have refused; the ledger path built
by string interpolation, so a model name containing a dot silently downgraded an answer to
UNCHECKED; a recorded answer in `VALIDATION.md` whose figures nothing reproduces; and the fact
that `two_hand` and `starting_class` get filled in silently and move results by 12%.

Its own two checks are `web/completeness.py` — the lookup nodes resolve what the user named, so
an answer that never mentions a resolved entity dropped something, which **attestation cannot
see** — and the four mechanical columns in `compare_models.py`: answered, attested, complete,
cost. Neither needs the recorded answers to be right, which matters, because one of them wasn't.

**The 18-question battery** (7 September) is the same layer widened, and widening it is what
made it useful. One question per pattern chosen to reach the five nodes no recorded entry
mentions, plus **four questions whose right answer is a refusal** — which nothing had ever
tested. Every question in the old three-question set was answerable, so a model that answers
everything scored full marks. `compare_models.py` now scores the two arms separately, because
"answered" means opposite things in them.

It immediately paid for itself. It found bug 23 and bug 24; it found that no node ranks
talismans while `VALIDATION.md` marks 5.1 as done; it showed that neither shipping candidate is
deterministic; and it reversed the model choice the three-question set had implied. Run it
with:

```console
$ ./scripts/compare_models.py --questions 1.1,2.1,3.1,4.1,4.2,5.1,6.2,8.1,9.2,10.3,11.3,11.5,11.6,12.8,14.4,15.4,15.6,7.1 --repeat 3
```

Two things about running it: `--concurrency 1` for models on a new OpenRouter account, which
are capped at 20 requests a minute and a single question is eight to fifteen sequential calls;
and `--estimate` first, whose per-decision rates in `SEEN_COST` are only as good as the last
measurement written into them.

Two audits found five more (bugs 18–22) and are worth repeating whenever a node is added:

1. **Which defaults change the question** rather than choosing a mode?
2. **Which nodes can still return a well-formed number for a thing that does not exist?**

The second is the sharper one. Bug 22 is bug 4 in two nodes written *after* bug 4 was fixed:
a guard that lives in one node is not a guard.

A third has since earned its place, and nothing automated covers it:

3. **Which recorded answers still reproduce?** Nothing checks `VALIDATION.md` against the code.
   Fixtures check the nodes, the spreadsheet checks the oracle, attestation checks the prose —
   and the file that says what the right answers *are* had never been re-run since each entry
   was written. 7.1 said Fire 377 and Heavy 394; the collection says 342 and 357, and so does
   the code at the commit that recorded it. Eighty-four entries remain unverified, and the ones
   with pinned inputs cost nothing to check.

## State of the evals

`vouch -C . eval --agent 'claude -p --allowedTools "" -- {prompt}' -n 3 --min-rate 0.9`

**This is the biggest gap in the project and it has grown.** The last complete measurement was
24/24 across the 8 cases that ran before a usage limit cut it short; earlier complete runs went
89% → 95% → 96% → 100% as fabrications were fixed. Since then the collection has gone from
eleven nodes to nineteen, and **`.vouch/evals.toml` still has its original 16 cases**. Nothing
in it asks for a caster's spread, a weapon or spell or ash ranking, a buff stack, a matchmaking
bracket, a stat curve, or a boss-coverage answer. Eight nodes have never been in front of a
live model at all.

Writing those cases and measuring the suite end to end is the first thing to do with a fresh
token budget.

`--allowedTools ""` matters: with its own tools the agent reads the repository instead of
routing through the published context, which measures the wrong thing.

---

## The rule this project keeps re-learning

Every fabrication was fixed **upstream of where it appeared** — by returning the figure in the
form a reader quotes, never by checking the prose harder. Fourteen instances, of which the
first five came from evals and the rest from working real questions:

| the agent wrote | because the node | the fix |
|---|---|---|
| an invented dexterity | required stats the user had not given | `character-build` fills from class minimums |
| `259` off a `259.576275` | returned only full precision | `attack_shown` / `status_shown` |
| `47` for "at RL150" | returned level 103 and no target | `target_level` → `levels_to_target` |
| `409` out of `"409/0/411/0/0"` | published figures inside a string | `shown` numbers beside it |
| `2` more points needed | returned `req_met` and not the gap | `scaling.<stat>.shortfall` |
| — | had no allocator at all | `build-allocate` |
| a caster's spread | maximised the catalyst, not the spell | `focus = "spell"` |
| a ranking of 570 weapons | had no ranking node at all | `weapon-rank`, `spell-rank` |
| `1.15 x 1.2 x 1.13` | returned three sentences with figures in them | `item-effect`'s `stacked_multiplier` |
| a spread that cannot hold the shield | heard only about the weapon | `stat_floors` |
| a stacked multiplier by hand | returned buffs and left the multiply | `buff-stack`, on `BuffMult` |
| "the ash accepts Blood" | had only the affinity it comes with | `ash-rank`, on `AshAffinity` |
| an element's coverage from memory | answered one fight at a time | `boss-coverage` |
| "soft cap at 40" | had the curve and never walked it | `stat-curve` |

**If a node leaves a caller one small sum, it has handed that sum to a model.** That is the
first thing to check when writing a new node.

The second thing to check is the one bugs 4 and 22 are about: **if a node can be asked about
something that does not exist, it will eventually be asked.** A staff casting an incantation,
an affinity a weapon cannot take, a grease that slides off, a cast a seal cannot make — each of
those returned a well-formed number until something refused it.

The corollary, learned twice the hard way while writing fixtures here: take a number from the
node, never from what it looked like on screen. Two fixture figures were written from a
truncated display and completed from memory; both failed and both were caught.

## Findings worth not rediscovering

**A number that is arithmetically right can be about nothing.** `spell-power` priced Comet cast
from an Erdtree Seal at 798.766. The spell buff was right, the multiply was right, and a sacred
seal cannot cast a sorcery. Three of the nine bugs the battery found are this shape: a
well-formed figure for a thing that does not exist. Contracts caught none of them, because
nothing in the schema knew the cast, the affinity or the weapon had to be possible.

**Both implementations can be wrong in the same place.** Every incantation in the game priced
at zero, because `spell-power` read `MagicAtk` and Black Flame's 244 is in `FireAtk`. The
Prometheux ontology computes `MagicAtk x SB / 100 x Mult` too, so the differential check agreed
with itself. It took a question a player would actually ask.

**The catalogue is 489 weapons, not 570.** Eighty-one rows are consumables, fifteen of them
without a weapon ID at all, which is what made the first full ranking crash rather than return
nonsense.

**`ap_calc.load_table` re-parses its CSV on every call** — a tenth of a second for the 1.3 MB
`EquipParamWeapon`. Invisible when a node prices one weapon, fatal at 489. Cached in
`lib/oracle.py`; `oracle/` stays byte-identical.

**A motion value is per damage type.** Establish Order's big hit is 300 holy and 0 physical,
and `optimal-affinity`'s `attack_mv` is one number. `weapon-skill` reports
`motion_values_uniform` so the scalar is only used where it means something.

**Two catalysts scale their spell buff off strength and dexterity** — the Clawmark Seal and the
Frenzied Flame Seal. A "pure faith" Frenzied Flame build is the wrong build: the optimum at
RL150 is strength 26 / dexterity 30 / intelligence 30 / faith 43.

**Seven ash-of-war families are a name plus " ?"**, the source marking a hit it could not
confirm. Normalising the punctuation away made all seven ambiguous with themselves.

**The upgrade cap is not derivable from `isInfuse`.** It was "+25 if infusable, else +10",
which is right for 512 of 570 weapons and wrong for 58 — the Academy and Carian Glintstone
staves, Great Club, Serpentbone Blade, the Perfume Bottles all take no affinity and still reach
+25. The cap comes from how far the weapon's `reinforceTypeId` band runs in
`ReinforceParamWeapon`. Found because a spell figure disagreed with the ontology.

**A boss name is not an identity.** 47 names in `BossResist.csv` repeat: the same enemy fought
in different places with different health, nine Death Rite Birds from 3442 to 28905. An
encounter is name **+** location.

**Phases are the fight, not an ambiguity.** `boss-lookup` returns every phase with its own
figures and has *no* boss-level defence or negation, so an answer cannot quote one number for
Rennala. What is *not* grouped is anything the table does not label: Malenia's two forms are
phases in the game and two unrelated names in the data, and grouping them would encode
knowledge the data does not carry.

**`MagicData` has three rows named "Comet"** — the plain cast at 292 and two charged variants
at 365. `Display Name` is the unique key, not `Name`.

**Zero damage is a real answer.** Rennala's bubble negates 100% of everything, and
`optimal-affinity`'s schema required damage above zero, making the correct answer a defect.

**A flat status cannot be built toward.** Great Stars' bleed and Star Fist's frost do not scale,
so maximising them is degenerate and the leftover points fall into vigor, producing a spread
that looks optimised and is not. `build-allocate` reports `objective_responds_to_stats`.

**`ap_calc.py` answers questions the game cannot ask.** Moonveil +25 returns 180.39 — an
upgrade level that does not exist, and *lower* than its real +10 figure of 643, so it does not
even look wrong. Out-of-range stats are computed rather than rejected. Every guard against that
lives here, not in `oracle/`.

**A model will not recover from a name that does not exist.** Question 4.1 asks for a
"Distinguished Greatsword", which is not in the game — the catalogue has a Distinguished
*Greatshield*. The recorded entry recovers by noting that Wave of Destruction is unique to the
Ruins Greatsword and pricing that. Neither model tried it: one declined, one exhausted its
decisions. `weapon-skill` can go from a skill to its weapon, and nothing tells a caller to
reach for it when a weapon lookup misses.

**`two_hand` and `starting_class` get filled in silently, and both move the answer.** On 7.1 a
model assumed two-handing and returned 383 where one-handed is 342 — internally consistent,
attested, and answering a question nobody asked. `starting_class` is bug 17's parameter doing
the same thing. Any parameter a model can invent that changes the result belongs in an `ask`.

---

## What is pending

### First: verify the record

`VALIDATION.md` is the file that says what the right answers are, and **nothing has ever
checked it against the code**. 7.1 was found wrong the first time a model re-ran it. Eighty-four
recorded entries remain, and the ones whose inputs are pinned in the entry cost nothing to
re-run — no model needed, just the nodes. Do this before trusting the battery as a scoring key,
because it is currently the scoring key for `scripts/compare_models.py`.

**A second entry is now in doubt, and this one was found for free.** 5.1 is marked `[x]`, and
both shipping candidates across all six runs independently said the same thing: no node ranks
or selects talismans, `buff-stack` only evaluates a set the caller supplies. They are right —
see *Fifth* below. So either that entry was worked by hand doing the ranking off-collection, or
it is wrong. Two of the eighty-five recorded entries have now been checked and both were
questionable; that is the argument for checking the rest.

Note also that `recorded_nodes` — the key `compare_models.py` scores `nodes_missed` against —
is extracted by matching backticked names in the entry body, and five nodes are named by no
entry at all. It is a weak key and worth strengthening while the entries are being re-run.

### Second: determinism — the collection's half is done, the model's half is not

**Done 7 September.** The drift was a model inventing judgement parameters, and the collection
now owns them. `lib/judgement.py` holds the reasoning and two kinds, kept deliberately
disjoint:

  * **the collection may decide** — `starting_class` and `two_hand`. Defaulted, and *reported*
    in a new `assumed` field on every result, pinned by a contract on each of the ten nodes
    that take one. The default is not the popular choice but the least-distorting one: Wretch's
    flat-10 floors are the lowest maximum of the ten classes, so the worst it can do to a stat
    is raise it to 10, where Astrologer would lift a 5-intelligence build to 16.
  * **the collection must not decide** — the survivability floors and the target level.
    `build-allocate`'s own docstring says how much vigor a build should hold back is an opinion
    and that a node answering it presents opinion as a calculation. That stands. What changed
    is that the collection now publishes the *option set* — four floor sets, three levels, with
    their values spelled out — so a model relays a fixed list instead of authoring a new one
    each run. The judgement stays the caller's and stops being re-invented on the way there.

Two things fell out of doing it. **Five nodes were still silently defaulting `starting_class`
to Wretch** — bug 17's exact shape, live and unnoticed. And the ten classes were enumerated
only in a *precondition*, which `markdown.rs` deliberately omits from the routing pack, so the
closed set the data has always known was invisible to every caller. It is an `enum` now.

`web/llm.py` sends a `seed` where a provider takes one, which is the small half.

**Measured, 7 September, luna at `--repeat 5`.** The claim holds on the axis that matters and
not on the one that looked like it mattered.

*What the fix did.* The same question now reaches the nodes with the **same arguments every
time**: across five runs each, 1.1 and 2.1 both show one distinct option-set taken. On 1.1 the
model still asks in every run — correctly, since that question states no floors — and offers
and takes the identical canonical set each time. On 2.1 it stopped asking entirely.

*What it did not do.* The figures in the prose still vary, because the narrator chooses which
ones to quote from an identical verified result. On 2.1 the four runs that never asked all
reach the same conclusion with the same values — Strength requirement 20 unmet, recommended
26/58/20 keeping the user's own 55/30/20 — and differ only in how much of it they mention.
That is a weaker thing than the old drift, where different inputs produced genuinely different
computed values, and it is the remaining work.

*Two things found while measuring, both of which had been hiding the result.*

`consistency()` grouped by model and not by question, so it had been comparing the figures in
an answer about talismans against the figures in an answer about boss resistances. It printed
DIFFERED for every multi-question run ever made and meant nothing by it. Fixed.

And set-comparison conflates the two kinds. A figure quoted in one run and omitted in another
is the narrator being terser; a run that reached different inputs computed a different answer.
The report now names which, by comparing what each run was actually told rather than by
whether it asked — asking is not the test, because a question that states no floor *should* be
asked about.

*One regression, found and closed.* On 2.1 the user states VIG 55 / MND 30 / END 20 in the
question, and the canonical option sets gave the model something to offer anyway: one run in
five asked for floors it had already been given and substituted 40/20/25. Per-parameter
guidance cut that from five runs to one; the general rule in `PLANNING_RULES` — *never ask for
a value the user's question already contains* — took it to zero.

**Still open: narrator figure selection.** The likely fix is the rule this project keeps
re-learning — a node that returns a large result and does not mark which figures are the
answer has handed that choice to a model. A `headline` subset per node is the shape.

### Third: the model choice, and what it rested on

**Settled 7 September: the collection ships on `openai/gpt-5.6-luna`.** On the 18-question
battery at three repeats it answered 33 of 42 answerable runs against `gpt-5.6-terra`'s 25,
everything it answered was attested *and* complete where terra left two incomplete, and it cost
$0.27 against $2.47. `qwen/qwen3.8-27b` was dropped for latency — 267s on 7.1 against terra's
46s — after being competitive on the mechanical columns.

**The three-question set had implied the opposite**, and the reason is worth keeping: 3.1, 1.1
and 7.1 happened to sit inside terra's strengths. Terra collapsed on `matchmaking` (10.3, never
routed to it at all) and on 12.8, which luna answered three times out of three. A sample chosen
for *shape* — one call, a chain, a long one — is not a sample chosen for coverage.

What is **not** settled is determinism, and it is now the largest open piece of work:

| | identical across repeats | differed |
|---|---|---|
| questions where a model asked | 1 | **14** |
| questions with no ask | 2 | 3 |

**The drift is the `ask` branch, and it is fixable.** A model invents its option set fresh each
run — luna offered `(vigor 40, mind 20, endurance 25)` on one run and the same plus
`focus bleed` on the next — so different parameters reach the node and different figures come
out. Every one is internally consistent and attested. Nothing is wrong except that the answer
moved.

The fix is `~/Dev/vouch/FEEDBACK.md` item 5: let the collection declare which parameters are
judgements and what their canonical options are, so the model relays a fixed list instead of
authoring one. That removes 14 of the 15 drift cases at the source. Two smaller sources remain
and should not be confused with it: the narrator choosing *which* figures to quote from a large
result (11.5 drifted with no ask involved, both models, from an identical `stat-curve` result),
and provider nondeterminism, which `temperature: 0` does not remove and an untried `seed` may
reduce. **The target is 99%, not 100%.**

Get a baseline with `--repeat 5` on a fixed set before changing anything; `consistency()` in
`compare_models.py` already reports it.

### Fourth: the evals

See *State of the evals* above. Nineteen nodes, sixteen eval cases, eight nodes never seen by a
live model. This is the largest gap in the project and the only one that measures whether an
agent can actually route to what has been built.

### Fifth: the routing preamble — the cost half is done, the reading half is not

The bill is handled. The fixed prefix went from **28,000 tokens to 18,900** (`engine.trimmed`:
`$schema` and `title` dropped, `params.*.guidance` folded into the schema `description` that
duplicated it, one example per node, no indentation), and `engine.Prompt` now carries two cache
breakpoints. Measured on one question with everything else held: **$0.0367 to $0.0119**, same
decisions, same calls, same answer. Across nine pairings, 66% less. `llm.py` documents the
environment variables, and `CACHE_BREAKPOINTS=0 PLANNING_REASONING=default` reproduces the old
behaviour exactly for a control arm.

**Do not assume a provider caches on its own.** With breakpoints off, luna reported 0% cached
on a prefix that was byte-identical across eight decisions; `kimi-k3` was already at 87% before
any of this. It is a property of the provider.

**Do not prune further for cost.** Cached, the full 18,900-token catalog reads at roughly what
a thin dynamic index would cost uncached, and it is lossless. What remains is a *reading*
question, not a billing one: **sixty-one notes**, 16,755 characters, 23% of the catalog. Past
some size notes stop being read rather than stop being true, and nothing measures which. Prune
before adding another one. `vouch describe` is not the pack; the pack omits contracts.

### Sixth: the data — all of it is in `DATA.md`

Six entries, each with what is missing, which questions it blocks, where to look, and how you
will know it landed. Deliberately in its own file: it is the one body of work that needs no
code changed first, and it is picked up cold at a different time from everything else here.

**The decision (7 September) is to fix the data rather than patch a node**, and the reason is
worth keeping at hand: building a ranking over a table that does not carry the quantity being
ranked produces exactly the well-formed answer about nothing this collection exists to prevent
— and it would be attested. Every item in `DATA.md` is currently answered by an honest refusal,
and three of them are held in place by the battery's refusal arm, so nothing can quietly start
guessing while the file is unfinished.

### Seventh: what the battery left open

`VALIDATION.md` has all 122 questions worked one at a time, with the calls, the figures and the
cross-checks. Ninety-one answer end to end and thirty-one are partial. **No question is
unanswerable**, and every partial is one of these five:

1. **Flat-attack and scaling-overridden hits are read, not priced.** Six of the ten Pattern 4
   skills have one. `optimal-affinity` prices a hit through the weapon's attack rating, so a
   hit carrying flat attack (Ghostflame Ignition's 140 magic) or replacing the weapon's scaling
   (Sacred Blade's bullet off Faith) has no path. The data says *which stat drives it*, which is
   worth quoting, and the damage is not computed. **The override is per hit, not per skill** —
   Sacred Blade's slash uses the weapon and its bullet does not — so any fix has to model hits.

2. **`build-allocate` cannot optimise for a skill**, which needs (1) first. It is the natural
   next `focus` after `spell`.

3. **The mechanics behind the numbers.** Frostbite's proc, Black Flame's percentage damage, the
   stance-break rule. The collection has the buildup figures and the poise motion values and
   none of the rules that turn them into effects. `boss-lookup` gives a fight's poise and
   `ash-rank` gives an ash's poise damage, so "how many of these break that" is arithmetic a
   caller can do; the rule itself is in no table here.

4. **Range, moveset, reach, cast time and aggro.** All of Pattern 15's partials and two others
   turn on them, and no table carries any of it. Saying so is the answer.

5. **Guard counters have no motion value in the extraction**, so "best greatshield for guard
   counters" is answered on guard boost and the negation split instead.

### Deliberately absent, not pending

- **Applying talisman effects to a build.** `item-effect` says what an item is worth, combines
  several, and now multiplies the damage bonuses whose conditions the caller asserts. Nothing
  *applies* one to a build: `planner.py` stubbed `EffectData_Active`, so `character-build`,
  `equip-load` and `defence` all report figures before talismans. `equip-load` refuses to take
  one rather than ignoring it; `item-effect` pins `applied_to_a_build: false`. Closing this
  means either modelling the effects, which has no oracle, or having the caller add them and
  say so.
- **Poise.** `planner.py` returns a figure on a scale not reconciled with the game's, so it is
  not published. An unverified number reads as authoritative.

### Not ported at all

Item locations, and `ConsumableEffect.csv`. Both live only in
`prometheux-workspace/files/elden-ring-brain/`; vendor into `data/` with provenance the way the
other six were. **Read that directory's file list before building anything** — three of the
twenty-two bugs exist because a parser was written against prose, or a node was left unbuilt,
while the structured table sat there unused.

---

## What is blocking a public launch

Reviewed 7 September, sized for *a few hits if any* rather than a front page. Ranked, with the
decisions already taken written down so they are not re-litigated.

**1. OpenRouter's rate limit.** New accounts are capped at 20 requests a minute per model, and
one question is eight to fifteen sequential calls. It cost a question during the 18-question
battery at concurrency 2. Nothing else on this list matters until the account tier is raised.

**2. Abuse, without building authentication.** *Decided: no account system.* Cloudflare in
front (free tier, one DNS change) with Turnstile — a script tag and one verify call, no
accounts, invisible to humans — plus a global concurrency cap, not just the per-IP limit, which
lives in process memory and resets on restart.

**3. The money ceiling — done.** `DAILY_SPEND` (default $5) now sits beside `DAILY_BUDGET`,
read from the provider's own cost figure and charged whether the question finished or failed. A
count of questions bounded nothing: 200 questions is $1.28 on luna and $19 on terra. This is
what makes a public endpoint tolerable without accounts — the worst case is a number we chose.

**4. Bugs 23 and 24 — done.** See `BUGS.md`.

**5. Data provenance and the Prometheux conversation.** Owner-handled, outside this file. See
`PLAN-web-app.md`.

**6. Determinism.** See *Second* in the pending list. Two people asking the same question get
different figures from a tool whose entire claim is that its numbers are computed. This is the
one that most deserves the effort.

**7. The prose channel.** `stop` reasons and `ask` question and label text are the only
model-authored strings the page renders, and they are therefore the whole surface for anyone
trying to use this as a free LLM. The architecture closes the rest: the planner may only emit
`call`/`done`/`ask`/`stop`, and the narrator sees nothing but verified results. Cap the length
hard, and where a stop follows a runtime refusal, render **the node's reason** rather than the
model's paraphrase — those messages were written to be acted on, and it improves the answer as
well as closing the channel.

**8. Making "I can't" useful.** Thirty-one of 122 question shapes are partial, so a quarter of
real questions end in a stop, and a stop is currently one sentence. It should say what the
collection *does* have that is adjacent — on 11.6, "no stance-break rule, but `ash-rank` gives
an ash's poise damage and `boss-lookup` gives a fight's poise, so the arithmetic is yours".
The models already called those nodes; the stop path throws it away.

**9. Answers in the wrong language.** 19% of battery answers came back in a language the
question was not asked in, down from roughly two thirds before a line was added to
`narration_prompt`. One came back in French. *Decided: parked* — it is cosmetic next to
determinism. If picked up, try the planning rules too, or restate it last rather than mid-prompt.

**10. Deployment.** `run.sh` is a development server: `uvicorn --reload`, no TLS, no process
manager. Conversations live in process memory and are lost on deploy. The `vouch` binary must
be on PATH, which is a deployment script's job. *Decided: a production server is a known,
accepted piece of work.*

**11. Ledger growth — done.** A conversation now deletes its ledger when it is evicted.

---

## Working notes

- **Check against the workbook, not just the extraction.** `scripts/check_spreadsheet.py` holds
  twenty-two figures read off three of the Build Planner's own saved builds. The fixtures pin
  the collection against `oracle/` and cannot catch a mistake in how the collection *uses* it —
  which is exactly what bug 17 was, and what 122 questions missed.
- **Regenerate `attack-power` fixtures** with `python3 scripts/generate_cases.py` after
  re-vendoring `oracle/`. They come from `ap_calc.SCREENSHOT_CASES`, the only figures here that
  trace to the game rather than to code.
- **Pin new nodes against the ontology** wherever `prometheux-workspace/HANDOFF.md` records a
  figure. Its "Default checks that already persisted" section is a fixture source, and it is
  how the upgrade-cap bug was found.
- **The routing preamble needs pruning before it needs anything else.** Sixty notes; see
  *What is pending*. Measure the real pack rather than `vouch describe`, which includes the
  contracts the pack leaves out.
- **Look for the rest of a bug's kind.** Five of the twenty-two in `BUGS.md` came from asking
  two questions of every node rather than from a player's question: *which defaults change
  what was asked?* and *which nodes can still return a well-formed number for a thing that
  does not exist?* Both are cheap and both found defects that returned numbers.
- **`vouch <cmd> | head` can panic** on a broken pipe. Recorded in the runtime's `DECISIONS.md`
  as known roughness; it is a race and rarely reproduces.
- Contracts have caught genuine mistakes in this repository more than once — rune level is stat
  sum − 79 rather than points + 1, and `weight_left` is the roll-change headroom rather than
  unused capacity. When a contract fires while you are writing it, check the assumption before
  changing the contract.

## Resuming

```console
$ cd ~/Dev/elden-ring-vouch
$ vouch test                                    # 296 cases, no model
$ python3 scripts/check_spreadsheet.py          # 22 figures from the workbook itself
$ vouch call boss-lookup --input '{"query":"rennala"}'
$ vouch call build-allocate --input '{"weapon":"Rivers of Blood","affinity":"Standard",
    "upgrade":10,"max_upgrade":10,"starting_class":"Samurai","target_level":150,
    "focus":"bleed","vigor":40,"mind":20,"endurance":25}'
$ vouch call weapon-rank --input '{"strength":55,"dexterity":14,"intelligence":9,"faith":60,
    "arcane":9,"limit":10}'
$ vouch call build-allocate --input '{"weapon":"Dragon Communion Seal","affinity":"Standard",
    "upgrade":10,"max_upgrade":10,"starting_class":"Prophet","target_level":150,
    "focus":"spell","spell":"Rotten Breath","vigor":40,"mind":30,"endurance":20}'
$ vouch call matchmaking --input '{"level":80,"upgrade":7,"somber":true}'
$ vouch call buff-stack --input '{"buffs":["Shard of Alexander","Lord of Blood'"'"'s Exultation"],
    "hit_kind":"Skill","assume":["Lord of Blood'"'"'s Exultation"]}'
$ vouch eval --agent 'claude -p --allowedTools "" -- {prompt}' -n 3 --min-rate 0.9
```

And the app, which needs no model to test and a key to run:

```console
$ cd web
$ python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
$ .venv/bin/python test_server.py               # 20 checks, canned model, real nodes
$ node test_client.mjs                          # 14 checks, stub DOM
$ ./run.sh                                      # localhost:8000, gpt-5.6-luna
$ cd .. && ./scripts/compare_models.py --questions 7.1 --estimate
```

The 18-question battery, which is what to run after touching a node, a prompt, or the model.
`--concurrency 1` because a new OpenRouter account is capped at 20 requests a minute:

```console
$ ./scripts/compare_models.py --repeat 3 --concurrency 1 --questions \
    1.1,2.1,3.1,4.1,4.2,5.1,6.2,8.1,9.2,10.3,11.3,11.5,11.6,12.8,14.4,15.4,15.6,7.1
```

**Read `BUGS.md` before changing a node.** Twenty-eight entries, each with what it returned
instead of an error, and the three audit questions at the bottom are the ones worth re-asking
every time a node is added. A fourth has earned its place: **can this node say no?** Bugs 23
and 24 were both a node with no way to report that the answer does not exist — one crashed and
one returned a well-formed nothing. `~/Dev/vouch/FEEDBACK.md` item 10 is why that keeps
happening.

The runtime is at `~/Dev/vouch`; its own `DECISIONS.md` covers where that stands.
