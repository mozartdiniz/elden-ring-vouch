# The data the collection does not have

Everything here is blocked on a table, not on code. Each entry says what is missing, which
real questions it blocks, where to look for it, and how you will know it landed. Nothing in
this file needs a node rewritten first — that is the point of separating it.

Written 7 September 2026, after the node-rules, node-code and app work was done and these were
what remained. `HANDOFF.md` has the state of everything else.

**Read this first: most of what was written here as missing is not.**

This file originally said every entry needed a table vendored from
`prometheux-workspace/files/elden-ring-brain/`. That directory is not on this machine, and
checking each entry against what *is* here changed most of them:

- **Item 1 is done.** The talisman figures were in `EffectData.csv`'s prose the whole time.
- **Items 2 and 3 need no source.** `StatusEffectData.csv` and `ConsumableData.csv` are
  vendored and read by nothing.
- **Item 4 is three things and one source** — `regulation.bin`, unpacked.
- **Item 5 has no identified source at all.**

That is the same mistake three times over, and it is `BUGS.md`'s most common bug shape — *the
table already knew and the code did not look* — appearing in the plan rather than in a node.
Before writing that something is missing here, grep `oracle/extracted/*/csv/` for it.

Two things that looked like sources and are not: `EffectData_Active.csv` is a 27-row live panel
from the Build Planner, and `~/Dev/EldenRing/paramdex/` is two ID-to-name maps. Paramdex
upstream is the same — it publishes definitions and names, **not values**.

**The standing rule still holds:** read a source's file list before writing a parser. Three of
the twenty-five bugs in `BUGS.md` exist because one was written against prose while the
structured table sat unused. New tables go in `data/`, never in `oracle/`, and
`data/README.md` declares the provenance.

---

## 1. Talismans — done, and `item-rank` is built

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

**`item-rank` is in**, 10 fixtures, ranking on `buffs.multiplier(entry, hit_kind)` with the
conditional ones flagged and `unconditional_only` for the question behind most askings of
"what should I wear". It ranks and does not choose: the slot count and the fight are the
caller's, and it names `buff-stack` as what prices a chosen set.

**What is left of this entry:** re-run question 5.1 against a live model, correct its
`VALIDATION.md` entry, and remove its line from `EXPECT` in `scripts/compare_models.py` — or
the battery will score a correct answer as a failure.

## 2. Status procs — readable now, from a table nobody reads

**No source needed.** `oracle/extracted/.../StatusEffectData.csv` is 1,512 rows, vendored, and
**no node in this collection reads it**. It carries what this entry was written to say was
missing:

| | frost | bleed | rot |
|---|---|---|---|
| `changeHpPoint` / `changeHpRate` | 30 flat | **15% + 100 flat** | 0.18% + 15 |
| `effectEndurance` | 40s | 1s | 90s |
| `neutralDamageCutRate` | **1.2** — the +20% damage taken | 1.0 | 1.0 |

That is question **11.3** — *"what exactly does the frostbite proc do, damage and the
damage-taken debuff"* — and **11.4**, answered from disk. Keyed by `SpEffectId` and
`statusType`, 268 frost rows, 270 bleed, 212 rot, 296 poison.

**Done when.** A node reports a status's proc — damage, duration, debuff — and 11.3 and 11.4
answer end to end. `EXPECT` in `scripts/compare_models.py` lists 11.3 in the refusal arm; take
it out in the same commit or the battery will score a correct answer as a failure.

**What is *not* here** is the buildup accumulation and decay rate — how fast a bar fills and
drains. That is the part of 11.4 about why a lower-buildup weapon can proc faster, and it needs
the source in item 5.

## 3. Consumables and locations — also readable now

**No source needed for the damage.** `ConsumableData.csv` is vendored and unread: 91 rows,
`Name, AtkID, attackBase{Physics,Magic,Fire,Thunder,Dark}`. Fire Pot at 230 fire, Redmane Fire
Pot at 326.

**Locations are on the machine**, in `~/Dev/EldenRing/DataSet` — `locations.csv` (177 rows,
region and description) and `items.csv` (462 rows, with an `obtainedFrom` column). That is the
fanapis export, a different provenance from `oracle/`, so it goes in `data/` with the
declaration `data/README.md` requires.

## 4. Three things that need the game's own params

These are one task, not three. All of them need `regulation.bin` unpacked — a game install and
a param tool — and none of them will ever appear in a spreadsheet extraction.

- **Black Flame's percentage-of-max-HP burn (11.2).** The hook is present and the row is not:
  `MagicData` gives Black Flame `durationSpEffect` 1626000 and 1627000, and neither resolves in
  `StatusEffectData`, which only covers status buildup. **Needs `SpEffectParam`.**
- **Range, reach and cast time (Pattern 15, 15.6).** `MagicData` has a `bulletRange` column and
  it is a false friend — the values are bullet *ids* like `10402151`, pointing into a `Bullet`
  param that was not extracted. `EquipParamWeapon` has no reach, range or length column among
  its 71. **Needs `Bullet`, and something for weapon reach.**
- **Guard-counter motion values (item 4 as it was).** `EquipParamWeapon` carries guard
  *defence* — `physGuardCutRate`, `staminaGuardDef`, `guardCutCancelRate` — and no motion value
  of any kind. No poise, stance or motion column exists. **Needs `AtkParam`.**

## 5. The stance-break rule, which is in no table anywhere

`boss-lookup` gives a fight's poise and `ash-rank` gives an ash's poise damage, so *"how many
of these break that"* is arithmetic a caller can already do. What is missing is the rule that
makes it meaningful: how stance damage accumulates, how fast it decays, and what a break
actually does. Same shape as the status buildup rates in item 2.

This is the only entry with no identified source at all. It may not be extractable from
anything; it may be community knowledge that would have to be asserted rather than computed,
which is a decision about what this collection is willing to publish.

---

## Where this leaves the data work

**Buildable now, with nothing that is not already on this machine:**

| | needs | closes |
|---|---|---|
| 1. talismans | *done* | 5.1, once `item-rank` exists |
| 2. status procs | read `StatusEffectData.csv` | 11.3, 11.4 |
| 3. consumables and locations | read `ConsumableData.csv`, vendor the fanapis export | Pattern 13, item questions |

**Parked, and honestly answered in the meantime:**

| | needs | affects |
|---|---|---|
| 4. Black Flame, range, guard counters | `regulation.bin` unpacked — one source, three items | 11.2, Pattern 15, guard-counter questions |
| 5. stance break | no identified source | 11.6 |

Every parked question is one the collection currently answers with an honest refusal, and
three of them are held in the battery's refusal arm so a future change cannot quietly start
guessing. That is the design working. It is the difference between a tool that covers less
than a player wants and one that cannot be trusted, and the collection stays on the right side
of that line for as long as this file is unfinished.

