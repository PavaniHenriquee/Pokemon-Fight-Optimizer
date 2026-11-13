# Engine notes

Read the matching section before engine, AI or search work. Moved out of `CLAUDE.md` to keep it short.

## Implementing moves, items and abilities (ENGINE_PLAN.md)

- Notation: no `*` = used by a trainer up to the Champion (do first), `*` = only on my own
  Pokemon. `!` = check the Showdown handler and pokeplatinum before coding; `!!` or more = also
  write me a mechanics note and wait for my OK. `(B)` / `(E)` = add the `basic_flag` /
  `expert_flag` branch from pokeplatinum `trainer_ai/script.s` and Pokemow.
- Group work by shared mechanism, not alphabetically. Per batch: mechanics note with sources →
  evidence for any bug it depends on, wait → engine, then AI → tests in the matching file →
  `pytest` + `-m jit` (+ `-m slow` if layout or turn flow changed) → tell me which
  `ENGINE_PLAN.md` boxes can be ticked.

### Checklist when adding a move or mechanic (go through all of it)

1. Mechanics: Showdown inherits gen4 → gen5 → gen6 → gen7 → gen8 → base `data/moves.ts`, so check every
   layer; then pokeplatinum (battle code and `trainer_ai/script.s`). Numbers from the RP sheet.
2. Data: `MoveDB.json` entry and `MoveName` (`DataBase/MoveDB.py`), both alphabetical. Inserting
   shifts every later id → `python generate_constants.py`. A two-turn move needs `"charge": 1`
   (the `charge` flag alone does nothing). Check flags (`gravity`, `protect`, `sound`, ...).
   `python -m DataBase.add_moves Move ...` builds both from those sources (`--write` inserts them and
   regenerates); its notes list what MoveDB can't hold, which is the batch's engine work.
3. New state: a `Pok` slot also goes in `Pokemon.to_np` (listed by hand), `reset_switch_out`,
   `_pass_baton` if Baton Pass keeps it, and `unlock_move` if it belongs to a charge or lock. A
   `Field` timer goes in `_count_down_field` at its Gen IV spot. A new enum class goes in
   `generate_constants.py` and `GENERATED_CLASSES` in `test_layout.py`.
4. Engine: hit check (`calculate_hit_miss`, the airborne / underground hit lists), power
   (`variable_power`), type chart (`matchup_types` / `gravity_types`), can't-move checks
   (`early_returns`), the move itself (`_execute_move_slot` / `_status_move`), called moves
   (Metronome, Copycat), end of turn, switch-in (`apply_hazards`, `is_grounded`).
5. A field effect that changes types, accuracy or damage must reach every caller, not just the
   engine: the AI (`trainer_ai_effectiveness`, `ai_move_damage`, `basic_flag`, the
   `check_*_pty` withdraw checks, `sub_after_death`, `copycat_beats`) and the rollout
   (`rollout_pref`, `field_move_fails`).
6. Selection: a move that can't be picked goes through `move_blocked`, which feeds both
   `valid_action_mask` and the AI's move loop.
7. Search: `node_key` must see any new state that changes outcomes (presence, not turns left).
   `VOL_STATUS2` gets `VOL2_KEY_BITS` bits per side there; grow it with the bitmap.
8. AI: `basic_flag` / `expert_flag` branches from the script; add the move to a `KIT_*` tuple
   in `test_trainer_ai.py`.
9. Metronome: `METRONOME_POOL` (`Models/move.py`) is every MoveDB move except
   `METRONOME_FORBIDDEN` (pokeplatinum `sCannotMetronomeMoves`), so a new move is callable by
   Metronome and Copycat right away, implemented or not. Until MoveDB has every Gen IV move,
   Metronome only calls moves already in MoveDB.
10. UI: `backend/serializer.py` (volatile names come from the enums, field state from `_field`),
    `frontend/src/types.ts`, the badge in `BattleView.tsx`.
11. Tests and checks: unit tests in the matching file; re-bless golden and explain every
    turns/HP change; `pytest`, `-m jit`, `-m slow`. Then list the `ENGINE_PLAN.md` boxes that
    can be ticked and the TODO comments that became outdated (remove them only when I ask).

### Rules for abilities and items

- Item effects are data: `HOLD_EFFECT` / `EFFECT_PARAM` / `EFFECT_TYPE` come from ItemDB ([pp] holdEffect /
  effectParam).
- Every defender-side ability check goes through `ignorable_ability` (Mold Breaker).
- Every weather read goes through `effective_weather` (Cloud Nine / Air Lock), except setting it, counting it
  down and `node_key`. The AI's script checks read the field's weather; its damage estimate, speed compare and
  `sub_after_death` read the effective one.
- Every base-power / stat / type-chart modifier also goes into `calculate_ai_logic_damage`; crit, the Metronome
  item and resist berries don't ([pp] TrainerAI_CalcDamage).
- A new target-ability check in `basic_flag` goes into `_EXPLICIT_RELEVANT`. An ability-tagged message calls
  `reveal_ability`.
