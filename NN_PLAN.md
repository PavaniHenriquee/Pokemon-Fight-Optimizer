# Neural Network: Implementation Plan

Plan approved 2026-11-05.

## How to use this file across sessions

- Start a session with: "Read `NN_PLAN.md` and `CLAUDE.md`, then do Step N."
- Steps run in order. Each starts with a short note of what will change and waits for your OK (CLAUDE.md), and ends with its checks run and its notes written here.
- When a step lands, tick its box and add its notes, deviations and measured numbers. Anything noticed but not fixed goes in **Discoveries**.
- A *gate* is a measured check that decides whether the next step is worth doing. Write the result here and wait for your call. Stopping at a gate is a fine outcome: rollouts keep working, and nothing depends on the network until Step 9.
- No step changes `Engine/`, so golden snapshots must not move. If they do, something is wrong.

| Step | Topic                                              | Status |
| ---- | -------------------------------------------------- | ------ |
| 0    | This file and pointers                             | [x]    |
| 1    | Renegade Platinum learnsets in PkDB                | [x]    |
| 1b   | Move `_select_expand`'s hot parts into njit        | [ ]    |
| 2    | Scenario sampler, arena, baseline numbers          | [ ]    |
| 3    | State encoder (replaces the shell), coverage test  | [ ]    |
| 4    | njit inference and weights file                    | [ ]    |
| 5    | Data generation                                    | [ ]    |
| 6    | Training, offline check (Gate 1)                   | [ ]    |
| 7    | Search integration, full-battle check (Gate 2)     | [ ]    |
| 8    | Improvement loop (Gate 3)                          | [ ]    |
| 9    | Ship: backend, UI, installer, docs                 | [ ]    |
| 10   | Policy head and PUCT (Gate 4)                      | [ ]    |

## Goal

Better decisions in the same search time, especially in fights that don't converge today. The target is that search with the network at 200 iterations per decision plays as well as today's search at 1000. That is the "usable speed" claim, measured in full battles rather than iterations per second.

Out of scope: threaded or batched inference (MCTS stays single-threaded), opponent modelling (the trainer AI is known), and trainers past Roark until the engine has them.

## What the measurements say (2026-11-05)

Machine: i5-8400 (6 cores, AVX2), 7.9 GB RAM, integrated GPU only, 309 GB free disk. Python 3.14.4, numba 0.65.1. You also work on another computer, with different package versions, so re-check timings, worker counts and RAM limits on whichever machine does the training.

Test fights, using TrainerDB teams:

- **Roark, good team**: Grotle 18, Prinplup 18, Psyduck 17, Makuhita 17.
- **Roark, weak team**: Diglett, Piplup, Geodude, Makuhita, Psyduck, Torchic at 16, with their trainer movesets.
- **Barry 2-P**: the first 3 of the weak team at 14.
- **Dallas**: the first 2 of the weak team at 12, against Youngster Dallas 1.

**Rollouts aren't where the time goes.** Backend loop and stop rule, 30 s limit:

| Fight           | Iter/s | select/expand | rollout | backprop | Converged?                         |
| --------------- | ------ | ------------- | ------- | -------- | ---------------------------------- |
| Roark, weak     | 2,170  | 329 µs (72%)  | 116 µs  | 14 µs    | No (best action 12% of visits)     |
| Barry 2-P       | 5,188  | 146 µs (76%)  | 29 µs   | 17 µs    | No (best action 77% of visits)     |
| Dallas          | 11,546 | 70 µs (82%)   | 6 µs    | 9 µs     | Yes, 1.3 s                         |

**Rollouts are where the quality goes.** Win rate / mean `evaluate_terminal` value from the start of the fight. Rollouts are 2,000 samples. MCTS columns are full battles played with that search budget, using today's rollouts, with battle counts in brackets (small samples, so read them as rough):

| Fight       | Rollout `heuristic_prob=0.48` (today) | Rollout `heuristic_prob=1.0` | MCTS 200 it/decision | MCTS 1000 it/decision |
| ----------- | ------------------------------------- | ---------------------------- | -------------------- | --------------------- |
| Roark, good | 25% / 0.126                           | 61% / 0.411                  | 76% / 0.377 (17)     | 100% / 0.756 (14)     |
| Roark, weak | 0.8% / 0.002                          | 27% / 0.106                  | 4% / 0.006 (24)      | 29% / 0.059 (7)       |
| Barry 2-P   | 9% / 0.049                            | 17% / 0.097                  | 38% / 0.187 (91)     | 58% / 0.278 (19)      |
| Dallas      | 85% / 0.569                           | 99% / 0.593                  | 100% / 0.985 (360)   | 100% / 0.997 (105)    |

