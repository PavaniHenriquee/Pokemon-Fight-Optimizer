# Plan: finish the unchecked moves in TODO.txt (main `# Moves` section)

## Progress (update at the end of every session)

| Phase                                     | Status                       | Notes                                                                                  |
| ----------------------------------------- | ---------------------------- | -------------------------------------------------------------------------------------- |
| Step 0: save plan                         | Done                         |                                                                                        |
| Phase 0: layout infrastructure            | Done (2026-10-26), committed | See "Phase 0: as built" below                                                          |
| Phase 1: data-driven moves                | Done (2026-10-27), committed | B1-B10 fixed, 97 TODO boxes ticked; Gust and Stomp left open                           |
| Phase 2: damage mechanics                 | Done (2026-10-27), committed | See "Phase 2: findings and decisions" and "Phase 2: outcome"; 16 TODO boxes ticked     |
| Phase 3: volatiles, no action restriction | Done (2026-10-27), committed | See "Phase 3: findings and decisions" and "Phase 3: outcome"; 17 TODO boxes ticked     |
| Phase 4: action-restricting volatiles     | Done (2026-10-27), committed | See "Phase 4: findings and decisions" and "Phase 4: outcome"; Disable added            |
| Phase 5: side conditions and field        | Done (2026-10-28), committed | See "Phase 5: findings and decisions" and "Phase 5: outcome"; frontend shows the field |
| Phase 6: switching moves                  | Done (2026-10-28), not committed | See "Phase 6: findings and decisions" and "Phase 6: outcome"; new Baton Pass phase |
| Phase 7: healing, items, misc             | **Next**                     |                                                                                        |
| Phase 8: move-calling                     | Not started                  |                                                                                        |

**Where to start next session:** Phase 7 (see Phase 7 below), after you've reviewed and committed Phase 6.

**Open issues carried forward:**

- (Fixed in Phase 3) `expert_vol_status` no longer raises: volatiles without an Expert check score 0, so Lucas 1, Dawn 1, Barry 2 (Taunt), the Foresight, Protect and Ingrain trainers all run.
- (Fixed in Phase 4) Taunt, Encore, partial trapping and Uproar work in battle. Nightmare is still a no-op.

## Step 0: Save this plan in the project

After approval, the first action is to write this plan verbatim to `MOVES_PLAN.md` at the project root, so you can come back to it in later sessions. That's the only change in that step.

## Context

About 190 moves in `TODO.txt` (lines 121-313) are unchecked. Stealth Rock is now listed only there, since you removed its duplicate from the second section. Most of them share a handful of missing engine mechanisms: volatiles, side conditions, recoil, variable damage, switching moves and move-calling moves. So the work is grouped by **mechanism**, not alphabetically. Each phase builds the shared infrastructure once and then finishes every move that depends on it.

Ordering rules from your answers and notation:

- Moves without `*` are used by trainers up to Roark, so they come first in every phase. Moves with `*` are on your own Pokemon and come right after.
- The number of `!` marks how careful to be:
  - `!` means checking the Showdown event handler and pret/pokeplatinum before coding.
  - `!!` or more means also writing an explicit mechanics write-up for you before coding.
- `(B)` and `(E)` mean adding the trainer-AI branch in `basic_flag` / `expert_flag` (`Models/trainer_ai_helper.py`), following pret/pokeplatinum and the Pokemow AI page.
- The second section ("Moves that isn't used until 1st gym") is deferred.

## Workflow for every phase

1. Before coding, give you a short mechanics note for each move in the phase, with refs (Bulbapedia, Showdown `data/moves.ts` + `sim/`, pokeplatinum). For `!!`+ moves, wait for your OK on that note.
2. For each existing bug the phase depends on: show the evidence, wait for your OK, then fix it in the same phase.
3. Implement the engine side, then the AI B/E branches.
4. Tests:
   - Unit tests in the matching file (`test_engine_helper.py`, `test_damage_calc.py`, `test_status_calc.py`, `test_battle.py`, `test_trainer_ai.py`).
   - Drop moves from `UNSUPPORTED_MOVES` in `test_database.py` as they start converting.
   - Move the strict xfails in `test_known_bugs.py` that start to XPASS.
5. Run `pytest` and `pytest -m jit`. Re-bless golden snapshots (`--update-golden`) only when the change is intended, and show you the diff.
6. Report which TODO boxes could be checked. I don't tick them unless you ask.

## Phase 0: Layout infrastructure (validate with you before coding)

- `VolStatus` in `Models/helper.py`: add bits to the existing bitmask, as you chose: PROTECT, ENDURE, FORESIGHT, TAUNT, ENCORE, PARTIALLY_TRAPPED, AQUA_RING, INGRAIN, YAWN, DESTINY_BOND, CHARGE, NIGHTMARE, MUD_SPORT, WATER_SPORT, RAGE, UPROAR, HELPING_HAND, FOLLOW_ME. That's about 27 bits, which stays under the int32 sign bit.
- New `Pok` counters in `Models/idx_const.py` (sizes stay derived):
  - PROTECT_COUNT
  - TRAP_TURNS, TAUNT_TURNS, ENCORE_TURNS, YAWN_TURNS, PERISH_TURNS, UPROAR_TURNS
  - CONSEC_COUNT, shared by Rollout, Ice Ball and Fury Cutter
  - LAST_MOVE_ID, needed per Pokemon by Encore and Mirror Move
  - CONSUMED_ITEM, for Recycle
- `Field` additions:
  - A per-side side-condition bitmask plus durations. Reflect, Light Screen, Mist, Safeguard and Lucky Chant each last 5 turns. The existing unused MY/OPP_SCREEN slots either get reused or have new slots added next to them; I'll ask you which.
  - Toxic Spikes layers.
  - Weather duration countdown on the existing `WEATHER_DURATION`.
  - A global LAST_MOVE slot for Copycat.
- Add `SideCondition` to `generate_constants.py`, and add the new members to `VolStatus` and `SideCondition` so that `Models/move.py:91-106` stops raising for the UNSUPPORTED_MOVES. Then regenerate constants.
- Expected side effect: the golden snapshots and NN feature sizes change (both are derived). Re-bless once and review the diff.

### Phase 0: as built (2026-10-26)

- Decisions from you: rename the unused screen slots; fix the `STIKCY_WEBS` typo (now `STICKY_WEBS`).
- `VolStatus`: the 18 bits above were added, 512 up to 2^26 (FOLLOW_ME). Odor Sleuth reuses FORESIGHT, as MoveDB already does.
- `SideCondition` already existed (Stealth Rock, Spikes, Toxic Spikes, Sticky Webs, Reflect, Light Screen, Aurora Veil). Added MIST, SAFEGUARD, LUCKY_CHANT and exported it in `generate_constants.py` and the `test_layout.py` class list.
- `Pok` counters added after WEIGHT, before AB_ID: PROTECT_COUNT, TRAP_TURNS, TAUNT_TURNS, ENCORE_TURNS, YAWN_TURNS, PERISH_TURNS, UPROAR_TURNS, CONSEC_COUNT, LAST_MOVE_ID, CONSUMED_ITEM. All start at 0 in `Pokemon.to_np` (0 means "none" for LAST_MOVE_ID and CONSUMED_ITEM, since ids are non-zero). `reset_switch_out` is unchanged; each phase clears its own counters.
- `Field`: MY_SCREEN became MY_SIDE_COND and MY_SCREEN_DURATION became MY_REFLECT_TURNS (same for OPP). Added per side: LIGHT_SCREEN_TURNS, MIST_TURNS, SAFEGUARD_TURNS, LUCKY_CHANT_TURNS, TOXIC_SPIKES (layers). Added global LAST_MOVE. All inserted before PHASE, so AI_KNOWS stays last and `FIELD_LEN` stays derived. WEATHER_DURATION already existed; its countdown is Phase 5.
- Correction to the expectation above: NN feature sizes did NOT change. `_VOL_BITS` in `NeuralNetwork/models.py` is a literal 9-bit tuple and the NN doesn't read the field block length. Whether the new volatiles/side conditions become features is your call when the network gets built.
- Golden snapshots: re-blessed. All 100 changes were the raw-array hash only; turns and HP were identical for every seed.
- `UNSUPPORTED_MOVES` shrank to just Low Kick (its power is the string `'weight'`, Phase 2). The trainer-team xfails that depended on the removed moves now pass.
- Checks: `pytest` 1237 passed / 5 xfailed, `pytest -m jit` 6 passed, `pytest -m slow` 5 passed. MCTS benchmark (200k iterations, same seed) about 16.0 s before and after, so no hot-path regression. `dev.bat` smoke run not done (backend is covered by the backend tests).

