# Neural Network: Implementation Plan

Plan approved 2026-11-05.

## How to use this file across sessions

- Start a session with: "Read `NN_PLAN.md` and `CLAUDE.md`, then do Step N."
- Steps run in order. Each starts with a short note of what will change and waits for your OK (CLAUDE.md), and ends with its checks run and its notes written here.
- When a step lands, tick its box and add its notes, deviations and measured numbers. Anything noticed but not fixed goes in **Discoveries**.
- A *gate* is a measured check that decides whether the next step is worth doing. Write the result here and wait for your call. Stopping at a gate is a fine outcome: rollouts keep working, and nothing depends on the network until Step 9.
- No step changes `Engine/`, so golden snapshots must not move. If they do, something is wrong.
- Measure, train and use the network on the home PC. The i5-8400 machine is only for editing source, so timings from it don't go in this file.
- Before running any benchmark, check which processor this is. On the 7800X3D, run it. On the i5-8400, don't: write "needs benchmark" with what to run in that step's notes here, so all the numbers come from the same computer, and run it the next time work happens on the home PC.

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

Every number here is from the home PC, which does the training and will run the finished network. The i5-8400's numbers are in git (commit 294a567).

To measure again, run `python -m benchmarks.run quick` (search speed and network kernels, about 1.5 minutes) or `all` (about 8 minutes). Each run records the machine and compares itself with earlier runs of the same length in `benchmarks/results/`. Timings move 5-30% between runs with no code change, most when other programs are busy. The tables below are the long version, `all compile quality25k --long` (about 1.5 hours): timings from `benchmarks/results/2026-11-05_2112.md`, win rates from an earlier run with the same seeds, which that command repeats exactly.

Machine: Ryzen 7 7800X3D (8 cores, 16 threads, 96 MB L3, AVX-512), 32 GB DDR5-6000 (about 16 GB free with the desktop open), RTX 5070 Ti 16 GB (driver 610.88, CUDA 13.3, about 14 GB free), 2 TB SSD with 980 GB free. Python 3.15.2, numba 0.68.1, llvmlite 0.50.0 (LLVM 22, targets `znver4`), numpy 2.5.4. The desktop stayed open during the timings, at about 10% of the machine. On its Balanced power plan **this PC sleeps after 45 idle minutes** and hibernates after 60.

Test fights, defined in `benchmarks/fights.py`. TrainerDB entries are used whole with only the level changed, and foes keep their TrainerDB items:

- **Roark, good team**: Grotle 18 (Overgrow, Hardy, 31 IVs, no item; Razor Leaf, Curse, Tackle), Prinplup 18 (Torrent, Gentle, 30 IVs, Oran Berry; Water Pulse, Peck, Pound), then Psyduck 17 and Makuhita 17 from the weak team's entries.
- **Roark, weak team**: at 16, in this order: Diglett (Camper Curtis 1), Piplup (Barry 2-C), Geodude (Worker Colin 1), Makuhita (Youngster Sebastian 1), Psyduck (Lass Madeline 1), Torchic (Reporter Helen 1).
- **Barry 2-P**: the first 3 of the weak team at 14.
- **Dallas**: the first 2 of the weak team at 12, against Youngster Dallas 1.

The first version of this file only named the species, and its scripts stayed on the other machine. Win rates don't depend on the machine, so these definitions were recovered by matching its rollout numbers. Roark weak and Dallas reproduce them within noise. Grotle's and Prinplup's moves were the closest fit of the candidates tried, so that team may not be the exact old one. **Barry 2-P now has its Potion.** The old numbers only match without it (8.7% / 16.6% against the old 9% / 17%, and 5.7% / 12.4% with it), so the old row wasn't the real fight.

**Where the time goes.** Backend loop and stop rule, 30 s limit, one process, mean of 2 runs:

