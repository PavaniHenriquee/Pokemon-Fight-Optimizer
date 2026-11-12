# Engine plan: Renegade Platinum up to the Champion

## Status

Updated only when asked.

- Done: Phase 0 (this file and the CLAUDE.md pointers), 2026-11-08.
- Done: 1.1 (trainer importer), 1.2 (trainer availability) and 1.3 (coverage report), 2026-11-08.
- Done: 1.4 (MoveDB entry helper), 2.1 (state design note) and 2.2 (`node_key` capacity), 2026-11-08.
- Done: Phase 3 (Substitute and its audit), 2026-11-08.
- Done: 4.1 (simple held items), 4.2 (items with their own rules) and 4.3 (berries), 2026-11-08.
- Done: 4.4 (choice items), 2026-11-09.
- Done: 4.5 (item moves), and with it Phase 4, 2026-11-09.
- Done: 5.1 (status, flinch or confusion chance) and 5.2 (stat changes on hit), 2026-11-09.
- Done: 5.3 (everything else in this phase), and with it Phase 5, 2026-11-09.
- Done: 6.1 (recharge), 6.2 (charge turn), 6.3 (semi-invulnerable, and what reaches it), 6.4 (rampage) and 6.5
  (crash damage), and with it Phase 6, 2026-11-10.
- Done: 7.1 (variable power), 7.2 (fixed and HP-based damage) and 7.3 (turn order), and with it Phase 7,
  2026-11-10.
- Done: 8.1 (stat stages), 2026-11-10.
- Done: 8.2 (status and sleep) and 8.3 (healing), and with it Phase 8, 2026-11-11.
- Done: 9.1 (weather) and 9.2 (field), 2026-11-11.
- Done: 9.3 (hazards and grounding), and with it Phase 9, 2026-11-11.
- Done: 10.1 (delayed effects) and 10.2 (sacrifice), 2026-11-12.
- Done: 10.3 (self-switch), and with it Phase 10, 2026-11-12.
- Done: 11.1 (restriction and trapping) and 11.2 (accuracy locks and protection), 2026-11-12.
- Done: 11.3 (reflection), and with it Phase 11, 2026-11-12. Its `benchmarks.run quick` on the home PC is still
  to do.
- Next: 12.1 (type and ability changes).

## Goal

Every singles battle in Renegade Platinum up to Champion Cynthia runs in the engine, at a usable speed. That
means every move, item, ability and trainer item that those trainers and my own Pokemon can have. After that,
the neural network work resumes (`NN_PLAN.md`).

## Decisions (2026-11-08)

- Singles only. Double and multi battles are out (see below); I play them without the tool.
- Mechanism first. Phases group shared mechanics across the whole game, cross-cutting ones first. They don't
  go split by split.
- A move or item enters MoveDB / ItemDB in the batch that implements it, as before.
- `TODO.txt` stays as the finished list up to the 1st gym. This file replaces it.
- `*` counts post-game sources too (1.3): post-game encounters, legendaries and items, so the tool is ready if
  I explore after the Champion. The sheet doesn't list berries: they come from [pp]'s berry trees.

## Out of scope

- Double and multi battles: Spear Pillar (Mars + Jupiter, with Barry as partner), Riley's tag battle on Iron
  Island, and Twins and couples on routes. TODO.txt's "Doubles: Bide" goes with them.
