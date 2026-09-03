# Bugs found by asking real questions

A running ledger. Every entry here was found by working a question from `VALIDATION.md`, not
by a fixture and not by an eval — the suite passed throughout.

**How this is used.** Questions arrive in batches. Each is worked in `VALIDATION.md`; anything
wrong that comes out of one lands here, whether it is fixed on the spot or deferred. Open
entries are the end-of-run work list.

Every entry carries: what was wrong, **what it returned instead of an error** where that
applies, the question that found it, and its kind.

**Kinds.** `algorithm` — our search or logic is wrong. `unread data` — the table already had
what was needed and the code did not look. `missing check` — a constraint nothing enforced.
`upstream` — in the vendored `oracle/`, worked around here rather than edited. `design` — not
a defect, a decision that left a caller doing arithmetic.

---

## Open

Not defects, but the two things most likely to become one.

| what | why it matters |
|---|---|
| **The routing preamble is 58 notes**, against nineteen when the handoff first said it would need pruning. An agent carries all of it every turn. Past some size the notes stop being read rather than stop being true, and nothing measures that. | every answer |
| **`data/PhysickEffect.csv` is vendored and no node reads it.** Questions 14.3 and 14.6 are partial because of it, and a vendored table nobody reads is the shape bug 11 had. | 14.3, 14.6 |

## Fixed

| # | what was wrong | found by | kind | commit |
|---|---|---|---|---|
| 17 | **The starting class silently changed the stats.** `planner.py` treats a class's stats as a *floor* — `max(user, class_value)` — and `spell-power`, `spell-rank` and `stat-curve` defaulted it to Wretch, whose flat tens lift anything below 10. `weapon-rank` hard-coded it. So a build with 9 intelligence was priced at 10, and spell-power's own parameter guidance said "leave it out unless the user named a class". Caught by the Build Planner's own saved strength build: its Frenzied Flame Seal is **222.87 on the sheet and 223.30 as a Wretch**. Small, systematic, and invisible — every spell figure the collection had ever produced was a Wretch's. | spreadsheet | unread data | `12248fe` |
| 16 | **The weapon-buff rule was computed and never exposed.** `ap_calc` has taken a `status_buff` since it was vendored and checks three conditions to accept it — class, affinity, and whether the weapon can be buffed — but nothing could ask *which* buffs a weapon takes. Pattern 12 is eight questions of exactly that, and the answers were sitting behind an input nobody could enumerate. Not a wrong number, a capability with no question shape attached. | 12.1 | design | `fac2fa0` |
| 15 | `spell-power` reported a spell's **base FP cost** as though it were what the caster pays. Lusat's Glintstone Staff charges 1.5x and Azur's 1.2x, both stated in `castingBonusRate` where every other catalyst puts a number. Question 9.6 asks "vale o custo de FP?" and the figures said the two staves cost the same: Comet at 70 intelligence is 24 FP from a Regal Scepter and 36 from Lusat's. | 9.6 | unread data | `a42dead` |
| 14 | **Spell names had no lookup.** `spell-power` matched the display name exactly and exited otherwise, so "Rellana's Twin Moons" — three rows in the table, `[1]`, `[2]`, `[3]` — came back as a crash-shaped defect where `weapon-lookup` would have listed three candidates. Question 9.1 compares three moon spells and broke on the third. | 9.1 | missing check | `a42dead` |
| 13 | `weapon-skill` resolved only ashes with rows in the hit table, so **an ash that deals no damage did not exist** — Seppuku is a self-buff and question 6.2 names it beside two ashes that do hit. The catalogue is now the union of the three ash tables. | 6.2 | unread data | `1c5b18f` |
| 12 | An ash's hits are grouped by variant and `weapon-skill` **summed across the groups**. Sword Dance came back as 48 hits and 4,400 status motion value where on a reaper it is three hits and 275 — a fact about no weapon in the game. Loretta's Slash's "24 hits" was four weapon classes times two hits times two FP states. `(Lacking FP)` rows were counted as further hits as well. | 6.1 | unread data | `1c5b18f` |
| 11 | `item-effect`'s multiplier stack multiplied **any** buffs the caller asserted, including two that overwrite each other. Golden Vow as a spell and as an ash share the `Aura` slot — the last one wins — so it would have returned 1.15 × 1.115 for a stack the game does not allow. It also read the figure out of prose when a structured per-hit-kind table existed in the workspace and had not been vendored. Replaced by `buff-stack`. | 5.7 | design + unread data | `15ae25d` |
| 1 | `build-allocate`'s greedy climb stalled at a local optimum. Moonveil RL150 returned dexterity 59 / intelligence 57 for **709.7631** where dexterity 66 / intelligence 50 is **709.8569** — no single point moved between the two pays for itself, only the seventh does. | 1.2 | algorithm | `91f4938` |
| 2 | `spell-power` read `MagicAtk` and nothing else, so **every incantation in the game priced at zero** — Black Flame's 244 is in `FireAtk`. Meteorite, a sorcery, returned 373.6 where it is 1046.08. Surfaced as a schema defect, which is the only reason it was never quoted. | 1.4 | unread data | `767aaba` |
| 3 | `build-allocate` returned `"affinity": "Lightning"` over figures for the Standard weapon. Dragon Halberd takes no affinity at all. `attack-power` had reported `affinity_ignored` since it was written; its sibling passed the request straight through. | 1.6 | missing check | `0912393` |
| 4 | `spell-power` priced **Comet cast from an Erdtree Seal at 798.766**. The spell buff was right and the multiply was right; a sacred seal cannot cast a sorcery. The first catalyst ranking for a Death sorcery came back led by a seal, above every staff. | 3.3 | missing check | `be34ad3` |
| 5 | **81 of the catalogue's 570 rows are consumables**, fifteen with no weapon ID, and the first full ranking crashed on `float(None)` rather than returning them. "570 weapons" was never a weapon count; it is 489. | 3.1 | unread data | `be34ad3` |
| 6 | `ap_calc.load_table` re-parses its CSV on every call — a tenth of a second for the 1.3 MB `EquipParamWeapon`, and `max_upgrade` calls it twice per weapon. Invisible at one weapon, fatal at 489: two minutes and a node timeout. Cached in `lib/oracle.py`; `oracle/` stays byte-identical. | 3.10 | upstream | `be34ad3` |
| 7 | The coarse fallback for too many live stats was a greedy climb with one-point swaps, and it stalled **17 points of spell attack short** on the Frenzied Flame Seal — 828.33 against 845.40. Replaced with a coarse-to-fine sweep. | 1.8 | algorithm | `be34ad3` |
| 8 | `item-effect` returned three sentences with the multipliers inside them — "Increases damage by 1.15x with weapon skills" — which is the multiply handed back to a model. Every Pattern 4 question ends "me mostra o multiplicador total". | 4.2 | design | `70713e5` |
| 9 | Seven ash-of-war families are a name plus `" ?"`, the source marking a hit it could not confirm. `normalize` stripped the punctuation, so all seven came back **ambiguous with themselves** and refused. Loretta's Slash and Establish Order are two of them. | 4.3 | unread data | `b4f735d` |
| 10 | `optimal-affinity`'s `attack_mv` is one number and a motion value is per damage type. Establish Order's big hit is 300 holy and **0 physical**; passing 300 gives 2146.30 by tripling an attack rating the skill never uses. `weapon-skill` now reports `motion_values_uniform`. | 1.13 | missing check | `7ff8fdb` |