| Fight           | Iter/s | select/expand | rollout | backprop | Converged?                         |
| --------------- | ------ | ------------- | ------- | -------- | ---------------------------------- |
| Roark, good     | 10,030 | 64 µs (64%)   | 28 µs   | 7 µs     | Yes, 15 s                          |
| Roark, weak     | 8,240  | 53 µs (43%)   | 63 µs   | 5 µs     | No (best action 12% of visits)     |
| Barry 2-P       | 11,710 | 61 µs (71%)   | 18 µs   | 6 µs     | No (best action 56% of visits)     |
| Dallas          | 31,230 | 26 µs (81%)   | 2.6 µs  | 3.2 µs   | Yes, 0.5 s                         |

Against the i5, this CPU sped up tree work far more than rollouts (Roark weak: select/expand 6x, rollout 1.8x, probably the 96 MB cache). In the longest fight rollouts are now the larger part, and select/expand still leads everywhere else. Per-decision searches keep small trees and run faster, 13-35k iterations/s on one process.

**Rollouts are where the quality goes.** Win rate / mean `evaluate_terminal` value from the start of the fight, 20,000 samples per cell:

| Fight       | Rollout `heuristic_prob=0.48` (today) | Rollout `heuristic_prob=1.0` |
| ----------- | ------------------------------------- | ---------------------------- |
| Roark, good | 24% / 0.123                           | 60% / 0.429                  |
| Roark, weak | 0.9% / 0.003                          | 27% / 0.107                  |
| Barry 2-P   | 5.7% / 0.030                          | 12% / 0.073                  |
| Dallas      | 85% / 0.570                           | 99% / 0.595                  |

The same, for full battles played by search with today's rollouts: a fresh tree per decision, the most visited action, battle counts in brackets. Time per decision is on 8 pinned workers.

| Iterations per decision | 200                  | 1000                | 5000              | 25,000            |
| ----------------------- | -------------------- | ------------------- | ----------------- | ----------------- |
| Time per decision       | 9-18 ms              | 38-90 ms            | 0.36-0.45 s       | 1.8-2.4 s         |
| Roark, good             | 94% / 0.515 (2000)   | 98% / 0.631 (1000)  | 99% / 0.804 (300) | 99% / 0.930 (80)  |
| Roark, weak             | 8% / 0.017 (2000)    | 47% / 0.106 (1000)  | 77% / 0.209 (300) | 93% / 0.327 (120) |
| Barry 2-P               | 29% / 0.145 (2000)   | 43% / 0.219 (1000)  | 51% / 0.253 (300) | 48% / 0.231 (120) |
| Dallas                  | 99.7% / 0.984 (2000) | 100% / 0.996 (1000) | not run           | not run           |

What that shows:

- Today's rollouts read far below what the search actually achieves, because 52% of their moves are random. On Roark with a good team they say 24%, while 1000-iteration play wins 98%.
- When nearly every rollout loses, leaf values are all about 0 and the search can't separate actions. That's the 12% figure above, and the weak-team fight is where a plain heuristic (27%) beats 200-iteration search (8%). Search passes it by 1000 iterations.
- `heuristic_prob=1.0` costs the same and wins more, but it ignores deaths: on Dallas it wins 99% with 0.92 deaths per win, while search wins 99.7-100% with 0.00-0.02. It stays unused (see Design decisions); the column is kept as a measurement.
- A bigger budget keeps buying a lot in the Roark fights, so there is real room for a better leaf value to gain at low budgets. Barry flattens from 5000 iterations (51% and 48%, with overlapping confidence intervals), so that fight may simply be about even with this team.
- On this PC today's search already wins 93-99% of both Roark fights at about 2 s per decision. What's left at that budget is deaths: 3.1 per win with the weak team, 0.15 with the good one. So the network has to earn its place at short budgets or in fewer deaths.

**A network in njit is affordable:**

