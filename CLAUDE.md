# Nuzlock Battle Optimizer: CLAUDE.md

Solo, local-only hobby project. A decision-support tool for Nuzlocke runs: MCTS over a
from-scratch Gen IV battle engine. First target is Renegade Platinum: singles battles up to the
Champion (done up to the 1st gym, the rest is `ENGINE_PLAN.md`). Main goal is usable speed; code
organization comes second.

## How to work with me

- Plan first. For anything beyond a one-line fix, describe the change and wait for my OK.
- Keep changes scoped to what I asked. No drive-by refactors, renames, formatting, or "cleanup".
- NEVER delete or rewrite existing code, comments, TODOs, or commented-out blocks unless I
  explicitly ask. If something looks wrong or unused, tell me and ask. Don't act on it.
- If you think you found a bug, explain the evidence and wait. Several things that look like
  bugs are intentional (see below).
- Keep diffs minimal and localized. Put explanations after the code, not as inline comments.
- If I push back on a diagnosis, re-check it and say plainly whether you were wrong.
- Validate architectural decisions with me before implementing them.
- Verify mechanics against the references (Bulbapedia, pret/pokeplatinum, Pokemow trainer AI
  page, Pokemon Showdown source) rather than memory. Bulbapedia returns 403 to automated
  fetches; use Showdown and pokeplatinum (raw.githubusercontent.com) and say which one a fact
  came from. Move numbers come from the Renegade Platinum MOVES sheet (CSV export, sometimes
  needs a login); mechanics stay Gen IV.
- Neural network work follows `NN_PLAN.md`: read it before touching `NeuralNetwork/`. Outside that work, ignore the folder.
- Engine work follows `ENGINE_PLAN.md`. At the start of a session read its Status section and the phase
  being worked on, not the whole file.
- The neural network is on hold until `ENGINE_PLAN.md` is finished. Until then don't open `NN_PLAN.md`,
  even when a benchmark, the README or a line below points to it. If engine work seems to need it, or a
  layout change breaks `NeuralNetwork/`, stop and ask me.

## Layout

- `Engine/`: battle flow (`battle.py`), damage, status, helpers. All `@njit`.
- `Models/`: `pokemon.py`, `move.py`, `ability.py`, `item.py`, `trainer_ai.py`,
  `trainer_ai_helper.py`, `idx_const.py` (array layout), `helper.py` (enums as dataclasses).
- `DataBase/`: JSON databases (`PkDB`, `MoveDB`, `AbilitiesDB`, `ItemDB`, `TrainerDB`) plus the
  `*.py` name-to-int enums. `TrainerDB.json` is the source of truth for trainer teams and items.
  `PkDB.json`'s `learnset` and `tutor` (what the Move Tutor and Special Tutors lists teach it, kept for the
  frontend) come from the sheet's DEX tab. `support.py`: what a trainer's team needs that the engine can't
  run yet (`NOT_IMPLEMENTED`, `TRAINER_ITEMS`).
  `EncounterDB.json`: what can be met per location, for the Tracker tab, plus the evolution lines for
  its species clause. A location is the summary's met location ([pp] `header.json`'s `locationName`),
  not the sheet's block. `ItemLocationDB.json`: where each item and TM/HM is picked up, for the
  Tracker's Items tab, by those locations in story order (one entry per pickup). No plates: they only come
  after the Champion, when a Nuzlocke is over. Of the key items it keeps
  only the rods: with HM03 they unlock the Pokémon tab's rod and Surf tables (`METHOD_NEEDS` in
  `lib/nuzlocke.ts`). A locked table is dimmed and left out of "Can still catch", but stays pickable.
- `SearchEngine/`: `my_mcts.py`, `models.py` (GameState, Node, UCB), `mcts_eval.py`
  (terminal eval, rollout heuristic), `helper.py` (pruning).
- `NeuralNetwork/`: feature extraction only. The network itself is planned, not built.
- `backend/`: FastAPI + WebSocket, MCTS in a background thread. `frontend/`: React + TS +
  Vite + Tailwind + shadcn/ui. `frontend/electron/`: the desktop app (`main.js` starts the
  backend on a free port, `preload.cjs`, `build_python.py` bundles Python for the installer).
- `UserData/box.json`: my saved Pokemon box, death box included (`dead` on an entry). The installed
  app keeps its own in `%APPDATA%\Nuzlocke Optimizer`, empty on first launch (the installer never
  bundles `UserData`). `UserData/nuzlocke.json`:
  the run in the Tracker tab (gitignored, the installed app keeps it in the same folder).
