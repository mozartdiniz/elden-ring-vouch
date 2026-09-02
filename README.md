# elden-ring

A [`vouch`](https://github.com/mozartdiniz/vouch) collection: Elden Ring build maths an agent
can be held to. Attack rating, scaling, requirements, status buildup and rune levels, computed
from the Build Planner spreadsheet tables rather than recalled by a model.

Ask a language model what Ordovis's Greatsword hits for at 60 strength and 60 faith and it
will give you a number. Ask this and you get 416 AR, a note that a Hero's dexterity is below
the weapon's requirement, and a ledger line saying which bytes produced both.

## The maths is not ours

`oracle/` is a verbatim copy of the extracted Build Planner spreadsheet: the CSV tables and
the Python that reimplements their formulas. It is **not edited here**, so it can be
re-vendored from upstream by copying rather than by merging, and so the arithmetic in this
repository is traceable to the spreadsheet rather than to us.

What this collection adds is everything the spreadsheet port does not have:

- **Contracts** — the conditions under which a number means anything.
- **Refusals** — a machine-readable "no answer" instead of a plausible one.
- **A ledger and attestation** — every call recorded, and a written answer reconciled against
  it, so a figure in the prose that no node produced is caught.
- **Routing context** — what to call, in what order, and what not to call.

That division matters, because the oracle is not shy. Asked for Moonveil +25, an upgrade level
the game does not have, `ap_calc.py` returns 180.39 without complaint — *lower* than the 643
the weapon really reaches at its +10 cap, so it does not even look wrong. Every guard against
that kind of answer lives in this repository, not in `oracle/`.

## Try it

```console
$ vouch -C . call weapon-lookup --input '{"query":"ordovis"}'
{
  "resolved": "Ordovis's Greatsword",
  "weapon_class": "Greatsword",
  "infusable": false,
  "max_upgrade": 10,
  ...
}
```

`max_upgrade` and `infusable` are the two bounds `attack-power` cannot check for itself — a
CEL precondition sees only the call's own arguments, never the weapon table — so a caller
carries them across:

```console
$ vouch -C . call attack-power --input '{
    "weapon": "Ordovis'\''s Greatsword", "affinity": "Standard",
    "upgrade": 25, "max_upgrade": 10,
    "strength": 60, "dexterity": 13, "intelligence": 10, "faith": 60, "arcane": 9 }'
{"outcome":"refusal","code":11,"node":"attack-power","reason":"this weapon cannot be upgraded
that far; weapon-lookup reported a lower max_upgrade for it — smithing-stone weapons reach
+25, somber weapons +10, and some weapons cannot be reinforced at all"}
```

At `+10` the same call returns 809 AR — the figure on the spreadsheet screenshot, pinned as a
fixture.

## The nodes

| | |
|---|---|
| `weapon-lookup` | Resolve a name across 570 weapons; report class, infusability and upgrade cap |
| `character-build` | A starting class plus the stats a user named → the full spread, rune level, HP, FP, stamina, equip load |
| `attack-power` | One weapon at one upgrade and stat spread → attack rating, scaling grades, requirements, status, guard |
| `optimal-affinity` | All thirteen affinities of one weapon, ranked by damage against a target |
| `spell-power` | One spell from one catalyst → attack, family bonus, FP cost, whether the build can cast it |
| `equip-load` | A loadout against a build's equip load → weight, roll type, and the endurance to change it |
| `defence` | A build and an armour set → per-element defences, damage negation, status resistances |
| `build-allocate` | A weapon, class and rune level → the stat spread, maximising attack or a status |
| `boss-lookup` | A boss encounter → every phase, each with its own health, poise, defences, negations and immunities |
| `weapon-skill` | An ash of war → its hits, motion values, and whether it replaces the weapon's scaling |
| `item-effect` | Talismans, crystal tears and great runes → what they do, individually and combined |

The order is the routing: **character-build** when the user described a build by only some of
its stats, **weapon-lookup** for any question naming a weapon, then **attack-power** for what
it hits for, or **optimal-affinity** for what to infuse it with.

### The question people actually ask

Every real question this collection was tested against has the same shape: *"monta a
distribuição"* — give me the spread. Everything else here reports on a spread somebody already
chose, so `build-allocate` is the node that answers it:

```console
$ vouch -C . call build-allocate --input '{"weapon":"Rivers of Blood","affinity":"Standard",
    "upgrade":10,"max_upgrade":10,"starting_class":"Samurai","target_level":150,
    "focus":"bleed","vigor":40,"mind":20,"endurance":25}'
{ "level": 150, "minimum_level": 73, "feasible": true,
  "stats": { "vigor": 40, "mind": 20, "endurance": 25, "strength": 12,
             "dexterity": 18, "intelligence": 9, "faith": 8, "arcane": 97 },
  "total_ar_rounded": 644, "status_shown": { "bleed": 79 }, ... }
```

Three things about it are worth knowing before trusting an answer built on it.

**The arithmetic is still the oracle's.** The node searches over spreads and asks `ap_calc` what
each is worth, so a spread's attack rating here is the same number `attack-power` gives for the
same stats — checked, not assumed. What is new is the search, not the maths.

**The survivability floors are yours.** How much vigor a build "should" have is a judgement with
nothing behind it, and a node that picked one would present an opinion as a calculation. `vigor`,
`mind` and `endurance` are required inputs, echoed back with
`floors_are_the_callers_choice: true`, and an answer has to say they were chosen.

**The focus changes the character.** Rivers of Blood at RL150 from a Samurai start puts 97 into
arcane for bleed, and 56 dexterity / 59 arcane for raw attack. Asking for one and reporting the
other is a different build.

What it does **not** know is skill damage. Four of the real questions it was tested against
ask for a build "focused on" an ash of war — Corpse Piler, Transient Moonlight — and a spread
that maximises a weapon is not always the spread for its skill. `weapon-skill` is what closes
that: 173 of the 2,643 recorded hits replace the weapon's scaling with a single stat, so it
reports `overrides_weapon_scaling` and an answer can say which case it is in. Corpse Piler does
not override, so the Rivers of Blood spread above genuinely applies to it; Ground Slam replaces
the scaling with strength, so it would not.

An impossible build is an answer rather than an error: a Rivers of Blood build at RL40 comes
back `feasible: false` with `minimum_level: 79`, because "that needs RL79" is what the asker
needs to hear.

### The question these compose to answer

"What should I infuse this with for Rennala?" is not the same question as "what should I infuse
this with", and the difference is the whole point:

```console
$ vouch -C . call boss-lookup --input '{"query":"rennala"}'
{ "resolved": "Rennala, Queen of the Full Moon", "location": "Academy of Raya Lucaria",
  "phase_count": 3, "multi_phase": true,
  "phases": [
    { "label": "Phase 1", "health": 3493.0, "poise": 0.0,
      "negation": { "physical": -10.0, "magic": 80.0, ... },
      "weak_to": ["physical", "pierce", "slash"],
      "immune_to": ["death", "madness", "sleep"] },
    { "label": "Bubble (Phase 1)", "negation": { "physical": 100.0, ... }, ... },
    { "label": "Phase 2", "health": 4097.0, "poise": 80.0, ... } ] }
```

A phase is the fight's own structure, so all of them come back and there is deliberately no
boss-level `negation` to quote instead: her first phase has no poise and takes extra physical,
her second has 80 poise and twice the frost resistance, and her bubble blocks everything. One
number for "Rennala" answers a question about a fight that does not exist.

Hand a phase's `negation` to `optimal-affinity` and the ranking changes: **Heavy** wins against
Rennala's first phase, where **Flame Art** wins against the generic reference. Add the multipliers from
`item-effect` for a couple of talismans and Standard and Quality overtake Flame Art too. None
of that is guessable, and all of it is a figure some node returned.

A name is not an identity either. Forty-seven names in that table are used in more than one
place — nine Death Rite Birds, from 3442 to 28905 health — so `boss-lookup` keys an encounter
on its name *and* its location, and reports the places when a query matches several. Keying on
the name alone was a real bug here: it kept whichever row came last in the file and called it
resolved.

The routing is `boss-lookup` → `optimal-affinity`, with `item-effect` alongside when the user
named a talisman. `item-effect` combines several items itself — stats summed, multipliers
multiplied — because that arithmetic in a caller is arithmetic a model performs.

`optimal-affinity` is the one worth trying first. "What should I infuse this with" is thirteen
comparisons against a target's defences — the shape of question a model answers from folk
wisdom, and the folk wisdom is often wrong. On a 60-strength two-handed Zweihander it is Fire
at 691, not Heavy at 662. On a 60-faith Longsword, Flame Art beats Sacred by 3.7 damage, which
is a coin toss and gets reported as one:

```console
$ vouch -C . call optimal-affinity --input '{"weapon":"Longsword","upgrade":25,
    "max_upgrade":25,"strength":60,"dexterity":13,"intelligence":10,"faith":60,"arcane":9}'
{ "best": "Flame Art", "best_damage": 492.08, "runner_up": "Sacred", "best_margin": 3.68, ... }
```

It also does in one call what the Prometheux ontology this collection re-implements needs
thirteen runs for: a Vadalog `${param}` concept cannot be spliced across thirteen affinities,
so the ranking had to be assembled by the caller. A node is a subprocess, so it just returns
the table.

## Three failures this is built around

Each of these was seen, not imagined.

**A number for a state the game does not have.** Moonveil +25. `attack-power` returns the
weapon's real cap alongside the answer, and a postcondition compares them, so the figure never
reaches stdout. When the caller passes `max_upgrade` from `weapon-lookup` it is caught one step
earlier, as a refusal that says what to do instead — and a caller who passes a *generous* cap
to get past that refusal is still caught by the postcondition, which uses the cap the node
looked up itself.

**A substitution nobody was told about.** A non-infusable weapon ignores the affinity it is
given: ask for a Heavy Moonveil and the sheet quietly prices a Standard one. The result carries
`affinity_requested`, `affinity_applied` and `affinity_ignored`, so an answer cannot repeat the
affinity that was asked for. `character-build` does the same for a stat asked below its class
floor.

**An invented stat, quoted back.** On the first live eval run, asked for a strength-faith build
at 60/60, the agent called `attack-power` — which needs all five stats — and made the other
three up, then wrote "your 12 dexterity". `vouch attest` refused the 12: no node had produced
it. `character-build` exists because of that run. An unnamed stat is now the starting class's
minimum, which is real data, and the result names which stats nobody chose.

The general rule, and it is worth stating because it is easy to get backwards: **the fix for a
fabricated number is usually upstream of where it appears.** Checking harder at the end catches
it; not making the caller invent it stops it.

## The second implementation, actually used

`spell-power` is the one node whose arithmetic is not the oracle's. The Python scripts stop at
a catalyst's spell buff; `attack = magic_attack x spell_buff / 100 x bonus` is ours, and the
family bonus needs `data/MagicFamily.csv`, which comes from the Prometheux ontology rather than
the spreadsheet.

So its fixtures are pinned against **that ontology's own recorded figures** — the independent
implementation this collection is a second version of. All five agree to six significant
figures:

| | Prometheux | here |
|---|---|---|
| Comet, Carian Regal Scepter +10 | 1090.912 | 1090.912 |
| Comet, Lusat's Glintstone Staff +10 | 1207.42 | 1207.42 |
| Comet, Academy Glintstone Staff +25 | 1009.444 | 1009.444 |
| Adula's Moonblade, Carian Glintstone Staff +25 | 503.97 | 503.97 |
| Ranni's Dark Moon, Carian Regal Scepter +10 | 1356.168 | 1356.168 |

`defence` and `attack-power`'s guard figures are pinned the same way, against the ontology's
recorded `character_defense`, `resist_base`, geared resists, and `guard_negation` /
`guard_boost` / `guard_resist` — a bare Vagabond's 79/93/85/75/89, base resists 92/92/92/99,
the Knight set's 200/224/147/154, and a Longsword's 45/30 block with a boost of 36.

Getting there took a real bug out of this collection. `max_upgrade` was "+25 if infusable, else
+10", which is right for 512 of the 570 weapons and wrong for 58 — including the Academy and
Carian Glintstone staves, which take no affinity and still upgrade to +25. Two of the five
figures disagreed until the cap was read from the reinforce table instead, where it belongs.
That is what a second implementation is for, and it earned its place on the first comparison.

## Testing

```console
$ vouch -C . test
80 cases, 80 passed, 0 failed
```

`nodes/attack-power/cases.toml` is **generated**, by `scripts/generate_cases.py`, from
`ap_calc.SCREENSHOT_CASES` — eight inputs whose outputs were read off the Build Planner
spreadsheet by hand. Those are the only figures here that trace back to the game rather than to
code, so they are what the fixtures pin, and generating the file means the expectations are the
oracle's rather than ones written from the same head as the node. Regenerate after re-vendoring
`oracle/`; the diff is then the spreadsheet's.

The hand-written cases at the end of that file cover what the oracle has no opinion about,
because it is what this collection adds: the bounds, the substitutions, and the refusals.

```console
$ vouch -C . eval --agent 'claude -p --allowedTools "" -- {prompt}' -n 3 --min-rate 0.9
...
27/27 runs passed (100%); the floor is 90%
```

Routing evals, with a model in the loop, so a rate rather than a pass. `--allowedTools ""`
matters: with its own tools the agent may read this repository instead of routing through the
published context, which measures the wrong thing.

The suite has been at 100% since the last of the fabrications was fixed upstream. It did not
start there — 89%, then 95%, then 96% — and each gap closed by returning a figure in the form
a reader quotes rather than by checking the prose harder. The routes are worth reading as much
as the rate: the agent chains `weapon-lookup → character-build → attack-power` unprompted, and
calls `spell-power` twice to compare two catalysts.

## Layout

```
elden-ring-vouch/
  .vouch/
    registry.toml      collection-level routing: what to call first, and what never to assume
    evals.toml         natural-language questions and what must happen
  oracle/              vendored verbatim, never edited
    scripts/           ap_calc.py, planner.py, opt_affinity_calc.py
    extracted/         the Build Planner CSV tables and their formulas
  lib/oracle.py        the one place that knows where the oracle lives
  nodes/               weapon-lookup, character-build, attack-power
  scripts/             generate_cases.py
```

## What is not ported yet

The Prometheux ontology this collection is a second implementation of still covers ashes of
war and their motion values, consumables, matchmaking bands, and item locations. Those tables
mostly live only in that workspace, not in the Build Planner extraction, so porting one starts
by vendoring it into `data/` with its provenance recorded — the way `MagicFamily.csv` and
`BossResist.csv` were, and never into `oracle/`.

Two things are deliberately absent rather than pending:

**Talisman effects, applied.** `item-effect` says what a talisman, tear or rune is worth, and
combines several. What nothing here does is *apply* one: `planner.py` never modelled them — the
Build Planner port stubbed `EffectData_Active` — so Great-Jar's Arsenal does not raise equip
load, and `character-build`, `equip-load` and `defence` all report figures before any of it.
`equip-load` refuses to take a talisman rather than accepting one and ignoring it, and
`item-effect` pins `applied_to_a_build: false`. Closing that gap means either modelling the
effects in `planner.py`'s place, which is arithmetic nobody has an oracle for, or having the
caller add the numbers and say that it did.

**Poise.** The planner returns a poise figure on a scale we have not reconciled with the
number the game shows, so it is not published. A figure whose meaning is unverified is worse
than an absent one, because it reads as authoritative.

Nothing here does ashes of war, item locations, or lore, and nothing here should pretend to.