| Piece                                                        | Measured                 |
| ------------------------------------------------------------ | ------------------------ |
| Dense layer 128x128, plain `@njit`                           | 6.9 µs                   |
| Same with `fastmath=True`                                    | 0.7 µs                   |
| Same at unknown offsets (see Design decisions)               | 12 µs                    |
| Candidate network (64k parameters), full forward             | 12 µs                    |
| Same, static move part cached per search                     | 7.5 µs                   |
| Flat MLP on the shell's 2315 inputs (660k parameters)        | 27 µs                    |
| Shell `to_nn_input`                                          | 1.9-2.5 µs               |
| 20 damage calcs                                              | 1.5 µs (76 ns each)      |
| Numba call overhead, 1 array / tuple of 12                   | 0.1 / 0.7 µs             |
| Engine compile without cache                                 | 87 s, 1,130 MB RSS       |
| Engine start from the Numba cache (43 MB)                    | 0.8 s, 158 MB RSS        |
| Search tree memory, Roark weak team                          | about 5.4 KB/iteration   |
| Data rate at 200 it/decision, one process alone              | 69-130 decisions/s       |
| Data rate at 1000 it/decision, one process alone             | 13-35 decisions/s        |
| Data rate at 5000 it/decision, one process alone             | 2.5-9 decisions/s        |
| Data rate at 200 it/decision, 8 pinned workers               | 449-824 decisions/s      |
| Data rate at 1000 it/decision, 8 pinned workers              | 87-227 decisions/s       |
| Data rate at 5000 it/decision, 8 pinned workers              | 16-61 decisions/s        |

So a leaf (forward 7-12 µs, encoder budget 10 µs, about 20 µs together) costs less than a rollout in the Roark fights (63 and 28 µs), about the same in Barry (18 µs) and more in Dallas (2.6 µs), which converges in half a second anyway. In Roark weak an iteration would drop from about 121 to about 78 µs before any gain in quality. Select/expand then becomes 68% of it, which is why Step 1b stays first.

**The network's size isn't forced by the hardware any more.** Same structure with wider layers, on this CPU:

| Move / Pokemon / hidden widths | Parameters | Full forward | Move part cached |
| ------------------------------ | ---------- | ------------ | ---------------- |
| 32 / 64 / 128 (candidate)      | 64k        | 12 µs        | 7.5 µs           |
| 48 / 96 / 192                  | 134k       | 21 µs        | 14 µs            |
| 64 / 128 / 256                 | 230k       | 30 µs        | 20 µs            |
| 96 / 192 / 384                 | 499k       | 48 µs        | 36 µs            |
| 128 / 256 / 512                | 870k       | 76 µs        | 58 µs            |

**8 pinned workers is the setting.** Decisions/s at 1000 it/decision, 30 s each. Pinned means one worker per physical core, on logical CPUs 0, 2, ..., 14:

| Workers     | Roark, weak | Barry 2-P | Speed of each, against alone |
| ----------- | ----------- | --------- | ---------------------------- |
| 1           | 12.7        | 18.1      | 100%                         |
| 4, pinned   | 49.9        | 64.6      | 98% / 90%                    |
| 8, pinned   | 85.6        | 120.5     | 84% / 83%                    |
| 8, unpinned | 74.9        | 102.0     | 73% / 71%                    |
| 16          | 95.5        | 128.0     | 47% / 44%                    |

Hyper-threading adds 4-12% across three runs, so 16 workers gain little and leave nothing for the desktop. 8 unpinned workers lost 12-33% against pinned ones, and that varied a lot between runs (59-75 decisions/s in Roark weak). Cause not investigated; the Balanced plan's core parking is the first suspect. RAM isn't the limit any more: a worker peaks at 182 MB at 1000 it/decision and about 210 MB at 5000.

**The GPU wins training and loses inference.** Candidate network, torch 2.15.0+cu132 (a Python 3.15 wheel exists; 2.1 GB, 3.2 GB installed, against 129 MB for +cpu):

