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
- [x] **1.4** I want a pure Faith incantation build at RL150 using the Erdtree Seal. Give me the stat spread, assuming Prophet start.
- [x] **1.5** Build de Bloodhound's Fang no nível 125 pra PvP/coop. Como distribuo os status?
- [x] **1.6** Quero usar a Dragon Halberd com Lightning affinity no nível 150. Monta os status considerando os requisitos da arma.
- [x] **1.7** Faz pra mim uma build de Comet Azur / Terra Magica full INT no nível 150, classe Astrologer.
- [x] **1.8** Estou montando um personagem de Frenzied Flame incantations no nível 150. Qual a distribuição ideal?
- [x] **1.9** Build de Fingerprint Stone Shield + Antspur (poison/rot) no nível 150. Como fica a distribuição?
- [x] **1.10** I want a RL150 dual-katana build (Nagakiba + Uchigatana) blood-focused. Give me the exact stat allocation from a Bandit start.
- [x] **1.11** Quero fazer a Sword of Milos no nível 120 com foco em sangramento e a skill que dá FP. Monta os status.
- [x] **1.12** Build de arcane/dragon communion pura no nível 150 pra spammar Rotten Breath e Ancient Dragons' Lightning Strike. Distribui pra mim.
- [~] **1.13** Faz uma distribuição pra Golden Order Greatsword no nível 150 aproveitando o Ash of War dela ao máximo.
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

- [x] **4.1** Qual distribuição + talismans + physick dá o maior Wave of Destruction possível na Distinguished Greatsword no nível 150? Me mostra o multiplicador total.
- [x] **4.2** Como eu maximizo o dano do Corpse Piler da Rivers of Blood? Stat que mais importa, talismans e o stack de multiplicadores.
- [x] **4.3** Quero o Loretta's Slash mais forte possível na Loretta's War Sickle no RL150. STR vs DEX vs FTH — qual prioriza, e quais buffs stackam?
- [~] **4.4** Maximize Ghostflame Ignition on the Death Poker at RL150 — stats, talismans, physick, and the final multiplier.
- [x] **4.5** Qual o setup que faz o Unsheathe da Uchigatana bater o máximo? Considera carregar ou não.
- [~] **4.6** Como faço o Sacred Blade da Golden Order Greatsword dar o maior dano de Holy? Faith é o principal mesmo?
- [~] **4.7** Quero o Storm Assault / Thundercloud mais forte numa arma de raio no RL150. Calcula o stack Shard of Alexander + Godfrey Icon + buffs.
- [~] **4.8** Maximum-damage Flaming Strike on the Flamberge with Flame Art — give me the stat split and the buff stack, charged vs not.
- [~] **4.9** Qual o maior dano possível do Gravitas / Nebula em armas de INT no RL150? Quais talismans e physick multiplicam isso?
- [~] **4.10** Como maximizar o Blood Blade / Seppuku-boosted hit numa katana blood no RL150? Mostra os multiplicadores.

## Pattern 5 — Talisman selection and per-boss swaps

"Best 4 talismans for [weapon/skill]", then "what do I swap [X] for against a boss that
doesn't allow crits / resists holy?" A fixed core plus one flex slot. Ranking talismans by the
multiplier they add to *your* damage source is calc; the swap logic is rule-based on top of an
immunity lookup.

- [x] **5.1** Quais 4 talismans maximizam o dano da minha Blasphemous Blade focada em Taker's Flames no RL150?
- [x] **5.2** Tô usando Shard of Alexander + Godfrey Icon + Ritual Sword + Dagger Talisman na Godslayer's Greatsword. Contra um dragão que não deixa fazer critical, troco o Dagger por qual?
- [~] **5.3** Best talisman package for a Cold Milady Wing Stance build — and what's the flex slot for bosses immune to Frostbite?
- [x] **5.4** Meu core é Graven-Mass + Graven-School + Magic Scorpion Charm no mago de gelo. Qual o quarto talismã? E ele stacka com os graven?
- [~] **5.5** Quais talismans pra uma build de bleed com Eleonora's Poleblade? Preciso de um pra quando o boss é imune a sangramento?
- [x] **5.6** Ranking dos talismans pra maximizar incantations de fogo (Giantsflame, Burn O Flame) num caster Faith RL150.
- [x] **5.7** I run Shard of Alexander + Rotten Winged Sword + Millicent's Prosthesis on a dual-twinblade build. Is the 4th slot better as Lord of Blood's Exultation or Ritual Sword?
- [x] **5.8** Contra Radagon/Elden Beast, quais talismans eu tiro do meu setup de bleed e quais entram?

## Pattern 6 — Ash of War selection for a weapon and a playstyle goal

"Which Ash for [weapon] if I want multi-hit for a fast bleed proc / stance break?" Hit count,
speed and affinity compatibility, not raw ash damage. A good test of whether the collection
knows which ashes accept which affinities.

- [x] **6.1** Quero uma foice (Grave Scythe) com afinidade de sangue e um Ash que bata várias vezes pra procar bleed rápido. Qual Ash aceita Blood e dá mais hits?
- [x] **6.2** Pra uma Twinblade blood, qual Ash of War acumula Hemorrhage mais rápido: Seppuku, Spinning Strikes ou Bloody Slash?
- [x] **6.3** Which Ash of War on a Cold Nagakiba gives the fastest Frostbite proc while still accepting Cold affinity?
- [x] **6.4** Qual Ash of War numa great hammer de STR dá mais stance/poise damage pra quebrar postura em coop?
- [~] **6.5** Pra uma lança de DEX/FTH, qual Ash de raio (Lightning Spear? Storm Stomp?) rende mais dano e aceita a afinidade certa?
- [x] **6.6** Quero girar uma curved sword continuamente com sangue. Qual Ash faz isso e aceita Blood affinity — Spinning Slash não serve?
- [x] **6.7** Numa greatsword de fogo, qual Ash of War combina melhor pra multi-hit + Fire buildup?
- [x] **6.8** Best Ash of War for fast poise damage on a colossal weapon that still lets me keep Heavy scaling?

