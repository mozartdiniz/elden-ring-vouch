# Validation battery — the questions the Prometheux ontology was validated with

Forty-two questions in four patterns, taken from the real questions Mozart asked the
Elden Ring Brain ontology. They are the *outside* view: what a player actually types, not
what a node happens to expose. Working through them is how this collection finds out which
question shapes it can answer end to end.

**Method for each question.** Route it the way the registry preamble says an agent should:
resolve names with `weapon-lookup`, fill unnamed stats from `character-build`, spend points
with `build-allocate`, price with `attack-power` / `spell-power` / `optimal-affinity`. Then
check the figures against the oracle in
`~/Downloads/elden-ring-ontology/elden-ring-ontology/elden-ring-wiki/scripts/`
(`ap_calc.py`, `planner.py`, `opt_affinity_calc.py`) — an independent run of the same maths.

**A question counts as done when the collection answers it with numbers that are its own and
that the oracle agrees with.** A question the collection *cannot* answer is not a failure to
paper over: record what is missing and leave it unchecked.

Status: `[ ]` untested · `[x]` answered and cross-checked · `[~]` partially answered (gap
recorded) · `[!]` cannot answer today.

---

## Pattern 1 — Build stat distribution for a target level

"I want a build around [weapon/concept], level [N], give me the stat spread." The most common
shape. Fixes a level, usually 150, and a weapon or theme; sometimes fixes a few stats and asks
for the rest. Calc-relevance high: weapon requirements, soft caps, starting-class bases, and
the exact point total for the level.

- [x] **1.1** Quero fazer uma build de Rivers of Blood no nível 150, foco em Corpse Piler. Monta a distribuição de status pra mim, assumindo classe Samurai.
- [~] **1.2** Monta uma distribuição RL150 pra Moonveil com foco em Transient Moonlight, priorizando dano da skill.
- [x] **1.3** Estou fazendo uma build de Great Stars (great hammer) com sangramento, nível 150, coop. Qual distribuição você faria?
- [ ] **1.4** I want a pure Faith incantation build at RL150 using the Erdtree Seal. Give me the stat spread, assuming Prophet start.
- [x] **1.5** Build de Bloodhound's Fang no nível 125 pra PvP/coop. Como distribuo os status?
- [x] **1.6** Quero usar a Dragon Halberd com Lightning affinity no nível 150. Monta os status considerando os requisitos da arma.
- [x] **1.7** Faz pra mim uma build de Comet Azur / Terra Magica full INT no nível 150, classe Astrologer.
- [ ] **1.8** Estou montando um personagem de Frenzied Flame incantations no nível 150. Qual a distribuição ideal?
- [x] **1.9** Build de Fingerprint Stone Shield + Antspur (poison/rot) no nível 150. Como fica a distribuição?
- [x] **1.10** I want a RL150 dual-katana build (Nagakiba + Uchigatana) blood-focused. Give me the exact stat allocation from a Bandit start.
- [x] **1.11** Quero fazer a Sword of Milos no nível 120 com foco em sangramento e a skill que dá FP. Monta os status.
- [x] **1.12** Build de arcane/dragon communion pura no nível 150 pra spammar Rotten Breath e Ancient Dragons' Lightning Strike. Distribui pra mim.
- [ ] **1.13** Faz uma distribuição pra Golden Order Greatsword no nível 150 aproveitando o Ash of War dela ao máximo.
- [x] **1.14** Quero uma build de Star Fist (fists) com Cold no nível 150. Como distribuo STR/DEX/INT?

## Pattern 2 — Rate my current build / re-allocate to a new level

A current spread plus a weapon: "is this optimized?" or "give me a spread for level N." The
tool has to spot wasted points — stats above the requirement or past a soft cap — and propose
a corrected spread that hits the target level exactly.