- `tests/`: pytest suite. `battle_driver.py` (engine-only battle loop + fixed scenarios),
  `golden/engine_battles.json` (engine snapshots), `conftest.py` (fixtures, JIT off).
- `benchmarks/`: everything behind the numbers in `NN_PLAN.md`, as one command. Reports in
  `benchmarks/results/`. The home PC runs it; the i5-8400 machine only edits source.

## Commands

- Run everything: `dev.bat` (backend on :8000, Vite frontend). It sets `PBO_SEED=37`, so its searches
  repeat; without `PBO_SEED` (the installed app, `electron:dev`) they're random.
- Desktop app (in `frontend/`): `npm run electron:dev` (Vite + Electron + the .venv backend on a
  free port, no backend hot reload); `npm run electron:preview` loads the built `dist/` instead.
- Installer (in `frontend/`): `npm run dist` → `frontend/release/Nuzlocke Optimizer Setup x.y.z.exe`
  (fetches sprites, builds, bundles Python with the .venv's package versions, runs electron-builder)
- Offline sprites: `python fetch_sprites.py` → `frontend/public/sprites/` (gitignored, skips files
  it has). `npm run dist` runs it.
- Benchmark / profile: `python main.py` (see the run\_\* functions)
- Full benchmarks: `python -m benchmarks.run quick` (search speed, network kernels, ~1.5 min), `all`
  (~8 min) or section names; `--smoke` only checks they still work. Extras only when named:
  `compile`, `quality25k`, `tuning` (the search's `c` values, `NN_PLAN.md` Step 1a, ~2 h). `--long` gives `NN_PLAN.md`'s full tables (~1.5 h). Each report records
  the machine and the change against earlier runs of the same length. The `training` section needs
  `pip install -r requirements-train.txt`.
- Debuggable, non-JIT run: set `NUMBA_DISABLE_JIT=1`
- Numba cache: the backend turns it on (`Utils/jit_cache.py`, `.numba_cache/backend/<hash of the
sources>`, `NUMBA_CACHE_ON=0` opts out; the installed app uses `%LOCALAPPDATA%`). `python main.py`
  runs uncached unless `NUMBA_CACHE_ON=1` (see `Utils/jit.py`); pytest runs with JIT off.
- After changing any enum or index class (`Pok`, `Move`, `Flags`, `Sec`, `Field`, `Item`,
  `MoveName`, `AbilityNames`, etc.): run `python generate_constants.py`
- Tests: `pytest` (fast, ~15s, JIT off), `pytest -m jit` (compiled engine + MCTS, ~2 min
  after any source change, seconds otherwise), `pytest -m slow` (long fuzz, ~1 min). Pylint
  isn't installed in the venv.
- Piping or redirecting `python main.py` on Windows needs `PYTHONIOENCODING=utf-8` (the `→` in
  `print_best_path` breaks cp1252)
- Re-bless engine snapshots after an intended engine change:
  `pytest tests/test_engine_golden.py --update-golden`, then review the JSON diff
- Refresh the encounter data from the RP sheet: `python -m DataBase.import_encounters [encounters.csv stats.csv]`
- Refresh the trainers from the RP sheet's split tabs (xlsx, ~19 MB):
  `python -m DataBase.import_trainers [workbook.xlsx]`, then `python fetch_sprites.py` for any new sprite
- Refresh the item locations (iTEMS/TMs tab, after the encounters, it reads their locations):
  `python -m DataBase.import_items [items.csv]`, then `python fetch_sprites.py` for any new icon
- Refresh PkDB's learnsets and tutor moves (DEX tab): `python DataBase/import_learnsets.py [dex.csv]`
- Coverage report (what trainers use, what the engine supports, `ENGINE_PLAN.md`'s `*` marks):
  `python -m DataBase.coverage`
- New MoveDB entries ([SD] gen4 data + the MOVES tab's numbers): `python -m DataBase.add_moves [--sheet
  workbook.xlsx] [--write] Move ...`; `--check` compares every MoveDB entry with what it would build

## Generated / derived files: don't hand-edit

- `Models/constants.py` is AUTO-GENERATED by `generate_constants.py`. Edit the source classes,
  then regenerate.
- `DataBase/EncounterDB.json` is generated by `DataBase/import_encounters.py`. A wrong location,
  table or evolution line is fixed there (`MET_ALIAS`, `HANDED_LEFT`, `EVOLUTION_FIXES`), then re-imported.
- `DataBase/TrainerDB.json` is generated by `DataBase/import_trainers.py`. A wrong value, class or sprite is
  fixed there (`SHEET_FIXES`, `CLASS_FIXES`, `CLASS_SPRITE`), then re-imported.
- `DataBase/ItemLocationDB.json` is generated by `DataBase/import_items.py`. A place or note it doesn't
  know is fixed there (`PLACE_ALIAS`, `PLACED_AFTER`, `NOTES`, `AREAS`), then re-imported.
- Sizes and offsets in `idx_const.py` and `NeuralNetwork/models.py` are derived with `len()` or
  arithmetic from name-tuples. Don't replace them with hand-typed literals.

## Numba rules (hot path: everything `@njit`)

- Statically inferrable types only. No `None` sentinels, no `isinstance`, no Python sets (use
  tuples), no `max(..., key=lambda)`, no variable-length list returns.
- Use fixed-size numpy buffers (`np.empty(N)` plus a counter) and return `buf[:n]`.
- Module-level numpy arrays are read-only inside `@njit`; allocate locally.
- Avoid numpy on very small arrays (about 6 elements or fewer). Plain loops are faster.
- Use `from Utils.jit import njit`, never `numba.njit` directly.
- `parallel=True` is counterproductive here.
- Numba has its own RNG, separate from Python's and NumPy's. Seed it through an `@njit`
  function (see `_seed_numba`).
- Every njit function body compiles ahead of running, including untaken branches. Don't
  reference names or constants that don't exist yet.

## Array architecture

- The whole battle state is one flat `int32` `battle_array`: 12 Pokemon blocks (mine 0-5,
  opponent 6-11) followed by the field block. Layout lives in `idx_const.py`.
- Slices of `battle_array` are VIEWS, so writing to them mutates the state. Reassign
  `current_pokemon` explicitly after switches within the same turn.
- `clone()` once per MCTS iteration at the top, not inside `step()`.
- Forced/locked states (charge, recharge, Bide, and the `LOCKED_MOVE` locks like Rollout and
  Uproar) loop inside `step()` and are never exposed as decision nodes.
- `VolStatus` is full (2^30 is the last bit under the int32 sign bit). New volatiles go in
  `VolStatus2` (`Pok.VOL_STATUS2`).
- Field state reaches the hot path as plain arguments, like `weather`: the defender's side
  condition mask (`def_side`) and a `gravity` bool.

## Intentional behavior (not bugs)

- The trainer AI mirrors the real Gen IV AI, quirks included. It cheats (knows my item, HP,
  and `my_last_move` rules), and `sub_after_death` implements the 255 damage overflow bug on
  purpose. Source of truth: pret/pokeplatinum and Pokemow.
- Commented-out blocks in `ability.py`, `idx_const.py`, and `move.py` are deliberately parked
  for later. TODO comments are my roadmap. Leave them.
- `ENGINE_PLAN.md` tracks implementation progress. Update its checkboxes and Status only if I ask.
  `TODO.txt` is the finished list up to the 1st gym, kept as a record: don't edit it.
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
  bind, Uproar, Disable, Encore, Taunt, Yawn; then Perish Song. Speed order, a tie is a coin flip.
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

## Known gaps (not done yet)

They live in `KNOWN_GAPS.md`, grouped by area. Before working on a move, item, ability, AI branch or UI area,
grep it for the names involved. New gaps go there, next to the ones they belong with.

## Trainer AI constraints

- `expert_flag` routes status moves by what the move is for, not by which field is set: a
  volatile on the FOE goes to `expert_vol_status` (Swagger, Flatter: confusion + boost); a
  self-side volatile next to a boost is only a marker and goes to `expert_stat` (Defense Curl,
  Charge); a self volatile with no boost goes to `expert_vol_status` (Focus Energy). Don't
  special-case individual moves to fix routing.

## Testing

- The suite runs with `NUMBA_DISABLE_JIT=1` (set in `conftest.py`), so Python's `random`
  drives every roll and `random.seed` makes tests reproducible. Typing errors in `@njit` code
  only show up in `pytest -m jit`; run it whenever njit code changed.
- `test_jit_smoke.py` runs in a subprocess with its own Numba cache under
  `.numba_cache/tests/<hash of sources>`. Numba's cache doesn't notice edits to callees in
  other files, so the hash forces a clean compile on any change. It seeds Numba's RNG itself.
- Golden snapshots (`test_engine_golden.py`) are ENGINE ONLY: `battle_driver.py` uses the
  engine and trainer AI, never `SearchEngine/`. They should only change when implementing a move
  or fixing a bug; any RNG call-order change moves them too. Changing a scenario in
  `battle_driver.py` also changes its snapshot. A layout change (new slot, `MoveName` shift)
  moves every hash but not turns/HP, so after a re-bless compare turns and HP against the old
  file to find the real outcome changes and explain each one.
- Search tests are structural only (no snapshots, no tuning values asserted) because the search
  is still changing.
- `test_known_bugs.py` holds strict xfails that assert the correct mechanic. When one gets
  implemented/fixed it fails with XPASS(strict): move it to the matching test file without the
  marker. `UNSUPPORTED_MOVES` in `test_database.py` is the MoveDB equivalent: those moves must
  still fail to convert, and `test_move_converts` fails once one converts, telling you to drop it.
- Database tests loop over every entry inside one test and list all the bad entries in the
  failure message, instead of one parametrized test per entry.
- Backend tests redirect `_BOX_PATH` to a temp file; never let a test write the real
  `UserData/box.json`.
- Fuzz invariants (`test_battle.py`): during the death phase after a double KO the opponent's
  active can be fainted; its replacement waits for `switch_in_action`. That's expected. The same
  goes for the Baton Pass phase when the foe fainted before my Baton Pass (e.g. a confusion
  self-hit); it's replaced at the end of the paused turn.

## Code conventions

- Import from where a thing is defined, not from wherever it's reachable. Put shared constants
  in a neutral module to break circular imports.
- Pylint config is in `.pylintrc`. Follow it and don't add new disables without asking.
- Trainer data belongs in `TrainerDB.json`, never in UI state.
- A rival variant's `if_starter` / `if_player` come from the sheet's split tabs (ROARK SPLIT to CHAMPION SPLIT). Never read them
  off the key's `-P/-T/-C`: that letter is your starter for Barry only (`Lucas 1-P` is met if you chose
  Chimchar).
- Species clause: a line is taken by the starter, a tracker row marked Caught or Dead, or anything in
  the PC box or death box. Missed doesn't take it. A Pokemon in the box with no tracker row can still
  be logged once. Deaths sync both ways by line and save at once, and so does everything done on the
  Tracker tab (it has no Save button); other box edits, party edits included, wait for Save or a search
  starting.
- Tracker and box: picking a Pokemon opens `BoxEditor` as a new catch, storing it adds the box entry and
  the row together, Cancel logs nothing. A line already in the box is only logged, no popup. Clicking a
  caught one edits its box entry, where the species changes only through the evolve buttons (`evolutions` in
  EncounterDB, from the STATS tab), and so does a right-click in the box. Clearing a row also
  takes it out of the box and party. A box entry and its party copy (matched by name) follow each other's
  edits, held item included.
- A new catch starts from `catchDraft` (`lib/nuzlocke.ts`): the level is the low end of the table clicked,
  the moves follow [pp] `BoxPokemon_SetDefaultMoves` and refill with the level until a move is edited, a
  move not in MoveDB is left out (it would stop a search with a `KeyError`), and the ability stays empty
  when the species has two.
- `"genderless": true` in `PkDB.json` comes from [SD] `gender: "N"` and [pp] `GENDER_RATIO_NO_GENDER`, which
  agree on every species. The box popup offers only "—" for those and only ♂ / ♀ for the rest.
- The box stays `null` until the real box has loaded (`lib/useBox.ts`), and an unreadable `box.json` or
  `nuzlocke.json` is an error, never an empty answer: both are saved whole, so an empty answer would
  overwrite the real file.

## Frontend conventions

- Node popup HP shows bracket ranges ("50%-74%"), not exact values, because outcomes are
  grouped by bracket.
- Win probability is the primary metric. Visit counts are secondary and shouldn't compete
  visually with it.
- The outcome pane has one dropdown per thing the foe did, so a real game's state is easy to find. Only the view splits
  them: the search still merges moves that leave the same state, and a state shows under each move that can reach it.
  The move picked stays on the path (`pathMoves`) and Continue uses it.
- Types for backend payloads live in `frontend/src/types.ts`. Keep them in sync with
  `backend/serializer.py` and `backend/main.py`.

## Before finishing a task

- Run the project's checks: `pytest`, plus `pytest -m jit` if any `@njit` code changed.
- Summarize what changed, and list anything you noticed but did NOT change.
- Anything noticed but not fixed: tell me. If I don't say otherwise, add it to `KNOWN_GAPS.md`.
