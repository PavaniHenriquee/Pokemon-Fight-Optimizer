# Plan: finish the unchecked moves in TODO.txt (main `# Moves` section)

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

## Verification (per phase)
- `pytest` (about 10s) plus `pytest -m jit` (compiled engine + MCTS) after every phase.
- New unit tests per move: the mechanic itself, the turn counters, the clear-on-switch, and AI scoring for the B/E branches.
- `UNSUPPORTED_MOVES` shrinks and strict xfails XPASS and move to their real files.
- Golden re-bless only on intended changes, with the JSON diff reviewed by you.
- `pytest -m slow` (fuzz) after Phases 0, 4, 5 and 6, since those change state layout and flow.
- Smoke run of the full app with `dev.bat`, plus `python main.py` to benchmark rollout speed after Phase 0 and Phase 4, to check for regressions on the hot path.