What that shows:

- Today's rollouts read far below what the search actually achieves, because 52% of their moves are random. On Roark with a good team they say 25%, while 1000-iteration play won all 14 battles.
- When nearly every rollout loses, leaf values are all about 0 and the search can't separate actions. That's the 12% figure above, and the weak-team fight is where a plain heuristic (27%) beats 200-iteration search (4%).
- `heuristic_prob=1.0` costs the same and wins more, but it ignores deaths: on Dallas it wins 99% with 0.92 deaths per win, while search wins 100% with 0.00-0.03. It stays unused (see Design decisions); the column is kept as a measurement.
- The bigger budget buys a lot, so there is real room for a better leaf value to gain at low budgets.

**A network in njit is affordable:**

| Piece                                                        | Measured                 |
| ------------------------------------------------------------ | ------------------------ |
| Dense layer 128x128, plain `@njit`                           | 13.4 µs                  |
| Same with `fastmath=True`                                    | 1.3 µs                   |
| Candidate network (64k parameters), full forward             | 47 µs                    |
| Same, static move part cached per search                     | 15 µs                    |
| Flat MLP on the shell's 2315 inputs (660k parameters)        | 24 µs                    |
| Shell `to_nn_input`                                          | 2.8 µs                   |
| 20 damage calcs                                              | 2.5 µs (125 ns each)     |
| Numba call overhead, 1 array / tuple of 12                   | 0.3 / 2.2 µs             |
| Engine compile without cache                                 | 116 s, 790 MB RSS        |
| Search tree memory, Roark weak team                          | about 5.9 KB/iteration   |
| Data rate at 200 it/decision, per process                    | 11-55 decisions/s        |
| Data rate at 1000 it/decision, per process                   | 6-14 decisions/s         |
| torch CPU wheel for Python 3.14 on Windows (pip dry run)     | 2.15.0+cpu, 129 MB       |

So a leaf costs about the same as a rollout: cheaper in long fights, slower in short ones that already converge in about a second.

**The shell's drift.** It reads 23 of 54 Pokemon slots, 19 of 72 move slots, 0 of 12 item slots, 15 of 34 field slots and 9 of 31 `VolStatus` bits. It has no `VolStatus2`, side conditions, Gravity, locks or timers, and no Baton Pass phase. It still imports and compiles.

## Design decisions

