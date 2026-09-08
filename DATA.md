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

## 1. Talismans — done, and `item-rank` is now buildable

**Closed 8 September 2026.** `data/BuffMult.csv` carries **33 damage talismans** where it
carried ten, across 23 hit kinds where it carried eight. `buff-stack` handles them with no node
code changed.

The figures were never missing. They were in `oracle/extracted/.../EffectData.csv`'s `Effects`
column — prose, generated and regular, read by nothing: not by this collection and not by the
workbook it came from. `scripts/extract_talisman_buffs.py` parses it and
`scripts/merge_talisman_buffs.py` merges it, both re-runnable so re-vendoring `oracle/` cannot
leave the table stale.

**What made it safe was the ten rows that already existed.** They were assigned by hand from a
different source, so the extractor reproducing them — figures *and* hit kinds — is evidence
rather than tautology. It caught two real errors on the way. The first was mine reading the
leading value of a stacking ramp where the table records where the ramp lands. The second was
subtler: *"with weapon skills"* naively means `Skill`, and the table has Shard of Alexander on
`ChargedSkill` as well, because a charged weapon skill is still a weapon skill. Ten hand-made
rows knew a domain fact the prose does not state.

**And one trap worth keeping in mind for any future widening.** `buffs.state_conditional`
decides a buff is gated on a *state* rather than a hit by asking whether its figure is above 1
on every hit kind, against `len(HIT_KINDS)`. Adding names to that tuple without adding a row
for each to every existing buff would have left nine buffs above 1 on eight of twenty-three —
so they would have stopped counting as state-gated, and `buff-stack` would have quietly stopped
asking the caller to assert a bleed proc or full HP. Nothing would have failed; Ritual Sword
Talisman's 1.1x would just have started applying to builds that are not at full HP. The merge
script widens every existing buff and refuses to write if any would lose the flag.

**What is left of this entry:** build `item-rank`. It is now a ranking over
`buffs.multiplier(entry, hit_kind)`, which exists, against a table that covers the field. When
it lands, re-run question 5.1, correct its `VALIDATION.md` entry, and remove its line from
`EXPECT` in `scripts/compare_models.py` — or the battery will score a correct answer as a
failure.

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
