# The data the collection does not have

Everything here is blocked on a table, not on code. Each entry says what is missing, which
real questions it blocks, where to look for it, and how you will know it landed. Nothing in
this file needs a node rewritten first — that is the point of separating it.

Written 7 September 2026, after the node-rules, node-code and app work was done and these were
what remained. `HANDOFF.md` has the state of everything else.

**Before starting any of it, read this.** The sourcing plan this file was written with does
not hold.

`prometheux-workspace/files/elden-ring-brain/` **is not on this machine.** Three places in the
documentation said to vendor the missing tables from it. Whatever is written below about where
data comes from is a description of what is needed, not of a file waiting to be copied. The
first task in every entry is therefore *find a source*, and that is a different job from
parsing one.

Two things that looked like sources and are not:

- `oracle/extracted/.../EffectData_Active.csv` is **not** a stubbed effect table. It is 27
  rows of the Build Planner's live active-effects panel, mostly blank, with no header. Item 5
  below used to read as "unstub `planner.py`"; it is the same missing data as item 1.
- `~/Dev/EldenRing/paramdex/` holds two files and both are ID-to-name maps. No parameters, no
  motion values.

**And the standing rule still applies to whatever source is found:** read its file list before
writing a parser. Three of the twenty-five bugs in `BUGS.md` exist because one was written
against prose while the structured table sat unused. New tables go in `data/`, never in
`oracle/`, and `data/README.md` declares the provenance.

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

**What is needed, at column level.** Not a new shape — `data/BuffMult.csv` is already the
right one and `buff-stack` already works on it:

```
Name, Kind, Slot, HitKind, MultPve, MultPvp, Notes
Shard of Alexander, Talisman, Passive, Skill, 1.15, 1.15, All weapon skills...
```

`HitKind` is what makes ranking possible — `All`, `Skill`, `ChargedSkill`, `ChargedR2`, `Crit`,
`Jump`, `Successive`, `Physical` — because "best for X" is a question about a hit kind, and one
row per talisman per hit kind is what lets it be answered by selection rather than by opinion.
`Slot` joins to `BuffSlot.csv`, which already says whether two things multiply or overwrite.

**What is missing is coverage, and one column.**

*Coverage.* `BuffMult.csv` holds **21 distinct buffs**, seven of them talismans. The game has
on the order of a hundred damage-relevant ones. And the oracle cannot fill the gap: of the 530
items in `EffectData.csv`, **two** carry an attack multiplier — Silver Tear Mask and Blue
Dancer Charm. 186 carry some quantified effect, but they are stat changes, HP and stamina
rates, damage cuts and resistances. Every damage boost anyone would rank on — Shard of
Alexander, Godfrey Icon, Ritual Sword, Lord of Blood's Exultation — is prose in an `Effects`
column and a number in nobody's. That is why `BuffMult.csv` was hand-built, and why extending
it is hand work rather than a parse.

*The column.* A machine-readable **condition**. Today it is prose in `Notes` — *"While the
bleed-proc aura is active (20s)"* — and `buff-stack` sidesteps that by making the caller assert
it through `assume`. Ranking cannot sidestep it: to rank you must know which candidates apply.
A `Condition` column with a small controlled vocabulary (`none`, `after-bleed-proc`,
`full-hp`, `low-hp`, `charged-only`, ...) is enough. It does not need to be evaluable — the
`assume` mechanism already exists and works — it needs to be *filterable*.

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

**Deliberate, and now known to be the same gap as item 1.** `character-build`, `equip-load` and
`defence` all report figures *before* talismans. `equip-load` refuses to take one rather than
ignoring it, and `item-effect` pins `applied_to_a_build: false`, so nothing pretends otherwise.

This used to read as "`planner.py` stubbed `EffectData_Active`, so unstub it". That was wrong:
`EffectData_Active.csv` is a 27-row live panel from the Build Planner, not a table of effects.
There is nothing to unstub. Applying a talisman to a build needs the same quantified,
condition-tagged table item 1 needs, which is why they should be done together and why doing
this one first would be building on nothing.

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