## Phase 1: Moves that are mostly data-driven (verify, fix shared bugs, then tick)

Trainer-used moves first:

- Growl, Leer, Tail Whip, Tackle, Scratch, Pound, Quick Attack, Peck, Headbutt, Slam, Vine Whip, Gust, Mega Drain, Metal Claw, Mud-Slap, Sand Attack, Scary Face, String Shot, Supersonic, Harden, Withdraw, Howl, Rock Throw, Rock Polish, Spark, Thunder Punch, Thunder Wave, Water Pulse, Wing Attack, Zen Headbutt, Hypnosis, Sing, Grass Whistle, Poison Sting, Fury Swipes, Force Palm
- (E): Karate Chop, Razor Leaf, Rock Tomb, Mud Shot, Shock Wave (TODO.txt spells it "Schock Wave")

Then the starred moves:

- Agility, Aurora Beam, Barrier, Bubble Beam, Comet Punch, Double Kick, Double Slap, Double Team, Dragon Breath, Draining Kiss, Extrasensory, Extreme Speed, Fake Tears, Fire Fang, Flame Wheel, Flash, Fury Attack, Horn Attack, Hyper Fang, Iron Defense, Iron Head, Kinesis, Lick, Mach Punch, Meditate, Mud Bomb, Nasty Plot, Pin Missile, Poison Fang, Poison Powder, Powder Snow, Psybeam, Rock Blast, Rock Slide, Screech, Silver Wind, Sleep Powder, Smog, Smokescreen, Stun Spore, Sweet Kiss, Sweet Scent, Thunder Shock, Twineedle, Vice Grip, Water Gun, Will-O-Wisp
- (E): Aerial Ace, Air Cutter, Feint Attack, Icy Wind, Magical Leaf, Swift
- (B): Bulk Up, Tickle, Focus Energy (AI side only; this also fixes the `test_ai_with_focus_energy` xfail via `expert_vol_status`)

Shared bugs to fix here (evidence goes to you first):

- `Sec.TARGET` is never read (`Engine/status_calc.py` `sec_effects` → `stat_changes` uses `_MOVE_TARGET`). Affects Metal Claw and Silver Wind.
- `CHANCE2` / `VOL_STATUS2` are ignored. Affects Fire Fang's flinch.
- Twineedle's secondary is rolled once instead of per hit.
- Type immunity blocks every Status move in `calculate_hit_miss` (`Engine/engine_helper.py:~253`). Showdown sets `ignoreImmunity` for Status moves by default; Thunder Wave is the exception. Affects Growl vs Ghost and similar.
- `apply_status` ignores type and ability status immunities. Affects Poison Powder vs Steel/Poison, Will-O-Wisp vs Fire, Thunder Wave vs Ground, and Static/Limber-style abilities as far as they're in scope.
- Gust's double damage vs Fly/Bounce needs semi-invulnerability, which arrives with Bounce in Phase 2. Gust gets ticked after that.

AI (E) groups to add in `expert_flag`, from its docstring TODO list: high-crit (Air Cutter, Karate Chop, Razor Leaf) and speed-lowering attacks (Icy Wind, Mud Shot, Rock Tomb). Check that the never-miss branch already covers Aerial Ace, Feint Attack, Magical Leaf, Swift and Shock Wave.

### Phase 1: findings (2026-10-26)

Sources used: RP MOVES sheet (CSV export), Showdown master `sim/battle-actions.ts`, `sim/pokemon.ts`, `data/moves.ts`, `data/typechart.ts`, `data/mods/gen4|gen5/*`, pret/pokeplatinum `src/battle/trainer_ai/script.s`, Pokemow `getBasicAI.js` / `getExpertAI.js` / `*CheckText.js`.

**Added to Phase 1:** Growth and Stomp are unchecked in TODO.txt but weren't in any phase. Stomp's Minimize doubling waits until Minimize exists.

**Data check:** all 99 Phase 1 entries match the RP sheet on type, category, power, accuracy and PP. Exceptions: Growth's effect (B6) and the Sweet Kiss type question (Q1). Draining Kiss is listed as "Draining Kiss (!!!)" in the sheet: Fairy, 75 power, 50% recovery, matching MoveDB.

**Mechanics notes by mechanism:**

- Plain damage: Tackle, Scratch, Pound, Peck, Slam, Vine Whip, Rock Throw, Wing Attack, Horn Attack, Vice Grip, Water Gun, Gust. Gust's Fly/Bounce doubling waits for Phase 2.
- Priority: Quick Attack and Mach Punch +1, Extreme Speed +2 (USUM value, per the RP convention).
- Multi-hit: Fury Swipes, Fury Attack, Comet Punch, Double Slap, Pin Missile, Rock Blast (2-5); Double Kick, Twineedle (2). Showdown rolls secondaries on every hit (B3).
- Drain 50%: Mega Drain, Draining Kiss.
- Target stat drops (status): Growl, Leer, Tail Whip, Sand Attack, Scary Face, String Shot, Fake Tears, Flash, Kinesis, Screech, Smokescreen, Sweet Scent, Tickle. Status moves ignore the type chart (Showdown `hitStepTypeImmunity`: `ignoreImmunity` defaults to true for Status), so Growl hits Ghosts and Sand Attack hits Flying types (B4).
- Self boosts: Harden, Withdraw, Howl (self-only in Gen IV; MoveDB's `allies` target is in the self-side tuple, so it works), Rock Polish, Agility, Barrier, Iron Defense, Double Team, Meditate, Nasty Plot, Bulk Up, Growth (B6).
- Secondary stat changes: Metal Claw and Silver Wind boost the USER (B1). Mud-Slap, Mud Bomb, Aurora Beam, Bubble Beam, Rock Tomb, Mud Shot, Icy Wind lower the target.
- Secondary status: Spark, Thunder Punch, Force Palm, Thunder Shock, Dragon Breath, Lick (paralysis; Electric types CAN be paralyzed in Gen IV, the immunity is Gen VI+, B7), Poison Sting, Smog, Poison Fang (50% toxic, USUM chance), Twineedle, Flame Wheel, Fire Fang (10% burn and a separate 10% flinch, B2), Powder Snow.
- Flinch: Headbutt, Zen Headbutt, Stomp, Iron Head, Hyper Fang, Extrasensory, Rock Slide, Fire Fang.
- Confusion: Supersonic, Sweet Kiss, Water Pulse, Psybeam.
- Status moves: Thunder Wave (respects Ground immunity: Showdown sets `ignoreImmunity: false`), Hypnosis, Sing, Grass Whistle, Sleep Powder, Poison Powder, Stun Spore, Will-O-Wisp. Grass types are not immune to powder moves in Gen IV. Status immunity by type: Fire can't be burned, Ice can't be frozen, Poison/Steel can't be poisoned (B5).
- High crit (crit ratio 2 = +1 stage): Karate Chop, Razor Leaf, Air Cutter.
- Never miss: Aerial Ace, Feint Attack, Magical Leaf, Swift, Shock Wave.
- Sound moves (Soundproof already handled): Growl, Supersonic, Sing, Grass Whistle, Screech, Howl.

**Bugs, waiting for your OK:**

- B1: `sec_effects` calls `stat_changes(sec=True)`, which picks the target from the move's primary target, so Metal Claw and Silver Wind boost the defender. Fix: use `Sec.TARGET`; self-boosts still apply when the target faints (Showdown `secondaries()` doesn't skip fainted targets).
- B2: `Sec.CHANCE2` / `Sec.VOL_STATUS2` are never read, so Fire Fang never flinches. Fix: separate 10% flinch roll.
- B3: the multihit loop calls `sec_effects` once after all hits, so Twineedle rolls poison once. Fix: roll per hit (Showdown runs secondaries inside the hit loop).
- B4: `calculate_hit_miss` returns INVULNERABLE for every move whose type the target is immune to, including status moves. Fix: the converter stores the effective `ignoreImmunity` (default true for Status, explicit value otherwise) and the engine skips the type check when it's set. MoveDB has `"ignore_immunity": true` on Thunder Wave, but Showdown has `false`; fix the entry.
- B5: `apply_status` has no type status immunities (Will-O-Wisp/Ember burn Fire types, Powder Snow freezes Ice types, Poison Powder/Poison Sting/Smog poison Poison types).
- B6: MoveDB Growth is +1 Atk / +1 SpA (Gen V+). RP sheet and Showdown gen4 mod: +1 SpA only.
- B7: `synchronize_reflect` refuses to paralyze Electric types. That immunity is Gen VI+ (Showdown gen5 typechart drops `par` from Electric). Synchronize is checked in TODO.txt.
- B8: `_expert_stat_opp` SpDef branch (Fake Tears) reads the AI's own SpDef stage; pokeplatinum `Expert_StatusSpDefenseDown` reads the target's.
- B9: `_expert_stat_opp` accuracy branch: the final "+0" check reads the AI's accuracy, pokeplatinum reads the target's (`IfStatStageEqualTo AI_BATTLER_DEFENDER`; its comment says attacker, the code says defender, Pokemow agrees with the code). Also `hp_pct_ai >= 70` should be `> 70`. The "-2 or lower" line correctly reads the AI's own accuracy. This refines the "SpDef and Acc branches" item in the noticed list below.
- B10: Tickle (Atk -1, Def -1) falls into the Atk-drop branch of `_expert_stat_opp`; pokeplatinum routes BATTLE_EFFECT_ATK_DEF_DOWN to `Expert_StatusDefenseDown`. Bulk Up's routing to the Def-up branch is correct (pokeplatinum and Pokemow agree).