- **2026-11-05 (your call): `heuristic_prob` stays 0.48.** Rollouts keep real randomness, so results improve in quality and aren't shaped by your own view of the game, which is what the heuristic encodes. Every comparison in this plan is against today's rollouts. Don't propose raising it or adding hand-written preferences to strengthen the search. A network fits this: its values are learned from search results, and Step 8's loop reduces the rollouts' share further.
- **2026-11-05 (your call): the Renegade Platinum sheet is the source of truth for game data, Complete version.** That's the COM line in its DEX tab (OLD is vanilla, CLA is the Classic patch; 129 species differ between CLA and COM on stats).
- **2026-11-05: the value head outputs a distribution, not a mean.** Seven classes: loss, or win with 0-5 *more* deaths. `_backprop` fills the histogram that `cvar_from_hist` reads, and a mean would erase the tail CVaR exists to penalize. `value`, `win` and `dead` are computed at run time from the classes with `evaluate_terminal`'s formula (current turn for the small turn penalty), so changing its numbers, `risk_lambda` or `alpha` needs no retraining. Classes that can't happen given who is alive get masked.
- **2026-11-05: backprop adds the whole distribution to the histogram** instead of sampling one outcome, which avoids putting sampling noise back. `stats` is already float and `cvar_from_hist` handles fractional counts. `Node.wins` and `Node.dead` become floats, and the serializer already sends them as plain numbers.
- **2026-11-05: inference is hand-written njit, no torch or ONNX at run time.** Measured 15-47 µs, nothing added to the installer, no RNG, and single-leaf calls suit a single-threaded search. Weights are one flat `float32` array passed as an argument, like `battle_array`. Never a module global: Numba freezes globals into compiled code and its cache doesn't see them. Kernels need `@njit(fastmath=True)` (10x, measured).
- **2026-11-05: shared encoders, about 64k parameters** (DeepSets style). Move features go through a move encoder and are pooled per Pokemon; Pokemon features plus that pool go through a Pokemon encoder; my active, foe active, my bench mean, foe bench mean and field features go through 2 hidden layers to the 7 classes. Candidate sizes: move 56→32, Pokemon 104→64, then 296→128→128→7. Bench order means nothing and teams are 1-6 Pokemon, so a flat MLP would have 10x the parameters and need far more data, on a CPU-only machine with 7.9 GB.
- **2026-11-05: the encoder gets engine-computed matchups.** Damage as % of HP for my moves against the foe's active and the reverse, using the helpers `rollout_pref` already uses (`effective_weather`, `normalized_type`, `ohko_fails`) with a fixed roll so encoding draws no RNG. At 125 ns per calc the network doesn't have to relearn the type chart.
- **2026-11-05: move, ability and item ids become embeddings through a name vocabulary stored in the weights file**, remapped at load, so alphabetical id shifts don't break a model.
- **2026-11-05: a coverage table stops the rot.** Every `Pok`, `Move`, `Flags`, `Sec`, `Item` and `Field` name and every `VolStatus`, `VolStatus2` and `SideCondition` bit is listed as encoded or deliberately ignored, and a test fails on any unlisted name. This adds one line to the checklist for new moves.
- **2026-11-05: training is PyTorch CPU, dev only**, in `requirements-train.txt`. It is not in `RUNTIME` in `build_python.py`, and the backend never imports it.
- **2026-11-05: labels come from search-played battles.** Rollout labels are only for bringing up the pipeline, because rollouts don't value avoiding deaths.
- **2026-11-05: data is stored raw.** `battle_array` plus raw outcomes (class, not `value`) in compressed shards under `.nn_data/` (gitignored). 17 KB per state uncompressed is fine for disk, and RAM only ever holds one shard. Encoding happens on the fly, so encoder changes don't invalidate data. Shards are stamped with a layout hash and refused on mismatch.
- **2026-11-05: data generation runs as independent single-threaded processes** with no shared tree, so the single-threaded MCTS rule stands. 4 workers on this RAM, never while training. The parent compiles to the Numba cache first, otherwise each worker pays 116 s and 790 MB.
- **2026-11-05: rollouts stay.** They remain the default until a gate says otherwise, and the fallback when weights are missing or don't match. Nothing is removed.

## Steps

### Step 1: Renegade Platinum learnsets in PkDB

Landed 2026-11-05. To refresh: `python DataBase/import_learnsets.py` (add a CSV path if the sheet asks for a login).

Source: Google sheet "Pokemon Renegade Platinum - Documentation", id `1G3MNevhLmW1sKYluM4WT9TM1RqrTAi1c4lIdTfeU-Jg`, DEX tab, `.../export?format=csv&gid=1888238811` (worked without a login on 2026-11-05).

**Deviation:** the plan said the LEARNSETS tab, but DEX is where the COM lines live and it has that tab's errors right (see Discoveries). The two agree on 502 of 505 species.

Format, checked: 505 blocks of 40 rows, name in column 1, level and move in columns 13 and 14, between `Level Up :` and `TMs HMs :`. Typing, stats and abilities have OLD / CLA / COM lines, but learnsets have a single list per species in both tabs, so there is no version to choose. The sheet doesn't label that list as a patch.

Parser traps:

- `(!)` and `(!!)` suffixes mark changed entries.
- Invisible Unicode (U+180E and similar) marks changes, so normalize before comparing.
- The gviz endpoint blanks numeric cells in mixed columns. Use the CSV export.
- 23 species names need an alias, listed in the importer (`Nidoran ♀` → `Nidoran_f`, `Deoxys (Attack)` → `Deoxys_attack`, `Rotom (Spin)` → `Rotom_fan`, `Rotom (Cut)` → `Rotom_mow`, ...).

What landed:

- `DataBase/import_learnsets.py` adds `"learnset": [[1, "Tackle"], [5, "Vine Whip"], ...]` to each species, right before `weight`, with one `[level, move]` per line. That's the format Prettier keeps when your editor formats `PkDB.json` on save (a single entry stays inline), so saving the file changes nothing, and a test holds the importer to it. The diff only adds lines and a rerun is byte-identical. The output stays ASCII, because `DataBase/loader.py` reads with the platform encoding. It stops without writing if the layout changes, the species don't match PkDB exactly, or anything but the learnsets would change.
- Every move is kept, in MoveDB's spelling when it exists, so the data stays complete as MoveDB grows. Filtering happens in the sampler.
- Six species corrected in PkDB to their COM lines, all of which held Classic or vanilla numbers or a typo:
  - Azumarill: SpA 60 → 80
  - Sudowoodo: HP 95 → 90
  - Qwilfish: Spe 85 → 95
  - Delibird: HP 65 → 45
  - Mothim: Atk 94 → 70, SpA 94 → 110, Spe 66 → 100
  - Cresselia: Def 110 → 120, SpD 120 → 130
- All 505 species were checked against their COM lines for typing, stats and abilities. Everything else matches apart from the items under Discoveries.
- Tests in `test_database.py`: all species have a learnset in level order within 1-100, moves the engine has use MoveDB's exact spelling, the six stat fixes, the parser traps, the importer failing on a bad cell, and the line insertion.

Coverage: 456 distinct level-up moves, 221 in MoveDB (every MoveDB move but Struggle). Entries not in MoveDB: 13% at level 16 or below (150 moves, led by Ancient Power, Ominous Wind, Thunder Fang, Ice Fang, Poison Gas), 15% at 20 or below, 24% at 30 or below. At level 16 or below, 501 of 505 species have 2+ usable moves and 498 have a damaging one. Ditto and Smeargle have none usable. Metapod, Kakuna, Abra, Silcoon and Cascoon have only status moves.

Checks: `pytest` 1813 passed, `pytest -m jit` 9 passed, golden snapshots unchanged. `/pokemon-data` keeps its shape because it picks its fields by name.

### Step 1b: move `_select_expand`'s hot parts into njit

Approved 2026-11-05, not started. It comes before Step 2 so the baseline and every later wall-clock number are measured on the faster search. It also raises the data rate in Step 5. No training involved, and it's worth doing whatever the gates say.

- Profile inside `_select_expand` first. The 72-82% isn't broken down yet. Candidates: `GameState` creation in `clone`, `NodeSnapshot.from_state`'s Python bench loops, `Node` creation, and the Python overhead around `best_slot`, `valid_action_mask`, `node_key` and `step_arr` at each tree level.
- Write a short note with the profile and the proposed change, and wait for your OK, because this is an architecture decision. There are two sizes: keep `Node` objects and move per-node work into njit, or keep the tree in flat arrays with selection as one njit call. The second is the bigger gain, but it also touches `backend/serializer.py`, `SearchEngine/helper.py` and everything else that reads nodes.
- MCTS stays single-threaded. `c`, `risk_lambda` and `alpha` don't change.

Done when: `pytest` and `pytest -m jit` pass, and iterations/s before and after on the three fights in the first table are written here.

### Step 2: scenario sampler, arena, baseline

No network yet. This defines how everything later gets judged.

- `NeuralNetwork/scenarios.py`, seeded:
  - Foe: a TrainerDB entry with its items and terrain.
  - My team: size 1-6, level from the trainer's top level -3 to +2.
  - Species pool: pre-Roark locations and gifts from the sheet's ENCOUNTERS tab (`gid=515626425`), evolved using the `Lv. N` rule in the STATS tab's last column (`gid=304097162`). ENCOUNTERS is a free-form grid and availability is a judgement call, so the list goes in a small data file **for your review**. Some slots (10-20%) come from all of PkDB for robustness.
  - Moves: the latest 4 learned at or below the level, filtered to MoveDB, with some older picks mixed in.
  - Ability from PkDB, random nature, IVs and gender, sometimes an early item.
  - Fights that 32 of today's rollouts call nearly decided are mostly dropped, since they teach little. Rollouts read low (0.8% on a fight 1000-iteration search wins 29% of), so check the thresholds against search results first.