- [x] **2.1** Minha personagem tá assim no nível 150: VIG 55 / MND 30 / END 20 / STR 12 / DEX 50 / INT 12 / FTH 45 / ARC 9, usando a Godslayer's Greatsword. Tá otimizado? O que você mudaria?
- [x] **2.2** Tô no nível 120 com VIG 40 / MND 20 / END 25 / STR 60 / DEX 14 / INT 9 / FTH 9 / ARC 7 usando a Greatsword pura STR. Me sugere uma distribuição pro nível 150.
- [x] **2.3** Rate my RL125 build: VIG 40 / MND 18 / END 28 / STR 20 / DEX 45 / INT 30 / FTH 8 / ARC 9 on a Cold Uchigatana. Am I wasting points?
- [x] **2.4** Meu mago tá com VIG 50 / MND 40 / END 15 / STR 10 / DEX 12 / INT 70 / FTH 10 / ARC 9 no nível 138. Quero subir pro 150 mantendo Comet Azur. Como redistribuo?
- [x] **2.5** Copiei meu save do nível 90 pra fazer um nível 150. Build atual: VIG 45 / MND 15 / END 30 / STR 50 / DEX 20 / INT 9 / FTH 25 / ARC 8, arma Blasphemous Blade. O que muda na subida pro 150?
- [x] **2.6** Tô no nível 100 com Faith 45 mas uso um seal que escala melhor com Arcane. Meus stats: VIG 45/MND 25/END 20/STR 14/DEX 18/INT 9/FTH 45/ARC 10. Isso faz sentido ou tô jogando pontos fora?
- [x] **2.7** Meu build de gelo tá VIG 40 / MND 35 / END 18 / STR 12 / DEX 16 / INT 60 / FTH 6 / ARC 9 no nível 125. Vale subir INT ou vigor primeiro pro 150?
- [x] **2.8** I'm RL80 with VIG 35 / MND 15 / END 25 / STR 40 / DEX 40 / INT 9 / FTH 9 / ARC 7 (quality). Is 40/40 actually worth it here or should I commit to one?

## Pattern 3 — Best weapon / staff / seal / spell for a build or for my stats

"Given my stats or this archetype, what is the best weapon / staff / spell school?" The
eligibility filter is pure calc — requirements met, ranked by AR — and the recommendation on
top of it is opinion-flavoured.

- [x] **3.1** Tenho VIG 60 / MND 20 / END 25 / STR 55 / DEX 14 / INT 9 / FTH 60 / ARC 9. Quais as armas mais fortes que eu consigo usar?
- [x] **3.2** Qual o melhor staff pra uma build de pure INT em 80, considerando Night sorceries?
- [x] **3.3** Qual o melhor seal pra uma build híbrida INT/FTH de Death sorceries?
- [x] **3.4** Estou com DEX 50 / ARC 45 no nível 150. Quais as melhores katanas pra mim?
- [x] **3.5** What's the best colossal weapon for a 66 STR quality-ish build at RL150?
- [x] **3.6** Quais as melhores incantations de fogo pra uma build de 60 Faith no jogo base + DLC?
- [~] **3.7** Qual o melhor greatshield pra uma build de STR focada em guard counter?
- [x] **3.8** Tenho FTH 80 puro. Qual a melhor arma de melee que escala em Faith sem precisar de INT?
- [x] **3.9** Qual a melhor lança/great spear pra uma build de DEX/FTH com Lightning?
- [x] **3.10** Melhor arma de Arcane que aproveita bem os 80 ARC sem depender de bleed?

## Pattern 4 — Maximize the damage of a specific weapon skill / Ash of War

"How do I make this skill hit as hard as possible?" Wants the whole recipe: the stat that
drives it, talismans, physick, buffs, and the stacked multiplier. The flagship calc case, and
the one this collection knows it does not close: skill damage is reported but never priced,
and no node applies a talisman.

