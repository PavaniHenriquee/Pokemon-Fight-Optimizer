# Known gaps (not done yet)

## Trainer AI

- Memento and Healing Wish (10.2): Basic and Expert follow [pp] `trainer_ai/script.s` only, Pokemow not checked.

- AI: the 8.1 branches (Belly Drum, Acupressure, Captivate, Haze, Psych Up, the swaps, Power Trick,
  the two-stat boosts, Expert Dragon Dance) follow [pp] `trainer_ai/script.s` only: Pokemow's per-move
  panels load with JavaScript and couldn't be fetched, so any place Pokemow differs isn't checked.
- AI: the 10.1 branches (Basic Future Sight / Doom Desire, Stockpile, Spit Up / Swallow, Expert Spit Up, Swallow
  in Expert_Recovery, the Encore and Heal Block lists) follow [pp] `trainer_ai/script.s` only, for the same reason.
- AI: Basic Imprison (11.1) checks only the AI's own Imprison. [pp] `Basic_CheckCanImprison` also gives -10 when
  the target has `MOVE_EFFECT_IMPRISONED`, which any Imprison attempt sets on it, a failed one included, until it
  leaves the field (my call: one bit).
- AI: Expert Heal Block counts every move with `drain` as a drain move ([pp] RECOVER_HALF_DAMAGE_DEALT), so
  Draining Kiss too; which effect RP gives it is unknown (ROM not read).
- AI: Expert Gravity reads the target's real ability;
  `expert_charge_invulnerable` skips the "target's last move isn't always-hit" check;
  pokeplatinum's Expert swaps the EVA_DOWN_2 / ACC_DOWN_2 logic (copy it when a -2
  accuracy/evasion move lands).
- AI, small [pp] differences no trainer up to Roark reaches: `basic_ability`'s Wonder Guard check
  reads the raw move type (Normalize ignored), and Natural Gift's berry type reaches its absorb
  checks ([pp] `LOAD_MOVE_TYPE` reads the data type); [pp] Basic_Main skips the immunity check for
  Guillotine / Sheer Cold, so into Wonder Guard the engine gives -12, [pp] 0; [pp] always knows my
  Shadow Tag / Magnet Pull / Arena Trap (no script check reads them yet).
- AI: `sub_after_death` phase 2 gives Weather Ball the weather's type for the whole damage calc; [pp]
  `BattleAI_PostKOSwitchIn` passes only the type chart the variable type, `CalcMoveDamage` keeps the data type
  (Normal), so [pp] adds no sun / rain boost there. Rounding only.
- AI: `sub_after_death` phase 2 scores a Ground move into my Levitate or Magnet Rise by its damage; [pp]
  `BattleAI_PostKOSwitchIn` runs `ApplyTypeChart` after `CalcMoveDamage` and scores it 0 (`MOVE_STATUS_IMMUNE`
  includes `LEVITATED` and `MAGNET_RISE`). `calculate_damage` has neither check.
- AI: Superpower and the recharge moves have no Basic branch of their own ([pp]
  `Basic_CheckNonStandardDamageOrChargeTurn`): the general checks cover them, with Pokemow's -12 into Wonder
  Guard where [pp]'s script gives -10.
- AI: `ai_move_damage` uses the raw base power except for the semi-invulnerable doublings (6.3). Pokemow's
  damage calc also sees Stomp vs Minimize, Brine and Rollout / Fury Cutter
  streaks (7.1).
- AI: `ai_move_damage` doesn't weigh Jump Kick / High Jump Kick's crash (6.5) when the move could miss or hit an
  immune target. [pp] `script.s` has no branch for BATTLE_EFFECT_CRASH_ON_MISS, so this only matters past the script.
- AI: `sub_after_death` stage 2 doesn't copy [pp]'s stale-score quirk (a skipped or empty move slot
  still compares the previous `score`, at first the last stage 1 type score).
- AI flags: the engine gives every trainer Basic + Evaluate Attack + Expert; vanilla [pp]
  (`res/trainers/data`) gives the Route 201 rival PRIORITIZE_EXTREMES instead of Expert and route
  trainers like Youngster Austin Basic only; RP's flags are unknown (ROM not read). Working
  assumption until the tool proves it wrong: RP keeps those 3 flags for every trainer, no more, no
  less. That's an educated guess: another Drayano hack's repo does exactly that, for simplicity
  and consistency.
- Drill Run: RP puts it in Horn Drill's slot, so [pp] Basic_Main's
  `IfMoveEqualTo MOVE_HORN_DRILL` would skip its damage scoring if RP kept that script.