| Training setup                                                 | States/s    |
| -------------------------------------------------------------- | ----------- |
| GPU, data held in VRAM, batch 4096 or more                     | 2.2M        |
| GPU, batches copied from RAM, no encoding                      | 550-600k    |
| GPU, one process encoding on the fly at 2.5 / 5 µs per state   | 300k / 160k |
| CPU on 8 threads, no encoding (16 threads 95k, 1 thread 48k)   | 103k        |
| CPU on 8 threads, the same two encoders on the fly             | 84k / 63k   |

Those are at batch 4096 or more. One state through torch takes 109 µs on the CPU and about 400 µs through the GPU, against 7-12 µs in njit, so inference stays njit. Encoding is what limits a GPU trainer: at 5 µs per encode the training step is only about 20% of its time. With 7 pinned data workers running and torch held to core 0, batch 16384 still does 2.4M states/s in VRAM, batch 4096 and copies from RAM drop by half, and the workers lose 7-9%.

Data on disk: a state is 4282 `int32`, 16.7 KB raw. `np.savez_compressed` gives 224 bytes per state in battle order and 460 shuffled, on the test fights only, so sampled teams will compress somewhat less. Shards write at 18-25k states/s and read at 125-170k. 100k raw states take 1.6 GB of RAM.

**The shell's drift.** It reads 23 of 54 Pokemon slots, 19 of 72 move slots, 0 of 12 item slots, 15 of 34 field slots and 9 of 31 `VolStatus` bits. It has no `VolStatus2`, side conditions, Gravity, locks or timers, and no Baton Pass phase. It still imports and compiles.

## Design decisions

