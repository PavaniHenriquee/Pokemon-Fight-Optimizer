# Testing notes

Read before adding or changing tests, or re-blessing golden snapshots. Moved out of `CLAUDE.md`.

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
