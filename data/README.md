# data

Tables that are **not** part of the Build Planner extraction, kept apart from `oracle/` so the
line between "the spreadsheet's data" and "someone's data" stays visible.

## MagicFamily.csv

Which spells belong to which family — "Carian Sword", "Full Moon", "Glintstone", and so on.
A staff's `castingBonusType` names one of these families and `castingBonusRate` gives its
multiplier, so without this table a catalyst's bonus cannot be applied to a spell.

The Build Planner does not publish it. It comes from the **Prometheux Elden Ring Brain**
ontology, where it was compiled by hand (`prometheux-workspace/files/elden-ring-brain/`), and
a spell may appear in more than one family — Adula's Moonblade is both Carian Sword and Cold.

That provenance matters when reading a `spell-power` result: the attack figures trace to the
spreadsheet, and the *choice of which bonus applies* traces to this file.

## BossResist.csv

Every named boss at NG: health, poise, per-type defences and negations, and the seven status
resistances. `9999` in a resistance column means immune, not merely tough — the table's own
convention, and the reason `boss-lookup` reports an `immune_to` list rather than leaving a
reader to interpret a large number.

Also not from the Build Planner: it comes from the same Prometheux ontology, compiled from the
community PvE data sheet. The negation figures are percentages on the same scale
`opt_affinity_calc.py` expects, which is what lets a boss's numbers be handed straight to
`optimal-affinity`.

Bosses appear once per phase, and a phase is a different fight: Rennala Phase 1 has -10
physical negation and 3493 health, Phase 2 has 80 poise and 4097. A query that matches more
than one is ambiguous in the way a weapon name is, and resolves to nothing.

## AshAttack.csv, AshCompat.csv

Ashes of war. `AshAttack` is 2,643 rows, one per *hit* — a skill is several — carrying each
hit's motion values per damage type, its status and poise motion values, stamina cost, any flat
attack it adds, and whether it **overrides the weapon's scaling**. `AshCompat` says which
affinity a skill defaults to and whether it can go on any weapon.

Both come from the Prometheux ontology rather than the Build Planner, which publishes no skill
data at all.

The override column is the reason a skill deserves its own node rather than a footnote: 173 of
those rows replace the weapon's scaling with a single stat, so a build optimised for a weapon
can be the wrong build for its ash. Most rows do not — `-` in 2,470 of them — and saying which
case a skill is in is more useful than a number.

Motion values are percentages on the scale `optimal-affinity`'s `attack_mv` expects, so a
skill's hit can be priced through the same maths as a normal swing.