- [ ] **4.1** Qual distribuição + talismans + physick dá o maior Wave of Destruction possível na Distinguished Greatsword no nível 150? Me mostra o multiplicador total.
- [ ] **4.2** Como eu maximizo o dano do Corpse Piler da Rivers of Blood? Stat que mais importa, talismans e o stack de multiplicadores.
- [ ] **4.3** Quero o Loretta's Slash mais forte possível na Loretta's War Sickle no RL150. STR vs DEX vs FTH — qual prioriza, e quais buffs stackam?
- [ ] **4.4** Maximize Ghostflame Ignition on the Death Poker at RL150 — stats, talismans, physick, and the final multiplier.
- [ ] **4.5** Qual o setup que faz o Unsheathe da Uchigatana bater o máximo? Considera carregar ou não.
- [ ] **4.6** Como faço o Sacred Blade da Golden Order Greatsword dar o maior dano de Holy? Faith é o principal mesmo?
- [ ] **4.7** Quero o Storm Assault / Thundercloud mais forte numa arma de raio no RL150. Calcula o stack Shard of Alexander + Godfrey Icon + buffs.
- [ ] **4.8** Maximum-damage Flaming Strike on the Flamberge with Flame Art — give me the stat split and the buff stack, charged vs not.
- [ ] **4.9** Qual o maior dano possível do Gravitas / Nebula em armas de INT no RL150? Quais talismans e physick multiplicam isso?
- [ ] **4.10** Como maximizar o Blood Blade / Seppuku-boosted hit numa katana blood no RL150? Mostra os multiplicadores.

---

## Results

Filled in as each question is worked. One entry per question, recording the calls made, the
figures returned, the oracle cross-check, and anything the collection could not supply.

**How the cross-check works.** Calling the oracle to confirm a node that wraps the oracle
proves nothing, so the check is on the part the node adds: `scratchpad/brute.py` and
`brutespell.py` price *every legal spread* through `ap_calc` / `planner` directly and report
the argmax. If build-allocate's search agrees with an exhaustive sweep, its answer is the
optimum and not a local one. That check has already failed twice.

### 1.1 Rivers of Blood, RL150, Corpse Piler, Samurai — done

`weapon-lookup` resolves it as a somber Katana, +10, no affinity. `weapon-skill` says Corpse
Piler is unique to it, 18 hits, highest motion value 155, and **`overrides_weapon_scaling`
false** — so the spread that is best for the weapon is best for the skill, which is the thing
the question needed to know.

`build-allocate` with vigor 40 / mind 20 / endurance 25 as stated floors:

| focus | spread | AR | bleed |
|---|---|---|---|
| attack | STR 12 · DEX 56 · ARC 59 | 675.826 | 76.4 |
| bleed | STR 12 · DEX 18 · ARC 97 | 644.748 | 79.5 |

Both spreads confirmed optimal by an exhaustive sweep of all 3,081 legal spreads, and both
agree with `ap_calc.py` to full precision.

### 1.2 Moonveil RL150, Transient Moonlight, skill damage — partial, and it found a bug

The spread came back **wrong**. `build-allocate` returned dexterity 59 / intelligence 57 for
709.7631 AR; the sweep found dexterity 66 / intelligence 50 for 709.8569, and `attack-power`
agreed with the sweep. The greedy climb had stalled below a soft cap, and the one-point swap
pass could not leave it — every single point moved between the two costs more than it buys and
only the seventh pays off. Fixed in `91f4938`: the search now prices every spread when few
enough stats are live.

What it still cannot do is the thing the question asked for. Transient Moonlight is ambiguous
between R1 and R2, both unique to Moonveil, and neither overrides the weapon's scaling — but
the damage is in the **bullet**, which the table gives as flat 140 (R1) / 155 (R2) magic with
no motion value at all. Nothing prices a flat-attack hit: `optimal-affinity` takes an
`attack_mv`, and a hit with no motion value has nothing to pass. So the answer is the
weapon-optimal spread with the skill unpriced, which is honest but is not what was asked.

### 1.3 Great Stars, bleed, RL150, coop — done

Great Stars is infusable, +25, and the affinity is the whole question. Running the thirteen
through `build-allocate` with focus `bleed`, two-handed, floors 50/20/30 from a Vagabond:

| affinity | bleed | AR | responds to stats |
|---|---|---|---|
| Blood | **141.7** | 501.97 | yes — ARC 83 |
| Occult | 115.6 | **702.89** | yes — ARC 83 |
| Poison | 70.9 | 501.97 | yes |
| Standard, Heavy, Keen, Quality, Fire, Flame Art, Lightning, Sacred, Magic | 55.0 | 441–589 | **no** |
| Cold | 50.0 | 522.38 | no |

Blood is the bleed answer and Occult trades 26 bleed for 200 AR. The nine flat rows are the
important part: on those affinities Great Stars' bleed does not scale at all, the node reports
`objective_responds_to_stats: false`, and the points fall into vigor rather than into a stat
that would not have moved the bar. Blood's spread confirmed against an exhaustive sweep.

### 1.4 Erdtree Seal, pure Faith incantations, RL150, Prophet — done, and it found a worse bug

**Every incantation in the game priced at zero.** `spell-power` read `MagicAtk` and nothing
else; Black Flame's 244 is in `FireAtk`, Lightning Spear's 234 in `LtngAtk`. It surfaced as a
schema defect rather than a wrong number, which is the only reason it was never quoted at
anybody — but it meant this question could not be answered at all. Meteorite, a sorcery,
returned 373.6 when it is 1046.08, because its 180 physical was never read.

The differential check could not have caught it: the Prometheux ontology computes
`MagicAtk x SB / 100 x Mult` too, so both implementations were wrong in the same place and
agreed with each other. Fixed in `767aaba`, with four fixtures.

The build then needed `focus = "spell"`, which did not exist — see 1.7. With both fixes:
faith 99, spell buff 367.0, Black Flame 895.48 **fire**, and 2 spare points into vigor.

### 1.5 Bloodhound's Fang, RL125, PvP/coop — done

Somber, +10, Standard only. From a Vagabond with floors 40/15/25: STR 42 · DEX 57, 762.496 AR,
bleed 55 flat. Confirmed by exhaustive sweep. The floor costs RL61, so 64 points were the
actual question.

### 1.6 Dragon Halberd with Lightning, RL150 — done, and it found a third bug

**Dragon Halberd takes no affinity.** It is somber: `weapon-lookup` says `infusable: false`,
`max_upgrade: 10`. `attack-power` has reported `affinity_ignored` since it was written, but
`build-allocate` passed the request straight through and returned `"affinity": "Lightning"`
over figures for the Standard weapon — an answer describing a weapon that does not exist.
Fixed in `0912393`.

The spread itself is right: STR 70 · DEX 49, 716.650 AR, confirmed by sweep. The answer has to
open by saying there is no Lightning version.

### 1.7 Comet Azur / Terra Magica, full INT, RL150, Astrologer — done, and it needed a feature

`build-allocate` could not build a caster: `focus = "attack"` on a staff maximises the staff's
own attack rating, which scales off different stats from the spell it casts. Added
`focus = "spell"` in `74f5d3f`, sharing `lib/spells.py` with `spell-power` so the two cannot
drift.

Comet Azur at RL150 from an Astrologer, floors 40/30/20, is intelligence 99 on every staff;
what changes is the staff:

| catalyst | spell buff | Comet Azur |
|---|---|---|
| Lusat's Glintstone Staff | 430.0 | **236.500** |
| Carian Regal Scepter | 388.0 | 213.400 |
| Azur's Glintstone Staff | 376.0 | 206.800 |

Terra Magica is the other half of the question and the answer is that it cannot be built for:
it has no attack value at all, so `objective_responds_to_stats` is false and the points go to
vigor. Pinned as a fixture.

### 1.9 Fingerprint Stone Shield + Antspur, RL150 — done, and it needed a feature

The shield needs **48 strength**, a third of the points at RL150, and `build-allocate` had no
way to hear about anything but the weapon it was optimising. Added `stat_floors` in `2689c34`.

Antspur Keen +25 with the shield's 48 strength as a floor: STR 48 · DEX 61, 459.062 AR,
scarlet rot 55. Confirmed by sweep. Rot is flat on every affinity — and *drops* to 50 on
Poison, Blood and Occult — so the rot half of the question is "you cannot build toward it, and
infusing makes it worse", which is a better answer than a spread.

