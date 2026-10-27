# Plan: finish the unchecked moves in TODO.txt (main `# Moves` section)

## Progress (update at the end of every session)
| Phase | Status | Notes |
|---|---|---|
| Step 0: save plan | Done | |
| Phase 0: layout infrastructure | Done (2026-10-26), committed | See "Phase 0: as built" below |
| Phase 1: data-driven moves | Done (2026-10-27), committed | B1-B10 fixed, 97 TODO boxes ticked; Gust and Stomp left open |
| Phase 2: damage mechanics | **Next** | Start with the mechanics notes; Hidden Power is `!!` and needs your OK on its note |
| Phase 3: volatiles, no action restriction | Not started | |
| Phase 4: action-restricting volatiles | Not started | |
| Phase 5: side conditions and field | Not started | |
| Phase 6: switching moves | Not started | |
| Phase 7: healing, items, misc | Not started | |
| Phase 8: move-calling | Not started | |

**Where to start next session:** Phase 2, workflow step 1. Write the mechanics notes (Hidden Power `!!` waits for your OK), show evidence for any bug it depends on (Struggle check, Reckless), then implement.

**Open issues carried forward:**
- Trainers with Protect, Taunt, Foresight or Ingrain now build, but the trainer AI raises `ValueError("Need implementation")` in `expert_vol_status` when it scores those status moves. Expert scoring runs for every trainer, so this hits Lucas 1, Dawn 1 and Barry 2 (Chimchar, Taunt), Natalie, Tristan, Sebastian and Colin (Foresight), Logan and Roark (Protect), Madeline and Darius (Ingrain). Confirmed with a non-JIT battle vs Youngster Logan (seed 2). Samantha's Wrap is damaging and doesn't hit this path. Before Phase 0 these trainers failed earlier, at team build. The safe "0, no crash" fallback is scheduled for Phase 3; consider pulling it forward if you want to run those trainers sooner.
- In battle, the new volatile bits are no-ops until their phase implements them. `vol_status` in `Engine/status_calc.py` only applies the bits it knows, so Protect and friends act like Splash, and Wrap etc. deal damage without trapping.

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

## Phase 4: Volatiles that restrict actions (touches SearchEngine valid actions and trainer AI `return_idx`)
- Taunt (!): trainer-used
- Encore (B/E, !): needs LAST_MOVE_ID
- Partial trapping: Wrap (E, !) is trainer-used; Bind, Clamp, Fire Spin, Whirlpool are starred. Covers 2-5 turns, 1/16 residual damage, and no switching.
- Uproar (!)
- The architecture check comes first: where valid actions get filtered for my side (MCTS) and for the AI. Locked states keep looping inside `step()` and are never exposed as decision nodes.

## Phase 5: Side conditions and field
- Reflect and Light Screen (B/E, !): damage modifiers, 5 turns. Then Brick Break (E, !) and Light Clay. Light Clay is an item; I'll ask before touching it.
- Mist (B, !), Safeguard (B, !), Lucky Chant (B/E, !): this also clears the Safeguard TODO in `basic_move_status`.
- Stealth Rock (B/E, !!): a per-side hazard applied in `switch_in`. Needs your call on the faint-on-switch-in flow, i.e. replacement after a hazard KO for both sides, including the AI's `sub_after_death`.
- Toxic Spikes (B/E, !)
- Rapid Spin (!)
- Rain Dance (B/E, !) and Sandstorm (B, !): weather setting with a 5-turn countdown.

## Phase 6: Switching moves (validate the architecture first)
- Roar and Whirlwind (B/E, !): fail on the first turn of a trainer battle? Check that. Random replacement, which is a chance node for MCTS.
- Baton Pass (B/E, !): passes stages and the passable volatiles. My replacement becomes a decision; the AI's follows the Gen IV AI switch logic.
- Teleport (B): fails in trainer battles.
- Pursuit (E, !): doubles power and hits before the switch.

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