- AI Basic Fling follows Pokemow (-10 only with no item); [pp] `Basic_CheckFling` is also -10 under Embargo (Fling
  power under 10) and with Multitype. The Klutz checks in Basic Fling and Expert Trick are left out (no RP species).
- AI: Expert Vital Throw's middle case (40-60% HP) is two rolls in [pp] (76/256, then 206/256); the engine
  queues one roll of 61/256 (23.8% for 23.9%).
- Expert Snatch (11.3) follows Pokemow: slower, target at 25% or less with no Recover / Defense Curl seen is
  26/256 of +1 and ends. [pp] `Expert_Snatch_TryScorePlus1` sends the other 230/256 on to the 226/256 roll of -2.

## Engine mechanics

- The confusion self-hit has no weather, so Flower Gift's sun boost doesn't reach it
  (`early_returns` has no field state).
- Metronome can call moves whose mechanics aren't in yet; they run as their data says.
- Metal Burst called by Metronome or Copycat always fails: whether the turn records damage is decided from the
  selected move (`action`'s `record_phy` / `record_sp`), so the caller's turn records nothing. [pp] records
  `lastDamageTaken` on every hit.
- Substitute: a failed Substitute keeps its Metronome item count (like the status moves above).
- Metronome item: a status move that fails inside `calculate_effects` (Thunder Wave on a statused
  foe, a stat move at ±6) doesn't give its count back; [pp] does (MOVE_STATUS_FAILED).
- Accuracy stages are netted with exact thirds; [pp] `HitRateByStage` is a rounded table (differs
  at -5, -4, +2, +4, +5), [SD gen4] applies accuracy and evasion separately.
- Reckless runs last in `base_power_ability`; its [pp] spot wasn't found (not in `battle_lib.c`).
  Rounding only.
- The weather is read once per move execution, so a Cloud Nine holder fainting mid-move keeps it
  off for the rest of that move ([pp] checks live).
- Natural Gift (`natural_gift`) writes the berry's type and power into the move slot itself, not a copy, so
  after it the slot keeps them (the move fails without a berry, but the AI and the rollout read the slot).
  Unconfirmed as a bug.
- Forecast is checked by ability only. Fine while only Castform can hold it (Trace can't copy it); once Skill
  Swap or Role Play exist, a non-Castform holder must not change ([pp] also checks `SPECIES_CASTFORM`).
- Unverified: an absorbed move ends an Uproar like any immune target; the "Soundproof user can't
  use a sound move on its own side" rule isn't in [pp] `TriggerImmunityAbility`.
- Thrash's fatigue confusion: Own Tempo always stops it. [pp] `subscript_confuse` checks it with
  `CheckIgnorableAbility`, so an end-of-turn Mold Breaker "attacker" (a stale `battleCtx->attacker`) would let
  it through.
- Whether RP's ROM lets Soundproof block Disarming Voice is unknown (the engine says yes).
- Custap is eaten when the turn order is set, not when its holder moves: a holder KO'd first by a higher
  priority move loses it ([pp] keeps it), and its slot's Recycle item follows.
- Choice lock: a locked move that leaves the moveset ends the lock in [pp] (`CheckInvalidMoves`); it needs Mimic or
  Transform (12.2). [pp] also clears the lock of a Pokemon hit while holding no choice item; the engine keeps it
  stored (it does nothing without a choice item) until a choice item comes back, which only Trick can do (4.5).
- Last Resort: Mimic, Sketch and Transform reset its count of moves used ([pp] `lastResortCount = 0`); none of
  them is in yet (12.2).
- Sleep Talk goes by [SD]'s `nosleeptalk` flag, so it never calls Nature Power; [pp] `Move_IsInvoker` leaves
  Nature Power out, so its Sleep Talk can.
- Uproar: a Soundproof Pokemon still falls asleep during one, Rest included (`sleep_blocked`, [pp]
  `subscript_rest`, CHECK_STATUS_STATE_SLEEP); [SD gen4]'s uproar stops every sleep.
- Called moves under Gravity or Heal Block fail ([SD] onModifyMove, my call). [pp] `Move_CanBeMetronomed`
  rerolls Metronome's pick instead and fails Copycat and Assist.
- Dream Eater runs `drain`, so a Liquid Ooze target hurts it; [pp] `subscript_dream_eater` has no Liquid Ooze
  check and heals.
- Metronome item: a failed Trick, Switcheroo or Embargo keeps its count, like the status moves above ([pp] gives
  it back on MOVE_STATUS_FAILED). A failed Fling gives it back.
- Chatter confuses at [SD gen4]'s 31% whenever a Chatot uses it. [pp] reads the recorded cry's volume (1%, 11% or
  31%, 1% with no valid recording, `BtlCmd_CheckChatterActivation`). Once Transform is in, a transformed Chatot
  mustn't confuse.
- Scald: which [pp] effect RP gives it is unknown (ROM not read). No AI branch reads the burn-hit effects yet.
- Wild Charge, Cut and Strength: which [pp] effect RP gives them is unknown too. The AI goes by their data:
  recoil, high crit, and no branch for Strength's Attack raise (like Meteor Mash).
- The AI's U-turn or Baton Pass replacement that faints to the hazards mid-turn stays in until the end of the
  turn: my slower move goes into it and fails. What [pp] does there wasn't checked.
- My U-turn: `_after_move_items` runs while the user is still in, before my pick (like Baton Pass). [pp] switches
  it out inside `subscript_attack_then_switch_out`, so a status berry can fire a step early here.
- Magic Coat / Snatch (11.3): a called move (Metronome, Copycat...) can be bounced or snatched ([SD]); [pp] has
  `SYSCTL_SKIP_STOLEN_CHECK` and whether a called move sets it wasn't traced. A stolen move keeps the original
  user's Metronome item count (not checked in [pp]). The rollout scores both moves as plain status moves.

## Items

- Not handled: Klutz and Embargo ([pp] `Battler_HeldItem` returns no item for them; the speed-halving items
  must keep working under them, [pp] reads the raw item there). Covet / Thief, Knock Off and Trick failing on a
  defender whose Quick Claw or Custap activated this turn ([pp] `BtlCmd_TryStealItem`, `subscript_knock_off`,
  `subscript_exchange_items`).
- Knock Off's Sticky Hold check reads the attacker's Mold Breaker directly, not through `ignorable_ability`.
- Species items read `Pok.ID`: once Transform is in they must read the transformed species, and [pp] skips the
  Griseous Orb boost for a transformed Giratina. [pp] also skips Trace for a Griseous Orb holder (unreachable,
  only Giratina can hold it).
- Two actives both holding Lagging Tail / Full Incense: [pp] lets the slower go first, the engine goes by speed
  (Showdown). Unreachable, only my side can have them.
- Switcheroo and Embargo also fail on a target whose Quick Claw or Custap activated this turn in [pp]
  (`subscript_exchange_items`, `subscript_embargo_start`); not handled, like Covet / Thief, Knock Off and Trick.
- Sticky Hold stopping Covet, Thief, Bug Bite or Pluck doesn't reveal the ability; [pp]'s "made ineffective"
  message names it (`subscript_steal_item`, `subscript_pluck`). Trick and Switcheroo reveal it.
- Fling: Shield Dust blocks the flung status or flinch as a secondary effect ([SD]); [pp]'s side-effect path for
  the fling scripts wasn't checked. A flung confusion berry only confuses a target below max HP (the held
  berry's rule); [SD] confuses at full HP too. A flung Leppa takes the move missing the most PP ([pp], like
  Bug Bite); [SD] gen4 takes the first one at 0 PP.

## MoveDB and tests

- MoveDB flags from after Gen IV (`python -m DataBase.add_moves --check` lists them): Absorb and Mega
  Drain have `heal`; Roar has no `protect`.
- `DamageSources.MAGIC_COAT` (MoveDB `"damage": "magic_coat"`) is Mirror Coat's, not the move Magic Coat's.
- MoveDB: Earthquake's flag is spelled `nonsky`, every other move's `non_sky`. Nothing reads it yet.
- `battle_driver.py`'s `_blocked` (the independent `legal_actions`) has Gravity but not Heal Block; no scenario
  gives my side a healing move under Heal Block yet.
- MoveDB order: `SHOCK_WAVE` sits before `SCRATCH` in `MoveName` and Nightmare before Night Shade in
  MoveDB.json. `add_moves` leaves existing lines alone, so a new move next to them can land a step off
  (Night Slash would go before Nightmare).
- MoveDB: Cut's `crit_ratio`, Strength's Attack raise and Hurricane's missing confusion are hand edits (RP effect
  changes, which `add_moves` only prints), so `add_moves --check` should list all three as different. Not run to
  confirm.