### 1.10 Nagakiba + Uchigatana, blood, RL150, Bandit — done

The same `stat_floors` feature answers it: Nagakiba's own 18/22 requirement dominates
Uchigatana's 11/15, so optimising Nagakiba Blood +25 for bleed gives STR 18 · DEX 22 · ARC 87,
bleed 116.572, and the Uchigatana in the other hand is 434.599 AR at the same spread with the
same 116.572 bleed. Confirmed by sweep.

Not modelled: power stance, and the second weapon's own AR is a separate `attack-power` call
rather than something the allocator weighs. Optimising for the *pair* is not a thing this node
does — it optimised one and the other came along.

### 1.11 Sword of Milos, RL120, bleed — done

Somber, +10, Standard only, so its bleed does not scale with anything: 55 flat,
`objective_responds_to_stats: false`, and the points go to vigor 98. The honest answer is that
a bleed focus is not available on this weapon and the build should be an attack build.

### 1.12 Arcane / dragon communion, RL150 — done

`focus = "spell"` on a Dragon Communion Seal, Prophet, floors 40/30/20:

| spell | spread | attack | family bonus |
|---|---|---|---|
| Rotten Breath | FTH 43 · ARC 68 | 544.391 physical | ×1.15 Dragon Communion |
| Ancient Dragons' Lightning Strike | FTH 43 · ARC 68 | 1145.516 lightning | none — it is Dragon Cult |

The split is the answer, and it is not a rule of thumb: 43/68 came out of pricing every
spread. Verified against an exhaustive sweep of 102,340 spreads run through `planner.py`
directly — same spread, same figure to full precision.

The bonus asymmetry is worth quoting too: the seal boosts Rotten Breath and does nothing for
the Lightning Strike, which belongs to a family a different seal boosts.

### 1.13 Golden Order Greatsword, RL150 — done

Somber, +10. From a Confessor with floors 40/20/25: STR 16 · DEX 36 · FTH 74, 794.928 AR split
275 physical / 519 holy. Confirmed by sweep.

"Aproveitando o Ash of War ao máximo" is the part that is not closed — same gap as 1.2. The
spread is the weapon's optimum, and whether it is the skill's depends on the skill's motion
values, which nothing prices.

### 1.14 Star Fist with Cold, RL150 — done

The case the node was built to get right, and it does: frost 105 is flat, nothing the user
levels changes it, `objective_responds_to_stats` is false, and the points fall into vigor 99
rather than producing a spread that looks optimised and is not. Confirmed by sweep — the
exhaustive search finds no spread better than the floor either.

The answer to give is "Cold Star Fist's frost cannot be built toward; build for attack, or
pick a weapon whose frost scales".


## Pattern 2 — every question is the same composition, and it works

There is no "rate my build" node, and none is needed. Every one of the eight is
`character-build` for what the spread actually is, `attack-power` or `spell-power` for what it
currently does, and `build-allocate` at the same rune level with the user's own vigor / mind /
endurance as the floors for what it could do. The gap between the last two is the answer.

**Seven of the eight state a rune level the spread is not at.** `character-build` returns
`levels_to_target` and the answer opens with it rather than with a correction the model did
arithmetic to find:

| # | claimed | actual | out by |
|---|---|---|---|
| 2.1 | 150 | 154 | +4 |
| 2.2 | 120 | 109 | −11 |
| 2.3 | 125 | 119 | −6 |
| 2.4 | 138 | 137 | −1 |
| 2.5 | 90 | 126 | +36 |
| 2.6 | 100 | 107 | +7 |
| 2.7 | 125 | 118 | −7 |
| 2.8 | 80 | 101 | +21 |

### 2.1 Godslayer's Greatsword, VIG 55 / DEX 50 / FTH 45 — done

The build **does not meet the weapon's strength requirement**: `attack-power` reports
`shortfall: strength 8`, and the penalty is most of the answer. Current 463.187 AR against
823.146 at the optimum for the same RL154 and the same floors — STR 32 · DEX 58 · FTH 20. The
45 faith is the waste: the weapon wants 20 of it.

