# Nuzlock Battle Optimizer: CLAUDE.md

Solo, local-only hobby project. A decision-support tool for Nuzlocke runs: MCTS over a
from-scratch Gen IV battle engine. First target is Renegade Platinum
(trainers up to the 1st gym). Main goal is usable speed; code organization comes second.

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

## Layout

- `Engine/`: battle flow (`battle.py`), damage, status, helpers. All `@njit`.
- `Models/`: `pokemon.py`, `move.py`, `ability.py`, `item.py`, `trainer_ai.py`,
  `trainer_ai_helper.py`, `idx_const.py` (array layout), `helper.py` (enums as dataclasses).
- `DataBase/`: JSON databases (`PkDB`, `MoveDB`, `AbilitiesDB`, `ItemDB`, `TrainerDB`) plus the
  `*.py` name-to-int enums. `TrainerDB.json` is the source of truth for trainer teams and items.
- `SearchEngine/`: `my_mcts.py`, `models.py` (GameState, Node, UCB), `mcts_eval.py`
  (terminal eval, rollout heuristic), `helper.py` (pruning).
- `NeuralNetwork/`: feature extraction only. The network itself is planned, not built.
- `backend/`: FastAPI + WebSocket, MCTS in a background thread. `frontend/`: React + TS +
  Vite + Tailwind + shadcn/ui. `frontend/electron/`: the desktop app (`main.js` starts the
  backend on a free port, `preload.cjs`, `build_python.py` bundles Python for the installer).
- `UserData/box.json`: my saved Pokemon box (the installed app keeps its own copy in
  `%APPDATA%\Nuzlocke Optimizer`, seeded from this one on first launch).
- `tests/`: pytest suite. `battle_driver.py` (engine-only battle loop + fixed scenarios),
  `golden/engine_battles.json` (engine snapshots), `conftest.py` (fixtures, JIT off).
- `benchmarks/`: everything behind the numbers in `NN_PLAN.md`, as one command. Reports in
  `benchmarks/results/`. The home PC runs it; the i5-8400 machine only edits source.

## Commands

- Run everything: `dev.bat` (backend on :8000, Vite frontend)
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

## Generated / derived files: don't hand-edit

- `Models/constants.py` is AUTO-GENERATED by `generate_constants.py`. Edit the source classes,
  then regenerate.
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
- `TODO.txt` tracks implementation progress. Update checkboxes only if I ask.
- MCTS is single-threaded ON PURPOSE. Parallel only inflated visit counts, and async rollout
  workers made select/expand as expensive as a rollout. Don't "optimize" this with threads or
  processes.
- The `"Test"` trainer in `TrainerDB.json` and odd entries in `box.json` are test data.
- Search tuning (`c`, `ROOT_C`, `terminal_iterations`) lives in
  `SearchEngine/models.py` and `my_mcts.py`. The code is the source of truth; ask before
  changing values. Keep `terminal_iterations` low enough to be reachable at tree depth.
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

## Implementing moves (TODO.txt)

- Notation: no `*` = used by trainers up to Roark (do first), `*` = on my own Pokemon. `!` =
  check the Showdown handler and pokeplatinum before coding; `!!` or more = also write me a
  mechanics note and wait for my OK. `(B)` / `(E)` = add the `basic_flag` / `expert_flag` branch
  from pokeplatinum `trainer_ai/script.s` and Pokemow. The second moves section ("isn't used
  until 1st gym") is deferred.
- Group work by shared mechanism, not alphabetically. Per batch: mechanics note with sources →
  evidence for any bug it depends on, wait → engine, then AI → tests in the matching file →
  `pytest` + `-m jit` (+ `-m slow` if layout or turn flow changed) → tell me which TODO boxes
  can be ticked.

### Checklist when adding a move or mechanic (go through all of it)

1. Mechanics: Showdown inherits gen4 → gen5 → gen6 → base `data/moves.ts`, so check every
   layer; then pokeplatinum (battle code and `trainer_ai/script.s`). Numbers from the RP sheet.
2. Data: `MoveDB.json` entry and `MoveName` (`DataBase/MoveDB.py`), both alphabetical. Inserting
   shifts every later id → `python generate_constants.py`. A two-turn move needs `"charge": 1`
   (the `charge` flag alone does nothing). Check flags (`gravity`, `protect`, `sound`, ...).
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
    turns/HP change; `pytest`, `-m jit`, `-m slow`. Then list the TODO.txt boxes that can be
    ticked and the TODO comments that became outdated (remove them only when I ask).

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
- `VOL2_KEY_BITS` (3) is full; a 4th `VolStatus2` bit needs room in `node_key` first.

## Engine decisions (settled, don't re-litigate)

- Pokemow wins over pokeplatinum when they differ on the AI (Feint, Worry Seed's HP check, the
  Perish Song withdraw, Blizzard).
- Copied Gen IV quirks: the Rage glitch (`_rage_glitch`), Magnitude is 0 in the AI's damage
  calc, the Basic Levitate check ignores Gravity, Synchronize paralyzes Electric types.
- My calls: Fury Cutter has no 160 cap; Take Down recoil is at least 1; Sweet Kiss stays Normal;
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
- End of turn (Gen IV): side timers, weather, Gravity count down; weather damage for both
  actives; then per Pokemon Ingrain, Aqua Ring, Speed Boost, Leech Seed, poison/burn, Curse,
  bind, Uproar, Disable, Encore, Taunt, Yawn; then Perish Song. Speed order, a tie is a coin flip.
- My calls (abilities/items): Simple doubles accuracy/evasion stages; Quick Claw / Stall follow [SD gen4] (one
  20% roll per holder per turn, within the same priority); the Metronome item follows [pp] (cap 10, keyed in
  `node_key` k4); RP's AI does steal with Covet; the rollout counts a working opponent OHKO as a KO.
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

- AI: Expert Gravity reads the target's real ability and skips Magnet Rise;
  `expert_charge_invulnerable` skips the "target's last move isn't always-hit" check;
  pokeplatinum's Expert swaps the EVA_DOWN_2 / ACC_DOWN_2 logic (copy it when a -2
  accuracy/evasion move lands).