**Questions:**

- Q1: Sweet Kiss type. The RP sheet's general notes say Charm, Moonlight and Sweet Kiss became Fairy, but its move table lists Sweet Kiss as NORMAL (MoveDB: Normal; Charm is Fairy in MoveDB).
- Q2: Ability status immunities (Limber, Immunity, Water Veil, Insomnia, Vital Spirit, Magma Armor) are unchecked abilities in TODO.txt. Add them to `apply_status` with B5, or leave them for the abilities pass?

**Done in this phase so far (AI side):**

- Expert high-crit branch (crit ratio > 1, not a charge move): resisted 0, super effective 128/256 of +1, otherwise 64/256 of +1.
- Expert speed-down-on-hit branch for exactly Icy Wind, Rock Tomb, Mud Shot (pokeplatinum checks these move IDs): resisted 0, AI faster -3, otherwise 186/256 of +2. Bulldoze isn't in the list, matching the real AI.
- Never-miss branch already covers Aerial Ace, Feint Attack, Magical Leaf, Swift, Shock Wave (tested).
- Basic Bulk Up and Tickle branches in `basic_moves` (they have -8 cases the generic stat check can't express), Basic Focus Energy (-10 if the AI already has it), Expert Focus Energy scores 0. `test_ai_with_focus_energy` moved from `test_known_bugs.py` to `test_trainer_ai.py`.
- Golden re-blessed: `weather_charge` changed on 16/20 seeds (opponent Onix has Rock Tomb, the new branch consumes AI rolls), `status` on 1/20 with the same outcome (opponent Machop has Karate Chop). Other scenarios unchanged.

### Phase 1: outcome (2026-10-27)

- Your answers: Q1 Sweet Kiss stays Normal. Q2 ability status immunities wait for the abilities pass. B7 follows Gen IV (the RP sheet only takes USUM values for moves, the engine is Gen IV), so Synchronize can paralyze Electric types.
- Fixed B1-B10. `test_synchronize_respects_type_immunities` changed: Pikachu now gets paralyzed.
- `Move.IGNORE_IMMUNITY` is now read. The converter sets it to 1 for Status moves unless MoveDB says otherwise. Future Sight keeps MoveDB's `true` (same as Showdown), so its unimplemented immediate hit now also skips the Dark immunity check; it's in the deferred section. The outdated TODO comment above that check in `calculate_hit_miss` was removed at your request, along with the done entries in the trainer AI TODO lists (Focus Energy, Tickle, Bulk Up, Moves Ignoring Accuracy, High Critical Hit Rate, Speed-Lowering Attacks).
- New tests: secondary target and self-boost on KO, Mud-Slap target, type status immunities (status moves and secondaries), status moves vs type immunity, Thunder Wave vs Ground, second flinch slot, Twineedle per-hit rolls, IGNORE_IMMUNITY flag, Gen IV Growth, Fake Tears / accuracy-drop / Tickle Expert routing.
- Golden re-blessed. Outcome changes: damage_sources 1/20, multihit_items 8/20, status 6/20, weather_charge 13/20, starters 0/20. Every other seed changed only its hash, because status moves now carry IGNORE_IMMUNITY = 1 in the array.
- Checks: `pytest` 1322 passed / 4 xfailed, `pytest -m jit` 6 passed, `pytest -m slow` 5 passed.
- TODO boxes ticked (97): every Phase 1 move above, including Growth and Focus Energy (B). Left open: Gust (waits for Bounce's semi-invulnerability in Phase 2) and Stomp (its `!` note is the Minimize doubling, which needs Minimize).
- Deferred to the abilities pass: Limber, Immunity, Water Veil, Insomnia, Vital Spirit, Magma Armor in `apply_status`; Flash Fire / Volt Absorb / Motor Drive / Levitate interactions with status moves (all unchecked abilities).

**Noted for later (not Phase 1):** pokeplatinum's Expert dispatch swaps EVA_DOWN_2 to the accuracy-down logic and ACC_DOWN_2 to the evasion-down logic. No Phase 1 move uses a -2 accuracy/evasion drop.

## Phase 2: Damage mechanics

- Recoil: Take Down (E). Also verify Struggle (!) and Reckless against it. Rock Head is an ability; I'll ask before touching it.
- Level-based damage: Seismic Toss, Night Shade. This makes the `test_known_bugs.py` xfail pass, so it moves to its real test file.
- Variable power, computed in the damage calc following the Flail pattern in `Engine/damage_calc.py`:
  - Low Kick (!, weight)
  - Magnitude (B, !)
  - Psywave (!)
  - Assurance (E, !): needs a "target was hit this turn" flag
  - Fury Cutter (!) and Rollout (!!) / Ice Ball (!), using CONSEC_COUNT, the lock, and the Defense Curl doubling
  - Natural Gift (B, !): uses the item's `NATURAL_GIFT_*` fields
- Hidden Power (!!): type and power are computed from IVs when the move array is built (IVs exist in `Models/pokemon.py`), then written into the move's TYPE/POWER slots. Trainer IVs come from `TrainerDB.json`.
- Mirror Coat (E, !): the MoveDB entry has no `damage` field. The engine path through `RECORD_DAMAGE` / `record_sp` is already there.
- Bounce (E, !): charge turn plus semi-invulnerability (`MoveOutcome.SEMI_INVULNERABLE`), with Gust and Twister as the exceptions.

### Phase 2: findings and decisions (2026-10-27)

Sources: pokeplatinum `src/battle/battle_script.c`, `battle_lib.c`, `battle_controller_player.c`, `trainer_ai/trainer_ai.c`, `trainer_ai/script.s`, `res/battle/scripts/effects|subscripts`, `res/moves/*/data.json`, `res/items/data/*.json`; Showdown `data/moves.ts`, gen3/4/5 mods, gen4 `scripts.ts`. The RP sheet now needs a login (401), so RP values weren't rechecked.

**Mechanics (Gen IV code, MoveDB numbers):**

- Take Down: recoil = dealt // 4, where dealt is HP actually lost (capped at the target's HP). Minimum 1 (your call; pokeplatinum has no minimum, Showdown gen4 has 1). Rock Head / Magic Guard wait for the abilities pass.
- Struggle: typeless, never misses, recoil max HP // 4 through Magic Guard and Rock Head, no Reckless. Already correct.
- Seismic Toss / Night Shade: damage = level, type immunity still applies.
- Psywave: max(1, level \* (rand(0..10) + 5) // 10) (effect script 0088). Type immunity applies.
- Low Kick: target weight in hectograms, inclusive Gen IV table (<=100: 20, <=250: 40, <=500: 60, <=1000: 80, <=2000: 100, else 120). `Pok.WEIGHT` becomes hectograms.
- Magnitude: roll 0-99: <5: 10, <15: 30, <35: 50, <65: 70, <85: 90, <95: 110, else 150.
- Assurance: double power if the target lost HP earlier this turn (`subscript_update_hp.s` sets the mask on any HP loss).
- Fury Cutter: count + 1 per use (max 5), power = base \* 2^(count - 1), no 160 cap (your call: 40 base, so up to 640). Resets on a miss/fail, a blocked turn, a different move, a switch.
- Rollout / Ice Ball: 5 locked uses, 30 \* 2^(n - 1), doubled by Defense Curl. PP only on the first use. Lock and count end after the 5th use, on a miss/fail/immunity, on full paralysis, flinch, confusion self-hit, sleep, or a switch. Freeze does not unlock (`subscript_frozen.s` has no UnlockMoveChoice).
- Natural Gift: power/type from the berry, fails without one. The effect script runs before the accuracy check, so the berry is used up even on a miss. Berry powers changed to Gen IV in ItemDB (all 22 current berries are 60 in pokeplatinum, types already match).
- Hidden Power: Gen IV formula for both type and power (30-70), computed from IVs when the move array is built. Trainer IVs are uniform, so even IVs give Fighting, odd IVs give Dark.
- Mirror Coat: engine path already there; MoveDB entry gets `"damage": "magic_coat"`.
- Bounce: turn 1 charges and sets the new SEMI_INVULNERABLE volatile. While it's set every move aimed at the user misses except Gust (Twister, Thunder, Sky Uppercut aren't in MoveDB), moves aimed at a side, and OHKO moves. Gust deals double damage to it. Blocked on turn 2 = lands and loses the move. MoveDB entry gets `"charge": 1`.

**Bugs fixed with your OK:** S1 `struggle()` ignored Huge Power / Guts / Hustle and halved burn damage under Guts (pokeplatinum and Showdown both run Struggle through the normal formula). S2 Struggle recoil was applied before the target took damage. R1 Reckless used 4915/4096 instead of Gen IV's power \* 12 // 10 (Take Down 90: 107 instead of 108).

**Your decisions:** D1 new VolStatus bits SEMI_INVULNERABLE and HURT_THIS_TURN. D2 blocked turns end non-Bide charge moves and locks; Bide keeps its pause rule. D3 the search's forced-turn loop also forces while LOCKED_MOVE != -1. D4 weight in hectograms. D5 Basic non-standard damage check for every implemented move on the pokeplatinum list. D6 fill in "AI knows Mirror Coat" in the Expert Counter branch.

**AI (pokeplatinum):** Basic Natural Gift (-10 without an eligible berry or vs immunity), Basic Magnitude (-10 vs Levitate unless Mold Breaker). Expert Recoil (+1 with Rock Head / Magic Guard unless resisted), Assurance, Mirror Coat (mirror of Counter), Charge turn with invulnerability (Bounce). AI damage: Seismic Toss / Night Shade = level, Psywave rolls its own value, Low Kick weight table, Hidden Power / Natural Gift real type and power, Magnitude 0 (its effect isn't in `sAltPowerMoveEffects`, a pokeplatinum quirk), Fury Cutter / Rollout / Assurance base power only.

### Phase 2: outcome (2026-10-27)

- Engine: `variable_power` in `damage_calc.py` (Flail, Low Kick, Magnitude, Fury Cutter, Rollout/Ice Ball, Assurance, Gust); level and Psywave damage sources; recoil after the hit (`_recoil`, `apply_recoil`); `unlock_move` on miss, full paralysis, flinch, confusion self-hit, sleep; Rollout lock and counters in `_execute_move_slot`; Bounce sets/clears SEMI_INVULNERABLE and `calculate_hit_miss` returns `MoveOutcome.SEMI_INVULNERABLE`; Natural Gift writes the berry's type/power into the move slot and sets CONSUMED_ITEM; HURT_THIS_TURN set on any HP loss in the action phase, cleared in `start_of_turn`; `reset_switch_out` clears CONSEC_COUNT.
- Data: MoveDB Mirror Coat `"damage": "magic_coat"`, Bounce `"charge": 1`, Psywave `"damage": "psywave"`; ItemDB berries 60; converter maps non-integer power to 0; `UNSUPPORTED_MOVES` is now empty.
- Search: forced-turn loop (`step_arr`) and `battle_driver.forced_action` also follow LOCKED_MOVE.
- AI: Basic Natural Gift and non-standard-damage checks; Expert Recoil, Assurance, Mirror Coat, Bounce; Counter's Mirror Coat step; AI damage for level/Psywave/Magnitude; `ai_move_view` for Natural Gift / Low Kick.
- Golden re-blessed: every hash changed (weight in hectograms). Outcomes changed only in weather_charge 5/20, all from Fury Cutter doubling (confirmed by replaying with flat Fury Cutter power: 20/20 match the old snapshot). Mirror Coat in damage_sources never executed in the 20 seeds (Abra always fainted before its -5 priority move).
- Checks: `pytest` 1441 passed, `pytest -m jit` 6 passed, `pytest -m slow` 5 passed.
- Follow-up fixes (your OK; Pokemow is the AI reference when it differs from pokeplatinum): Basic ability checks now score -12 for Volt Absorb/Motor Drive/Water Absorb/Flash Fire/Levitate and for Wonder Guard when the move is NOT 2x/4x (was inverted), Soundproof stays -10; the separate non-standard-damage helper was dropped since these generic checks now cover it. Drain heals from HP actually lost. Iron Fist uses Gen IV 12/10 rounding. AI flat damage is 0 vs immunity. `node_key` now hashes every VOL_STATUS bit (third key element); HURT_THIS_TURN is cleared at the end of `turn_sim` so it never splits nodes. Golden re-blessed: outcomes changed in multihit_items 1/20 and status 2/20, all from the drain fix (replaying with raw-damage drain matches the old snapshot). Checks: `pytest` 1450 passed, `-m jit` 6, `-m slow` 5.
- TODO boxes that can be ticked (not ticked): Assurance, Bounce, Fury Cutter, Gust, Hidden Power, Ice Ball, Low Kick, Magnitude, Mirror Coat, Natural Gift, Night Shade, Psywave, Rollout, Seismic Toss, Struggle, Take Down. Rock Head stays open (abilities pass). Ticked on 2026-10-27; the done `# TODO: recoil` comments and the outdated charge NOTE in `early_returns` were removed/updated at your request.

## Phase 3: Volatiles without action restrictions

- Trainer-used:
  - Foresight (B/E, !): Ghost hit by Normal/Fighting, evasion ignored. It feeds into the AI effectiveness TODO at `trainer_ai_helper.py:204`.
  - Protect (E, !): consecutive-use chance from PROTECT_COUNT, checked against `Flags.PROTECT`.
  - Mud Sport and Water Sport (B/E, !)
  - Ingrain (B, !)
- Starred:
  - Endure (E, !)
  - Feint (E, !): breaks Protect
  - Attract (B, !)
  - Leech Seed (B/E, !)
  - Aqua Ring (B/E, !)
  - Charge (!)
  - Destiny Bond (E, !)
  - Yawn (!)
  - Odor Sleuth (B/E, !)
  - Rage (!)
  - Helping Hand (B, !) and Follow Me (!): these fail or do nothing in singles; I'll confirm with you.
- End-of-turn hooks go into `_apply_residual` (`Engine/battle.py`), in the Gen IV residual order: Aqua Ring, Ingrain, Leech Seed, Yawn.
- `reset_switch_out` must clear each of these, except Ingrain's trap, which only matters while the Pokemon is on the field.
- AI: replace `expert_vol_status`'s `raise ValueError("Need implementation")` with per-volatile branches. Until a move gets its real branch, it gets a safe "0, no crash" fallback so that moves on your own Pokemon don't crash anything.

### Phase 3: findings and decisions (2026-10-27)

Sources: pokeplatinum `battle_script.c` (TryProtection, TryYawn, TryHelpingHand, FollowMe), `battle_controller_player.c` (CheckMonConditions order, CheckMoveHitOverrides, CheckStatusDisruption, RageBuilding, the Rage flag pre-move state), `battle_lib.c` (ApplyTypeChart, BasicTypeMulApplies, CalcMoveDamage), effect scripts and subscripts, `res/moves/*/data.json`, `trainer_ai/script.s` and `trainer_ai.c`; Showdown `data/moves.ts`, gen4-gen8 mods, gen4 `conditions.ts`; RP MOVES sheet (the CSV export works again); Pokemow `ExpertCheckText.js` / `BasicCheckText.js` / `getBasicAI.js` / `getExpertAI.js`; Bulbapedia Rage glitch page.

**Data:** all 17 moves match the RP sheet. Priorities are USUM (Protect/Endure +4, Feint/Follow Me +2, Helping Hand +5). Feint is 30 in RP with the Gen IV fail rule. MoveDB Mud Sport / Water Sport got `vol_status`.

**Mechanics as built:**

- Protect / Endure: share PROTECT_COUNT, chance 1, 1/2, 1/4, then 1/8. Fail when nothing acts after the user (also when the foe switches or uses an item). The count resets on another move, a blocked turn, or a failure. Protect blocks moves with the `protect` flag (`MoveOutcome.PROTECTED`, new). Endure caps a KO hit at 1 HP (`endure_damage`, before drain/recoil/Counter see the damage). Both bits clear at the end of the turn.
- Feint: fails unless the target is protecting, then lifts the protection and hits.
- Foresight / Odor Sleuth: `matchup_types` drops the Ghost type against Normal/Fighting in the hit check, the damage calc and the AI effectiveness; positive evasion counts as 0.
- Mud Sport / Water Sport: user volatile, halves Electric / Fire base power while either active has it (`sport_power`, also in the AI damage calc).
- Ingrain: heal max HP // 16 (min 1), no switching for either side (`valid_action_mask`, `battle_driver.legal_actions`, every withdraw check in `choose_move`), grounds Flying types for Ground moves (`matchup_types`).
- Aqua Ring: heal max HP // 16 (min 1).
- Leech Seed: fails vs Grass / already seeded. Drains max HP // 8 (min 1) into the opposing active, not if it's fainted, not through Magic Guard.
- Attract: male + female only, 50% immobilized after confusion, ends when the source leaves (`switch_in` clears the foe's bit, plus the end-of-turn replacement and the death-phase replacement of mine).
- Charge: doubles the next Electric move's base power (`charge_power`, also in the AI damage calc), cleared after every move attempt that isn't Charge (`_clear_charge` in `action`).
- Destiny Bond: cleared at the top of `early_returns`; if the holder faints from a move, the attacker faints after drain/recoil.
- Yawn: fails on a statused / drowsy target; YAWN_TURNS 2, last residual step; at 0 sleep 2-5 turns if still no status.
- Rage: set when Rage hits; +1 Atk per damaging hit survived. Your decision Q1: the Gen IV glitch is copied (`_rage_glitch` in `turn_sim`): a raging Pokemon that picks anything but Rage keeps Rage and loses Flinch, Confusion, Uproar, partial trap, Attract, Focus Energy, Destiny Bond, Nightmare, Curse, Foresight, Defense Curl. Bide is left out of the wipe so its CHARGE_RECHARGE lock stays consistent.
- Helping Hand / Follow Me: no effect in singles.
- Residual order (Gen IV): weather for both actives, then per Pokemon Ingrain, Aqua Ring, Speed Boost, Leech Seed, poison/burn, Curse, Yawn. Both steps go in speed order (follow-up below).
- Your decision Q2: the AI learns my moves. `_execute_move_slot` sets my slot's `ENEMY_AI_KNOWS_MOVEn` bit when the move gets past `early_returns`; it's already cleared on my switch.

**AI:** Basic Leech Seed, Foresight/Odor Sleuth, Ingrain, Aqua Ring, Mud/Water Sport, Yawn (status, Insomnia, Vital Spirit), Helping Hand; E1 fixed (a genderless AI can't Attract). Expert Protect, Endure, Foresight (own-Ghost quirk), Destiny Bond, Leech Seed (Pokemow's Toxic check), Mud/Water Sport, Aqua Ring, Feint; everything else scores 0. Feint follows Pokemow where it differs from pokeplatinum: the "HP not full or Leftovers/Black Sludge" condition is an or, and a target Protect chain of 2 already scores -2.

### Phase 3: outcome (2026-10-27)

- Tests: volatile targets and fail rules (`test_status_calc`), Protect chance/count, Protect flag, Foresight, Ingrain grounding, Endure, Destiny Bond clear, Attract roll, switch resets (`test_engine_helper`), Charge/Sports/matchup types (`test_damage_calc`), turn flow for every move plus residuals, Rage glitch and AI_KNOWS bits (`test_battle`), Ingrain valid actions (`test_search`), Basic/Expert scores, the 0 fallback, every Phase 3 move in an AI kit, an Ingrained AI never switching (`test_trainer_ai`).
- Golden re-blessed: every hash changed and no outcome did (turns and HP identical for all 100 seeds). Replaying with the AI_KNOWS bits disabled matches the old file 100/100, so the only change is the new revealed-move bits. No scenario uses a Phase 3 move.
- Checks: `pytest` 1579 passed, `pytest -m jit` 6 passed, `pytest -m slow` 5 passed.
- Follow-up fixes (your OK):
  - `end_of_turn` called `switch_in(current_pokemon, current_opp)` after the AI's replacement; it's now `switch_in(new_opp, current_pokemon)`, so the replacement's Intimidate fires.
  - `switch_in_action` now runs `switch_in` for my replacement when the foe is still standing.
  - Bounce: Expert -1 once the AI saw the target use Protect (Pokemow Fly check).
  - Basic sleep moves: Insomnia scores -10 like Vital Spirit.
  - Charge: no Basic or Expert check, per Pokemow (`NO_AI_CHECK_M`).
  - Residuals: weather for both actives first, then the per-Pokemon list, both in speed order (pokeplatinum re-sorts speed before the end of the turn; a tie is a coin flip). Speed Boost moved to its Gen IV slot after Aqua Ring.
  - Golden re-blessed. Outcome changes: starters 16/20, weather_charge 6/20 and damage_sources seeds 2 and 18 from the residual order and its tie roll; damage_sources seeds 1, 4, 7, 11, 19 from the end-of-turn `switch_in` fix. With the old order and the old call patched back in, all 100 outcomes match the previous file, so the death-phase `switch_in` fix changed none.
  - Checks: `pytest` 1589 passed, `-m jit` 6, `-m slow` 5.
- TODO boxes ticked on 2026-10-27 at your request: Aqua Ring, Attract, Charge, Destiny Bond, Endure, Feint, Follow Me, Foresight, Helping Hand, Ingrain, Leech Seed, Mud Sport, Odor Sleuth, Protect, Rage, Water Sport, Yawn. Waiting on other passes: Oblivious vs Attract and Insomnia/Vital Spirit vs Yawn (abilities), Safeguard vs Yawn (Phase 5), Uproar vs Yawn (Phase 4), Roar failing on Ingrain (Phase 6), Liquid Ooze / Big Root (abilities/items).

## Phase 4: Volatiles that restrict actions (touches SearchEngine valid actions and trainer AI `return_idx`)

- Taunt (!): trainer-used
- Encore (B/E, !): needs LAST_MOVE_ID
- Partial trapping: Wrap (E, !) is trainer-used; Bind, Clamp, Fire Spin, Whirlpool are starred. Covers 2-5 turns, 1/16 residual damage, and no switching.
- Uproar (!)
- The architecture check comes first: where valid actions get filtered for my side (MCTS) and for the AI. Locked states keep looping inside `step()` and are never exposed as decision nodes.

### Phase 4: findings and decisions (2026-10-27)

Sources: pokeplatinum `battle_script.c` (TryEncore, TryDisable, Random), `battle_controller_player.c` (CheckMonConditions, CheckStatusDisruption order, FightCommand, UpdateMoveBuffers), `battle_lib.c` (CheckInvalidMoves, Battler_IsTrapped, Battler_CanPickCommand, MoveFailed, faint cleanup), effect scripts and subscripts (bind, encore, taunt, uproar, fall asleep), `trainer_ai.c` and `trainer_ai/script.s`; Showdown gen4 `moves.ts` / `conditions.ts`; Pokemow; RP MOVES sheet (all match MoveDB; Disable 100% from RP, Showdown gen4 has 80).

**Your decisions:** B1 (Attract checked before paralysis, pokeplatinum has it after) stays as Showdown has it. Encore packs its slot into `ENCORE_TURNS` (turns \* 4 + slot). Disable added to the phase, with a new `Pok.DISABLE_TURNS` packed the same way and a new `VolStatus.DISABLE` bit. The two `#TODO: User is taunted` lines in Counter / Mirror Coat were replaced by the check.

**Mechanics as built:**

- Last move (`Pok.LAST_MOVE_ID`): set once the move gets past `early_returns` (a miss still counts), 0 after a blocked turn, reset on switch.
- Taunt: fails on a taunted target, 3-5 turns counted down at every residual including the one it landed. Status-category moves can't be selected and fail if picked before Taunt landed (after flinch, before confusion).
- Encore: needs a last move with PP that isn't Encore, Mirror Move or Struggle; 3-7 turns; the slower target uses the encored move the turn it lands; ends a residual after its counter reaches 0, or when the encored move is out of PP. Not a lock: switching stays open.
- Disable: needs a last move with PP; 3-6 turns, same countdown as Encore; the disabled move can't be selected and fails if picked before (after flinch, before Taunt).
- Wrap, Bind, Clamp, Fire Spin, Whirlpool: a hit target that survives and isn't bound gets 3-6 turns; at the residual (after Curse) the counter drops, then 1/16 (min 1, not with Magic Guard) while it's above 0, so 2-5 hits. No switching. Freed when the binder switches out (`switch_in`) or faints (no damage that turn).
- Uproar: locks in on its first hit for 3-6 turns, PP only once. Nobody falls asleep while an active is making an uproar (sleep moves, Yawn's sleep), except Soundproof; a sleeper wakes when it tries to move, and the Uproar residual wakes everyone. A blocked turn or an immune target ends it at that residual; a miss or Protect doesn't.
- Residual order: ...Curse, Bind, Uproar, Disable, Encore, Taunt, Yawn.
- Valid actions (`valid_action_mask`, `battle_driver.legal_actions`) and the AI (`choose_move`) skip moves blocked by Disable, Encore or Taunt through `move_blocked`, Struggle if none is left. A bound active can't switch (also every AI withdraw check).

**AI:** Basic Encore / Disable -8 on a target that already has it. Expert Encore (Pokemow list, the moves in MoveDB), Expert Disable, Expert binding moves (Wrap, Bind, Clamp, Fire Spin: Toxic, Curse, Attract; Perish Song left as a TODO), Counter / Mirror Coat +1 at 60.9% vs a taunted target. Taunt, Uproar and Whirlpool have no Expert check; Uproar's Basic Soundproof check already existed.

### Phase 4: outcome (2026-10-27)

- Layout: `Pok.DISABLE_TURNS`, `VolStatus.DISABLE`, MoveDB Disable (MoveName shifts by one after Dig). `Pokemon.to_np` lists the counters by hand, so it got the new slot too.
- Tests: Taunt/Encore/Disable fail rules and durations, Uproar sleep block (`test_status_calc`), `move_blocked`, the Disable/Taunt execution check, Uproar wake-up and early end, trap freed on switch, switch resets (`test_engine_helper`), trap damage and countdown, binder fainting, Magic Guard, Uproar lock/PP/wake/miss, Yawn vs Uproar, last move, Encore on the slower target, countdowns (`test_battle`), move filters and the bind switch block (`test_search`), every AI branch, blocked moves and a bound AI never switching (`test_trainer_ai`).
- Golden re-blessed: hashes only, 100/100 outcomes identical to the old file (new field in the layout).
- Checks: `pytest` 1657 passed, `pytest -m jit` 6 passed, `pytest -m slow` 5 passed. Benchmark (main.py battle, 100k iterations, compile excluded, best of 3): 8.16s vs 8.29s at the Phase 3 commit.
- TODO boxes that can be ticked: Taunt, Encore, Bind, Clamp, Fire Spin, Whirlpool, Wrap, Uproar, Disable. Waiting on other passes: Rapid Spin freeing a bind (Phase 5), Shed Shell, Grip Claw (not in ItemDB), Uproar vs Rest (Rest not in MoveDB).

## Phase 5: Side conditions and field

- Reflect and Light Screen (B/E, !): damage modifiers, 5 turns. Then Brick Break (E, !) and Light Clay. Light Clay is an item; I'll ask before touching it.
- Mist (B, !), Safeguard (B, !), Lucky Chant (B/E, !): this also clears the Safeguard TODO in `basic_move_status`.
- Stealth Rock (B/E, !!): a per-side hazard applied in `switch_in`. Needs your call on the faint-on-switch-in flow, i.e. replacement after a hazard KO for both sides, including the AI's `sub_after_death`.
- Toxic Spikes (B/E, !)
- Rapid Spin (!)
- Rain Dance (B/E, !) and Sandstorm (B, !): weather setting with a 5-turn countdown.

### Phase 5: findings and decisions (2026-10-28)

Sources: pokeplatinum `battle_lib.c` (BattleSystem_CalcDamage screens, crit roll and Lucky Chant, BattleAI_PostKOSwitchIn), `battle_controller_player.c` (CheckFieldConditions before CheckMonConditions, PP spent before the target-exists check), effect scripts and subscripts (break screens, hazards check, Toxic Spikes, Stealth Rock, Rapid Spin, Mist, Safeguard, Yawn), `trainer_ai.c` (TrainerAI_CalcDamage passes the defender's side conditions) and `trainer_ai/script.s`; Showdown gen4 `moves.ts`; Pokemow.

**Your decisions:**

- Faint on entry:
  - A switch-in that faints to the hazards is replaced right away.
  - My replacement during the death phase that faints keeps the phase on `DEATH_END_OF_TURN`, and the turn doesn't advance. After a double KO the AI's replacement is already in when I pick again, as in Gen IV.
  - The AI loops `sub_after_death` until one survives, capped at 6.
- A move aimed at a fainted foe has no effect. `early_returns` already covers this, so nothing new was added there (see the PP note below).
- Light Clay and Smooth Rock wait for the items pass.
- Side info reaches the hot path as an int mask (the defender's `Field.SIDE_COND`), passed like `weather`. `switch_in` takes `battle_array` and `is_mine`.
- Rapid Spin is done as a whole. It also clears the Spikes bit, though Spikes isn't in MoveDB.
- The frontend shows the field.

**Mechanics as built:**

- Per-side slots are derived in `idx_const.py` (`SIDE_REFLECT_TURNS = Field.MY_REFLECT_TURNS - Field.MY_SIDE_COND`, etc.). `side_base(is_mine)` gives either side's `SIDE_COND`.
- Reflect and Light Screen:
  - They halve physical / special damage after burn (`screen_damage`), in `multipliers`, Struggle and the AI's damage calc.
  - A crit and Brick Break ignore them.
  - Each lasts 5 turns and fails while it's up.
- Brick Break: on a hit it clears both screens of the target's side. A miss or a Ghost-type target clears nothing.
- Mist:
  - It blocks drops coming from the foe: primary moves, secondary effects (`stat_changes` with `def_side`) and Intimidate (`switch_in`).
  - The user's own drops and any raises (Swagger) go through.
  - 5 turns.
- Safeguard:
  - It blocks major status (primary and secondary), confusion, Yawn landing and Toxic Spikes.
  - It doesn't block an already-landed Yawn's sleep, Synchronize or Leech Seed.
  - 5 turns.
- Lucky Chant: no crit roll against that side, 5 turns.
- Stealth Rock:
  - Set once on the foe's side.
  - On entry it deals max HP × Rock effectiveness / 8, minimum 1, and also hits Flying types.
  - It triggers the on-damage berry check.
- Toxic Spikes:
  - Up to 2 layers. On entry, 1 layer poisons and 2 badly poison.
  - Only grounded Pokemon are affected (not Flying types, not Levitate). A grounded Poison type absorbs them.
  - Steel types, Immunity, Leaf Guard in sun, Safeguard and an existing status block it.
- Entry order: Magic Guard skips the hazards entirely. Otherwise Toxic Spikes, then Stealth Rock, then switch-in abilities if the Pokemon is still alive.
- Rapid Spin: on a hit it frees the user from a bind and Leech Seed and clears Stealth Rock, Spikes and Toxic Spikes from its side. Screens stay.
- Rain Dance and Sandstorm:
  - They fail under the same weather, otherwise they set it for 5 turns.
  - The slower mover sees weather the faster mover set that turn.
- End of turn (`_count_down_field`): the side timers (Reflect, Light Screen, Mist, Safeguard, Lucky Chant, both sides) count down first, then the weather, then the residuals.
  - A weather that runs out this turn doesn't hit this turn.
  - `WEATHER_DURATION` 0 means permanent.

**AI:**

- Basic:
  - -8 for Reflect / Light Screen / Mist / Safeguard already on the AI's side; -10 for Lucky Chant.
  - Toxic Spikes -10 at 2 layers; Stealth Rock -10 if already set. Both -10 when the target has nobody else alive.
  - Sandstorm and Rain Dance -8 under the same weather. Rain Dance also -8 against a statused Hydration target, unless the AI's Pokemon has Swift Swim or Hydration.
  - Safeguard on the target's side gives -10 to the status checks and to confusion.
- Expert:
  - Reflect / Light Screen: -2 under 50% HP; at 90% HP or more, 50% of +1; 75% of +1 if the target's last move matches (no move yet counts as Physical).
  - Rain Dance: Swift Swim and slower +1; under 40% HP -1; Hail, Sun or Sand +1; Rain Dish, or Hydration while statused, +1.
  - Brick Break +1 against a screen.
  - Lucky Chant: -1 under 70% HP; +1 after seeing a high-crit move; else 25% of +1.
  - Toxic Spikes / Stealth Rock: 50% to skip; else +1, plus 75% of +1 with Roar / Whirlwind.
  - Mist, Safeguard and Sandstorm score 0 (before, they fell into the always-hit branch).
- The AI's damage calc and `sub_after_death` see my screens.

### Phase 5: outcome (2026-10-28)

- Tests:
  - Screens, crits and the AI damage calc (`test_damage_calc`).
  - Mist and Safeguard, primary and secondary (`test_status_calc`).
  - Lucky Chant, Stealth Rock damage by type, Toxic Spikes layers / absorb / immunities, Magic Guard, faint before Intimidate, Mist vs Intimidate (`test_engine_helper`).
  - Timers, failing while up, layering, the side each move lands on, Brick Break, Rapid Spin, the weather countdown and its last turn, permanent weather, the second mover seeing the new weather, and every faint-on-entry flow (`test_battle`).
  - The death phase staying on after a hazard KO (`test_search`).
  - Every Basic / Expert branch (`test_trainer_ai`).
- Golden re-blessed:
  - `multihit_items` (16/20 seeds) and `weather_charge` (19/20) changed: Rain Dance and Sandstorm now set the weather, and the AI scores them through their own checks.
  - `starters`, `status` and `damage_sources` are identical.
- Checks: `pytest` 1751 passed, `pytest -m jit` 6 passed, `pytest -m slow` 5 passed.
- Benchmark: main.py battle, 100k iterations, compile excluded, best of 3. 19.49s against 18.88s at HEAD, run back to back. That battle has no Phase 5 moves, so the ~3% is the plumbing.
- TODO boxes that can be ticked: Brick Break, Light Screen, Lucky Chant, Mist, Rain Dance, Rapid Spin, Reflect, Safeguard, Sandstorm, Stealth Rock, Toxic Spikes. Waiting on other passes: Light Clay, Smooth Rock and Damp Rock (items), Spikes damage (Spikes isn't in MoveDB), Magnet Rise / Gravity / Iron Ball grounding, Drizzle / Sand Stream setting weather (abilities).
- Noticed, not changed:
  - `early_returns` fails a move aimed at a fainted foe before PP is spent and clears the last move. pokeplatinum spends PP first (`BEFORE_MOVE_STATE_DECREMENT_PP` before `CHECK_TARGET_EXISTS`).
  - Weather and side moves (target `all` / `foe_side`) also fail while the foe is fainted.
  - `sub_after_death` passes weather 0, but pokeplatinum passes the field conditions.
  - `node_key` doesn't include side conditions or weather.
  - The rollout heuristic in `mcts_eval` ignores screens.
  - The now-implemented `# TODO: Screen`, `# TODO: Safeguard`, the hazard TODO in `switch_in`, the weather TODO in `end_of_turn` and the matching docstring TODO entries are still in place.

## Phase 6: Switching moves (validate the architecture first)

- Roar and Whirlwind (B/E, !): fail on the first turn of a trainer battle? Check that. Random replacement, which is a chance node for MCTS.
- Baton Pass (B/E, !): passes stages and the passable volatiles. My replacement becomes a decision; the AI's follows the Gen IV AI switch logic.
- Teleport (B): fails in trainer battles.
- Pursuit (E, !): doubles power and hits before the switch.

### Phase 6: findings and decisions (2026-10-28)

Sources: pokeplatinum subscripts (`force_target_to_switch_or_flee`, `baton_pass`, `pursuit`, `switch_pokemon`, `teleport`), `battle_script.c` (BtlCmd_TryWhirlwind, BtlCmd_TryPursuit), `battle_lib.c` (BattleSystem_CanWhirlwind, BattleSystem_UpdateAfterSwitch, BattleAI_PostKOSwitchIn), `battle_display.c` (Task_TrainerShowPartyMenu), `constants/battle/condition.h` and `moves.h` (the BATON_PASSED masks), `trainer_ai/script.s`.

**Your decisions:**

- My Baton Pass replacement is a mid-turn decision (option B), not a per-target action. Profiled below.
- Roar / Whirlwind: my random replacement makes separate outcomes, so my active slot is in `node_key`.
- The AI's Baton Pass replacement is `sub_after_death`. Confirmed: every AI party prompt goes through `BattleAI_PostKOSwitchIn`.
- Pursuit on a switch is resolved in `start_of_turn`, and `action` skips the pursuer.
- `POISON_AB_IM` has Poison Heal instead of Poison Point (pokeplatinum Basic_CheckCannotPoison). Basic Yawn now checks Safeguard (Basic_CheckCannotSleep).

**Mechanics as built:**

- Layout:
  - New `Field.PENDING_OPP_MOVE` (opp move slot + 1 still to run, 0 none). `FIELD_LEN` follows it.
  - New `BattlePhase.BATON_PASS = 2`.
- Roar and Whirlwind:
  - They fail on Suction Cups (unless Mold Breaker), Ingrain, an empty bench, or a semi-invulnerable target (the hit check already did that).
  - In trainer battles too, a lower level user fails unless `(rand(256) * (atk lv + def lv) >> 8) + 1 > def lv / 4`. There's no turn 1 rule.
  - The replacement is uniform among the alive bench. Hazards and switch-in abilities apply.
  - A dragged-out Pokemon that hadn't moved loses its move.
- Baton Pass:
  - It fails with nobody to switch in.
  - It passes the stat stages, confusion with its counter, Focus Energy, Curse, Leech Seed, Ingrain, Aqua Ring, Mud Sport, Water Sport and Heal Block. Substitute, Perish Song, Mean Look, Lock-On, Embargo and Magnet Rise pass in pokeplatinum but aren't in the engine yet.
  - Mine: `_baton_pass` sets the phase, `action` stores the slower foe's move and stops, `turn_sim` returns `BATON_PASS` before the end of turn. `baton_pass_action` switches with the pass, runs the pending move (Encore re-checked) and then `_finish_turn` (the old tail of `turn_sim`).
  - The AI's: `sub_after_death` with the new `exclude` param, so it never picks the passer. My slower move hits the replacement.
- Pursuit:
  - It only triggers on a voluntary switch, not on Baton Pass, Roar or a post-KO replacement.
  - It needs the pursuer alive and not asleep or frozen. Paralysis, confusion and the other turn checks don't apply.
  - It hits at double power before the switch, spends PP, and Destiny Bond triggers on a KO. The chosen replacement still comes in.
  - There's no Pressure in the engine, so it costs 1 PP either way.
- Teleport does nothing in a trainer battle, as before. Only the AI score changed.
- Search:
  - `valid_action_mask` only offers switches outside `TURN_START`.
  - `step_arr`, `rollout_arr` and `GameState` route the Baton Pass phase like the death phase: no AI move, `baton_pass_action` instead.
  - `node_key`: my slot at bits 59-61 and the Baton Pass phase at bit 62 of `k1`.
- Frontend: a "Baton Pass: choose who receives it" banner and a "Baton Pass to:" switch label. The serializer sends `phase: "BATON_PASS"`.

**AI:**

- Basic:
  - Roar / Whirlwind -10 with no bench or against Suction Cups (unless Mold Breaker). Soundproof still -10 through the ability check.
  - Baton Pass -10 on the AI's last Pokemon. Teleport -10.
- Expert:
  - Roar / Whirlwind: target in for more than 3 turns (`TURNS_ACTIVE - 1 > 3`) queues 75% +2 and 50% +2. Otherwise hazards on its side or a +3 stage (Atk, Def, SpA, SpD, Eva) gives 50% +2, else -3.
  - Baton Pass follows the script (its comment doesn't match it). At +3: +2 at 176/256 when HP <= 60% (faster) or <= 70% (slower). At +2: -2 when HP > 60% (faster) or >= 70% (slower). No boost: -2.
  - Pursuit: 50% +1 on the AI's first turn, or against a Ghost or Psychic target. The U-turn part waits for U-turn in MoveDB.
  - Teleport scores 0 (it no longer falls into the always-hit branch).

### Phase 6: outcome (2026-10-28)

- Tests:
  - Roar and its failures and level roll, the dragged-out Pokemon losing its move, my Baton Pass faster and slower, the carry-over, Baton Pass into Stealth Rock, the AI's Baton Pass, and Pursuit both ways, without a switch and asleep (`test_battle`).
  - The Baton Pass phase's actions, `step_arr` and `GameState` through it, and `node_key` (`test_search`).
  - Every new Basic / Expert branch and `sub_after_death`'s exclude (`test_trainer_ai`).
  - New `switching` scenario in `battle_driver.py`, so the fuzz and golden tests cover these moves. Over 20 seeds: 32 Roar / Whirlwind drag-outs, 24 failures, 15 Pursuits on a switch, 7 Baton Pass picks of mine.
- Golden re-blessed:
  - The five old scenarios have the same turns and HP on every seed. Their hash changed only because the array grew by one slot (checked by hashing without it: 100/100 match).
  - `switching` is new.
- Checks: `pytest` 1831 passed, `pytest -m jit` 6 passed, `pytest -m slow` 6 passed.
- Benchmarks (compile excluded, best of 3):
  - main.py battle, 100k iterations: 19.35s against 19.19s before this phase.
  - Baton Pass profile, 30k iterations on a Ninjask Baton Pass team: 4.93s with Baton Pass against 4.89s with it swapped for Focus Energy. The tree had 796 Baton Pass nodes with 238 expanded picks, so option B costs about 1% and does branch.
- TODO boxes ticked: Baton Pass, Pursuit, Roar, Teleport, Whirlwind, Suction Cups (line 58).
- Fixed after review, Natural Cure withdraw (`choose_move`): it ran with no bench and its `sub_after_death` pick could be the active, so the AI either dropped the withdraw or "switched" into itself (stages reset, hazards again). It now needs `ai_bench > 0` and passes `exclude=opp_active`, like pokeplatinum TrainerAI_ShouldSwitch / BattleAI_PostKOSwitchIn. `if sub == opp_active: pass` is unreachable now and left in place. Golden unchanged.
- Noticed, not changed:
  - No Pressure in the engine.
  - `NeuralNetwork/models.py` has an is-death feature but nothing for the Baton Pass phase.

## Phase 7: Healing, items, misc

- Recover (B/E, !)
- Synthesis (B/E, !): weather-dependent
- Refresh (B/E, !)
- Knock Off (B/E, !)
- Recycle (B/E, !): uses CONSUMED_ITEM
- Worry Seed (B/E, !): changes the ability to Insomnia and wakes the target
- Perish Song (B, !): also covers the AI TODO at `trainer_ai.py:200`
- Splash (!): only interacts with Gravity

## Phase 8: Move-calling (the most careful phase)

- Mirror Move (E, !), Copycat (B/E, !), Nature Power (!): need Renegade Platinum's battle terrain. Check whether it's needed at all.
- Metronome (!!!!!!): trainer-used. **Decision needed at this phase:** MoveDB has only 209 moves, while Gen IV Metronome can call around 450. Either expand MoveDB (a large data job) or restrict the pool and document the inaccuracy.

## Things I noticed but won't touch without your OK (AI side; mostly unrelated to moves)

- `SELF_KILL_MOVE` and `MAYBE_BAD_MOVES` (`trainer_ai_helper.py:70-77`) use `_MOVE_SELFDESTRUCT` (array index 24, which is the Bug Bite id) instead of `_MOVENAME_SELFDESTRUCT`.
- The poison check in `basic_move_status` (`trainer_ai_helper.py:~285`) looks inverted: it penalizes when the target is NOT Steel/Poison.
- `is_damaging = ... and not final_damage` (`trainer_ai.py:~285`) means the "-1 if not max damage" penalty never fires.
- The SpDef and Acc branches of `_expert_stat_opp` read the AI's own stages (`ai_pok`) instead of `u_pok`.
- Dragon Dance crashes in `_expert_stat_self` (second section, deferred).
- Explosion and Selfdestruct don't make the user faint (second section, deferred). Recharge is a no-op, which matters for Hyper Beam (also deferred).
- (Found in Phase 0) When `python main.py` output is piped or redirected on Windows, Python falls back to cp1252 and the `→` in `print_best_path` raises UnicodeEncodeError. A normal terminal is fine. Set `PYTHONIOENCODING=utf-8` when piping.
- (Found in Phase 0) pytest was missing from `venv` even though `requirements.txt` pins it; installed pytest 9.1.1 and httpx 0.28.1 from the pins.

## Verification (per phase)

- `pytest` (about 10s) plus `pytest -m jit` (compiled engine + MCTS) after every phase.
- New unit tests per move: the mechanic itself, the turn counters, the clear-on-switch, and AI scoring for the B/E branches.
- `UNSUPPORTED_MOVES` shrinks and strict xfails XPASS and move to their real files.
- Golden re-bless only on intended changes, with the JSON diff reviewed by you.
- `pytest -m slow` (fuzz) after Phases 0, 4, 5 and 6, since those change state layout and flow.
- Smoke run of the full app with `dev.bat`, plus `python main.py` to benchmark rollout speed after Phase 0 and Phase 4, to check for regressions on the hot path.