### 2.2 Greatsword, pure strength, → RL150 — done

745.424 now at RL109; 853.184 at RL150 with strength 99 and the leftovers in vigor 47. Nothing
is being wasted, there are simply 41 levels unspent.

### 2.3 Cold Uchigatana, "am I wasting points?" — done

Almost nothing: 568.965 against an optimum of 573.390 at their real RL119 — 0.8%. The shape of
the waste is intelligence 30 where the optimum wants 20, and dexterity 45 where it wants 55.
Worth saying plainly that the build is fine.

### 2.4 Comet Azur mage, RL137 → 150 — done

181.720 now (spell buff 330.4) against 208.815 at RL150 with intelligence 88 (spell buff
379.663). The redistribution also drops strength, dexterity and faith to the class floor, so
the answer has to say it needs a respec rather than just levels.

### 2.5 Blasphemous Blade, "what changes going to 150" — done

743.199 now against 807.978 at RL150: STR 40 · DEX 40 · FTH 41, vigor 45. The build is already
RL126 rather than the RL90 the question assumed, which changes what "going to 150" means.

### 2.6 Faith 45 on a seal that scales arcane — done, and the answer is yes, badly

The sharpest result in this pattern. Rotten Breath from a Dragon Communion Seal at their
spread: **275.340**. At the same RL107 with the points where the seal actually scales — faith
25, arcane 43 — it is **459.106**. Two thirds more damage for no extra levels, and the
question ("isso faz sentido ou tô jogando pontos fora?") gets a number instead of an opinion.

### 2.7 Ice build, "INT or vigor first?" — done

A trade, quantified, with the judgement left where it belongs. Carian Regal Scepter casting
Adula's Moonblade at RL150:

| vigor floor | intelligence | Adula's Moonblade | HP |
|---|---|---|---|
| 40 | 99 | 516.04 | 1450 |
| 50 | 90 | 506.97 | 1704 |
| 60 | 80 | 496.89 | 1900 |

Twenty points out of intelligence costs 3.7% of the spell and buys 31% more health.

### 2.8 "Is 40/40 quality actually worth it?" — done, and the numbers say no

`optimal-affinity` on a Longsword +25 at their 40/40: Quality wins its own bracket at 416.061,
but by a margin of 4.36 over Lightning — a coin toss, and the node says so. The real answer is
the comparison the question implies:

| spread | best affinity | damage |
|---|---|---|
| STR 20 / DEX 60 | Lightning | **458.48** |
| STR 60 / DEX 20 | Fire | 437.53 |
| STR 40 / DEX 40 | Quality | 416.06 |

Committing beats splitting by 10% on this weapon. "40/40 quality" is folk wisdom the arithmetic
disagrees with, which is the sort of thing this collection exists to settle.

## Pattern 3 — the shape the collection could not answer at all

Every node here started from a weapon somebody had already named. Nothing looked across the
catalogue, and the registry's advice — "comparing weapons means calling attack-power once per
weapon" — is not advice that survives 489 weapons. An agent given it would rank from memory,
which is the exact failure the collection exists to prevent.

Two nodes close it. **`weapon-rank`** prices the whole catalogue at a build's stats, each
weapon at its own upgrade cap, and drops the ones the build cannot hold. **`spell-rank`**
does the same over the 384 spells from a named catalyst. Writing them turned up three
defects, all committed with fixtures:

- **A seal cannot cast a sorcery, and nothing knew that.** `spell-power` priced Comet from an
  Erdtree Seal at 798.766 — arithmetically correct, about a cast that cannot happen — and the
  first ranking for question 3.3 came back led by a sacred seal, above every staff. The check
  now reads the game's own `enableMagic` / `enableMiracle` flags, which is how the Staff of
  the Great Beyond comes back casting both.
- **Eighty-one of the catalogue's 570 rows are consumables**, fifteen with no weapon ID, which
  crashed the first full ranking. "570 weapons" was never a weapon count; it is 489.