- **2026-11-05 (your call): `heuristic_prob` stays 0.48.** Rollouts keep real randomness, so results improve in quality and aren't shaped by your own view of the game, which is what the heuristic encodes. Every comparison in this plan is against today's rollouts. Don't propose raising it or adding hand-written preferences to strengthen the search. A network fits this: its values are learned from search results, and Step 8's loop reduces the rollouts' share further.
- **2026-11-05 (your call): the Renegade Platinum sheet is the source of truth for game data, Complete version.** That's the COM line in its DEX tab (OLD is vanilla, CLA is the Classic patch; 129 species differ between CLA and COM on stats).
- **2026-11-05: the value head outputs a distribution, not a mean.** Seven classes: loss, or win with 0-5 *more* deaths. `_backprop` fills the histogram that `cvar_from_hist` reads, and a mean would erase the tail CVaR exists to penalize. `value`, `win` and `dead` are computed at run time from the classes with `evaluate_terminal`'s formula (current turn for the small turn penalty), so changing its numbers, `risk_lambda` or `alpha` needs no retraining. Classes that can't happen given who is alive get masked.
- **2026-11-05: backprop adds the whole distribution to the histogram** instead of sampling one outcome, which avoids putting sampling noise back. `stats` is already float and `cvar_from_hist` handles fractional counts. `Node.wins` and `Node.dead` become floats, and the serializer already sends them as plain numbers.
- **2026-11-05: inference is hand-written njit, no torch or ONNX at run time.** Measured 7-12 µs against 109 µs for torch on the CPU and about 400 µs through the GPU, nothing added to the installer, no RNG, and single-leaf calls suit a single-threaded search. Weights are one flat `float32` array passed as an argument, like `battle_array`. Never a module global: Numba freezes globals into compiled code and its cache doesn't see them. Kernels need `@njit(fastmath=True)` (10x, measured) and must slice before the inner loop (`row = w[a:b]`, then `row[j]`). An index with an unknown offset (`w[off + i * n + j]`) keeps Numba's negative-index check in the loop and stops vectorization: one 128x128 layer took 12 µs that way against 0.7 µs sliced.
- **2026-11-05: shared encoders, about 64k parameters** (DeepSets style). Move features go through a move encoder and are pooled per Pokemon; Pokemon features plus that pool go through a Pokemon encoder; my active, foe active, my bench mean, foe bench mean and field features go through 2 hidden layers to the 7 classes. Candidate sizes: move 56→32, Pokemon 104→64, then 296→128→128→7. Bench order means nothing and teams are 1-6 Pokemon, so a flat MLP would have 10x the parameters and need far more data. A wider network is affordable now (230k parameters costs 30 µs), so it's an arena arm if Gate 1 or 2 asks for more capacity.
- **2026-11-05: the encoder gets engine-computed matchups.** Damage as % of HP for my moves against the foe's active and the reverse, using the helpers `rollout_pref` already uses (`effective_weather`, `normalized_type`, `ohko_fails`) with a fixed roll so encoding draws no RNG. At 76 ns per calc the network doesn't have to relearn the type chart.
- **2026-11-05: move, ability and item ids become embeddings through a name vocabulary stored in the weights file**, remapped at load, so alphabetical id shifts don't break a model.
- **2026-11-05: a coverage table stops the rot.** Every `Pok`, `Move`, `Flags`, `Sec`, `Item` and `Field` name and every `VolStatus`, `VolStatus2` and `SideCondition` bit is listed as encoded or deliberately ignored, and a test fails on any unlisted name. This adds one line to the checklist for new moves.
- **2026-11-05 (your call): training uses the RTX 5070 Ti whenever it can, dev only**, with PyTorch from `requirements-train.txt` (`torch==2.15.0+cu132`, from the `whl/cu132` index). It is not in `RUNTIME` in `build_python.py`, and the backend never imports it. On the GPU a trainer encoding on the fly does 160k states/s on one core, against 63k on all 8 for CPU training, and data generation can keep running next to it.
- **2026-11-05 (your call): no fixed time target.** The aim is the fastest search that plays well. The seconds per decision in Step 2 and Gate 2 are measurement points, not goals, and no budget is too long or too short to try.
- **2026-11-05: benchmarks live in `benchmarks/`, outside `NeuralNetwork/`.** Step 7 adds `NeuralNetwork` to `BACKEND_DIRS`, which would ship them in the installer and put their JSON reports in the Numba cache hash, so every saved report would force a recompile.
- **2026-11-05: labels come from search-played battles.** Rollout labels are only for bringing up the pipeline, because rollouts don't value avoiding deaths.
- **2026-11-05: data is stored raw.** `battle_array` plus raw outcomes (class, not `value`) in compressed shards under `.nn_data/` (gitignored). 16.7 KB per state raw and 224-460 bytes compressed, so disk is no concern. 100k raw states take 1.6 GB of RAM, so the trainer can mix several shards at once. Encoding happens on the fly, so encoder changes don't invalidate data. Shards are stamped with a layout hash and refused on mismatch.
- **2026-11-05: data generation runs as independent single-threaded processes** with no shared tree, so the single-threaded MCTS rule stands. 8 workers, each pinned to its own physical core. It can overlap GPU training, with 7 workers and the trainer on core 0, which costs the workers 7-9%. The parent compiles to the Numba cache first, otherwise each worker pays 87 s and 1,130 MB instead of 0.8 s and 158 MB.
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

- Profile inside `_select_expand` first. The 43-81% isn't broken down yet. Candidates: `GameState` creation in `clone`, `NodeSnapshot.from_state`'s Python bench loops, `Node` creation, and the Python overhead around `best_slot`, `valid_action_mask`, `node_key` and `step_arr` at each tree level.
- Write a short note with the profile and the proposed change, and wait for your OK, because this is an architecture decision. There are two sizes: keep `Node` objects and move per-node work into njit, or keep the tree in flat arrays with selection as one njit call. The second is the bigger gain, but it also touches `backend/serializer.py`, `SearchEngine/helper.py` and everything else that reads nodes.
- MCTS stays single-threaded. `c`, `risk_lambda` and `alpha` don't change.