- New RNG calls run only when the ability/item is present, so golden scenarios without it keep their RNG order.

## Engine decisions (settled, don't re-litigate)

- Pokemow wins over pokeplatinum when they differ on the AI (Feint, Worry Seed's HP check, the
  Perish Song withdraw, Blizzard).
- Copied Gen IV quirks: the Rage glitch (`_rage_glitch`), Magnitude is 0 in the AI's damage
  calc, the Basic Levitate check ignores Gravity, Synchronize paralyzes Electric types.
- My calls: Fury Cutter has no 160 cap; Take Down recoil is at least 1; Sweet Kiss is Fairy;
  Attract is checked before paralysis (Showdown order); Worry Seed wakes a sleeper immediately;
  Helping Hand / Follow Me do nothing in singles; Recycle's item belongs to the battle slot.
  From Showdown, since pokeplatinum code wasn't found: Gravity's accuracy x6840/4096, a called
  move Gravity blocks fails.
- Representation: weight is in hectograms. Encore / Disable pack the slot into their counter
  (turns \* 4 + slot). `SEMI_INV_MOVE` holds the charging move id: Bounce is airborne, Dig
  underground, Dive goes there too. A called move keeps `LOCKED_MOVE` on the caller's slot and
  stores itself in `CALLED_MOVE`. My Baton Pass replacement is a mid-turn decision
  (`BattlePhase.BATON_PASS`, `Field.PENDING_OPP_MOVE`); my slot is in `node_key` so Roar's
  random drag-out splits nodes. The AI learns my moves through the `AI_KNOWS` bits. Nature
  Power reads an optional `"terrain"` in `TrainerDB.json`.
- `Field.OPP_MOVE_RAN` is the foe's slot + 1 + 16 × PP paid in the turn, written once its move passes the can't-move
  checks (0: it didn't move). Nothing in the battle reads it. `step_arr` packs it per turn and returns it, also for the
  forced turns of a step, for the outcome dropdowns and Continue's PP.
- End of turn (Gen IV): side timers, weather, Gravity count down; weather damage for both
  actives; then per Pokemon Ingrain, Aqua Ring, Speed Boost, Leech Seed, poison/burn, Curse,
  bind, Uproar, Thrash, Disable, Encore, Taunt, Yawn; then Perish Song. Speed order, a tie is a coin flip.
- My calls (abilities/items): Simple doubles accuracy/evasion stages; Quick Claw / Stall follow [SD gen4] (one
  20% roll per holder per turn, within the same priority); the Metronome item follows [pp] (cap 10, keyed in
  `node_key` k4); RP's AI does steal with Covet; the rollout counts a working opponent OHKO as a KO. King's Rock
  / Razor Fang follow [SD gen4] (10% per hit, Serene Grace doubles it) on its move list plus RP's damaging moves
  from after Gen IV (`kings_rock` in MoveDB, which `add_moves` sets). Choice Band / Specs go before every
  ability ([pp] applies Huge Power, Pure Power and Slow Start first), and Band boosts the confusion self-hit ([pp]).
- Berries (4.3): Micle follows [pp] (lasts until the holder's next accuracy roll or a switch-out, OHKO and
  always-hit moves keep it); Safeguard doesn't stop a confusion berry's confusion ([SD]); Enigma, Jaboca and
  Rowap work per hit ([SD]); Bug Bite follows [pp] PluckBerry, quirk included: a plucked Persim raises Attack
  below +6 instead of curing confusion, a plucked Leppa takes the move missing the most PP.
- Item moves (4.5): RP's AI steals and swaps with Thief, Trick and Switcheroo too, like Covet ([pp] fails them for
  the AI side). Thief runs Covet's path, Pluck Bug Bite's. A target holding no choice item after a move loses its
  lock ([pp] UpdateMoveBuffers, defender side).
- Embargo suppresses the item block: `refresh_item` (`Models/item.py`) keeps only `ITEM_ID` while it's up, so
  every effect read sees no item and checks for holding one still see it. Anything that moves an item between
  Pokemon goes through `switch_items` / `refresh_item`. A read [pp] makes on the raw item (the speed-halving
  items, the AI's `LoadHeldItemEffect`, a plucked berry) uses `raw_hold_effect` / `raw_item_type` or
  `ITEM_TABLE`. Baton Pass keeps it.
- Fling: the item still boosts the damage, then it's gone (on a miss or Protect too), recyclable. Its effects
  follow [SD] and land on the hit: the item's `fling_status` / `fling_volatile` (ItemDB) as a sure secondary,
  berries and herbs on the target. An Embargoed target gets no effect at all ([pp] BattleSystem_FlingItem).
- Substitute: every damaging move hits it (Gen IV has no bypass for them, sound moves included). A multi-hit
  move's hits after it breaks reach the Pokemon with their effects ([SD]; [pp] blocks them for the rest of the
  turn). A status move into one still reveals the ability that would block it ([pp] order). Its HP cost isn't
  damage (no Assurance, no Focus Band). The Rage glitch wipes it ([pp] statusVolatile bit).