- `_build_battle` lives in `backend/main.py`, and importing `backend` turns on the backend cache and deletes old cache folders. So extract its body into `Utils/helper.py` and have the backend call it.
- `NeuralNetwork/arena.py`: full battles for an agent, where an agent is a search budget, a leaf evaluator and optional `c` / `risk_lambda` / `alpha`. Single-action decisions skip the search. Reports win %, deaths per win, mean value, CVaR15 of value, confidence intervals and decisions/s. Arms play the same scenarios so differences are paired. Comparison budgets are wall clock per decision, with at most 4 workers.
- `NeuralNetwork/data/bench_set.json`: about 300 fixed scenarios stored by name, so id shifts don't change them. Weighted toward hard trainers, with Roark and the rivals also reported separately.
- Run the baseline: today's rollouts at 0.1 s, 0.5 s and 2 s per decision (about an hour on 4 workers, estimated at 20 decisions per battle). Write the results here.

Tests: every sampled scenario builds, the same seed gives the same scenario, and an arena smoke run works at tiny budgets.

### Step 3: state encoder

Rewrites the contents of `NeuralNetwork/models.py`. Nothing imports it, so nothing else is affected. Keeps its `_write_*(out, offset, ...)` pattern and widths derived from name tuples (CLAUDE.md rule). `split_features` and the import-time dummy compile go away, and that check moves to a test.

- Per move: static part (type, category, power, accuracy, priority, crit, multi-hit, effects, flags that change outcomes) and dynamic part (PP, `move_blocked`, matchup damage, KO flag, effectiveness).
- Per Pokemon: HP, stats, stages, status, both volatile bitmaps, timers and locks, types, ability and item ids, consumed / knocked-off, what the AI knows.
- Field: weather and turns, effective weather, Gravity, both sides' conditions, timers and Toxic Spikes layers, terrain, phase including Baton Pass, pending opp move, AI items, the AI's last-turn facts.
- Order: actives first, then bench by party slot, zeros for empty or fainted. Keep the slot map for the policy head later.

Tests in `tests/test_nn_features.py`: coverage table complete, widths match, array not mutated, no RNG consumed. Add a line to the CLAUDE.md move checklist. Budget: 15 µs or less per encode under JIT.

Done when: `pytest` and `pytest -m jit` pass, with `test_jit_smoke.py`'s `SOURCE_DIRS` extended.

### Step 4: inference and weights file

- `NeuralNetwork/inference.py`: `@njit(fastmath=True)` forward over the flat weights, offsets derived in one place, static move embeddings computed once per search and passed in. Returns the 7 class probabilities with impossible classes masked.
- `NeuralNetwork/weights.py`: `.npz` load and save with no torch dependency, holding weights, name vocabularies, encoder version, layout hash, engine source hash and training config. A layout or encoder mismatch refuses to load. An engine hash mismatch only warns. A model is about 256 KB, so weights are committed under `NeuralNetwork/weights/`.

Tests in `tests/test_nn_inference.py`: output matches a stored fixture, probabilities sum to 1, shuffling bench slots doesn't change the output, a mismatched file is refused. Budget: 50 µs or less per leaf including encoding on this CPU, measured with random weights.

### Step 5: data generation

`NeuralNetwork/datagen.py`. The parent compiles to the Numba cache, then spawns 4 workers, each seeded through njit (`_seed_numba`). Each worker plays sampled scenarios and writes shards.

- Pipeline bring-up: states from rollout play, labelled by 16 of today's rollouts each. Roughly 1M states in 5-10 minutes (estimate from measured rollout cost). These labels only prove the pipeline works.
- Real data: battles played by search at 1000 it/decision. Each decision records the state, the root's outcome-class distribution for the chosen action, root visit shares (stored now, used by Step 10), the valid-action mask, and later the battle's real outcome class. At the measured rate, about 0.7-1.6M states per night.

Add `.nn_data/` to `.gitignore`. Tests: a shard round-trips, and a wrong layout hash is refused.

### Step 6: training and Gate 1

`NeuralNetwork/train.py` and `requirements-train.txt`. Cross-entropy on the 7 classes against a soft target that mixes the real outcome and the search's root distribution. Train/validation split is by scenario, never by state. Export through `weights.py`. A parity test checks torch against the njit forward (`pytest.importorskip("torch")`).

**Gate 1**, on held-out scenarios:

- Lower Brier score on win and lower value error than a 16-rollout estimate from today's rollouts.
- Predicted win % within 5 points in each decile.

Failing means more or better data or features. It does not move on to Step 7.

### Step 7: search integration and Gate 2