- **`ap_calc.load_table` re-parses its CSV on every call.** Invisible at one weapon, fatal at
  489: `max_upgrade` calls it twice each, and the first ranking took two minutes and hit the
  node timeout. Cached in `lib/oracle.py`, which leaves `oracle/` byte-identical. 0.6 s now.

### 3.1 STR 55 / FTH 60, what can I wield — done

489 weapons considered, **280 usable**. Top of the list: Shadow Sunflower Blossom 931.41,
Maliketh's Black Blade 927.89, Staff of the Avatar 908.25, Golden Halberd 871.98. The
half-usable figure is the useful part of the answer as much as the ranking is.

### 3.2 Best staff for Night sorceries, pure INT 80 — done

**Staff of Loss**, 1014.81 for Night Comet, on a spell buff of 339.4 — beating Lusat's, whose
spell buff is 413.5, because the ×1.3 Night bonus applies and Lusat's does not have one. A
ranking on spell buff alone gets this backwards, which is why the family table earns its
keep.

### 3.3 Best seal for Death sorceries — done, after correcting the premise

Death sorceries are sorceries, so there is no seal in the answer. Out of a staff, for an
INT 50 / FTH 50 hybrid: **Staff of the Great Beyond** 154.66, then Prince of Death's Staff
154.38 — 0.28 apart, a coin toss, and the second one carries a ×1.1 Death bonus while the
first is simply a better hybrid staff.

### 3.4 Best katanas at DEX 50 / ARC 45 — done

Ten katanas, **six usable**. Rivers of Blood 644.64 (72 bleed), Sword of Night 625.60,
Hand of Malenia 547.86, Serpentbone Blade 522.00, Dragonscale Blade 493.10. Moonveil,
Nagakiba, Star-Lined Sword and Meteoric Ore Blade are out on requirements — and priced with a
penalty rather than excluded, they would have ranked *above* usable weapons, which is why they
are dropped and not shown as weak.

### 3.5 Best colossal weapon, 66 STR — done

With `affinity: "best"`: **Giant-Crusher, Fire +25, 917.34**, then Prelate's Inferno Crozier
889.96 and Duelist Greataxe 872.69. Great Club is fourth on 858.55 as Standard — it is one of
the 58 weapons that take no affinity and still reach +25.

### 3.6 Best fire incantations at 60 Faith — done

62 fire incantations castable from an Erdtree Seal, **46 within reach**. Flame of the Fell God
1135.23 for 34 FP, Giantsflame Take Thee - Charged 1064.11 for 30, **O, Flame! - Charged
1053.17 for 16** — which is the answer a damage-only ranking hides.

### 3.7 Best greatshield for guard counters — partial

The shield list is right and it is not ranked on the thing the question asked about.
`weapon-rank` returns guard boost and the negation split beside the attack rating, so:
Verdigris Greatshield blocks 100% physical at 90 stability, Fingerprint Stone Shield 95% at
77 but with the highest attack rating and 70 madness. What is **not** modelled is guard
counter damage — a guard counter is an attack with its own motion value, and nothing in the
extraction carries one.

### 3.8 FTH 80, melee that scales faith without intelligence — done

**Gargoyle's Blackblade 759.34**, then Golden Epitaph 600.31 and Sentry's Torch 599.02. 193 of
489 usable at those stats. Reading the intelligence requirement off each row is what makes the
"sem precisar de INT" half of the question answerable.

### 3.9 Best great spear, DEX/FTH lightning — done

Ten great spears, seven usable. **Treespear 723.67** — Standard, because Treespear is another
of the somber-but-+25 weapons and takes no infusion at all — then Spear of the Impaler 709.97
and Vyke's War Spear 697.01 (65 madness). The best actually-Lightning-infused entry is
Messmer Soldier's Spear at 669.31, which is the honest correction to the question.

### 3.10 Best arcane weapon at 80 ARC that is not about bleed — done

Occult sweeps the list. The top row, Great Katana at 712.44, carries 108 bleed and so is
exactly what the question excluded; the answer is **Iron Greatsword, Occult +25, 700.18**,
with no status at all. Reading the exclusion off `status_shown` is the whole trick.