- [pp] over [SD]: Heatproof halves base power; Safeguard blocks Flame Orb; Snow Warning sets hail; Shed Skin is
  30%. Copied quirks: Fire Fang always passes Wonder Guard; Expert Explosion's second evasion -1 starts at +3
  (Pokemow).
- Sleep of 2-5 lasts 1-4 turns (counter drops first, wakes at 0). Struggle is typeless (no type item).
  Explosion / Selfdestruct faint the user before the hit check; a double KO counts as a loss. Focus Band rolls
  on every damaging hit, lethal or not. The confusion self-hit uses Bulbapedia's Gen IV factor table (no Muscle
  Band). OHKO moves follow [pp] TryOHKOMove; Horn Drill is left out (RP has Drill Run there).

## Mechanics order reference ([pp])

- Base power (CalcMoveDamage): variable → Charge ×2 → Technician (≤60, ×15/10, not Struggle) → type item
  ×120/100 → Light Ball ×2 → Muscle Band ×110/100 → Thick Fat (def) /2 → Mud/Water Sport /2 → pinch abilities
  ×15/10 → Heatproof (def) /2 → Dry Skin (def) ×125/100 → Rivalry → Iron Fist ×12/10 → Reckless (spot not found).
- After the base formula: burn (not Guts) → screens → weather → Flash Fire ×15/10 → +2 → crit ×2 (Sniper ×3) →
  Metronome item ×(10+n)/10 → roll → STAB (Adaptability ×2) → types → Filter / Solid Rock ×3/4 (SE, at least 1)
  → Expert Belt ×120/100 → Tinted Lens. Resist berries / Chilan: [SD] final modifier, `max(1, dmg // 2)`.
- Item boosts use [pp]'s integer x(100+effect_param)/100, never Showdown's 4096 chain.
- Accuracy (CheckMoveHitAccuracy): stages → Compound Eyes → Sand Veil → Snow Cloak → Hustle → Tangled Feet →
  Bright Powder / Lax Incense → Gravity. No Guard skips the roll and the semi-invulnerable check.
- Hit check: type check (Levitate, Scrappy, Wonder Guard) → accuracy → absorbing abilities (`_hit_outcome` →
  `absorb_move`).
- Speed (CompareBattlerSpeed): stages (Simple) → Swift Swim / Chlorophyll → Quick Feet or paralysis ÷4 → Slow
  Start ÷2 → Unburden ×2.
- Residual damage and heals use `BattleSystem_Divide` (at least 1); toxic is `Divide(max, 16) * n`.
- Status items run after every move for both actives (`_after_move_items`), on switch-in after the hazards, and
  at end of turn after Yawn.
- On-hit abilities (`on_hit_abilities`) run per hit after recoil, drain and the secondary effect, the KO hit
  included. Every 30% roll is `randint(0, 9) < 3`.

## Trainer AI constraints

- `expert_flag` routes status moves by what the move is for, not by which field is set: a
  volatile on the FOE goes to `expert_vol_status` (Swagger, Flatter: confusion + boost); a
  self-side volatile next to a boost is only a marker and goes to `expert_stat` (Defense Curl,
  Charge); a self volatile with no boost goes to `expert_vol_status` (Focus Energy). Don't
  special-case individual moves to fix routing.

## Search details

- MCTS is single-threaded ON PURPOSE. Parallel only inflated visit counts, and async rollout
  workers made select/expand as expensive as a rollout. Don't "optimize" this with threads or
  processes.
- Search tuning (`c`, `ROOT_C`, `terminal_iterations`) lives in
  `SearchEngine/models.py` and `my_mcts.py`. The code is the source of truth; ask before
  changing values. Keep `terminal_iterations` low enough to be reachable at tree depth.
- Continue from here starts from the node's snapshot on purpose, it exists for rare nodes with few visits. Replaying
  the path to rebuild the history doesn't work there: a rare step that needs a rare state before it gave no hit in
  30 s (Reporter Helen, depth 6, 24 visits). Only a last step whose move differs from the snapshot's visit runs again,
  capped at 100 ms, and the foe's PP is arithmetic (the root's minus what each picked move paid).
- The search has no risk term on purpose. A CVaR penalty was tested and removed (`README.md`,
  `NN_PLAN.md` Step 1a); risk comes from the price of a death in `evaluate_terminal`. `ROOT_C` is a
  larger `c` for the root only. `quality`'s CVaR15 column only reports battle results.

## Search / rollout constraints

- `rollout_pref` must not `continue` past status moves. That can empty the candidate list and
  crash.
- Weighted choice uses a linear scan over summed integer weights. It beats `random.choices`
  at small n.
- Don't re-roll the full status gate on every hit of a multihit move. Only check for a faint
  mid-sequence.

## Commands

- Coverage report (what trainers use, what the engine supports, `ENGINE_PLAN.md`'s `*` marks):
  `python -m DataBase.coverage`
- New MoveDB entries ([SD] gen4 data + the MOVES tab's numbers): `python -m DataBase.add_moves [--sheet
  workbook.xlsx] [--write] Move ...`; `--check` compares every MoveDB entry with what it would build