- `_evaluate_leaf(state, net)` next to `_rollout` in `SearchEngine/my_mcts.py`: exact `evaluate_terminal` on terminal states, the network otherwise.
- `_backprop` takes the distribution. The rollout path behaves exactly as before.
- Used by `mcts_loop` and `_mcts_worker`, switched by a `net` argument. Default off.
- Add `NeuralNetwork` to `BACKEND_DIRS` in `Utils/jit_cache.py`, which also adds it to the installer. `source_hash` ignores `.npz`, which is correct because weights are run-time arguments.
- `c`, `risk_lambda` and `prune_dominated` were tuned for noisy rollouts. Try other values as arena arms, and change defaults only with your OK.

Tests in `tests/test_search.py`: histogram sums equal visits with fractional counts, terminal leaves are exact, nodes stay valid (structural, as usual).

**Gate 2**, on the bench set at 0.1 s and 0.5 s per decision:

- Mean battle value above today's rollouts, with the 95% CI of the paired difference above 0.
- CVaR15 no worse.
- Record how much more time rollouts need to match it. That is the speed multiple, and the target is 5x.

If it fails, try in this order: mix the network with today's rollouts at the leaf, short rollouts ending in a network evaluation, more data from Step 8's loop. If none work, stop here and keep whichever arm the arena favours.

### Step 8: improvement loop and Gate 3

`NeuralNetwork/loop.py`, unattended overnight: generate with the current best search, train, run the arena against the previous best, keep the new model only if it wins. **Gate 3**: stop when two generations in a row fail to improve.

### Step 9: ship

- `BattleConfig` option, on by default only if you say so after Gate 2. Clear fallback to rollouts when weights are missing or mismatched. `_warm_up` compiles the network path.
- Backend and `frontend/src/types.ts` report which evaluator ran, with a small indicator in the top bar. Win probability stays the primary metric.
- Installer builds with the weights, without torch or `.nn_data/`.
- Update CLAUDE.md (Layout, Commands, how to retrain) and the README paragraph.

### Step 10: policy head, PUCT and Gate 4

- Per-action logits over `ACTION_ORDER`'s 11 slots: moves from their move embedding, switches from that Pokemon's embedding, masked by `valid_action_mask`. Trained on the visit shares stored since Step 5.
- A new `best_slot_puct` next to `best_slot`. `Node` gets a `priors` slot filled by the same forward as the leaf value, and expansion tries high-prior actions first instead of random ones.

**Gate 4**: beats the best value-only arm at equal wall clock. Otherwise it stays off.

## Side tracks (not scheduled, your call)

- **Flat values in hard fights.** When all leaf values are near 0, exploration dominates (12% of visits after 65k iterations). Normalizing values to the range seen in the tree is the usual fix and can be tested as an arena arm.

## Risks

- **Engine changes make a model stale.** New moves or mechanics mean retraining, so it must stay one command. Layout mismatches refuse to load and engine changes warn.
- **Moves the sampler can't draw.** 13% of early level-up entries aren't in MoveDB, so the network never sees them until they're implemented and it's retrained.
- **Sampler versus your real teams.** Report the bench set by trainer, and add real teams to it when you have them.
- **It may simply not win.** Rollouts plus search are already strong at 1000+ iterations in small fights. The gates exist so that gets found out early.

## Discoveries (noticed, not changed)

Places where the sheet disagrees with itself or with PkDB, and PkDB was deliberately left alone. They matter if a later step reads those tabs.

- **Nidorina's DEX block has Charmander's stats** on all three lines (39/52/43/60/50/65). PkDB and the STATS tab agree on 70/62/67/55/55/56, so PkDB is unchanged.
- **The STATS tab has Giratina's two forms swapped.** The DEX COM lines agree with PkDB (Altered 150/100/120/100/120/90, Origin 150/120/100/120/100/90), so PkDB is unchanged.
- **LEARNSETS tab errors:** `Twinneedle` on Beedrill and Cloyster, and `Thrash` at level 50 on Wailord. DEX has `Twineedle` and `Amnesia`, and Amnesia is the one that fits: the rest of Wailord's list mirrors Wailmer's, which has Amnesia in both tabs.
- **Snover and Abomasnow:** the sheet writes Ice/Grass on all three lines, PkDB Grass/Ice. Order only, and the engine sites checked read both types together, so PkDB is unchanged.
- **`Anticipate`** is the sheet's name for PkDB's `Anticipation` (7 species). Spelling only.
