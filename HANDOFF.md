# elden-ring-vouch — handoff

Read this to resume after a fresh chat. It records what is built, what it rests on, what is
known to be missing, and the traps that have already cost time.

`README.md` says how to use the collection. This file says where the work stands.

*Last worked on 2 September 2026. Both repositories clean.*

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
  lib/oracle.py            the one place that knows where the oracle lives
  lib/spells.py            the spell tables, and the one multiply that is not the oracle's
  lib/buffs.py             what a buff multiplies per hit kind, and whether two of them stack
  lib/ashes.py             which affinities an ash accepts, and its hits on one weapon class
  nodes/                   nineteen nodes
  scripts/generate_cases.py  regenerates attack-power fixtures from the oracle
  VALIDATION.md            122 questions, worked one at a time — read this next
  BUGS.md                  what the questions found, open and fixed — the work list
```

**The `oracle/` vs `data/` split is the important one.** `oracle/` is a byte-identical copy of
the wiki extraction and is re-vendored by copying, never merging. `data/` holds tables that
came from the Prometheux workspace, which is a different provenance and is declared as such in
`data/README.md`. Anything new from that workspace goes in `data/`, never in `oracle/`.

## The nodes

| Node | Answers | Cases |
|---|---|---|
| `weapon-lookup` | resolve a name across the catalogue; class, infusability, upgrade cap | 11 |
| `weapon-rank` | a stat spread → the weapons it can use, ranked | 9 |
| `spell-lookup` | resolve a spell name; type, forms, families, requirements | 7 |
| `spell-rank` | a catalyst + a build → the spells it can cast, ranked | 6 |
| `ash-rank` | **a weapon class + an affinity → the ashes that fit, ranked four ways** | 7 |
| `boss-lookup` | an encounter's every phase: health, poise, defences, negations, immunities | 14 |
| `boss-coverage` | **many fights at once: which element covers them, which are immune** | 7 |
| `weapon-skill` | an ash of war's hits, motion values, affinities, and whether it replaces the scaling | 16 |
| `item-effect` | talismans, tears and runes: stats, weight, resistances | 11 |
| `buff-stack` | **what a set of buffs multiplies, for one kind of hit — and which do not stack** | 15 |
| `character-build` | class + named stats → full spread, rune level, HP/FP/stamina/load | 13 |
| `build-allocate` | weapon or spell + class + level → the spread | 21 |
| `attack-power` | one weapon at one spread → AR, scaling, requirements, status, guard | 18 |
| `optimal-affinity` | all thirteen infusions ranked against a target | 13 |
| `spell-power` | one spell from one catalyst → attack per type, family bonus, FP actually charged | 17 |
| `defence` | a build and armour → defences, negation, status resistances | 11 |
| `equip-load` | a loadout → weight, roll type, endurance to change it | 9 |
| `matchmaking` | **who a character can play with, and the upgrade bracket that keeps them there** | 9 |
| `stat-curve` | **what each point in a stat buys, and where the curve bends** | 7 |

`vouch -C . test` → **225 cases, 225 passed**.

## State of the evals

`vouch -C . eval --agent 'claude -p --allowedTools "" -- {prompt}' -n 3 --min-rate 0.9`

The last complete measurement was **24/24 across the 8 cases that ran** before a usage limit
cut the run short at case 9. Earlier complete runs went 89% → 95% → 96% → 100% as fabrications
were fixed. **The suite has not been measured end to end since `build-allocate` and
`weapon-skill` were added**, and three eval cases for them are unverified against a live model.
That is the first thing to do with a fresh token budget.

`--allowedTools ""` matters: with its own tools the agent reads the repository instead of
routing through the published context, which measures the wrong thing.

---

## The rule this project keeps re-learning

Every fabrication an eval caught was fixed **upstream of where it appeared** — by returning the
figure in the form a reader quotes, never by checking the prose harder. Ten instances so far,
the last four found by the question battery rather than by an eval:

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

**If a node leaves a caller one small sum, it has handed that sum to a model.** That is the
first thing to check when writing a new node.

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

---

## What is pending

### First: measure the suite

Run the evals end to end. They have not been measured since `build-allocate` and `weapon-skill`
were added, and **nothing in `.vouch/evals.toml` covers the four nodes and features the
question battery added** — no eval asks for a caster's spread, a weapon ranking, a spell
ranking, or a multiplier stack. Writing those cases is the other half of this job.

### Second: what the battery left open

`VALIDATION.md` has all 42 questions worked one at a time, with the calls, the figures and the
cross-checks. Thirty-three answer end to end and nine are partial. **No question is
unanswerable**, and the nine partials come down to four things:

1. **Flat-attack and scaling-overridden hits are read, not priced.** Six of the ten Pattern 4
   skills have one. `optimal-affinity` prices a hit through the weapon's attack rating, so a
   hit that carries flat attack (Ghostflame Ignition's 140 magic) or replaces the weapon's
   scaling (Sacred Blade's bullet off Faith) has no path. The data says *which stat drives it*,
   which is worth quoting, and the damage is not computed.

2. **The override is per hit, not per skill.** Sacred Blade's slash uses the weapon and its
   bullet does not. Any future skill objective has to model hits, not skills.

3. **`build-allocate` cannot optimise for a skill.** When a skill overrides the weapon's
   scaling the weapon-optimal spread is the wrong build, and the node can only say so. This is
   the natural next `focus`, and it needs (1) first.

4. **Guard counters have no motion value in the extraction**, so "best greatshield for guard
   counters" is answered on guard boost and negation instead.

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

Item locations. Those tables live only in
`prometheux-workspace/files/elden-ring-brain/`; vendor into `data/` with provenance.

---

## Working notes

- **Regenerate `attack-power` fixtures** with `python3 scripts/generate_cases.py` after
  re-vendoring `oracle/`. They come from `ap_calc.SCREENSHOT_CASES`, the only figures here that
  trace to the game rather than to code.
- **Pin new nodes against the ontology** wherever `prometheux-workspace/HANDOFF.md` records a
  figure. Its "Default checks that already persisted" section is a fixture source, and it is
  how the upgrade-cap bug was found.
- **The routing pack has grown and nobody has re-measured it.** The preamble is **38 notes,
  ~10 KB on its own**, against nineteen when this note first said pruning would eventually be
  needed — and there are thirteen nodes now rather than eleven. Measure the real pack before
  adding another note; `vouch describe` is not it, because the pack omits contracts.
- **`vouch <cmd> | head` can panic** on a broken pipe. Recorded in the runtime's `DECISIONS.md`
  as known roughness; it is a race and rarely reproduces.
- Contracts have caught genuine mistakes in this repository more than once — rune level is stat
  sum − 79 rather than points + 1, and `weight_left` is the roll-change headroom rather than
  unused capacity. When a contract fires while you are writing it, check the assumption before
  changing the contract.

## Resuming

```console
$ cd ~/Dev/elden-ring-vouch
$ vouch test                                    # 172 cases, no model
$ vouch call boss-lookup --input '{"query":"rennala"}'
$ vouch call build-allocate --input '{"weapon":"Rivers of Blood","affinity":"Standard",
    "upgrade":10,"max_upgrade":10,"starting_class":"Samurai","target_level":150,
    "focus":"bleed","vigor":40,"mind":20,"endurance":25}'
$ vouch call weapon-rank --input '{"strength":55,"dexterity":14,"intelligence":9,"faith":60,
    "arcane":9,"limit":10}'
$ vouch call build-allocate --input '{"weapon":"Dragon Communion Seal","affinity":"Standard",
    "upgrade":10,"max_upgrade":10,"starting_class":"Prophet","target_level":150,
    "focus":"spell","spell":"Rotten Breath","vigor":40,"mind":30,"endurance":20}'
$ vouch eval --agent 'claude -p --allowedTools "" -- {prompt}' -n 3 --min-rate 0.9
```

The runtime is at `~/Dev/vouch`; its own `DECISIONS.md` covers where that stands.