- AI, small [pp] differences no trainer up to Roark reaches: `basic_ability`'s Wonder Guard check
  reads the raw move type (Normalize ignored), and Natural Gift's berry type reaches its absorb
  checks ([pp] `LOAD_MOVE_TYPE` reads the data type); [pp] Basic_Main skips the immunity check for
  Guillotine / Sheer Cold, so into Wonder Guard the engine gives -12, [pp] 0; [pp] always knows my
  Shadow Tag / Magnet Pull / Arena Trap (no script check reads them yet).
- AI party type check (`party_effectiveness`, [pp] `BattleSystem_CalcEffectiveness`): no Iron Ball
  (not in ItemDB).
- AI: `sub_after_death` stage 2 doesn't copy [pp]'s stale-score quirk (a skipped or empty move slot
  still compares the previous `score`, at first the last stage 1 type score).
- The confusion self-hit has no weather, so Flower Gift's sun boost doesn't reach it
  (`early_returns` has no field state).
- Drill Run (not in MoveDB): RP puts it in Horn Drill's slot, so [pp] Basic_Main's
  `IfMoveEqualTo MOVE_HORN_DRILL` would skip its damage scoring if RP kept that script.
- Not in MoveDB yet: Spikes damage, Magnet Rise, Iron Ball, Rest, Snore, U-turn, Fly, Dive,
  Heal Block.
- Not handled: Klutz and Embargo ([pp] `Battler_HeldItem` returns no item for them); resist berries
  vs Substitute (no Substitute yet, [SD] skips the berry on a substitute); Covet / Thief failing on a
  defender whose Quick Claw activated ([pp] `BtlCmd_TryStealItem` wasn't found).
- Metronome can call moves whose mechanics aren't in yet; they run as their data says.
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
- UI: no copied ability, no "the AI knows this ability" marker, and the field's weather shows while
  Cloud Nine / Air Lock suppress it.
- Whether RP's ROM lets Soundproof block Disarming Voice is unknown (the engine says yes).
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
- Benchmarks: `quality` and the `tuning` stages share seeds (`100_000 * iters + i`), so re-running `quality`
  isn't an independent check of values `tuning` chose. `tuning`'s fresh-seed stage is.
- Benchmarks on the i5: at this repo's folder depth, `.numba_cache/benchmarks/...` reaches the 260
  character path limit and the compile fails. `PBO_CACHE_ROOT` set to a short folder gets around it.

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

## Frontend conventions

- Node popup HP shows bracket ranges ("50%-74%"), not exact values, because outcomes are
  grouped by bracket.
- Win probability is the primary metric. Visit counts are secondary and shouldn't compete
  visually with it.
- Types for backend payloads live in `frontend/src/types.ts`. Keep them in sync with
  `backend/serializer.py` and `backend/main.py`.

## Before finishing a task

- Run the project's checks: `pytest`, plus `pytest -m jit` if any `@njit` code changed.
- Summarize what changed, and list anything you noticed but did NOT change.
- Anything noticed but not fixed: tell me. If I don't say otherwise, add it to Known gaps.
