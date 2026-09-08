# The data the collection does not have

Everything here is blocked on a table, not on code. Each entry says what is missing, which
real questions it blocks, where to look for it, and how you will know it landed. Nothing in
this file needs a node rewritten first — that is the point of separating it.

Written 7 September 2026, after the node-rules, node-code and app work was done and these were
what remained. `HANDOFF.md` has the state of everything else.

**Before starting any of it, read this.** The sourcing plan this file was written with does
not hold, and for item 1 it turned out not to be needed.

`prometheux-workspace/files/elden-ring-brain/` **is not on this machine.** Three places in the
documentation said to vendor the missing tables from it. For items 2, 3, 4 and 6 the first
task is therefore *find a source*, which is a different job from parsing one — and two things
that looked like sources are not:

- `oracle/extracted/.../EffectData_Active.csv` is a 27-row live panel from the Build Planner,
  mostly blank, with no header. Not a stubbed effect table; there is nothing to unstub.
- `~/Dev/EldenRing/paramdex/` holds two files and both are ID-to-name maps. Paramdex upstream
  is the same: it publishes **definitions and names, not values**. The values live in the
  game's `regulation.bin`, and there is no Elden Ring install on this machine.
- `~/Dev/EldenRing/DataSet/` is the fanapis export. 87 base-game talismans plus DLC, with
  `id, name, image, description, effect` — and `effect` is prose with no numbers in it at all
  (*"Raises attack power of arrows and bolts"*). Useful as the **roster**, which is the
  checklist of what any table must cover. Useless as the table.

**Item 1 needs none of them.** See below: the figures were in `oracle/` the whole time.

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

**Why the Build Planner does not already do this, which is the thing worth understanding.**

The obvious question is how the source workbook manages without this table. The answer is in
`oracle/extracted/.../formulas/`, and it is not "it does it some other way".

The wiring is real and complete. `EffectData_Active` pulls the user's equipped items from the
Planner's dropdowns and looks each one up:

```
C4:  =PlannerData!E3
E3:  =IF($D3, E$1, IFERROR(VLOOKUP($C3, EffectData!$A:$AW,
                    MATCH(E$2, EffectData!$2:$2, 0), False), E$1))
```

Row 25 aggregates the result and `PlannerData` reads it back — `=EffectData_Active!AR25`, which
is `physicsAttackPowerRate`. So an effect that lands in one of the numeric columns *is* applied
to the damage figure, automatically, with no user arithmetic.

**And the prose column is read by nothing.** Zero references to `EffectData!B` across every
sheet in the workbook. The multiplier in *"Increases damage by 1.15x ... with weapon skills"* is
shown to the person and never enters a calculation.

The reason is structural rather than an oversight. The workbook's effect model has **a
damage-type axis and no hit-kind axis**: five columns, `physics`/`magic`/`fire`/`thunder`/
`dark` AttackPowerRate. Shard of Alexander's boost applies to weapon skills, Godfrey Icon's to
charged attacks, Lord of Blood's Exultation's to everything but only after a bleed proc. None
of those is a damage type, so there is no cell to put them in, and the author wrote the number
into the description instead. That is why only two of 530 items carry an attack multiplier: not
missing data, a model that cannot express the effect.

So the Build Planner **does not apply Shard of Alexander**. It applies that talisman's stat and
defence columns and silently ignores its damage. The user is expected to know.

Two things follow. `item-effect` pinning `applied_to_a_build: false` and `equip-load` refusing
to take a talisman are not gaps in the port — they are honest about a limit that is real in the
source. And `data/BuffMult.csv` having a `HitKind` column is not a stylistic choice: it is the
axis the workbook lacks, which is why the two tables cannot be merged and why this one has to
be built rather than extracted.

**Where the numbers are: `oracle/extracted/.../EffectData.csv`, in the prose column.**

This was looked for in the wrong place twice. The quantified columns are no help — of 530
items, **two** carry an attack multiplier. But the `Effects` column is not free text. It is
generated, and it is regular:

```
Shard of Alexander          "Increases damage by 1.15x (holy bugged in PvP: 1x) with weapon skills"
Godfrey Icon                "Increases damage by 1.15x ... with charged spells and charged weapon skills"
Lord of Blood's Exultation  "Increases damage by 1.2x (1.12x in PvP) for 20 seconds when bleed is triggered within 7m"
Ritual Sword Talisman       "Increases damage by 1.1x while at full HP"
```

**157 of the 530 rows** say *"increases damage by Nx"*. 112 carry a separate PvP figure. 127
carry a condition clause, and the clauses cluster into a small vocabulary — *with weapon
skills*, *with jump attacks*, *when bleed is triggered within 7m*, *while at full HP*, *with
Dragon Cult incantations*. That vocabulary is the `Condition` column, discovered rather than
invented.

`BuffMult.csv` is still the target shape, and it already has 21 buffs in it:

```
Name, Kind, Slot, HitKind, MultPve, MultPvp, Notes
Shard of Alexander, Talisman, Passive, Skill, 1.15, 1.15, All weapon skills...
```

**The 21 are the differential check, and they already agree.** They were hand-built from a
different source, and the prose gives the same figures — Shard of Alexander 1.15 on `Skill`,
Lord of Blood's Exultation 1.2 PvE and 1.12 PvP. So a parser over `Effects` can be verified
against them before it is trusted for the other 136, which is the same shape of check the two
implementations gave each other everywhere else in this project.

**Yes, this is writing a parser against prose, which `BUGS.md` warns about twice.** The warning
is worth re-reading and then overruling here, because it is a warning about writing a parser
*while the structured table sits unused* — bugs 11 and 15. There is no structured table: the
quantified columns are empty for exactly these items, upstream publishes names without values,
and the game data is not on this machine. The prose is machine-generated, regular, and comes
with a 21-row validation set. Those are different circumstances and they point the other way.

**Extracted, named, and checked.** `scripts/extract_talisman_buffs.py` writes
`data/BuffMult-talismans.draft.csv` — 33 talismans in `BuffMult.csv`'s exact shape, 759 rows,
directly appendable once the names are agreed. Re-runnable, so re-vendoring `oracle/` cannot
leave it stale.

**There is no schema decision. That was my error and the check found it twice.**

I first wrote this entry claiming two decisions were needed — a `Condition` column and a
representation for stacking ramps. Neither is. `lib/buffs.py` already says so:

> `state_conditional`: *True when the figure is above 1 on every hit kind. Then the condition
> is not the kind of hit but a state — a bleed proc, full HP, **a successive hit tier** —
> which nothing here can observe, so the caller has to assert it.*

So a buff gated on a **state** takes its multiplier on all eight hit kinds; that is what makes
`buff-stack` demand `assume`. Nine of the 33 are like that — the four Exultations, Blade of
Mercy, the HP gates. A **ramp** is one of those states, and the table records where the ramp
lands. My extractor was reading the first tier off the prose and the ten known talismans said
so on its first run; I wrote that up as a difference of convention when it was a bug.

**What is left is one naming pass, against an unchanged schema.** Twenty-one clauses become
`HitKind` values, of which six already exist. The proposal is in the script, applied to the
draft, and reproduces all ten known talismans exactly:

| clause | HitKind |
|---|---|
| with weapon skills | `Skill`, `ChargedSkill` |
| with charged spells and charged weapon skills | `ChargedSkill`, `ChargedR2` |
| with charged R2s / jump attacks / continuous attacks | `ChargedR2` / `Jump` / `Successive` |
| with guard counters | `GuardCounter` *(new)* |
| with horseback / dashing / rolling / 2h attacks | `Horseback`, `Dashing`, `RollBackstep`, `TwoHanded` *(new)* |
| with arrow / bolt, aimed arrow / bolt | `Ranged`, `RangedAimed` *(new)* |
| with kicking / weapon-throwing / roar / pot / perfume / storm / magma / final light | *(new)* |

**Fifteen new `HIT_KINDS` values.** Adding them touches `lib/buffs.py` and `buff-stack`'s input
schema, and nothing else.

That check is worth keeping for its own sake: *"with weapon skills"* naively means `Skill`, and
the table has Shard of Alexander on `ChargedSkill` too, because a charged weapon skill is still
a weapon skill. The ten hand-assigned rows knew a domain fact the clause does not state, and
the proposal only reproduces them because the check made it.

**Do not** build a ranking over what exists now. Ranking on a partially populated table would
produce exactly the well-formed answer about nothing that this collection exists to prevent,
and it would be attested.

**Done when.** `data/BuffMult.csv` covers the talisman roster in `~/Dev/EldenRing/DataSet`,
its 21 original rows are unchanged and still agree, `vouch call item-rank` ranks for a stated
goal and hit kind, and question 5.1 answers end to end — with its `VALIDATION.md` entry
re-run and corrected, and its line removed from `EXPECT` in `scripts/compare_models.py`, or
the battery will start scoring a correct answer as a failure.

**A note on where not to get this.** Several online builders do apply talismans, and their
existence is useful evidence that the classification is tractable. They are still not a source.
Use one as a *third* check if you like — compute a build with and without a talisman and
compare the ratio — but never ingest their numbers. Where a builder disagrees with the oracle,
the oracle wins, because its figure can be traced and theirs cannot.

That is not mainly a licensing point, though `data/README.md` declares provenance for every
table for a reason. It is that attestation checks a figure came from a node and cannot check
the table underneath. An untraceable number placed under the guarantee gets certified by it,
which is the one failure mode with no downstream guard. Fextralife and its kin carry
community-entered, frequently patch-stale figures; that is exactly the class of number this
collection exists to replace, and putting it *below* the runtime rather than above it would be
the worst possible place for it.

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