- Post-game and rematches (the sheet's POST GAME and REMATCHES tabs).
- The plates (Multitype's and Judgment's type change): post-Champion pickups. Arceus itself is in (1.3, see
  Decisions), and without a plate Judgment is a plain Normal move.
- Klutz: no RP species has it (PkDB).
- Search tuning, except what new mechanics need (`node_key`, the rollout).

## How to work from this file

- Read Status and the phase in progress, not the whole file.
- A numbered step is about one batch. Each batch follows CLAUDE.md: the per-batch flow under "Implementing
  moves, items and abilities" and the checklist below it.
- Notation, as in CLAUDE.md:
  - no `*`: a trainer up to the Champion uses it (do first)
  - `*`: only my own Pokemon can have it
  - `!`: check the Showdown handler and pokeplatinum first
  - `!!`: also write a mechanics note and wait for OK
  - `(B)` / `(E)`: the `basic_flag` / `expert_flag` branch from [pp] `trainer_ai/script.s` and Pokemow
- Where the marks come from:
  - `(B)`, `(E)` and `!` come from TODO.txt where it listed the entry. For everything else, the batch checks
    `script.s`.
  - TODO.txt's `*` meant "up to Roark", so nothing here has `*` yet. 1.3 adds them.
- At the end of a batch, list the boxes that can be ticked. Tick them and update Status only when asked.
- At the end of each phase:
  - `pytest`, `pytest -m jit`, and `pytest -m slow` if the layout or turn flow changed
  - a new `tests/battle_driver.py` scenario that exercises the phase's mechanics
  - `python -m benchmarks.run quick` on the home PC, compared with the previous report
  - the coverage report (1.3)

## Phase 1: data foundation

The engine phases only need this for the `*` marks. If the sheet needs a login, Phase 2 can start while the
CSVs get exported by hand.

- [x] 1.1 Trainer importer, `DataBase/import_trainers.py`, on the pattern of `import_encounters.py`. It
      downloads a tab by gid, or takes an exported CSV.
  - Source: the TRAiNERS tab and the split tabs (GARDENiA, FANTINA, MAYLENE, WAKE, BYRON, CANDICE, VOLKNER,
    CHAMPiON SPLiT). Find which one has the full sets (level, item, ability, nature, IVs, moves) and the
    rival variants.
  - Output: TrainerDB.json with every singles trainer from the Roark split to Cynthia, in story order, with a
    new `"split"` field. Double and multi battles are skipped, and the run lists them.
  - It has to reproduce the 34 current entries exactly; review the diff with me.
  - Some things the sheet may not give: the gender rule, IVs, the sprite per trainer class, and `terrain`
    for Nature Power, Secret Power and Camouflage users. They follow the rule the current entries used, once
    I've confirmed it.
  - Afterwards, TrainerDB.json goes under "Generated / derived files" in CLAUDE.md, and the ROARK SPLIT line
    there covers every split (with my OK).
- [x] 1.2 Trainer availability (confirm the design at the step).
  - `/trainers` says what each trainer still lacks:
    - moves not in MoveDB and items not in ItemDB
    - entries that exist but aren't implemented yet: the moves below marked "in MoveDB", Color Change and
      Forecast. One small constant lists them, and it only shrinks.
  - The Setup picker groups trainers by split. Unsupported trainers show as disabled, with what they lack.
    `/start` refuses them.
  - `test_trainer_pokemon_build` covers the supported trainers. Check it in the app with the run-app skill.
- [x] 1.3 Coverage report, `python -m DataBase.coverage`.
  - It covers every move, item, ability and trainer item a trainer up to the Champion uses. For each one: the
    first split, how many trainers, and whether it's supported. It also shows how many trainers per split are
    supported.
  - Entries only my own Pokemon can have get `*` in this file. The sources are the learnsets in PkDB, the TMs
    in ItemLocationDB and the species in EncounterDB.
  - It also places the moves under "To check". If it suggests a different phase order, propose it and wait.
- [x] 1.4 (ask first) MoveDB entry helper. It builds a batch's entries from Showdown's gen4 data (every
      inheritance layer) with the MOVES tab's numbers. Then it inserts them alphabetically into MoveDB.json and
      `MoveName`.

## Phase 2: state and search capacity

This is architecture, so a note comes first and waits for OK.

- [x] 2.1 Design note. For each new piece of state: where it lives (VolStatus2 bits, new `Pok` slots, or
      per-side `Field` slots on the shared `SIDE_*` layout), what switch-out resets, what Baton Pass keeps, and
      how `node_key` sees it. Draft list to check:
  - Per Pokemon:
    - Substitute HP, the choice-locked slot and the Stockpile count
    - turns left for Magnet Rise, Embargo, Heal Block and Lock-On
    - bits for Torment, Imprison, Miracle Eye, Mean Look, Power Trick, Transform and Grudge
    - a rampage counter (Thrash) and the moves used since switch-in (Last Resort)
    - a backup of the original types and moves, for Roost, Conversion, Camouflage, Color Change, Forecast,
      Transform and Mimic
    - item identity changes from Trick, Thief and Fling
  - Per side: Spikes layers; Tailwind turns; Wish (turns, HP); Future Sight and Doom Desire (turns, damage).
  - Field: Trick Room (`Field.TRICKROOM` exists).
  - `node_key`: k1, k2 and k3 are full, and so is `VOL2_KEY_BITS` (3). It needs at least one more 64-bit word.
  - Agreed (2026-11-08). Sources: [pp] `battle_mon.h` `MoveEffectsData`, the `*_BATON_PASSED` masks in
    `constants/battle/condition.h` and `moves.h`, `battle_lib.c` `BattleSystem_UpdateAfterSwitch`; [SD gen4]
    Wish, Future Sight, Doom Desire.
    - Patterns: a flag with a counter is a bit plus its own turns slot (like Taunt); one `Pok` slot per
      counter, before `AB_ID`; per-side timers on the `SIDE_*` layout. Each slot comes with its batch.
    - Per Pokemon (switch-out clears all of it unless noted; "BP" = Baton Pass keeps it, [pp]):
      - Substitute: `VOL2.SUBSTITUTE` + `Pok.SUB_HP`. BP, with its HP. Keyed: only whether it's up.
      - Choice lock: `Pok.CHOICE_LOCK` (slot + 1). Keyed: the slot (the foe's comes from the AI's tie-break).
      - Stockpile: `Pok.STOCKPILE`, the count plus the Def / SpD stages it gave (Spit Up / Swallow take those
        back). Keyed: the count.
      - Magnet Rise, Embargo, Lock-On: `VOL2` bit + `*_TURNS` slot; Heal Block: its `VolStatus` bit +
        `HEAL_BLOCK_TURNS`. BP, turns included. Lock-On also ends when its target switches out, and its timer
        restarts when the target Baton Passes.
      - Torment, Imprison, Miracle Eye, Grudge: `VOL2` bits.
      - Mean Look / Block / Spider Web: `VOL2.MEAN_LOOK` on the trapped one. It also ends when the trapper
        switches out other than by Baton Pass. BP (the receiver stays trapped).
      - Power Trick: `VOL2` bit, Atk/Def swapped in place and swapped back on switch-out. BP, and the receiver's
        Atk/Def get swapped.
      - Gastro Acid: `AB_ID` cleared with the `BASE_AB_ID` backup (Worry Seed's) + `VOL2.GASTRO_ACID`. BP,
        unlike Worry Seed.
      - Roost, Magic Coat, Snatch: `VOL2` bits for the turn, like `PROTECT`.
      - Thrash: `Pok.RAMPAGE_TURNS` beside `LOCKED_MOVE`, also cleared in `unlock_move`.
      - Last Resort: `Pok.LAST_RESORT`, a mask of the slots used since switch-in. Keyed: one derived bit,
        "knows it and it would work".
      - Types: `Pok.BASE_TYPE1/2` from `to_np`, switch-out restores `TYPE1/2` from them. Keyed: `TYPE1/2`.
      - Moves (Mimic, Transform): `Pok.ORIG_MOVE1..4`, 0 untouched, else `id * 128 + PP`, rebuilt from
        `MOVE_TABLE` on switch-out. Not keyed.
      - Items (Trick, Thief, Fling): no new slot, the item block is rebuilt from `ITEM_TABLE` and `bench_delta`
        already has the bench's item id. Keyed: the item id.
      - Transform's other backups (stats, weight, gender, species) are decided in its batch (12.2).
    - Per side: `SIDE_SPIKES` (layers, keyed); `SideCondition.TAILWIND` + `SIDE_TAILWIND_TURNS`;
      `SideCondition.WISH` + `SIDE_WISH_TURNS` (no HP slot: [SD gen4] heals half the recipient's max HP);
      `SideCondition.FUTURE_SIGHT` on the target's side + `SIDE_FUTURE_TURNS`, `SIDE_FUTURE_DAMAGE` (fixed at
      use, typeless) and `SIDE_FUTURE_MOVE` (the hit rolls 90 or 85 accuracy). Field: `Field.TRICKROOM`.
    - `node_key`, opp in the low 32 bits of k5 and k6, mine in the high 32 (empty in the death phase):
      - k1: unchanged, the side conditions masked to the 10 bits they use now.
      - k2: `VOL_STATUS2` moves out; Gravity at bit 56, Trick Room at 57.
      - k5: `VOL_STATUS2` 0-19 (`VOL2_KEY_BITS` 20), choice slot 20-22, Stockpile 23-24, Last Resort 25,
        Encore slot 26-27, Disable slot 28-29 (each only while its bit is set).
      - k6: side conditions from 1024 up 0-3, Spikes layers 4-5, item id 6-14, `TYPE1` 15-19, `TYPE2` 20-24,
        `LOCKED_MOVE` + 1 25-28, charging 29, recharging 30.
      - Locks are keyed because a Rollout hit with a small roll and a miss can land in the same HP bracket.
      - Siblings have the same Pokemon in each slot, so keying the item id and types always only sees real
        changes.
- [x] 2.2 Build the agreed capacity with `node_key` tests, but no mechanics yet: the new key word(s), more
      VOL2 key bits, and keyed item and type changes. Each slot comes with its own batch, following the note. If
      a layout change breaks `NeuralNetwork/`, stop and ask.

## Phase 3: Substitute

It's cross-cutting, so it goes first: every later batch checks its moves against it.

- [x] Substitute(B/E) !!
- [x] Audit every MoveDB move against it once: status moves, secondaries, drain, trapping, multi-hit, Baton
      Pass, and resist berries (the Known gaps line).

## Phase 4: items

### 4.1 Simple held items

Type boosters:

- [x] BlackGlasses \*
- [x] Dragon Fang \*
- [x] Magnet \*
- [x] Spell Tag
- [x] Odd Incense \*
- [x] Rock Incense \*
- [x] Rose Incense \*
- [x] Wave Incense \*
- [x] Wise Glasses

Species items:

- [x] DeepSeaTooth \*
- [x] DeepSeaScale \*
- [x] Soul Dew \*
- [x] Adamant Orb \*
- [x] Lustrous Orb \*
- [x] Griseous Orb \* !
- [x] Lucky Punch \*
- [x] Stick \*
- [x] Metal Powder \*
- [x] Quick Powder \*

Crit, accuracy and flinch:

- [x] Razor Claw \*
- [x] Zoom Lens !
- [x] Wide Lens
- [x] King's Rock !
- [x] Razor Fang \* (not on the iTEMS/TMs tab: [pp] hides one on Route 214)

Speed and order:

- [x] Macho Brace \*
- [x] Power Anklet \*
- [x] Power Band \*
- [x] Power Belt \*
- [x] Power Bracer \*
- [x] Power Lens \*
- [x] Power Weight \*
- [x] Lagging Tail \* !
- [x] Full Incense \* !
- [x] Iron Ball \* !

No battle effect:

- [x] No-effect items, only the ones a trainer or my box holds, so Fling, Trick, Thief and Knock Off see
      them: Amulet Coin, Cleanse Tag, Everstone, Exp. Share, Luck Incense, Lucky Egg, Pure Incense, Smoke Ball,
      Soothe Bell, evolution items and stones, scarves, flutes
- [x] Rare Candy (Lady Celeste's and Rich Boy Liam's Blissey)

### 4.2 Items with their own rules

- [x] Life Orb !
- [x] Shell Bell \*
- [x] Focus Sash !
- [x] Toxic Orb
- [x] White Herb !
- [x] Sticky Barb \* !
- [x] Destiny Knot \*

### 4.3 Berries

Status:

- [x] Cheri Berry \*
- [x] Rawst Berry \*
- [x] Aspear Berry \*
- [x] Persim Berry \*
- [x] Leppa Berry \* !

HP (they confuse by nature):

- [x] Figy Berry \* !
- [x] Wiki Berry \* !
- [x] Mago Berry \* !
- [x] Aguav Berry \* !
- [x] Iapapa Berry \* !

Pinch:

- [x] Liechi Berry
- [x] Ganlon Berry \*
- [x] Salac Berry \*
- [x] Petaya Berry
- [x] Apicot Berry \*
- [x] Lansat Berry \*
- [x] Starf Berry !
- [x] Micle Berry \* !
- [x] Custap Berry \* !

Others:

- [x] Enigma Berry \* !
- [x] Jaboca Berry \*
- [x] Rowap Berry \*

### 4.4 Choice items

This covers the lock state, `move_blocked`, the AI, and Encore and Struggle.

- [x] Choice Band !!
- [x] Choice Specs !!
- [x] Choice Scarf !!

### 4.5 Item moves

- [x] Thief(E) \*
- [x] Pluck(E)
- [x] Trick(B/E) !!
- [x] Switcheroo(B) !!
- [x] Embargo(B/E) !
- [x] Fling(B/E) !! (last: it needs every item's Fling data)

## Phase 5: plain damage moves

The engine already has these mechanics. Each move needs data plus its AI branches.

### 5.1 Status, flinch or confusion chance

Burn:

- [x] Fire Blast
- [x] Flamethrower
- [x] Heat Wave
- [x] Lava Plume
- [x] Blaze Kick
- [x] Sacred Fire
- [x] Scald !

Paralysis:

- [x] Thunderbolt
- [x] Discharge
- [x] Zap Cannon
- [x] Body Slam

Poison:

- [x] Sludge
- [x] Sludge Bomb
- [x] Gunk Shot
- [x] Poison Jab
- [x] Cross Poison
- [x] Poison Tail

Freeze:

- [x] Ice Punch

Confusion:

- [x] Dizzy Punch
- [x] Dynamic Punch
- [x] Signal Beam
- [x] Rock Climb \*
- [x] Chatter !

Flinch:

- [x] Dark Pulse
- [x] Dragon Rush
- [x] Icicle Crash
- [x] Needle Arm \* !
- [x] Rolling Kick \*
- [x] Waterfall

Fangs:

- [x] Ice Fang
- [x] Thunder Fang

Binding:

- [x] Magma Storm \* !

### 5.2 Stat changes on hit

Target drop chance:

- [x] Bug Buzz
- [x] Crunch
- [x] Crush Claw
- [x] Earth Power
- [x] Energy Ball
- [x] Flash Cannon
- [x] Focus Blast
- [x] Iron Tail
- [x] Mirror Shot \*
- [x] Moonblast
- [x] Muddy Water
- [x] Octazooka
- [x] Play Rough
- [x] Psychic
- [x] Rock Smash \*
- [x] Shadow Ball
- [x] Seed Flare \*

Self raise chance:

- [x] Charge Beam
- [x] Meteor Mash
- [x] Steel Wing \*
- [x] Ancient Power
- [x] Ominous Wind

Self drop:

- [x] Close Combat(E) !
- [x] Superpower(E) !
- [x] Hammer Arm(E) !
- [x] Overheat !
- [x] Draco Meteor !
- [x] Leaf Storm !
- [x] Psycho Boost !

### 5.3 Everything else in this phase

Plain:

- [x] Aqua Tail
- [x] Cut \*
- [x] Dazzling Gleam
- [x] Dragon Claw
- [x] Dragon Pulse
- [x] Drill Peck
- [x] Egg Bomb
- [x] Hyper Voice
- [x] Judgment \* (Arceus, post-game: Normal without a plate)
- [x] Mega Kick
- [x] Mega Punch
- [x] Megahorn
- [x] Pay Day
- [x] Power Gem
- [x] Power Whip
- [x] Strength
- [x] X-Scissor

High crit:

- [x] Slash
- [x] Night Slash
- [x] Psycho Cut
- [x] Cross Chop
- [x] Stone Edge
- [x] Leaf Blade
- [x] Shadow Claw
- [x] Crabhammer \*
- [x] Drill Run ! (it's in Horn Drill's slot, see Known gaps)
- [x] Attack Order
- [x] Aeroblast
- [x] Spacial Rend

Priority:

- [x] Bullet Punch
- [x] Ice Shard
- [x] Shadow Sneak
- [x] Vacuum Wave

Sure hit:

- [x] Aura Sphere
- [x] Magnet Bomb
- [x] Shadow Punch
- [x] Vital Throw(E)

Multi-hit:

- [x] Bone Rush
- [x] Icicle Spear
- [x] Spike Cannon
- [x] Double Hit
- [x] Bonemerang

Recoil:

- [x] Double-Edge
- [x] Brave Bird
- [x] Wood Hammer
- [x] Head Smash
- [x] Wild Charge
- [x] Flare Blitz

Drain:

- [x] Giga Drain
- [x] Leech Life
- [x] Drain Punch

Fixed damage:

- [x] Sonic Boom

## Phase 6: forced turns and hit rules

### 6.1 Recharge

- [x] Hyper Beam (in MoveDB)
- [x] Giga Impact
- [x] Blast Burn
- [x] Hydro Cannon
- [x] Frenzy Plant
- [x] Roar of Time \*
- [x] Rock Wrecker \*

### 6.2 Charge turn

- [x] Solar Beam !
- [x] Skull Bash
- [x] Sky Attack
- [x] Razor Wind

### 6.3 Semi-invulnerable, and what reaches it

- [x] Fly
- [x] Dive
- [x] Shadow Force !
- [x] Sky Uppercut
- [x] Surf
- [x] Thunder ! (weather accuracy too)
- [x] Hurricane ! (RP's version)

### 6.4 Rampage

- [x] Thrash !
- [x] Outrage !
- [x] Petal Dance !

### 6.5 Crash damage

- [x] Jump Kick !
- [x] High Jump Kick !

## Phase 7: power and damage rules

### 7.1 Variable power

- [x] Eruption
- [x] Water Spout
- [x] Wring Out(E)
- [x] Crush Grip(E) \*
- [x] Reversal(E)
- [x] Punishment(E)
- [x] Trump Card(E)
- [x] Facade(E)
- [x] Smelling Salts(E)
- [x] Wake-Up Slap(E)
- [x] Grass Knot
- [x] Return !! (where friendship comes from)
- [x] Frustration !! (same)
- [x] Present !
- [x] Triple Kick !
- [x] Beat Up !!
- [x] Last Resort(B/E)
- [x] Secret Power \* !

### 7.2 Fixed and HP-based damage

- [x] Super Fang(E)
- [x] Endeavor(E)
- [x] Pain Split(E)
- [x] Metal Burst(B/E)
- [x] False Swipe

### 7.3 Turn order

- [x] Avalanche
- [x] Revenge
- [x] Payback(E)
- [x] Sucker Punch(E) ! (in MoveDB)
- [x] Focus Punch(E) ! (in MoveDB)

## Phase 8: status moves

### 8.1 Stat stages

- [x] Swords Dance
- [x] Calm Mind(B)
- [x] Cosmic Power(B)
- [x] Acid Armor
- [x] Tail Glow \*
- [x] Sharpen \*
- [x] Defend Order
- [x] Feather Dance
- [x] Metal Sound
- [x] Cotton Spore
- [x] Dragon Dance(B/E) (in MoveDB)
- [x] Swagger (in MoveDB)
- [x] Flatter (in MoveDB)
- [x] Belly Drum(B/E) !
- [x] Acupressure(B/E) !
- [x] Psych Up(E) ! (in MoveDB)
- [x] Haze(E)
- [x] Power Swap(B/E) \*
- [x] Guard Swap(B/E)
- [x] Heart Swap(E) \*
- [x] Power Trick(B/E) !
- [x] Captivate(B/E)

### 8.2 Status and sleep

- [x] Toxic(E)
- [x] Glare
- [x] Spore
- [x] Lovely Kiss
- [x] Dark Void \*
- [x] Poison Gas
- [x] Teeter Dance
- [x] Rest(E) !
- [x] Sleep Talk(B/E) ! (in MoveDB)
- [x] Snore(B)
- [x] Nightmare(B/E) ! (in MoveDB)
- [x] Dream Eater ! (in MoveDB)
- [x] Psycho Shift(B/E) !
- [x] Heal Bell(E) !
- [x] Aromatherapy(E) !

### 8.3 Healing

- [x] Milk Drink \*
- [x] Soft-Boiled
- [x] Slack Off
- [x] Heal Order
- [x] Moonlight
- [x] Morning Sun
- [x] Roost !
- [x] Heal Block(B/E) !

## Phase 9: weather, field and hazards

### 9.1 Weather

- [x] Sunny Day(E)
- [x] Hail(E)
- [x] Weather Ball !
- [x] Heat Rock
- [x] Icy Rock \*
- [x] Forecast (ability) !

### 9.2 Field

- [x] Trick Room(B/E) ! (in MoveDB)
- [x] Tailwind(B/E) !

### 9.3 Hazards and grounding

- [x] Spikes(E) !
- [x] Defog(B/E) \* !
- [x] Rapid Spin clears Spikes too
- [x] Magnet Rise(B/E) !

## Phase 10: delayed effects, sacrifice and self-switch

### 10.1 Delayed effects

- [x] Future Sight(B) !! (in MoveDB)
- [x] Doom Desire(B) !!
- [x] Wish !
- [x] Stockpile(B)
- [x] Spit Up(B/E)
- [x] Swallow(B)

### 10.2 Sacrifice

- [x] Memento(B/E)
- [x] Healing Wish(B/E) !! (the replacement is picked mid-turn)
- [x] Grudge \* !

### 10.3 Self-switch

- [x] U-turn(E) !! (my mid-turn pick reuses the Baton Pass phase; the AI uses its post-KO pick)

## Phase 11: restriction, trapping and protection

### 11.1 Restriction and trapping

- [x] Torment(B)
- [x] Imprison(B/E)
- [x] Spite \* !
- [x] Mean Look(B)
- [x] Block
- [x] Spider Web \*

### 11.2 Accuracy locks and protection

- [x] Lock-On(B/E)
- [x] Mind Reader(E)
- [x] Miracle Eye(B/E)
- [x] Detect(E)

### 11.3 Reflection

- [x] Magic Coat(E) !!
- [x] Snatch(E) !!

## Phase 12: copying, calling and type/ability changes

### 12.1 Type and ability changes

- [ ] Conversion(E) \*
- [ ] Conversion 2 \*
- [ ] Camouflage(B)
- [ ] Color Change (ability) !
- [ ] Role Play
- [ ] Skill Swap \*
- [ ] Gastro Acid(B/E)

### 12.2 Copying

- [ ] Mimic !!
- [ ] Sketch \* !
- [ ] Transform \* !!

### 12.3 Calling

- [ ] Assist !
- [ ] Me First(E) !!

## To check in 1.3

No RP learnset or TM has these. Place each one if the DEX tab's tutor or egg lists or a trainer team have it,
and drop it otherwise. Done in 1.3 (the DEX tab has no egg moves):

- [x] Twister: dropped, nothing has it
- [x] Frenzy Plant: in 6.1, three trainers use it
- [x] Volt Tackle: dropped, nothing has it
- [x] Lunar Dance: dropped, nothing has it
- [x] Brine: dropped, nothing has it
- [x] Any other tutor move: Judgment (in 5.3), nothing else

## Phase 13: trainer AI

- [ ] 13.1 Only if the tool shows the 3-flag assumption is wrong (`KNOWN_GAPS.md`, "AI flags").
      The assumption: every RP trainer has Basic, Evaluate Attack and Expert, no more and no less. If it's wrong:
  - add per-trainer `ai_flags` in TrainerDB, defaulting to those 3
  - add whatever flags the evidence shows, for example Setup First Turn ! (Pokemow + [pp] `script.s`).
    [pp] `res/trainers/data` gives it to Lucian, and to Mars at Spear Pillar (a multi battle).
- [ ] 13.2 Trainer items that 1.3 finds and the AI can't use yet, per [pp] `TrainerAI_ShouldUseItem`.
      Possible ones: Max Potion, X Attack, X Accuracy, Dire Hit, Guard Spec and status heals. Done already:
      Potion, Super Potion, Hyper Potion, Full Restore, Full Heal, X Special, X Defend and X Speed.
- [ ] 13.3 Re-check each line in `KNOWN_GAPS.md`'s Trainer AI section against the trainers now covered. Do the ones a
      trainer reaches.

## Phase 14: wrap-up

- [ ] A `pytest -m slow` fuzz battle against every TrainerDB trainer.
- [ ] `python -m benchmarks.run quick` compared with the last report from before this plan
      (`benchmarks/results/`).
- [ ] UI leftovers, and the box editor's "manual add can add any species". Known gaps says to remove it once
      the app covers the full game; ask first.
- [ ] README Status, the CLAUDE.md intro, and the Known gaps cleanup (only what I approve).
- [ ] Remove CLAUDE.md's NN hold line. `NN_PLAN.md` work resumes.

## Where the numbers came from (2026-11-08)

- MoveDB had 222 moves. 244 were missing and are in Phases 3 to 12: 235 from PkDB's learnsets (the DEX tab)
  and 9 TM/HM-only ones (ItemLocationDB). 12 more are in MoveDB but have no mechanics yet, marked "in
  MoveDB".
- ItemDB had 58 items. The rest come from the iTEMS/TMs tab (ItemLocationDB) and the Gen IV battle berries.
- AbilitiesDB had 122, every ability any species has.
- TrainerDB had 34 trainers, the Roark split.
- AI flags (pokeplatinum `res/trainers/data`): every gym leader, Elite Four member, Cynthia, Cyrus and the
  late rival use Basic, Evaluate Attack and Expert. Lucian and Mars at Spear Pillar also have Setup First Turn.