- Tests that seed Metronome (`test_choice_item_locks_metronome_into_itself`, the `move_calling` golden scenario)
  call a different move each time `METRONOME_POOL` grows, so a MoveDB batch can move them.
- `Models/battlefield.py` (`Battlefield`) isn't used anywhere, and its `to_np` writes Trick Room and its turns at
  indices 5 and 6, which aren't today's `Field` layout. Left alone (9.2).

## Search and Continue

- Search: in the death phase `node_key` leaves out my whole side, my side conditions included, so a Future Sight
  the foe set on my side this turn doesn't split nodes there (nor Spikes / Toxic Spikes it set). Rare: my active
  has to faint the same turn.
- Search: the rollout (`status_move_blocked`) doesn't see the 8.1 fails (`stage_move_fails`: Belly Drum at half
  HP or less or at +6, Acupressure with every stat at +6 or behind its Substitute, Captivate on Oblivious, the same
  gender or genderless; `confuse_boost_fails`: Swagger / Flatter at +6 on a confused foe), so it weighs them at 1.
  `stage_move_fails` reveals Oblivious, so the rollout would need a version without the reveal.
- Search: the rollout (`sleep_move_fails`) sees Sleep Talk fail only while awake, not asleep with nothing it can
  call (a choice lock, Encore, only uncallable moves, `sleep_talk_move`), so it weighs those at 1.
