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
  bugs are intentional.
- Keep diffs minimal and localized. Put explanations after the code, not as inline comments.
- If I push back on a diagnosis, re-check it and say plainly whether you were wrong.
- Validate architectural decisions with me before implementing them.
- Verify mechanics against the references (pret/pokeplatinum [pp], Pokemon Showdown source [SD],
  Pokemow trainer AI page) rather than memory, and say which one a fact came from. Bulbapedia
  returns 403 to automated fetches. Move numbers come from the Renegade Platinum MOVES sheet;
  mechanics stay Gen IV.
- Engine work follows `ENGINE_PLAN.md`. At the start of a session read its Status section and the
  phase being worked on, not the whole file.
- The neural network is on hold until `ENGINE_PLAN.md` is finished. Until then ignore
  `NeuralNetwork/` and don't open `NN_PLAN.md`, even when something points to it. If engine work
  seems to need it, or a layout change breaks `NeuralNetwork/`, stop and ask me.

## Notes files: read the matching one before working in its area

- `docs/ENGINE_NOTES.md`: the checklist for adding a move or mechanic, rules for abilities and items,
  settled engine decisions (don't re-litigate them), the [pp] mechanics order, trainer AI routing,
  search / rollout constraints. Read before any engine, AI or search change.
- `docs/TESTING_NOTES.md`: golden snapshots, the JIT smoke test, `test_known_bugs.py`, fuzz invariants.
  Read before adding or changing tests or re-blessing.
- `docs/APP_NOTES.md`: data files, import / installer / benchmark commands, Tracker and box rules,
  frontend conventions. Read before frontend, backend, Tracker or database-import work.
- `KNOWN_GAPS.md`: what isn't done yet, by area. Before working on a move, item, ability, AI
  branch or UI area, grep it for the names involved. New gaps go there.

## Layout

- `Engine/`: battle flow (`battle.py`), damage, status, helpers. All `@njit`.
- `Models/`: `pokemon.py`, `move.py`, `ability.py`, `item.py`, `trainer_ai.py`,
  `trainer_ai_helper.py`, `idx_const.py` (array layout), `helper.py` (enums as dataclasses).
- `DataBase/`: JSON databases plus the `*.py` name-to-int enums. `TrainerDB.json` is the source of
  truth for trainer teams and items. `support.py`: what the engine can't run yet.
- `SearchEngine/`: `my_mcts.py`, `models.py` (GameState, Node, UCB), `mcts_eval.py`
  (terminal eval, rollout heuristic), `helper.py` (pruning).
- `backend/`: FastAPI + WebSocket, MCTS in a background thread. `frontend/`: React + TS +
  Vite + Tailwind + shadcn/ui, `frontend/electron/` is the desktop app.
- `UserData/`: my box (`box.json`) and Tracker run (`nuzlocke.json`). Never let a test write them.
- `tests/`: pytest suite (JIT off). `benchmarks/`: reports in `benchmarks/results/`.

## Commands

- Run everything: `dev.bat` (backend on :8000, Vite frontend, `PBO_SEED=37`).
- Tests: `pytest` (~15s, JIT off), `pytest -m jit` (compiled engine + MCTS, ~2 min after a source
  change), `pytest -m slow` (long fuzz, ~1 min). Pylint isn't installed in the venv.
- After changing any enum or index class (`Pok`, `Move`, `Flags`, `Sec`, `Field`, `Item`,
  `MoveName`, `AbilityNames`, etc.): `python generate_constants.py`
- Re-bless engine snapshots after an intended engine change:
  `pytest tests/test_engine_golden.py --update-golden`, then review the JSON diff
- Debuggable, non-JIT run: set `NUMBA_DISABLE_JIT=1`
- Benchmark / profile: `python main.py` (piping it on Windows needs `PYTHONIOENCODING=utf-8`);
  `python -m benchmarks.run quick` (~1.5 min).

## Generated / derived files: don't hand-edit

- `Models/constants.py` (from `generate_constants.py`), and `EncounterDB.json`, `TrainerDB.json`,
  `ItemLocationDB.json` (from `DataBase/import_*.py`: fix the importer, then re-import).
- Sizes and offsets in `idx_const.py` and `NeuralNetwork/models.py` are derived with `len()` or
  arithmetic from name-tuples. Don't replace them with hand-typed literals.

## Numba rules (hot path: everything `@njit`)

- Statically inferrable types only. No `None` sentinels, no `isinstance`, no Python sets (use
  tuples), no `max(..., key=lambda)`, no variable-length list returns.
- Use fixed-size numpy buffers (`np.empty(N)` plus a counter) and return `buf[:n]`.
- Module-level numpy arrays are read-only inside `@njit`; allocate locally.
- Avoid numpy on very small arrays (about 6 elements or fewer). Plain loops are faster.
- Use `from Utils.jit import njit`, never `numba.njit` directly. `parallel=True` is counterproductive.
- Numba has its own RNG. Seed it through an `@njit` function (see `_seed_numba`).
- Every njit function body compiles ahead of running, including untaken branches. Don't
  reference names or constants that don't exist yet.

## Array architecture

- The whole battle state is one flat `int32` `battle_array`: 12 Pokemon blocks (mine 0-5,
  opponent 6-11) followed by the field block. Layout lives in `idx_const.py`.
- Slices of `battle_array` are VIEWS, so writing to them mutates the state. Reassign
  `current_pokemon` explicitly after switches within the same turn.
- `clone()` once per MCTS iteration at the top, not inside `step()`.
- Forced/locked states (charge, recharge, Bide, the `LOCKED_MOVE` locks) loop inside `step()`
  and are never exposed as decision nodes.
- `VolStatus` is full. New volatiles go in `VolStatus2` (`Pok.VOL_STATUS2`).
- Field state reaches the hot path as plain arguments, like `weather`, `def_side`, `gravity`.

## Intentional behavior (not bugs)

- The trainer AI mirrors the real Gen IV AI, quirks and cheating included (`sub_after_death`'s 255
  overflow bug is on purpose). Source of truth: pret/pokeplatinum and Pokemow.
- Commented-out blocks in `ability.py`, `idx_const.py`, and `move.py` are deliberately parked
  for later. TODO comments are my roadmap. Leave them.
- Update `ENGINE_PLAN.md`'s checkboxes and Status only if I ask. Don't edit `TODO.txt`.
- MCTS is single-threaded ON PURPOSE, and the search has no risk term on purpose. Don't
  "optimize" it with threads or processes.
- Search tuning (`c`, `ROOT_C`, `terminal_iterations`) lives in `SearchEngine/models.py` and
  `my_mcts.py`. Ask before changing values.

## Code conventions

- Import from where a thing is defined, not from wherever it's reachable. Put shared constants
  in a neutral module to break circular imports.
- Pylint config is in `.pylintrc`. Follow it and don't add new disables without asking.
- Golden snapshots should only change when implementing a move or fixing a bug; new RNG calls run
  only when their ability/item is present. Explain every turns/HP change after a re-bless.

## Before finishing a task

- Run the project's checks: `pytest`, plus `pytest -m jit` if any `@njit` code changed.
- Summarize what changed, and list anything you noticed but did NOT change.
- Anything noticed but not fixed: tell me. If I don't say otherwise, add it to `KNOWN_GAPS.md`.
