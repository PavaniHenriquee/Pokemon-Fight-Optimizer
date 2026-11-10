# Known gaps (not done yet)

## Trainer AI

- AI: Expert Gravity reads the target's real ability and skips Magnet Rise;
  `expert_charge_invulnerable` skips the "target's last move isn't always-hit" check;
  pokeplatinum's Expert swaps the EVA_DOWN_2 / ACC_DOWN_2 logic (copy it when a -2
  accuracy/evasion move lands).
- AI, small [pp] differences no trainer up to Roark reaches: `basic_ability`'s Wonder Guard check
  reads the raw move type (Normalize ignored), and Natural Gift's berry type reaches its absorb
  checks ([pp] `LOAD_MOVE_TYPE` reads the data type); [pp] Basic_Main skips the immunity check for
  Guillotine / Sheer Cold, so into Wonder Guard the engine gives -12, [pp] 0; [pp] always knows my
  Shadow Tag / Magnet Pull / Arena Trap (no script check reads them yet).
- AI: Superpower and the recharge moves have no Basic branch of their own ([pp]
  `Basic_CheckNonStandardDamageOrChargeTurn`): the general checks cover them, with Pokemow's -12 into Wonder
  Guard where [pp]'s script gives -10.
- AI: `MOVE_EXCEP` still lacks moves [pp] `sNoDamageCalcMoveEffects` and Pokemow's excluded list leave out of the
  damage compare: Spit Up, Eruption, Water Spout, Super Fang,
  Reversal, Present, Endeavor, Metal Burst, Trump Card, Wring Out, Punishment, Crush Grip. Add each in its batch.
- AI: `PROTECT_LIKE_M` (the "saw the target use Protect" checks) holds only Protect. Detect goes in once it's in
  MoveDB ([pp] `IfMoveEffectKnown BATTLE_EFFECT_PROTECT` covers both).
- AI: `ai_move_damage` uses the raw base power except for the semi-invulnerable doublings (6.3). Pokemow's
  damage calc also sees Stomp vs Minimize, Facade, SmellingSalt, Wake-Up Slap, Brine, Rollout / Fury Cutter
  streaks and Weather Ball (7.1).
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

## Engine mechanics

- Sucker Punch (not in yet): [SD gen4] fails it into a recharging target, whose locked slot is a damaging move.
- The confusion self-hit has no weather, so Flower Gift's sun boost doesn't reach it
  (`early_returns` has no field state).
- Metronome can call moves whose mechanics aren't in yet; they run as their data says.
- Substitute: Dream Eater failing against one waits for Dream Eater's batch (8.2, no sleep check yet either).
  Focus Punch: Expert's +5 behind a Substitute and losing focus when hit aren't in; a hit on the Substitute
  mustn't break focus. A failed Substitute keeps its Metronome item count (like the status moves above).
- Metronome item: a status move that fails inside `calculate_effects` (Thunder Wave on a statused
  foe, a stat move at ±6) doesn't give its count back; [pp] does (MOVE_STATUS_FAILED).
- Accuracy stages are netted with exact thirds; [pp] `HitRateByStage` is a rounded table (differs
  at -5, -4, +2, +4, +5), [SD gen4] applies accuracy and evasion separately.
- Reckless runs last in `base_power_ability`; its [pp] spot wasn't found (not in `battle_lib.c`).
  Rounding only.
- The weather is read once per move execution, so a Cloud Nine holder fainting mid-move keeps it
  off for the rest of that move ([pp] checks live).
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
- Sleep Talk isn't in yet: its move pool must go through `move_blocked` ([pp] `TrySleepTalk`), so it fails
  under a choice lock ([SD gen4] agrees). It also skips every charge move ([pp] `Move_IsMultiTurn`): go by the
  charge flag, since [SD]'s flags leave `nosleeptalk` off Fly.
- Metronome item: a failed Trick, Switcheroo or Embargo keeps its count, like the status moves above ([pp] gives
  it back on MOVE_STATUS_FAILED). A failed Fling gives it back.
- Chatter confuses at [SD gen4]'s 31% whenever a Chatot uses it. [pp] reads the recorded cry's volume (1%, 11% or
  31%, 1% with no valid recording, `BtlCmd_CheckChatterActivation`). Once Transform is in, a transformed Chatot
  mustn't confuse.
- Scald: which [pp] effect RP gives it is unknown (ROM not read). No AI branch reads the burn-hit effects yet.
- Wild Charge, Cut and Strength: which [pp] effect RP gives them is unknown too. The AI goes by their data:
  recoil, high crit, and no branch for Strength's Attack raise (like Meteor Mash).

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
  (Showdown). Unreachable, only my side can have them. Iron Ball ending Magnet Rise waits for Magnet Rise.
- Switcheroo and Embargo also fail on a target whose Quick Claw or Custap activated this turn in [pp]
  (`subscript_exchange_items`, `subscript_embargo_start`); not handled, like Covet / Thief, Knock Off and Trick.
- Sticky Hold stopping Covet, Thief, Bug Bite or Pluck doesn't reveal the ability; [pp]'s "made ineffective"
  message names it (`subscript_steal_item`, `subscript_pluck`). Trick and Switcheroo reveal it.
- Fling: Shield Dust blocks the flung status or flinch as a secondary effect ([SD]); [pp]'s side-effect path for
  the fling scripts wasn't checked. A flung confusion berry only confuses a target below max HP (the held
  berry's rule); [SD] confuses at full HP too. A flung Leppa takes the move missing the most PP ([pp], like
  Bug Bite); [SD] gen4 takes the first one at 0 PP.

## MoveDB and tests

- Not in MoveDB yet: Spikes damage, Magnet Rise, Rest, Snore, U-turn,
  Heal Block.
- MoveDB flags from after Gen IV (`python -m DataBase.add_moves --check` lists them): Absorb and Mega
  Drain have `heal`; Stealth Rock, Foresight and Taunt are `reflectable`; Roar has no `protect`. They matter
  once Magic Coat and Heal Block are in.
- MoveDB: Earthquake's flag is spelled `nonsky`, every other move's `non_sky`. Nothing reads it yet.
- MoveDB order: `SHOCK_WAVE` sits before `SCRATCH` in `MoveName` and Nightmare before Night Shade in
  MoveDB.json. `add_moves` leaves existing lines alone, so a new move next to them can land a step off
  (Night Slash would go before Nightmare).
- `test_trainer_lacks` (`test_database.py`) uses U-turn as its missing move: swap it once U-turn is added.
- MoveDB: Cut's `crit_ratio`, Strength's Attack raise and Hurricane's missing confusion are hand edits (RP effect
  changes, which `add_moves` only prints), so `add_moves --check` should list all three as different. Not run to
  confirm.
- Tests that seed Metronome (`test_choice_item_locks_metronome_into_itself`, the `move_calling` golden scenario)
  call a different move each time `METRONOME_POOL` grows, so a MoveDB batch can move them.

## Search and Continue

- Search: the rollout's quick type check (`rollout_pref`) uses `gravity_types`, so it misses Ingrain grounding a
  Flying type (Iron Ball and Gravity reach it).
- Search: the rollout (`rollout_pref`) doesn't weigh Jump Kick / High Jump Kick's crash (6.5) on a move that could
  miss or hit an immune target (a Ghost: no damage and no crash in [pp]).
- Search: `node_key` sees a rampage only through `LOCKED_MOVE`, not `RAMPAGE_TURNS`, so 2 turns left and 1
  left (confusion this turn) share a node.
- Leppa on the foe (only through a Covet on my Leppa holder) gives back PP that Continue's foe PP arithmetic
  doesn't see.
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