Done when: `pytest` and `pytest -m jit` pass, and iterations/s before and after on the fights in the first table are written here (`python -m benchmarks.run search`).

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
- `NeuralNetwork/arena.py`: full battles for an agent, where an agent is a search budget, a leaf evaluator and optional `c` / `risk_lambda` / `alpha`. Single-action decisions skip the search. Reports win %, deaths per win, mean value, CVaR15 of value, confidence intervals and decisions/s. Arms play the same scenarios so differences are paired. Comparison budgets are wall clock per decision, with at most 8 pinned workers and nothing else heavy running. Each worker runs at 80-85% of its speed alone, so a budget here is a little less search than the same time in the app.
- `NeuralNetwork/data/bench_set.json`: about 300 fixed scenarios stored by name, so id shifts don't change them. Weighted toward hard trainers, with Roark and the rivals also reported separately.
- Run the baseline: today's rollouts at 0.02 s, 0.1 s, 0.5 s and 2 s per decision (about 40 minutes on 8 pinned workers at a rough 25 decisions per battle; the test fights measured 4-38). In the hard fights those budgets are about 200, 1000, 5000 and 25,000 iterations here. Write the results here.

Tests: every sampled scenario builds, the same seed gives the same scenario, and an arena smoke run works at tiny budgets.

### Step 3: state encoder

Rewrites the contents of `NeuralNetwork/models.py`. Nothing imports it, so nothing else is affected. Keeps its `_write_*(out, offset, ...)` pattern and widths derived from name tuples (CLAUDE.md rule). `split_features` and the import-time dummy compile go away, and that check moves to a test.

- Per move: static part (type, category, power, accuracy, priority, crit, multi-hit, effects, flags that change outcomes) and dynamic part (PP, `move_blocked`, matchup damage, KO flag, effectiveness).
- Per Pokemon: HP, stats, stages, status, both volatile bitmaps, timers and locks, types, ability and item ids, consumed / knocked-off, what the AI knows.
- Field: weather and turns, effective weather, Gravity, both sides' conditions, timers and Toxic Spikes layers, terrain, phase including Baton Pass, pending opp move, AI items, the AI's last-turn facts.
- Order: actives first, then bench by party slot, zeros for empty or fainted. Keep the slot map for the policy head later.

Tests in `tests/test_nn_features.py`: coverage table complete, widths match, array not mutated, no RNG consumed. Add a line to the CLAUDE.md move checklist. Budget: 10 µs or less per encode under JIT.

Done when: `pytest` and `pytest -m jit` pass, with `test_jit_smoke.py`'s `SOURCE_DIRS` extended.

### Step 4: inference and weights file

- `NeuralNetwork/inference.py`: `@njit(fastmath=True)` forward over the flat weights, offsets derived in one place, static move embeddings computed once per search and passed in. Returns the 7 class probabilities with impossible classes masked.
- `NeuralNetwork/weights.py`: `.npz` load and save with no torch dependency, holding weights, name vocabularies, encoder version, layout hash, engine source hash and training config. A layout or encoder mismatch refuses to load. An engine hash mismatch only warns. A model is about 256 KB, so weights are committed under `NeuralNetwork/weights/`.

Tests in `tests/test_nn_inference.py`: output matches a stored fixture, probabilities sum to 1, shuffling bench slots doesn't change the output, a mismatched file is refused. Budget: 30 µs or less per leaf including encoding on the home PC, measured with random weights.

### Step 5: data generation

`NeuralNetwork/datagen.py`. The parent compiles to the Numba cache, holds the PC awake while it runs (`SetThreadExecutionState`, since the PC otherwise sleeps after 45 idle minutes), then spawns 8 workers, each pinned to its own physical core with `psutil` and seeded through njit (`_seed_numba`). Each worker plays sampled scenarios and writes shards.