- Search: the rollout's quick type check (`rollout_pref`) uses `gravity_types`, so it misses Ingrain grounding a
  Flying type (Iron Ball and Gravity reach it).
- Search: the rollout (`rollout_pref`) doesn't weigh Jump Kick / High Jump Kick's crash (6.5) on a move that could
  miss or hit an immune target (a Ghost: no damage and no crash in [pp]).
- Search: the rollout's damage estimate (`mcts_eval.py`) sees Present at power 0 and Triple Kick / Beat Up as one
  10-power hit (7.1), only its move weights are off.
- Search: the rollout (`rollout_pref`) runs `calculate_damage` on Super Fang, Endeavor and Metal Burst like on
  any power-0 move (7.2), so it never sees their KO, and a super effective Metal Burst (Steel) gets the bonus
  weight even when it would fail moving first.
- Search: the rollout (`rollout_pref`) weighs Payback, Revenge and Avalanche at their base power, and Sucker
  Punch and Focus Punch as if they always hit (7.3): it doesn't see the doubling or the fail (a status move
  picked, a hit before Focus Punch). Only its move weights are off.
- Search: the rollout weighs Trick Room at 1 like any status move (9.2), also when it's up and helps me (a second
  one ends it). `field_move_fails` only catches Tailwind already up.
- Search: the rollout doesn't see Baton Pass or Healing Wish (10.2) fail on my last Pokemon, both are weighed like
  any status move.
- Search: `node_key` sees a rampage only through `LOCKED_MOVE`, not `RAMPAGE_TURNS`, so 2 turns left and 1
  left (confusion this turn) share a node.
- Leppa on the foe (only through a Covet on my Leppa holder) gives back PP that Continue's foe PP arithmetic
  doesn't see.
- Continue's Foe PP after Spite: the suggested move is the one the foe used that turn, so when my Spite moved
  first (it hit the move before) the 4 PP land on the wrong move until edited. A Spite Metronome calls isn't seen.
- Search: `evaluate_terminal` counts deaths, so every Pokemon is worth the same: a win that loses the
  team's best Pokemon scores like one that loses its worst.
- Search: `ROOT_C` costs wins at very low budgets: Roark weak at 200 iterations wins 2.1%, against 8.7% with
  a root `c` of 0.3. The app runs at least 5000 unless stopped by hand or given a lower cap
  (`NN_PLAN.md` Step 1a).
- Search: `prune_dominated`'s 0.88 and the 5,000-visit stop rule are hand-set too. Nothing has pointed
  at them yet.
- Search: `mcts_loop` (benchmarks, `python main.py`) prunes every 500 iterations, the backend every 2500,
  so full-battle numbers prune sooner than the app. Low `c` values could score a bit differently there.
- Search: at the first turn of Roark weak and Barry 2-P the stop rule never fires within 350,000 iterations
  (29-42 s), so the app runs to its cap, 500,000 by default in the UI. Roark weak's top action has only 12% of
  the visits.
