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