- Pipeline bring-up: states from rollout play, labelled by 16 of today's rollouts each. About 1M states in 1.1 minutes (14,800 states/s measured on the test fights). These labels only prove the pipeline works.
- Real data: battles played by search at 1000 it/decision. Each decision records the state, the root's outcome-class distribution for the chosen action, root visit shares (stored now, used by Step 10), the valid-action mask, and later the battle's real outcome class. At the measured rate, about 2.5-3.5M states per 8-hour night from hard fights, more from easy ones. 5000 it/decision would give 0.5-0.7M states from stronger play; choose when this step starts.

Add `.nn_data/` to `.gitignore`. Tests: a shard round-trips, and a wrong layout hash is refused.

### Step 6: training and Gate 1

`NeuralNetwork/train.py`, with torch installed from `requirements-train.txt`. One process encoding on the fly is enough to start: 50 epochs over 3M states take about 16 minutes on the GPU at 5 µs per encode. Holding encoded data in VRAM fits only about 900k states at the candidate's 3592 floats, so it's a later option if encoding ever limits training. Cross-entropy on the 7 classes against a soft target that mixes the real outcome and the search's root distribution. Train/validation split is by scenario, never by state. Export through `weights.py`. A parity test checks torch against the njit forward (`pytest.importorskip("torch")`).

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

**Gate 2**, on the bench set at 0.02 s, 0.1 s and 0.5 s per decision:

- Mean battle value above today's rollouts, with the 95% CI of the paired difference above 0.
- CVaR15 no worse.
- Record how much more time rollouts need to match it. That is the speed multiple, and the target is 5x.

If it fails, try in this order: mix the network with today's rollouts at the leaf, short rollouts ending in a network evaluation, more data from Step 8's loop. If none work, stop here and keep whichever arm the arena favours.

### Step 8: improvement loop and Gate 3

`NeuralNetwork/loop.py`, unattended overnight, holding the PC awake like Step 5: generate with the current best search, train, run the arena against the previous best, keep the new model only if it wins. The arena runs alone because its budgets are wall clock. **Gate 3**: stop when two generations in a row fail to improve.

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

- **Flat values in hard fights.** When all leaf values are near 0, exploration dominates (12% of visits after 230k iterations). Normalizing values to the range seen in the tree is the usual fix and can be tested as an arena arm.

## Risks

- **Engine changes make a model stale.** New moves or mechanics mean retraining, so it must stay one command. Layout mismatches refuse to load and engine changes warn.
- **Moves the sampler can't draw.** 13% of early level-up entries aren't in MoveDB, so the network never sees them until they're implemented and it's retrained.
- **Sampler versus your real teams.** Report the bench set by trainer, and add real teams to it when you have them.
- **It may simply not win.** Rollouts plus search are already strong on this PC: 93-99% of both Roark fights at about 2 s per decision. The gates exist so that gets found out early.

## Discoveries (noticed, not changed)

Places where the sheet disagrees with itself or with PkDB, and PkDB was deliberately left alone. They matter if a later step reads those tabs.

- **Nidorina's DEX block has Charmander's stats** on all three lines (39/52/43/60/50/65). PkDB and the STATS tab agree on 70/62/67/55/55/56, so PkDB is unchanged.
- **The STATS tab has Giratina's two forms swapped.** The DEX COM lines agree with PkDB (Altered 150/100/120/100/120/90, Origin 150/120/100/120/100/90), so PkDB is unchanged.
- **LEARNSETS tab errors:** `Twinneedle` on Beedrill and Cloyster, and `Thrash` at level 50 on Wailord. DEX has `Twineedle` and `Amnesia`, and Amnesia is the one that fits: the rest of Wailord's list mirrors Wailmer's, which has Amnesia in both tabs.
- **Snover and Abomasnow:** the sheet writes Ice/Grass on all three lines, PkDB Grass/Ice. Order only, and the engine sites checked read both types together, so PkDB is unchanged.
- **`Anticipate`** is the sheet's name for PkDB's `Anticipation` (7 species). Spelling only.
