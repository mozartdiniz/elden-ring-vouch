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

## Testing

```console
$ vouch -C . test
35 cases, 35 passed, 0 failed
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
$ vouch -C . eval --agent 'claude -p --allowedTools "" -- {prompt}' -n 5 --min-rate 0.8
```

Routing evals, with a model in the loop, so a rate rather than a pass. `--allowedTools ""`
matters: with its own tools the agent may read this repository instead of routing through the
published context, which measures the wrong thing.

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

The Prometheux ontology this collection is a second implementation of covers considerably
more: optimal affinity against real enemy defences, spell scaling and catalyst choice, armour
and poise, guard and status comparison, and full loadout planning. `opt_affinity_calc.py` and
most of `planner.py` are vendored here and unused so far.

Nothing here does ashes of war, item locations, or lore, and nothing here should pretend to.