## Pattern 7 — Affinity and element coverage against boss resistances

"My status doesn't work on [boss] — what do I use instead?", and the big-picture version:
"which element covers the most bosses?" A resistance and immunity lookup across the table plus
an AR recomputation per affinity. The most deterministic pattern in the set.

- [x] **7.1** Meu build de bleed na Gargoyle's Twinblade (STR 40/DEX 23/ARC 12) não funciona no Radagon e na Elden Beast. Qual affinity eu troco pra esses dois?
- [x] **7.2** Considerando jogo base + DLC, qual elemento tem a maior cobertura de bosses pra uma build de Faith: Fogo, Raio ou Sagrado? Quero uma resposta baseada nas resistências, não em opinião.
- [x] **7.3** Which bosses in the DLC are immune or highly resistant to Frostbite? I run a Cold build and want to know when to swap.
- [x] **7.4** Holy é ruim contra quais bosses do endgame? Vale a pena uma arma Holy secundária ou é armadilha?
- [x] **7.5** Tenho uma build de raio. Quais bosses do DLC resistem bastante a Lightning e o que eu levo contra eles?
- [x] **7.6** Monta uma matriz de Fire / Lightning / Holy × os bosses do DLC e me diz qual escola cobre mais lutas em RL150.
- [x] **7.7** Bleed, Frost e Poison: contra quais bosses cada um é inútil? Quero saber quando meu status hunter não vai ajudar.
- [x] **7.8** Elden Beast e Radagon: qual affinity dá mais AR real na minha arma quando não posso usar status? Compara Heavy vs Fire vs Quality.

## Pattern 8 — Co-op generalist for a specific boss pool

"People summon me for these five bosses. Build one character that does well against all of
them without swapping gear." Coverage plus survivability, not peak single-target damage — the
element-coverage calc of Pattern 7 framed as a build.

- [x] **8.1** No coop me chamam muito pra Malenia, Mohg, Maliketh e Godfrey. Monta um único personagem RL150 que vai bem em todos sem eu trocar equipamento.
- [x] **8.2** Meu summon pool é praticamente só DLC: Rellana, Messmer, Romina, Bayle, Consort Radahn. Que build cobre todos esses no RL150?
- [~] **8.3** Quero um "boss killer" de coop RL150 que eu equipo e esqueço que existe menu. Contra bosses aleatórios do jogo todo, que arma(s) + incantations você monta?
- [x] **8.4** I get summoned mostly for Fire Giant, Godskin Duo, and Astel. One RL150 build that handles all three — what is it?
- [~] **8.5** Monta uma build de coop RL138 focada em sobrevivência + stance break que seja útil em qualquer boss do late game.
- [~] **8.6** Quero um personagem que seja o "seguro de vida" do host: stagger, espaço e agro, dano secundário. Que build e que arma no RL150?
- [x] **8.7** Preciso de um generalista RL125 pra ajudar amigos travados no mid-game (Rennala, Radahn, Morgott). Qual build não trivializa mas ajuda?

## Pattern 9 — Compare two options: which is better, and when

"Is X better than Y?" — weapon, spell, ash, build path. The answer wanted is conditional (X for
exploration, Y for big bosses), not a flat winner. The numeric half is calc; the "when" is a
judgement that has to rest on it.

- [x] **9.1** Rennala's Full Moon vs Ranni's Dark Moon vs Rellana's Twin Moons — qual é a melhor pra PvE e em que situação cada uma ganha?
- [x] **9.2** Blasphemous Blade vs Sword of Night and Flame pra uma build de coop RL150 — qual você escolhe e por quê?
- [x] **9.3** Loretta's Greatbow vs Loretta's Mastery: qual é mais consistente pra sniping vs bosses grandes?
- [~] **9.4** STR/FTH vs DEX/FTH como generalista de coop no RL150 — qual cobre mais e qual dá mais dano por golpe?
- [x] **9.5** Rivers of Blood vs Nagakiba (blood) pra proc rápido de sangramento — qual acumula Hemorrhage mais rápido no mesmo Arcane?
- [x] **9.6** Carian Regal Scepter vs Lusat's Glintstone Staff em 70 INT: quanto de dano a mais o Lusat dá e vale o custo de FP?
- [x] **9.7** Dagger Talisman vs Godfrey Icon na Ordovis: qual dá mais dano real por ciclo, considerando que nem todo boss deixa riposte?
- [x] **9.8** Cold affinity vs Blood affinity numa Sword Lance pro meu status hunter — qual proca mais rápido contra bosses não-imunes?
- [~] **9.9** Great Katana vs Nagakiba pra uma build de DEX/bleed no DLC — moveset, alcance e proc, qual ganha?
- [x] **9.10** Heavy vs Quality na Gargoyle's Twinblade com STR 50/DEX 30 — qual dá mais AR de verdade?
## Pattern 10 — Low-level and capped builds, and matchmaking tiers