### What the shape of that list says

**Nothing was wrong with the data.** No wrong figure turned up anywhere in the extraction, and
the oracle's arithmetic held at every cross-check, including an exhaustive sweep of 1,837,620
spreads. Every entry is in the layer this collection wrote, except #6, which is a performance
problem in the vendored copy.

**Four of them are the same mistake.** #2, #5, #9 and, in effect, #4 are all *the table already
knew and the code did not look*: `FireAtk` was populated, the consumables were labelled
`Consumable`, the `" ?"` suffix was a deliberate convention, `enableMagic` and `enableMiracle`
were sitting there. The fix each time was to read a column that was already present.

**Three returned a number rather than an error** — #1, #4 and #7 — which is the failure mode
this collection exists to prevent, and the one fixtures and evals both missed. #11 would have
been a fourth: it was caught by the next batch of questions arriving before anyone quoted it.

**#11 is also the first entry against work done in this pass.** A stopgap built for Pattern 4
was wrong by the time Pattern 5 asked a sharper question, and the table that made it
unnecessary had been sitting unvendored in the workspace the whole time. Worth checking the
workspace's file list before building a parser — #15 is the same lesson a second time.

**#17 is the one no question found.** Fourteen patterns and 122 questions did not surface it,
because every figure was internally consistent and nothing to compare against was outside the
collection. It took three PDFs of the source spreadsheet, and a 0.43 discrepancy in the fourth
decimal place of a spell buff. That is the argument for checking against the thing upstream of
your oracle, not just against your oracle.

**Six of the seventeen are the same mistake**: #2, #4, #5, #9, #12, #13 and #15 are all *the
table already knew and the code did not look*. That is the single most productive thing to
check when something looks wrong.

---

## Not bugs: features the questions demanded

Kept here because they came out of the same pass and belong in the same work list.

| feature | the question that needed it | commit |
|---|---|---|
| `build-allocate` `focus = "spell"` — build for the spell, not the catalyst | 1.4, 1.7, 1.8, 1.12 | `74f5d3f` |
| `build-allocate` `stat_floors` — the rest of the loadout has requirements | 1.9, 1.10 | `2689c34` |
| `weapon-rank` — rank the catalogue at a build's stats | 3.1, 3.4, 3.5, 3.7–3.10 | `be34ad3` |
| `spell-rank` — rank the spells a catalyst can cast | 3.6 | `2821fc1` |

## Not bugs: limits the questions hit

Real answers the collection cannot give, recorded so they are not re-found. Detail in
`HANDOFF.md`'s pending section.

- **Flat-attack and scaling-overridden hits are read, not priced.** Six of the ten Pattern 4
  skills have one. The override is **per hit**, not per skill.
- **`build-allocate` cannot optimise for a skill**, so when a skill overrides the weapon's
  scaling the node can only say the spread is not the skill's.
- **Guard counters have no motion value** in the extraction.
- **Talismans are still not applied to a build** — deliberate, and unchanged.
