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
  nodes/                   eleven nodes
  scripts/generate_cases.py  regenerates attack-power fixtures from the oracle
```

**The `oracle/` vs `data/` split is the important one.** `oracle/` is a byte-identical copy of
the wiki extraction and is re-vendored by copying, never merging. `data/` holds tables that
came from the Prometheux workspace, which is a different provenance and is declared as such in
`data/README.md`. Anything new from that workspace goes in `data/`, never in `oracle/`.

## The nodes

| Node | Answers | Cases |
|---|---|---|
| `weapon-lookup` | resolve a name across 570 weapons; class, infusability, upgrade cap | 11 |
| `boss-lookup` | an encounter's every phase: health, poise, defences, negations, immunities | 14 |
| `weapon-skill` | an ash of war's hits, motion values, and whether it replaces the scaling | 8 |
| `item-effect` | talismans, crystal tears, great runes — individually and combined | 11 |
| `character-build` | class + named stats → full spread, rune level, HP/FP/stamina/load | 13 |
| `build-allocate` | **weapon + class + level → the spread**, maximising attack or a status | 13 |
| `attack-power` | one weapon at one spread → AR, scaling, requirements, status, guard | 18 |
| `optimal-affinity` | all thirteen infusions ranked against a target | 13 |
| `spell-power` | one spell from one catalyst → attack, family bonus, castability | 10 |
| `defence` | a build and armour → defences, negation, status resistances | 11 |
| `equip-load` | a loadout → weight, roll type, endurance to change it | 9 |

`vouch -C . test` → **131 cases, 131 passed**.

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
figure in the form a reader quotes, never by checking the prose harder. Six instances so far:

| the agent wrote | because the node | the fix |
|---|---|---|
| an invented dexterity | required stats the user had not given | `character-build` fills from class minimums |
| `259` off a `259.576275` | returned only full precision | `attack_shown` / `status_shown` |
| `47` for "at RL150" | returned level 103 and no target | `target_level` → `levels_to_target` |
| `409` out of `"409/0/411/0/0"` | published figures inside a string | `shown` numbers beside it |
| `2` more points needed | returned `req_met` and not the gap | `scaling.<stat>.shortfall` |
| — | had no allocator at all | `build-allocate` |

**If a node leaves a caller one small sum, it has handed that sum to a model.** That is the
first thing to check when writing a new node.

The corollary, learned twice the hard way while writing fixtures here: take a number from the
node, never from what it looked like on screen. Two fixture figures were written from a
truncated display and completed from memory; both failed and both were caught.

## Findings worth not rediscovering

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

Run the evals end to end. Three cases (`build-allocate` ×2, `weapon-skill` ×1) have never been
seen by a live model.

### Second: the two question shapes still unanswered

Tested against fourteen real questions. Eleven are answerable end to end. The two gaps:

1. **Skill damage is reported but never priced.** `weapon-skill` gives motion values and
   `optimal-affinity` takes an `attack_mv`, so the pieces exist and are not wired. Until they
   are, "build focused on Transient Moonlight" gets a spread optimal for the *weapon*, with a
   note that the skill was not modelled. Needs care: 173 of 2643 hits override the weapon's
   scaling, and for those the weapon-optimal spread is the wrong answer.

2. **`build-allocate` cannot build a caster.** It maximises weapon attack or a status. A
   question like "distribuição pra Comet Azur full INT" gets requirements and spell AR from
   `spell-power`, but no optimised spread. The objective would be spell attack through a
   catalyst, which `spell-power` already computes — the search is the same, the objective is
   different.

### Deliberately absent, not pending

- **Applying talisman effects.** `item-effect` says what an item is worth and combines several.
  Nothing *applies* one: `planner.py` stubbed `EffectData_Active`, so `character-build`,
  `equip-load` and `defence` all report figures before talismans. `equip-load` refuses to take
  one rather than ignoring it; `item-effect` pins `applied_to_a_build: false`. Closing this
  means either modelling the effects, which has no oracle, or having the caller add them and
  say so.
- **Poise.** `planner.py` returns a figure on a scale not reconciled with the game's, so it is
  not published. An unverified number reads as authoritative.

### Not ported at all

Consumables, matchmaking bands, item locations. Those tables live only in
`prometheux-workspace/files/elden-ring-brain/`; vendor into `data/` with provenance.

---

## Working notes

- **Regenerate `attack-power` fixtures** with `python3 scripts/generate_cases.py` after
  re-vendoring `oracle/`. They come from `ap_calc.SCREENSHOT_CASES`, the only figures here that
  trace to the game rather than to code.
- **Pin new nodes against the ontology** wherever `prometheux-workspace/HANDOFF.md` records a
  figure. Its "Default checks that already persisted" section is a fixture source, and it is
  how the upgrade-cap bug was found.
- **The routing pack is 404 lines / 26 KB** (~7k tokens) with nineteen preamble notes. Fine
  today. It grows with every node, and at some point the preamble needs pruning rather than
  appending.
- **`vouch <cmd> | head` can panic** on a broken pipe. Recorded in the runtime's `DECISIONS.md`
  as known roughness; it is a race and rarely reproduces.
- Contracts have caught genuine mistakes in this repository more than once — rune level is stat
  sum − 79 rather than points + 1, and `weight_left` is the roll-change headroom rather than
  unused capacity. When a contract fires while you are writing it, check the assumption before
  changing the contract.

## Resuming

```console
$ cd ~/Dev/elden-ring-vouch
$ vouch test                                    # 131 cases, no model
$ vouch call boss-lookup --input '{"query":"rennala"}'
$ vouch call build-allocate --input '{"weapon":"Rivers of Blood","affinity":"Standard",
    "upgrade":10,"max_upgrade":10,"starting_class":"Samurai","target_level":150,
    "focus":"bleed","vigor":40,"mind":20,"endurance":25}'
$ vouch eval --agent 'claude -p --allowedTools "" -- {prompt}' -n 3 --min-rate 0.9
```

The runtime is at `~/Dev/vouch`; its own `DECISIONS.md` covers where that stands.