- Continue from here: only the foe's PP follows every step of the path. Everything else comes from the node's
  snapshot, or its parent's when the last step runs again, so it keeps that visit's history for the earlier steps: my
  own PP (a flinch doesn't show in `node_key`) and hidden counters. If the last step's re-run misses its 100 ms, the
  foe's last move and my `MIRROR_MOVE` stay the snapshot's visit's too.
- Search: Struggle as a regular move crashes the search after 2 iterations with `IndexError: tuple index out of
  range` in `rollout_arr`, cause not traced. The same party without it runs fine. `/pokemon-data` leaves it out, so
  the move lists don't offer it, and only a box entry already saved with it can reach this.

## Benchmarks

- Benchmarks: `quality` and the `tuning` stages share seeds (`100_000 * iters + i`), so re-running `quality`
  isn't an independent check of values `tuning` chose. `tuning`'s fresh-seed stage is.
- Benchmarks on the i5: at this repo's folder depth, `.numba_cache/benchmarks/...` reaches the 260
  character path limit and the compile fails. `PBO_CACHE_ROOT` set to a short folder gets around it.
- Benchmarks: `benchmarks/fights.py` keeps its own copy of the trainer item table; `TRAINER_ITEMS` in
  `DataBase/support.py` is the one the backend and the coverage report read.

## Trainers

- Trainers: `terrain` is the map's battle background ([pp] CalcTerrain's fallback). The tile the player stands
  on (tall grass, sand, snow, mud) can override it in the game, and the sheet doesn't say which.
- Trainers: three sheet natures no [pp] class's personality gives are kept as the sheet has them: Gym Leader
  Byron's Bastiodon, Gentleman Backlot's Espeon, Poké Kid Danielle's Raichu. Galactic Grunt [954] has only a
  genderless Shedinja, so its class gender is a guess (male); only the sprite depends on it.

## Tracker, Box, Setup, UI, Lint

- UI: a Substitute shows as a chip, without its HP.
- UI: Block and Spider Web show the "Mean Look" chip (one bit for all three).
- UI: no badge for a rampage (Thrash, Outrage, Petal Dance), like Rollout.
- UI: no "the AI knows this ability" marker, and the field's weather shows while Cloud Nine / Air Lock
  suppress it.
- Tracker: met locations come from vanilla [pp] `header.json`s, RP's ROM wasn't read. The sheet's
  "met location" notes agree on every location they mention (Routes 204, 205, 212, the Lost Tower).
- Tracker: two box Pokemon of one evolution line (only possible through manual add) move to the death
  box together, since the tracker and the box match by line. Clearing a row removes only the first one.
- Tracker: a sprite that fills its frame (Gyarados, Onix) covers part of its card's text at 2x.
- Tracker: the starter lock only hides its ✕. Deleting its entry from the PC box still works; the starter stays
  chosen and shows "Not in your box".
- Tracker: Veilstone City is the last location on the Pokémon tab (the sheet's encounter tab lists it with the
  legendaries). The Items tab puts it after Route 215 (`PLACED_AFTER`).
- Tracker items: a pickup's id is the sheet's text (location, area, item, how), so a re-import after the sheet
  rewords one of those un-ticks it. Ids no longer in the data are ignored.
- Tracker locks: badges are ignored (HM03 alone unlocks Surf, no Fen Badge check), a rod unlocks fishing spots
  only reachable by Surf, and Honey Tree / Poké Radar tables are never locked (Honey isn't in the tab, the Radar
  comes from Rowan at the start).
- Tracker items: the iTEMS/TMs tab only lists notable items (no Potions, Balls, berries).
- Box: a one-gender species (12 male only, 18 female only, [SD] and [pp] agree) starts Male and can be
  set to either, so Nidoran♀ can be saved Male. PkDB only marks the genderless ones.
- Box: an entry saved with a gender before PkDB marked its species genderless keeps its ♂ / ♀ mark until
  it's edited. Battles already ignore it (`_build_battle`).
- Box: a held item is only set and shown in the party, the box editor and summary don't have it.
- Box editor: manual add can still add any species, on purpose, for manual testing while the app only
  covers up to the 1st gym. To be removed once it covers the full game.
- Setup: below 1800×900 (full HD at 125% Windows scaling is 1536×864) the side panels stay small and a party of
  5-6 takes 3 rows and scrolls.
- Setup: a party card's ✕ reflows the cards, so a sprite can land under the cursor and open its hover card.
- Setup: at 3× a sprite that fills its frame (Gyarados) pokes a few pixels past its party card's edge.
- Lint: the `calculateStats` export in `PokemonSlots.tsx` fails `react-refresh/only-export-components`, and so do
  `ui/button.tsx` and `ui/combobox.tsx`. `ConfigureView.tsx` has two `react-hooks/exhaustive-deps` warnings.
- Setup: Natural Gift shows MoveDB's Normal with no power, the engine takes both from the held berry
  (Hidden Power follows the IVs, `lib/hiddenPower.ts`).
- UI: Weather Ball shows MoveDB's Normal 50 in the move lists, the engine uses the weather's type and 100.
