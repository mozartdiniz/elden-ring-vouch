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

- [ ] **1.1** Quero fazer uma build de Rivers of Blood no nível 150, foco em Corpse Piler. Monta a distribuição de status pra mim, assumindo classe Samurai.
- [ ] **1.2** Monta uma distribuição RL150 pra Moonveil com foco em Transient Moonlight, priorizando dano da skill.
- [ ] **1.3** Estou fazendo uma build de Great Stars (great hammer) com sangramento, nível 150, coop. Qual distribuição você faria?
- [ ] **1.4** I want a pure Faith incantation build at RL150 using the Erdtree Seal. Give me the stat spread, assuming Prophet start.
- [ ] **1.5** Build de Bloodhound's Fang no nível 125 pra PvP/coop. Como distribuo os status?
- [ ] **1.6** Quero usar a Dragon Halberd com Lightning affinity no nível 150. Monta os status considerando os requisitos da arma.
- [ ] **1.7** Faz pra mim uma build de Comet Azur / Terra Magica full INT no nível 150, classe Astrologer.
- [ ] **1.8** Estou montando um personagem de Frenzied Flame incantations no nível 150. Qual a distribuição ideal?
- [ ] **1.9** Build de Fingerprint Stone Shield + Antspur (poison/rot) no nível 150. Como fica a distribuição?
- [ ] **1.10** I want a RL150 dual-katana build (Nagakiba + Uchigatana) blood-focused. Give me the exact stat allocation from a Bandit start.
- [ ] **1.11** Quero fazer a Sword of Milos no nível 120 com foco em sangramento e a skill que dá FP. Monta os status.
- [ ] **1.12** Build de arcane/dragon communion pura no nível 150 pra spammar Rotten Breath e Ancient Dragons' Lightning Strike. Distribui pra mim.
- [ ] **1.13** Faz uma distribuição pra Golden Order Greatsword no nível 150 aproveitando o Ash of War dela ao máximo.
- [ ] **1.14** Quero uma build de Star Fist (fists) com Cold no nível 150. Como distribuo STR/DEX/INT?

## Pattern 2 — Rate my current build / re-allocate to a new level

A current spread plus a weapon: "is this optimized?" or "give me a spread for level N." The
tool has to spot wasted points — stats above the requirement or past a soft cap — and propose
a corrected spread that hits the target level exactly.

- [ ] **2.1** Minha personagem tá assim no nível 150: VIG 55 / MND 30 / END 20 / STR 12 / DEX 50 / INT 12 / FTH 45 / ARC 9, usando a Godslayer's Greatsword. Tá otimizado? O que você mudaria?
- [ ] **2.2** Tô no nível 120 com VIG 40 / MND 20 / END 25 / STR 60 / DEX 14 / INT 9 / FTH 9 / ARC 7 usando a Greatsword pura STR. Me sugere uma distribuição pro nível 150.
- [ ] **2.3** Rate my RL125 build: VIG 40 / MND 18 / END 28 / STR 20 / DEX 45 / INT 30 / FTH 8 / ARC 9 on a Cold Uchigatana. Am I wasting points?
- [ ] **2.4** Meu mago tá com VIG 50 / MND 40 / END 15 / STR 10 / DEX 12 / INT 70 / FTH 10 / ARC 9 no nível 138. Quero subir pro 150 mantendo Comet Azur. Como redistribuo?
- [ ] **2.5** Copiei meu save do nível 90 pra fazer um nível 150. Build atual: VIG 45 / MND 15 / END 30 / STR 50 / DEX 20 / INT 9 / FTH 25 / ARC 8, arma Blasphemous Blade. O que muda na subida pro 150?
- [ ] **2.6** Tô no nível 100 com Faith 45 mas uso um seal que escala melhor com Arcane. Meus stats: VIG 45/MND 25/END 20/STR 14/DEX 18/INT 9/FTH 45/ARC 10. Isso faz sentido ou tô jogando pontos fora?
- [ ] **2.7** Meu build de gelo tá VIG 40 / MND 35 / END 18 / STR 12 / DEX 16 / INT 60 / FTH 6 / ARC 9 no nível 125. Vale subir INT ou vigor primeiro pro 150?
- [ ] **2.8** I'm RL80 with VIG 35 / MND 15 / END 25 / STR 40 / DEX 40 / INT 9 / FTH 9 / ARC 7 (quality). Is 40/40 actually worth it here or should I commit to one?

## Pattern 3 — Best weapon / staff / seal / spell for a build or for my stats

"Given my stats or this archetype, what is the best weapon / staff / spell school?" The
eligibility filter is pure calc — requirements met, ranked by AR — and the recommendation on
top of it is opinion-flavoured.

- [ ] **3.1** Tenho VIG 60 / MND 20 / END 25 / STR 55 / DEX 14 / INT 9 / FTH 60 / ARC 9. Quais as armas mais fortes que eu consigo usar?
- [ ] **3.2** Qual o melhor staff pra uma build de pure INT em 80, considerando Night sorceries?
- [ ] **3.3** Qual o melhor seal pra uma build híbrida INT/FTH de Death sorceries?
- [ ] **3.4** Estou com DEX 50 / ARC 45 no nível 150. Quais as melhores katanas pra mim?
- [ ] **3.5** What's the best colossal weapon for a 66 STR quality-ish build at RL150?
- [ ] **3.6** Quais as melhores incantations de fogo pra uma build de 60 Faith no jogo base + DLC?
- [ ] **3.7** Qual o melhor greatshield pra uma build de STR focada em guard counter?
- [ ] **3.8** Tenho FTH 80 puro. Qual a melhor arma de melee que escala em Faith sem precisar de INT?
- [ ] **3.9** Qual a melhor lança/great spear pra uma build de DEX/FTH com Lightning?
- [ ] **3.10** Melhor arma de Arcane que aproveita bem os 80 ARC sem depender de bleed?

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

*(nothing yet)*