"Best distribution capped at RL[low] to get the most out of [weapon], because I want to keep
my level low for co-op", and which weapon upgrade keeps you in the right bracket. A tight point
budget plus the level-and-upgrade to matchmaking-range formula. The most deterministic pattern
in the whole battery.

- [ ] **10.1** Qual a melhor distribuição capada no RL35 pra tirar o máximo da Noble's Slender Sword, mantendo nível baixo pra coop? Compara começar como Samurai vs Wretch.
- [ ] **10.2** Quero um cosplay de Vagabond Knight no RL45 usando a Lordsworn's Greatsword. Monta os status e diz o upgrade de arma que me mantém no matchmaking de Stormveil.
- [ ] **10.3** What weapon upgrade level keeps me in the Raya Lucaria co-op bracket at character level 60? And what somber equivalent?
- [ ] **10.4** Build de invasão RL25 com uma katana blood — distribuição e o +X de arma pra não estourar o matchmaking early.
- [ ] **10.5** Quero manter um personagem travado no RL80 pra coop no late-game. Qual o teto de upgrade de arma normal e somber que ainda casa bem?
- [ ] **10.6** Cosplay de Confessor RL50 com Golden Vow e uma arma keen. Monta os status e me diz a faixa de coop ideal.
- [ ] **10.7** Meu RL70 usa +16 normal / +6 somber. Isso é mid-game? Em que áreas eu sou útil em coop nessa faixa?
- [ ] **10.8** Vou copiar meu save do RL70 e fazer um RL130. O que muda de verdade na distribuição sem descaracterizar o build de twinblade?

## Pattern 11 — Mechanics: how does X actually work

"What is the difference between these spells?", "how does frostbite buildup work?" Pure
understanding questions, usually asked to inform a later build decision. The test is whether
the collection cites exact numbers or hand-waves, and whether it knows when it has no figure.

- [ ] **11.1** Qual a diferença entre as três magias de lua no Elden Ring e quando uso cada uma?
- [ ] **11.2** Como o dano do Black Flame (% de HP máximo) funciona, e por que ele é reduzido na DLC e ainda mais contra Messmer/Bayle/Consort?
- [ ] **11.3** Como o buildup de Frostbite é calculado e o que exatamente o proc faz (dano + debuff de dano recebido)?
- [ ] **11.4** Bleed/Hemorrhage: como o buildup escala com Arcane e por que uma arma com "menos bleed" pode procar mais rápido?
- [ ] **11.5** Como funciona o soft cap de Vigor e onde estão os breakpoints de HP importantes?
- [ ] **11.6** What exactly does poise/stance damage do, and how does stance break lead to a critical/riposte?
- [ ] **11.7** Qual a diferença entre Spinning Strikes e Spinning Weapon, e por que um aceita Blood affinity e o outro não?
- [ ] **11.8** Como o scaling de sorceries se comporta depois de 60 INT vs 80 INT — quanto realmente ganho por ponto?
- [ ] **11.9** Como funciona o dano de multiplicadores de talismã/physick — eles são multiplicativos entre si ou aditivos?

## Pattern 12 — Can weapon X do Y: feasibility and the workaround

"Is there a way to make [weapon] proc [status]?" The weapon cannot natively, so what is wanted
is the workaround list — grease, buff incantation, an off-hand, a talisman synergy — and which
one is best. The capability half is a lookup; the ranking is rule-based on top of it.

- [ ] **12.1** Is there a way to make the Marais Executioner's Sword proc bleed? What are the workarounds and which is best for PvE?
- [ ] **12.2** Dá pra colocar sangramento na Godslayer's Greatsword de alguma forma, já que ela não aceita Blood affinity?
- [ ] **12.3** Consigo aplicar Frostbite numa arma que não pode ser infundida com Cold? Como?
- [ ] **12.4** Can I make a colossal sword proc a status without losing its Heavy scaling? What are my options?
- [ ] **12.5** Tem algum jeito de fazer a Blasphemous Blade causar bleed sem perder o Taker's Flames?
- [ ] **12.6** Não tem um Ash of War que gire a arma continuamente e aceite Blood affinity? O Spinning Weapon não serve.
- [ ] **12.7** Consigo botar dano de raio numa arma somber que já tem elemento fixo? Ou só via incantation?
- [ ] **12.8** Dá pra usar Bloodflame Blade numa arma com Blood affinity? Os efeitos stackam ou se anulam?

## Pattern 14 — Getting an effect without the stat investment

"How do players with no Faith get Golden Vow or Flame, Grant Me Strength?" Stat-free
substitutes for a buff, and what they are actually worth. A good test of whether the collection
knows the ash version of Golden Vow is a fixed buff that does not scale.

- [ ] **14.1** Como jogadores sem Faith conseguem os buffs equivalentes ao Flame, Grant Me Strength e ao Golden Vow?
- [ ] **14.2** Quero o efeito do Golden Vow numa build de pure INT sem gastar ponto em Faith — o Ash of War Golden Vow resolve? O buff escala?
- [ ] **14.3** Dá pra ter cura sem Faith? Quais as opções e quão eficientes comparadas ao Heal?
- [ ] **14.4** How do I get a fire-damage buff on a Strength build with zero Faith? Which physick/perfume/talisman stack?
- [ ] **14.5** Quero um buff de dano físico stackável sem Faith numa build de DEX. Monta o combo (Ash + talismã + physick) e me diz o ganho aproximado.
- [ ] **14.6** Consigo o efeito do Flame, Cleanse Me (curar scarlet rot/poison) sem investir em Faith?
- [ ] **14.7** Buff de defesa sem Faith pra coop — o que substitui o lado defensivo do Golden Vow?

