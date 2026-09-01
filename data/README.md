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
