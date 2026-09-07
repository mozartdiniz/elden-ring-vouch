# The data the collection does not have

Everything here is blocked on a table, not on code. Each entry says what is missing, which
real questions it blocks, where to look for it, and how you will know it landed. Nothing in
this file needs a node rewritten first — that is the point of separating it.

Written 7 September 2026, after the node-rules, node-code and app work was done and these were
what remained. `HANDOFF.md` has the state of everything else.

**Before starting any of it:** read the file list in
`prometheux-workspace/files/elden-ring-brain/` first. Three of the twenty-four bugs in
`BUGS.md` exist because a parser was written against prose, or a node was left unbuilt, while
the structured table sat there unused. That has happened often enough to be a rule.

**And when one lands:** the tables in `data/` come from the Prometheux workspace, which is a
different provenance from `oracle/`, and `data/README.md` declares it. Anything new goes in
`data/`, never in `oracle/`, which is re-vendored by copying.

---

## 1. No table says what a talisman is worth, so there is no `item-rank`

**The gap.** `weapon-rank`, `spell-rank` and `ash-rank` all exist because something quantified
the thing being ranked. Nothing quantifies a talisman against a goal, so the collection cannot
answer *"which four talismans maximise X"* — which is Pattern 5, eight questions, and among the
most common things a player actually asks.

**How it was found, which is the interesting part.** Both shipping candidates, across all six
runs of question 5.1, independently stopped and said the same thing: *"no node ranks or selects
talismans; buff-stack only evaluates a set the caller supplies."* They were right. The models
found a hole in the collection by refusing to invent their way around it.

**Also note:** `VALIDATION.md` marks 5.1 as `[x]` done. Either that entry was worked by hand
with the ranking done off-collection, or it is wrong. It is the second recorded entry found
questionable out of two ever checked — see `HANDOFF.md`, *First: verify the record*.

**What is needed.** A table mapping each talisman to the quantity it multiplies or adds, under
the conditions that gate it. `data/BuffMult.csv` does this for buffs and is the shape to copy:
what it multiplies, per hit kind, PvE and PvP. `item-effect` already reads stat columns and
attack multipliers from the effect tables, so some of this exists — what is missing is
*coverage of every talisman* and the conditions, so a ranking can be computed rather than
asserted.

**Do not** build a ranking over what exists now. Ranking on a partially populated table would
produce exactly the well-formed answer about nothing that this collection exists to prevent,
and it would be attested.

**Done when.** `vouch call item-rank` ranks the talisman list for a stated goal, question 5.1
answers end to end without a stop, and the recorded entry for 5.1 has been re-run and corrected.

## 2. The mechanics rules behind the numbers

**The gap.** The collection has the buildup figures and the poise motion values and none of the
rules that turn them into effects. Every Pattern 11 partial is this:

| question | has | missing |
|---|---|---|
| 11.2 | Black Flame's attack figures | the percentage-of-max-HP rule, and its DLC reduction |
| 11.3 | frostbite buildup per hit | how buildup accumulates and decays, what the proc does |
| 11.4 | bleed buildup, arcane scaling | why a lower-buildup weapon can proc faster |
| 11.6 | an ash's poise damage, a fight's poise | what stance damage does and how a break becomes a riposte |

**The current behaviour is correct and should not be "fixed" in code.** Both models stopped on
11.3 and 11.6, three runs each, and said the collection has no rule for it. That is the right
answer and the refusal arm of the battery now checks it stays the right answer. These become
answerable when a table carries the rule, not before.

**What is needed.** Buildup accumulation and decay rates, proc effects and durations, and the
stance-break rule. None is in the Build Planner extraction. `ConsumableEffect.csv` in the
workspace is unported and may carry some of the status side.

**Done when.** 11.2, 11.3, 11.4 and 11.6 answer end to end — and the four refusal-arm entries
in `scripts/compare_models.py`'s `EXPECT` are updated in the same commit, or the battery will
start reporting correct answers as failures.

## 3. Range, moveset, reach, cast time and aggro

**The gap.** No table carries any of it. All of Pattern 15's partials turn on it, plus two
others: 15.1 (a loadout that is not all short-range), 15.5 (a spellblade bar that complements
melee), 15.6 (a long-range option that is not ice).

**Saying so is the answer**, and 15.6 is in the battery's refusal arm for exactly that reason.

**What is needed.** Per-spell range bands and cast times; per-weapon reach. Probably not in the
Build Planner extraction at all — this may be a new source rather than an unported one, and
that changes the provenance question, so decide where it goes before parsing anything.

**Done when.** A spell or weapon can be asked for its range band, and Pattern 15 answers.

## 4. Guard counters have no motion value

**The gap.** The extraction carries no motion value for guard counters, so *"best greatshield
for guard counters"* is answered on guard boost and the negation split instead — a real answer
to an adjacent question.

**What is needed.** Guard-counter motion values per weapon class. Small, self-contained, and
the only one of these four that is a single missing column rather than a missing subject.

**Done when.** `weapon-skill` or `optimal-affinity` can price a guard counter.

## 5. Talismans are still not applied to a build

**Deliberate, and unchanged.** `planner.py` stubbed `EffectData_Active`, so `character-build`,
`equip-load` and `defence` all report figures *before* talismans. `equip-load` refuses to take
one rather than ignoring it, and `item-effect` pins `applied_to_a_build: false`, so nothing
pretends otherwise.

Closing it means either modelling the effects, which has no oracle, or having the caller assert
them and say so. It is listed here because it is a data-shaped decision, not because it is
scheduled.

## 6. Not ported at all

Item locations, and `ConsumableEffect.csv`. Both live only in
`prometheux-workspace/files/elden-ring-brain/`. Vendor into `data/` with provenance the way the
other six were. `ConsumableEffect.csv` is also a candidate source for item 2.

---

## What these have in common

Every one of them is a question the collection currently answers with an honest refusal. That
is the design working: none of them returns a well-formed number about nothing, and the
refusal arm of the 18-question battery now holds three of them in place so a future change
cannot quietly start guessing.

Which means none of this is urgent in the way a wrong answer would be. It is the difference
between a tool that covers less than a player wants and a tool that cannot be trusted, and the
collection is firmly on the right side of that line while this file is unfinished.
