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

The order is the routing: **character-build** when the user described a build by only some of
its stats, **weapon-lookup** for any question naming a weapon, then **attack-power** for what
it hits for, or **optimal-affinity** for what to infuse it with.

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

The Prometheux ontology this collection is a second implementation of still covers more:
ashes of war and their motion values, boss resistances, consumables and physick tears,
matchmaking bands, and the effect catalogues behind talismans and crystal tears.

Two things are deliberately absent rather than pending:

**Talisman effects.** `planner.py` never modelled them — the Build Planner port stubbed
`EffectData_Active` — so Great-Jar's Arsenal does not raise equip load here. `equip-load`
therefore does not take a talisman, and returns `talismans_modelled: false`, rather than
accepting one and quietly ignoring it.

**Poise.** The planner returns a poise figure on a scale we have not reconciled with the
number the game shows, so it is not published. A figure whose meaning is unverified is worse
than an absent one, because it reads as authoritative.

Nothing here does ashes of war, item locations, or lore, and nothing here should pretend to.