## Pattern 15 — Spell loadouts and range coverage

"Build me a spell bar", or "my school feels too short-range, how do I cover long range?" A full
loadout inside the slot and FP budget, plus a fix for a playstyle gap. The budgeting is calc;
the curation is judgement that has to rest on it.

- [ ] **15.1** Minha build de gelo (70 INT, Carian Regal Scepter +10) parece que só joga curto/médio alcance. Monta uma barra de magias que cubra long range sem abandonar o tema de gelo.
- [ ] **15.2** Faz uma barra de incantations de Faith pra coop RL150 que cubra buff, dano à distância, dano corpo a corpo e cura, dentro dos slots.
- [ ] **15.3** My pure INT RL150 mage needs a full spell loadout: opener, main DPS, close-range, AoE, and a boss nuke. Build the bar.
- [ ] **15.4** Monta um kit de Death sorceries temático mas funcional pro RL150 (INT 60 / FTH 45), com Prince of Death's Staff.
- [ ] **15.5** Quero um spellblade RL150: uma arma de melee + uma barra enxuta de magias que complementa o corpo a corpo. Monta o loadout.
- [ ] **15.6** Preciso de uma opção de long range que não seja de gelo mas se beneficie do debuff do Ranni's Dark Moon. Quais entram na barra?
- [ ] **15.7** Build a dragon-communion incantation bar for an Arcane/Faith RL150 that covers Bayle and general PvE.
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

### 1.13 Golden Order Greatsword, RL150 — partial

Somber, +10. From a Confessor with floors 40/20/25: STR 16 · DEX 36 · FTH 74, 794.928 AR split
275 physical / 519 holy. Confirmed by sweep.

"Aproveitando o Ash of War ao máximo" took two fixes to get an honest answer. Establish Order
was one of the seven skills ambiguous with itself and refused outright (`b4f735d`); it resolves
now — 7 hits, holy motion values up to 300, `overrides_weapon_scaling` false, so the weapon's
spread is the skill's spread.

Pricing it is where it stops, and the reason is new. **Establish Order's motion values are not
uniform**: the big hit is 300 holy and **0 physical**, and `optimal-affinity`'s `attack_mv` is
one number for the whole hit. Passing 300 gives 2146.30, which triples a physical attack rating
the skill does not use. `weapon-skill` now reports `motion_values_uniform` per hit and for the
skill, so this is a refusal to quote rather than a wrong figure — Corpse Piler is uniform and
passes straight through, Establish Order is not.

### 1.4 Erdtree Seal, pure Faith incantations — done

See above: two fixes and a feature. Faith 99, spell buff 367.0, Black Flame **895.48 fire**.

### 1.8 Frenzied Flame incantations, RL150 — done, and the answer is not a pure faith build

The Frenzied Flame Seal is one of **two catalysts in the game whose spell buff takes strength
and dexterity** — the Clawmark Seal is the other — so "pure faith" is the wrong build for it.
At RL150 from a Prophet with floors 40/30/20, Frenzied Burst is maximised at
**STR 26 · DEX 30 · INT 30 · FTH 43** for 845.40, against 828.33 for the spread a greedy search
finds and well above what pure faith reaches.

That result is also what exposed the search's local optimum: no single point moved between
those four stats pays for itself, and only a move of several does. Pinned against an exhaustive
sweep of 1,837,620 spreads.

Worth noting for the catalyst choice: the Erdtree Seal actually beats it on raw damage here
(917.50 against 828.33 for Frenzied Burst, faith 99), because the Frenzied Flame Seal's ×1.2
family bonus does not make up for its lower spell buff at these levels.

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

## Pattern 4 — the flagship, and it half closes

These ten are the case the collection was built for and the one it could not do: identify the
stat that drives a skill, price the hit, and multiply the buff stack. Three things had to
change, and after them the pattern splits cleanly in two.

**The multiplier stack now computes.** `item-effect` returned three sentences with the figures
inside them — "Increases damage by 1.15x with weapon skills" — which is the multiply handed
back to a model, the failure this collection keeps closing upstream. It now reads the figure
out of the description (144 of the 157 items that carry one state it in exactly one shape) and
multiplies **only the items whose conditions the caller asserts**. Shard of Alexander is 1.15
with a weapon skill and nothing at all on a normal swing.

**Skill damage was already priceable and nobody had wired it.** `weapon-skill` gives a hit's
motion value and `optimal-affinity` takes one as `attack_mv`. Corpse Piler's 155 is 918.46
against the standard reference where a normal 100-motion swing is 543.89, and 1267.48 with the
stack applied. Two registry notes now say so.

**Seven skills were ambiguous with themselves** — see `b4f735d`. Loretta's Slash was one, and
question 4.3 simply refused before that.

What is left is one real limit, and it is now precise. **A hit is priceable when its damage is
a motion value.** It is not when the hit carries *flat attack* (Ghostflame Ignition's 140-magic
explosion, Flaming Strike's 138 fire) or when it *overrides the weapon's scaling* (Sacred
Blade's bullet off Faith, Blood Blade's off Arcane, Gravitas' off Intelligence). Those are
read off the table and reported; nothing prices them, and the override is **per hit**, not per
skill — which is a sharper fact than the collection had before.

| # | skill | what drives it | priced |
|---|---|---|---|
| 4.1 | Wave of Destruction | weapon scaling, mv 85 + 170 bullet | **yes** |
| 4.2 | Corpse Piler | weapon scaling, mv up to 155 | **yes** |
| 4.3 | Loretta's Slash | weapon scaling, mv up to 172 | **yes** |
| 4.4 | Ghostflame Ignition | flat: 55 a tick, 140 explosion | no |
| 4.5 | Unsheathe R1 / R2 | weapon scaling, mv 190 / 245 | **yes** |
| 4.6 | Sacred Blade | slash on the weapon, bullet flat 180 holy off **Faith** | slash only |
| 4.7 | Storm Assault | main hit mv 200 on the weapon, bullets off **Str/Dex** | main hit only |
| 4.8 | Flaming Strike | one bullet, flat 138 fire off **Strength** | no |
| 4.9 | Gravitas | mv 100 on the weapon, three bullets flat 60 magic off **Intelligence** | main hit only |
| 4.10 | Blood Blade | slash mv 55 on the weapon, bullet flat 115 off **Arcane** | slash only |

### 4.1 Wave of Destruction — done, after correcting the weapon

There is no "Distinguished Greatsword" in the catalogue: `weapon-lookup` matches nothing, and
saying so is the answer rather than pricing something near it. Wave of Destruction is unique to
the **Ruins Greatsword**. At RL150 two-handed from a Vagabond: STR 66 · INT 44, 965.88 AR; the
skill's bullet at 170 motion value is **1362.31** against the standard reference, where a
normal swing is 779.43.

### 4.2 Corpse Piler — done, end to end

`overrides_weapon_scaling: false`, so the weapon-optimal spread is the skill's spread:
STR 12 · DEX 56 · ARC 59. Highest motion value 155.

| | damage |
|---|---|
| normal swing (mv 100) | 543.89 |
| Corpse Piler #3 (mv 155) | 918.46 |
| + Shard of Alexander ×1.15 and Lord of Blood's Exultation ×1.2 = **×1.38** | **1267.48** |

Both conditions are asserted rather than assumed: the first because a Corpse Piler is a weapon
skill, the second because Rivers of Blood procs bleed. Neither would apply to a plain R1.

### 4.3 Loretta's Slash — done, and the premise was wrong

Loretta's War Sickle scales strength, dexterity and **intelligence** — no faith at all, so
"STR vs DEX vs FTH" has a two-way answer. At RL150: STR 51 · DEX 57 · INT 20, 769.90 AR
(545 physical / 224 magic). Loretta's Slash at its 172 motion value: **1153.91**.

### 4.4 Ghostflame Ignition — partial

Every damaging hit is **flat**: 55 magic a tick, 140 magic on the explosion, with no motion
value and no scaling override. So the weapon's attack rating does not drive it, which is the
useful half of the answer, and nothing here prices what does.

### 4.5 Unsheathe, charged versus not — done

The charge *is* the R1/R2 distinction: mv 190 against mv 245. On a Uchigatana +25 at DEX 70,
Lightning is the best infusion for it either way — **1136.40 uncharged, 1465.41 charged**, a
29% gain. Keen is second at 976.43 / 1259.08.

### 4.6 Sacred Blade — partial, and "Faith é o principal mesmo?" gets a real answer

Half yes, and the half matters. The slash (mv 65) uses the weapon's own scaling; the **bullet
is flat 180 holy and overrides the weapon's scaling to Faith**. So faith drives the projectile
and not the swing, on any weapon the ash is put on.

### 4.7 Storm Assault — partial

Main hit mv 200 on the weapon's scaling, and the jump and land bullets override to **Str/Dex**.
The stack the question asks for computes: Shard of Alexander ×1.15 and Godfrey Icon ×1.15 give
**×1.3225**, with Godfrey Icon's own condition — "with charged spells and charged weapon
skills" — quoted so a reader can check it applies to the hit they meant.

### 4.8 Flaming Strike — partial

The skill is a single bullet, flat 138 fire, scaling overridden to **Strength**, so a Flamberge
with Flame Art contributes nothing to it but its own swing. That is a useful answer and it is
not the one the question asked for.

### 4.9 Gravitas — partial

Mv 100 on the weapon, plus three separately stacking bullets of flat 60 magic each, all
overridden to **Intelligence**. The three-bullet structure is worth quoting on its own.

### 4.10 Blood Blade / Seppuku — partial, and Seppuku is simply absent

Blood Blade is nine hits: three slashes at mv 55 on the weapon's scaling and their bullets at
flat 115 physical, overridden to **Arcane**. **Seppuku is not in the table at all** —
`weapon-skill` matches nothing — because it deals no damage; it is a self-buff, and its attack
bonus is not modelled anywhere in this collection. Saying that is better than a number.

---

## Where the battery leaves the collection

*After 83 questions in nine patterns.*

| pattern | done | partial | unanswerable |
|---|---|---|---|
| 1 — build for a level | 12 | 2 | 0 |
| 2 — rate / re-allocate | 8 | 0 | 0 |
| 3 — best weapon / spell | 9 | 1 | 0 |
| 4 — maximise a skill | 4 | 6 | 0 |
| 5 — talismans and swaps | 6 | 2 | 0 |
| 6 — ash of war selection | 7 | 1 | 0 |
| 7 — element coverage | 8 | 0 | 0 |
| 8 — coop generalist | 4 | 3 | 0 |
| 9 — comparisons | 8 | 2 | 0 |
| **total** | **66** | **17** | **0** |

**Fifteen bugs**, tracked in `BUGS.md` with what each returned instead of an error. Four of
them would have handed a reader a well-formed number for something that does not exist.

**Eight features** the questions demanded and the collection did not have: a caster objective
(`focus = "spell"`), loadout requirements (`stat_floors`), and the six nodes `weapon-rank`,
`spell-rank`, `spell-lookup`, `buff-stack`, `ash-rank` and `boss-coverage`.

**Five tables vendored** from the Prometheux workspace that had been sitting there unused:
`AshAffinity`, `AshClass`, `BuffMult`, `BuffSlot`, `PhysickEffect`. Two of the bugs exist
because a parser was written against prose when the structured table was already available —
worth checking the workspace's file list before building anything.

**What is still not modelled**, and would be the next thing to build:

- **Flat-attack and scaling-overridden hits.** Six of the ten Pattern 4 skills have one, and
  the override is **per hit**, not per skill. The data says which stat drives them; nothing
  computes the damage.
- **A skill objective for `build-allocate`**, which depends on the above.
- **Talismans applied to a build.** `buff-stack` multiplies damage under asserted conditions,
  but nothing adds a talisman's stat bonuses into `character-build`, `equip-load` or `defence`.
- **Moveset, reach, cast time and aggro.** Questions 9.9 and 8.6 turn on them and no table
  carries any of it. Saying so is the answer.
- **Guard counters**, which have no motion value in the extraction.

## Pattern 5 — the multiplier stack, on a table that was there all along

Eight questions about which talismans to wear and what to swap. Working the first one found
that the multiplier stack built for Pattern 4 was wrong: it multiplied **any** buffs a caller
asserted, including two that overwrite each other, and it read figures out of prose when
`BuffMult.csv` and `BuffSlot.csv` were sitting unvendored in the workspace. `buff-stack`
replaced it — see bug 11 — and then needed a second axis for the caster questions.

**Two axes, and a hit is usually both.** `hit_kind` is how you hit; `damage_sources` is what
the damage is. A Comet cast is a *sorcery* dealing *magic*, so Graven-Mass and Magic Scorpion
Charm both apply, which is what the game does and what one value would have made exclusive.

### 5.1 Blasphemous Blade, Taker's Flames, RL150 — done

Taker's Flames is a weapon skill, so `hit_kind = "Skill"`. Of the eleven talismans in the
table, three do anything at all:

| talisman | × | condition |
|---|---|---|
| Shard of Alexander | 1.15 | all weapon skills |
| Warrior Jar Shard | 1.1 | — |
| Ritual Sword Talisman | 1.1 | at full HP |
| **total** | **1.3915** | |

The fourth slot has no damage multiplier left for this hit, and that is the answer: Dagger
Talisman, Godfrey Icon, Claw, Axe, the three Successive ones are each worth exactly 1.0 here,
with `not_counted` saying which hit they *do* want. Spend the slot on survivability.

Also: Taker's Flames reports `motion_values_uniform: false`, so its 510 motion value cannot go
through `optimal-affinity`'s scalar `attack_mv` — the guard from bug 10 firing on a real
question.

### 5.2 Godslayer's Greatsword, dragon that allows no crits — done

The setup is Shard + Godfrey + Ritual + Dagger. On a plain weapon skill, **only two of the
four do anything**: Shard 1.15 and Ritual 1.1, total 1.265. Dagger Talisman is out because it
is a critical-only 1.17, and Godfrey Icon is out because it wants a *charged* skill — so the
answer is not "swap the Dagger", it is "two of your four slots are already dead unless you
charge the skill". Charge it and Godfrey adds 1.15.

### 5.3 Cold Milady Wing Stance, flex slot for frost-immune bosses — partial

Milady resolves (Light Greatsword, infusable, +25) and Wing Stance resolves with six accepted
affinities and **no damaging hits of its own** — it is a stance, like Seppuku. The frost half
is answerable: seven of the DLC's 42 phases are outright immune to frost, and
`boss-coverage` names them. What is not answerable is the flex slot itself, because the
stance's follow-up attacks are not separable in the table.

### 5.4 Graven-Mass + Graven-School + Magic Scorpion Charm — done, and yes they stack

All three are `Passive`, and `BuffSlot` says Passive multiplies. For a magic sorcery:
1.08 × 1.04 × 1.12 = **1.257984**. The Scorpion Charm's price comes with it — ten points of
physical negation, fifteen in PvP — because quoting the bonus alone is half an answer.

### 5.5 Eleonora's Poleblade, bleed, flex for bleed-immune bosses — partial

The weapon resolves (Twinblade, somber, +10). The bleed-immunity half is exact: **84 of the
game's 238 phases are immune to bleed**, and the list is one call. The talisman half is thin,
because `BuffMult` carries eleven talismans and the ones a bleed build actually swaps to are
mostly not among them.

### 5.6 Best talismans for fire incantations at 60 Faith — done

`damage_sources = ["incantation", "fire"]`: Flock's Canvas 1.08, Faithful's Canvas 1.04, Fire
Scorpion Charm 1.12 → **1.257984**, the same product as the sorcery package and for the same
reason. Graven-Mass is excluded with "it multiplies sorcery damage, and this hit is incantation
and fire".

### 5.7 Fourth slot: Lord of Blood's Exultation or Ritual Sword? — done

On successive twinblade hits, with Rotten Winged Sword Insignia and Millicent's Prosthesis
already on:

| fourth slot | total |
|---|---|
| Lord of Blood's Exultation | **1.50516** |
| Ritual Sword Talisman | 1.37973 |

Lord of Blood's wins by nine per cent — conditional on a bleed having procced, which for a
twinblade build it will have. The node makes that condition an assertion rather than an
assumption.

### 5.8 Radagon and Elden Beast: what a bleed setup loses — done

| fight | immune to | takes most |
|---|---|---|
| Radagon of the Golden Order | bleed, madness, sleep | fire (0% negation) |
| Elden Beast | **every status except death** | physical (10%) |

So the bleed talismans come off for both, Lord of Blood's Exultation included since nothing
will proc. Radagon negates 35% physical and 0% fire; Elden Beast negates 40% of every element
and 10% physical. They want opposite answers, which is why one recommendation for "Radagon and
Elden Beast" is wrong.

## Pattern 6 — the affinity an ash accepts, which was in no table

Eight questions turning on "qual Ash aceita Blood?", and `AshCompat` carries only the affinity
an ash *arrives with*. `data/AshAffinity.csv` — 982 rows of skill-and-affinity — closes it, and
`ash-rank` sorts what fits four different ways. Writing it found bugs 12 and 13.

The four rankings matter: **Stormcaller tops nearly every list on raw totals** (14 hits, 600
status, 1540 poise) and **overrides the weapon's scaling to Str/Dex**, which the node reports,
so on a build that is not Str/Dex it is the wrong answer despite the numbers.

| # | question | answer |
|---|---|---|
| 6.1 | Grave Scythe, Blood, most hits | Stormcaller 600 status / Double Slash 525 over 6 hits — 35 ashes fit |
| 6.2 | Twinblade blood: Seppuku vs Spinning Strikes vs Bloody Slash | none of the three: **Seppuku has no damaging hits at all** (self-buff), and Double Slash at 525 beats Bloody Slash. Spinning Strikes does not go on a twinblade |
| 6.3 | Cold Nagakiba, fastest frost proc | **Spinning Weapon**, 750 status over 11 hits — ahead of Stormcaller's 600 |
| 6.4 | Great hammer, stance break | Stormcaller 1540, then **Savage Lion's Claw 850** without a scaling override |
| 6.5 | DEX/FTH spear, lightning ash | partial — "Lightning Spear" as an ash is ambiguous with the incantations; Lightning Slash resolves, 4 hits, six affinities |
| 6.6 | Curved sword, Blood, continuous spin | **Spinning Slash does serve**: it accepts all thirteen affinities including Blood and goes on curved swords. It is Keen by default, which is what the question mistook for a restriction |
| 6.7 | Greatsword, Fire, multi-hit | **Spinning Gravity Thrust**, 9 hits and 585 status, behind Stormcaller only |
| 6.8 | Colossal, poise, keeping Heavy | **Savage Lion's Claw** — Stormcaller has more poise damage but overrides scaling to Str/Dex, which throws the Heavy scaling away |

## Pattern 7 — the pattern the collection was furthest from, and now closest to

Eight questions across the whole boss table. `boss-coverage` answers all of them in one call
each.

### 7.1 Gargoyle's Twinblade against Radagon and the Elden Beast — done

Two fights, two different answers, both computed against the real negation:

| fight | negation | best infusion |
|---|---|---|
| Radagon | 35 phys / 0 fire / 20 ltng / 80 holy | **Fire, 377** |
| Elden Beast | 10 phys / 40 fire / 40 ltng / 80 holy | **Heavy, 394** |

### 7.2 Fire, lightning or holy for faith, base game and DLC — done

Over all 238 phases: **fire**, on 18.98% average negation against lightning's 22.03 and holy's
25.43, and 50 outright wins to lightning's 49 and holy's 32. Holy is resisted 50% or more on
16 phases and fully negated on one.

### 7.3 DLC fights immune to frost — done

**Seven of 42**: three Ghostflame Dragons, a Death Rite Bird, a Fallingstar Beast, and both
phases of the Putrescent Knight. Toughest non-immune is Bayle the Dread at 744 resistance.

### 7.4 Where holy is bad — done

Same call as 7.2 with the summary read the other way: holy is the worst of the three on
average, 16 phases resist it at 50% or more, and Radagon and the Elden Beast — the fights a
holy weapon is most often carried for — negate 80% of it apiece. The secondary-holy-weapon idea
is the trap the question suspected.

### 7.5 DLC fights that resist lightning — done

Ancient Dragon Senessax at 80%, then Promised Consort Radahn, Metyr, Bayle and the Ghostflame
Dragons at 40. Against Senessax the answer is physical; against Radahn, holy.

### 7.6 A fire/lightning/holy matrix of the DLC — done

42 rows, one per phase, with each fight's best type and the summary above. Fire wins.

### 7.7 Where bleed, frost and poison are useless — done

Of 238 phases: **bleed immune on 84**, frost on 49, poison on 49, scarlet rot on 41. A bleed
build is switched off for a third of the game's fights, which is a larger number than the
question expected.

### 7.8 Elden Beast and Radagon: Heavy vs Fire vs Quality — done

Answered by 7.1's second table: Heavy wins on the Elden Beast, Fire on Radagon, and the gap
between them is the 35%-versus-10% physical negation. One weapon cannot be best against both.

## Pattern 8 — a build for a pool of fights

Seven questions, and every one is Pattern 7's coverage call feeding `build-allocate`. Four
answer cleanly; three are partial, and for the same reason each time.

### 8.1 Malenia, Mohg, Maliketh, Godfrey — done

Seven phases. **Physical is best on average at 13.57% negation**, against lightning's 22.86 and
holy's 45.71 — and holy wins none of the seven. Two of the seven, Mohg's second form and
Godfrey's, are immune to bleed *and* frost, so a status build is off for a third of the pool.
The build is a physical one; `weapon-rank` and `build-allocate` do the rest.

### 8.2 DLC pool: Rellana, Messmer, Romina, Bayle, Consort Radahn — done

Same shape, the DLC table, and fire's coverage from 7.2 with Bayle's lightning resistance
called out.

### 8.3 "Any boss in the game" — partial

The coverage call works over all 238 phases and says fire. What the question wants beyond that
— one loadout, no menu — is a judgement the collection has no figure for.

### 8.4 Fire Giant, Godskin Duo, Astel — done

Five phases, and **physical wins outright on three of the five at 6% average negation**, against
fire's 44 and holy's 32. Fire against the Fire Giant is the trap the numbers catch. Nothing in
the pool is immune to bleed.

### 8.5, 8.6 Survivability, stance break, aggro — partial

Stance break is answerable through `ash-rank`'s poise ranking. Survivability is
`character-build` and `defence`. **Aggro is not in the data at all**, and neither is the
threat a summon draws, so the "seguro de vida" half of 8.6 has no computed answer.

### 8.7 Mid-game generalist at RL125 — done

Rennala, Radahn and Morgott through `boss-coverage`, then a spread at RL125. Rennala's bubble
negating 100% of everything is the one that shapes the answer.

## Pattern 9 — comparisons, and two bugs on the way

Ten head-to-heads. Eight land cleanly, and working them found bugs 14 and 15.

### 9.1 Rennala's Full Moon vs Ranni's Dark Moon vs Rellana's Twin Moons — done

From a Carian Regal Scepter at 80 intelligence:

| spell | attack | FP | family bonus |
|---|---|---|---|
| Rennala's Full Moon | **1479.46** | 47 | ×1.1 Full Moon |
| Ranni's Dark Moon | 1356.17 | 57 | ×1.1 Full Moon |
| Rellana's Twin Moons | three separate hits | — | — |

Full Moon wins on damage *and* costs ten less FP, which is not the usual expectation. Rellana's
is the one that broke: it is stored as `[1]`, `[2]` and `[3]`, and asking for the bare name used
to be a crash. Now it resolves to three candidates.

### 9.2 Blasphemous Blade vs Sword of Night and Flame — done

At RL150 from a Confessor with 45/25/25 floors: Blasphemous Blade **796.51** (STR 40 · DEX 40 ·
FTH 36, 499 physical / 296 fire) against Sword of Night and Flame **701.92** (INT 50 · FTH 50,
three damage types of about 230 each). The Blasphemous Blade also leaves 80 points in strength
and dexterity, which is a different build to live in.

### 9.3 Loretta's Greatbow vs Loretta's Mastery — done

270 magic for 24 FP against 108 magic for 39 FP. The Greatbow is two and a half times the
damage for two thirds the cost per cast; Mastery's case has to be its multi-hit pattern, which
the spell table does not carry.

### 9.4 STR/FTH vs DEX/FTH as a coop generalist — partial

Both spreads compute, and `weapon-rank` ranks what each can hold. "Which covers more" is
Pattern 7 and answered; "more damage per hit" depends on the weapon, and the honest answer is
the ranking rather than a single number.

### 9.5 Rivers of Blood vs Nagakiba for a fast proc — done

At ARC 60 / DEX 30: Rivers of Blood 637.85 AR and **76 bleed**; Nagakiba Blood +25 441.59 AR
and **114 bleed**. The Nagakiba procs half again as fast and hits a third softer — which is the
conditional answer the question wanted.

### 9.6 Carian Regal Scepter vs Lusat's at 70 INT — done, and the FP was wrong

Lusat's gives **+10.2% damage for +50% FP**: 1062.88 at 36 FP against 964.77 at 24. That is
**29.5 damage per FP against 40.2** — the Regal Scepter is 36% more efficient, the opposite of
what the figures said before bug 15 was fixed.

### 9.7 Dagger Talisman vs Godfrey Icon on Ordovis — done

The best answer in the pattern, because it is three answers:

| the hit | multiplier | which talisman |
|---|---|---|
| uncharged Ordovis's Vortex | 1.0 | **neither** |
| charged | 1.15 | Godfrey Icon |
| riposte | 1.17 | Dagger Talisman |

So "considerando que nem todo boss deixa riposte" is exactly right, and the answer is that
against a boss with no riposte you charge the skill and wear Godfrey.

### 9.8 Sword Lance, Cold vs Blood — done

At STR 21 / DEX 40 / INT 20 / ARC 40: Cold **547.47 AR with 153 frost**, Blood 434.73 with 150
bleed. Cold wins on both counts. The first run of this at strength 20 returned 162 AR for
Blood — the weapon needs 21, and `shortfall: strength 1` is the node catching a one-point miss
that costs 60% of the attack rating.

### 9.9 Great Katana vs Nagakiba for DEX/bleed — partial

At DEX 50 / ARC 45, both Blood +25: Great Katana **597.78 AR and 132 bleed**, Nagakiba 485.97
and 108. The Great Katana wins both. Moveset and reach, which the question also asks about, are
not in the extraction.

### 9.10 Heavy vs Quality on a Gargoyle's Twinblade at STR 50 / DEX 30 — done

Heavy 478.36, Quality 456.81 — and **Fire beats both at 494.71**, which is the answer the
question did not ask for and needs.