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
| 1a   | Values for `best_action` (needs benchmark)         | [x]    |
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

To measure again, run `python -m benchmarks.run quick` (search speed and network kernels, about 1.5 minutes) or `all` (about 8 minutes). Each run records the machine and compares itself with earlier runs of the same length in `benchmarks/results/`. Timings move 5-30% between runs with no code change, most when other programs are busy. The tables below are the long version, `all compile quality25k --long` (about 1.5 hours): timings from `benchmarks/results/2026-11-05_2112.md`, win rates from an earlier run with the same seeds, which that command repeats exactly. The "Where the time goes" and full-battle tables were measured again with Step 1a's values, in `benchmarks/results/2026-11-06_1923.md`. Step 1a has the old numbers next to them.

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
| Roark, good     | 11,030 | 62 µs (68%)   | 22 µs   | 6 µs     | Yes, 12.5 s                        |
| Roark, weak     | 8,410  | 52 µs (43%)   | 62 µs   | 4 µs     | No (best action 11% of visits)     |
| Barry 2-P       | 11,980 | 60 µs (72%)   | 18 µs   | 6 µs     | No (best action 47% of visits)     |
| Dallas          | 36,880 | 22 µs (82%)   | 1.6 µs  | 2.6 µs   | Yes, 0.7 s                         |

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
| Time per decision       | 10-18 ms             | 39-89 ms            | 0.34-0.45 s       | 1.7-2.3 s         |
| Roark, good             | 93% / 0.549 (2000)   | 98% / 0.736 (1000)  | 99% / 0.884 (300) | 98% / 0.920 (80)  |
| Roark, weak             | 2% / 0.005 (2000)    | 44% / 0.107 (1000)  | 80% / 0.254 (300) | 94% / 0.435 (120) |
| Barry 2-P               | 27% / 0.137 (2000)   | 43% / 0.224 (1000)  | 52% / 0.257 (300) | 48% / 0.231 (120) |
| Dallas                  | 99.8% / 0.994 (2000) | 99.8% / 0.996 (1000) | not run          | not run           |

What that shows:

- Today's rollouts read far below what the search actually achieves, because 52% of their moves are random. On Roark with a good team they say 24%, while 1000-iteration play wins 98%.
- When nearly every rollout loses, leaf values are all about 0 and the search can't separate actions. That's the 11% figure above, and the weak-team fight is where a plain heuristic (27%) beats 200-iteration search (2%). Search passes it by 1000 iterations.
- `heuristic_prob=1.0` costs the same and wins more, but it ignores deaths: on Dallas it wins 99% with 0.92 deaths per win, while search wins 99.8% with 0.00. It stays unused (see Design decisions); the column is kept as a measurement.
- A bigger budget keeps buying a lot in the Roark fights, so there is real room for a better leaf value to gain at low budgets. Barry flattens from 5000 iterations (52% and 48%, with overlapping confidence intervals), so that fight may simply be about even with this team.
- On this PC today's search already wins 94-98% of both Roark fights at about 2 s per decision. What's left at that budget is deaths: 2.3 per win with the weak team, 0.17 with the good one. So the network has to earn its place at short budgets or in fewer deaths.

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
| Search tree memory, Roark weak team                          | about 5.2 KB/iteration   |
| Data rate at 200 it/decision, one process alone              | 69-130 decisions/s       |
| Data rate at 1000 it/decision, one process alone             | 13-35 decisions/s        |
| Data rate at 5000 it/decision, one process alone             | 2.5-9 decisions/s        |
| Data rate at 200 it/decision, 8 pinned workers               | 449-824 decisions/s      |
| Data rate at 1000 it/decision, 8 pinned workers              | 87-227 decisions/s       |
| Data rate at 5000 it/decision, 8 pinned workers              | 16-61 decisions/s        |

So a leaf (forward 7-12 µs, encoder budget 10 µs, about 20 µs together) costs less than a rollout in the Roark fights (62 and 22 µs), about the same in Barry (18 µs) and more in Dallas (1.6 µs), which converges in under a second anyway. In Roark weak an iteration would drop from about 118 to about 76 µs before any gain in quality. Select/expand then becomes 68% of it, which is why Step 1b stays first.

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
- **2026-11-06 (your call): CVaR is out of the search, which changes the two decisions above.** There's no histogram to fill and no tail to keep. The 7 classes still have a job: `win` and `dead` come from them, and changing `evaluate_terminal`'s numbers still needs no retraining. So they stay for now, and `_backprop` takes the value computed from the classes, with `wins` and `dead` as fractions. Look at this again at Step 6, since a value per Pokemon (CLAUDE.md, Known gaps) would change what the classes have to say.
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

### Step 1a: values for `best_action`

**Decided 2026-11-06: `c` 0.3, `ROOT_C` 1.2, CVaR removed from the code** (see Decision at the end of this step). `tuning` now only tries `(c, root c)` pairs. The tables below came from the code in `benchmarks/results/2026-11-06_tuning_with_cvar.patch`, applied on commit 2b82d54, along with its sections `tuningarms`, `tuningfinal`, `tuningstop` and `tuningfresh`.

Added 2026-11-06. **Needs benchmark, on the home PC:**

```
python -m benchmarks.run tuning --smoke
python -m benchmarks.run tuning
```

The first command only checks that it runs. The second takes about 2.5 hours, keeps the PC awake while it runs, and saves its report to `benchmarks/results/` after each stage, so a crash keeps what was measured. It changes no defaults.

`c`, `risk_lambda` and `alpha` were chosen by trying 2-3 values by eye, before most of the engine existed, so they need real values. It comes before Step 1b and Step 2 so every later baseline uses them. `N_BINS`, `prune_dominated`'s values and the stop rule stay out of this step.

**Why.** In a real fight against Dawn 1-P the app recommended a move with about a 6% chance of a needless death. The exact team isn't known (IVs and nature weren't saved), so these positions use Eevee 9 and Chimchar 9 with level-up moves and 15 IVs. None of this has been checked against that exact position.

Picks and deaths don't depend on the machine, so these came from short runs on the i5. With 5-10 searches per cell they show direction, not exact rates. Deaths are per battle, with the first move forced and search playing the rest, 150 battles at 2000 iterations per decision:

| Position                  | Move that risks it | Its deaths    | Other move | Its deaths    | Today's values pick |
| ------------------------- | ------------------ | ------------- | ---------- | ------------- | ------------------- |
| Eevee 9/30, foe 9/31      | Covet              | 0.060 ± 0.038 | Switch     | 0.000         | Covet, 98% of visits |
| Eevee 15/30, foe 9/31     | Covet              | 0.060 ± 0.038 | Switch     | 0.000         | Covet, 98% of visits |
| Eevee 15/30, foe 31/31    | Sand Attack        | 0.073 ± 0.042 | Switch     | 0.000         | Sand Attack, 98%    |
| Chimchar 11/28, foe 18/31 | Ember              | 0.027 ± 0.026 | Switch     | 0.180 ± 0.061 | Ember, 99% (correct) |

Battles started at full HP looked fine: 80 battles, 0 deaths, and no needless risk in 286 decisions. It only showed up in positions set up with a Pokemon already damaged, as after an earlier fight: 15 of 48 were flagged by one-turn death rate, and the table holds the ones checked by playing them out. The last row matters as much as the others: a switch can be safe this turn and still worse overall, so any new values have to keep picking Ember there.

**Cause.** `best_slot` reads CVaR from the action's histogram, which counts every visit: random rollout moves and the bad lines being explored below that action, not only good play. So a safe action that needs follow-up moves reads as risky until it has been searched, and the penalty stops it from being searched. At Eevee 9/30:

| Action | Reads mean | Reads CVaR | Penalty at λ 0.3 | Real value | Visits |
| ------ | ---------- | ---------- | ---------------- | ---------- | ------ |
| Covet  | 0.974      | 0.787      | 0.056            | 0.973      | 98%    |
| Switch | 0.843      | 0.374      | 0.141            | 0.999      | 1%     |

The penalty lands hardest on the safe move, so here the risk term causes the risk. More search doesn't help: 100,000 iterations with no stop rule still gave Covet 99.8% of visits. The picks change fastest at low λ:

| Picks of the right move, of 10 | λ 0 | 0.05 | 0.1 | 0.15 | 0.2 | 0.3 |
| ------------------------------ | --- | ---- | --- | ---- | --- | --- |
| Eevee 9/30, foe 9/31           | 9   | 4    | 0   | 0    | 0   | 0   |
| Eevee 15/30, foe 31/31         | 8   | 6    | 4   | 2    | 2   | 0   |
| Chimchar 11/28, foe 18/31      | 10  | 10   | 10  | 10   | 10  | 10  |

Also measured:

- **λ of 1 or more breaks the search.** For actions with equal CVaR the score is `(1-λ)·avg + λ·cvar`, so at 1 the mean cancels (visits split exactly 20.0% across 5 actions) and above 1 the worse action scores higher. The sweep stays below 1.
- **CVaR can't separate actions early in a hard fight.** At the start of Roark good, Roark weak and Barry 2-P, 76-100% of each root action's results land in the lowest bin at 5000 iterations, so all of them read CVaR 0.083 at any α up to 0.15.
- **`c` alone didn't fix it.** With λ 0.3, no `c` from 0.1 to 1.4 got more than 1 of 5 right picks on these positions, and 0.1 lost the right pick where staying in is correct.
- **`evaluate_terminal` needs no change for this.** At λ 0 the current price of a death was enough to pick the safe move. Its numbers are arbitrary, but they follow the intent: try not to lose a Pokemon, and if one must go, don't add more deaths or a wipe.

**What the section does.** `benchmarks/tuning.py`, seeds fixed:

1. Plays both first moves of 7 positions to the end, 300 battles each, to check the right answers again: the 4 above and 3 where only a crit kills.
2. Scores 34 sets on those positions, 20 searches each, under the backend's loop and stop rule.
3. Plays the best 9 and today's values in full battles at 1000 iterations per decision: Roark good, Roark weak, Barry 2-P, 300 battles each.
4. Plays the best 3 and today's values the same way at 5000.

**Choosing.** Fewest deaths per win among sets whose win rate isn't significantly below today's. If none clearly beats today's, the values stay. Write the tables here and wait for your call. Then, with your OK:

- Change the defaults in `Node.best_action`. Check whether `tests/test_search.py` needs anything, though it asserts no tuning values.
- Run `pytest` and `pytest -m jit`. Golden snapshots must not move, since they don't use the search.
- Run `python -m benchmarks.run quality quality25k --long` and update the win-rate tables above, since every number there used the old values.

**If no set fixes the positions without losing wins,** the cause is the formula and not its values. Options, each an architecture decision for your OK: search by the mean alone and use CVaR only to choose the final action; or a larger `c` at the root only, so every first move gets enough visits for its histogram to mean something. Either would be tried as extra arms in this same section.

**Bring back:** the report's `.md` file, and whether the cause above matches what you suspected in the real fight.

**Your read of the real fight (2026-11-06):** even a switch risks a crit, so the search took the line where a crit kills because it has fewer turns and the turn penalty rewards that, and every Pokemon is worth the same. On these positions the numbers don't support the turn penalty part. A turn costs 0.0005 and a first death 0.43, so a death costs as much as 860 turns. At Eevee 9/30 the real values already put the switch ahead, 0.999 against Covet's 0.973, and the switch had 0 deaths in 300 battles. The search misread it at 0.843, and with `evaluate_terminal` unchanged the picks went from 0/20 to 20/20. The real fight's exact team isn't known, so this doesn't rule it out there. The other part holds: `evaluate_terminal` only counts deaths, so all Pokemon cost the same (CLAUDE.md, Known gaps).

**Results, 2026-11-06, on the 7800X3D.** Full tables are in `benchmarks/results/2026-11-06_1309.md` (`tuning`, 84 minutes, not the 2.5 hours estimated) and `2026-11-06_1434.md` (`tuningarms`, 60 minutes). `tuningarms` is the two extra arms above, with your OK, plus a finer `c` grid. Today's values played the same numbers through both code paths, so the tables can be compared directly.

The right answers held up. In all 7 positions the right first move had fewer deaths when played out, 300 battles each:

| Position                  | Right move's deaths | Tempting move's deaths |
| ------------------------- | ------------------- | ---------------------- |
| Eevee 9/30, foe 9/31      | 0.000               | 0.053 ± 0.025          |
| Eevee 15/30, foe 9/31     | 0.000               | 0.053 ± 0.025          |
| Eevee 15/30, foe 31/31    | 0.000               | 0.070 ± 0.029          |
| Chimchar 11/28, foe 18/31 | 0.033 ± 0.020       | 0.180 ± 0.043          |
| Crit, Quick Attack first  | 0.000               | 0.070 ± 0.029          |
| Crit, immune switch       | 0.000               | 0.070 ± 0.029          |
| Crit, Roark behind        | 0.067 ± 0.028       | 0.663 ± 0.053          |

Right picks, 20 searches per position, under the backend's stop rule. The other four positions are 18-20 of 20 for every set here except those with `c` 0.2, so the Eevee columns decide:

| Values                         | Eevee 9/30 | Eevee 15/30, foe 9 | Eevee 15/30, foe 31 | All 7 |
| ------------------------------ | ---------- | ------------------ | ------------------- | ----- |
| Today: c 0.42, λ 0.3, α 0.15   | 0/20       | 0/20               | 0/20                | 56%   |
| c 0.2, λ 0                     | 4/20       | 4/20               | 10/20               | 64%   |
| c 0.3, λ 0                     | 16/20      | 15/20              | 12/20               | 86%   |
| c 0.35, λ 0                    | 16/20      | 16/20              | 17/20               | 91%   |
| c 0.42, λ 0                    | 17/20      | 15/20              | 17/20               | 92%   |
| c 0.5, λ 0                     | 14/20      | 16/20              | 19/20               | 92%   |
| c 0.55, λ 0                    | 16/20      | 12/20              | 19/20               | 91%   |
| c 0.6, λ 0                     | 1/20       | 1/20               | 20/20               | 73%   |
| c 0.8, λ 0                     | 0/20       | 0/20               | 19/20               | 71%   |
| c 0.42, λ 0.05                 | 9/20       | 4/20               | 16/20               | 77%   |
| c 0.42, λ 0.1, α 0.5           | 13/20      | 14/20              | 14/20               | 85%   |
| c 0.2, λ 0, root c 0.6         | 20/20      | 20/20              | 16/20               | 95%   |
| c 0.3, λ 0, root c 0.6         | 20/20      | 20/20              | 17/20               | 97%   |
| c 0.3, λ 0, root c 1.2         | 20/20      | 20/20              | 18/20               | 99%   |
| c 0.42, λ 0, root c 0.6        | 20/20      | 20/20              | 20/20               | 100%  |
| c 0.42, λ 0, root c 0.8        | 20/20      | 20/20              | 20/20               | 99%   |
| c 0.42, λ 0.1, root c 0.8      | 20/20      | 20/20              | 18/20               | 99%   |
| c 0.42, λ 0.3, root c 1.2      | 20/20      | 20/20              | 17/20               | 98%   |

- A root `c` above the tree's `c` gives 20/20 on both foe 9/31 positions for every value tried, even at today's λ 0.3. With one `c` for the whole tree, plain λ 0 drops sharply between `c` 0.55 and 0.6 on those same two. That fits this reading: a high `c` below the root puts exploration noise into the means of a line that needs follow-up moves, and a low `c` at the root never gives that line enough visits. Not measured directly.
- Searching by the mean and using CVaR only for the final choice changed no count at any final λ (0.1, 0.3, 0.6), so it tied with plain λ 0 and never reached the battles.
- α moves the picks a lot, with no clear pattern: at `c` 0.42, λ 0.3 on the Eevee columns, α 0.05 gives 0/20, 0/20, 20/20, α 0.15 gives 0/20, 0/20, 0/20 and α 0.5 gives 10/20, 6/20, 15/20. The histogram has only 6 bins, which may be why. Not measured.

Full battles, 300 each, same seeds. Win, deaths per win, value:

| 5000 iterations per decision | Roark good        | Roark weak        | Barry 2-P         |
| ---------------------------- | ----------------- | ----------------- | ----------------- |
| Today: c 0.42, λ 0.3, α 0.15 | 98.7%, 0.54, 0.804 | 77.3%, 3.87, 0.209 | 51.3%, 1.77, 0.253 |
| c 0.42, λ 0                  | 98.7%, 0.36, 0.857 | 79.3%, 3.86, 0.215 | 51.7%, 1.79, 0.254 |
| c 0.42, λ 0.05               | 98.7%, 0.39, 0.851 | 78.0%, 3.80, 0.216 | 47.0%, 1.67, 0.245 |
| c 0.42, λ 0.1, α 0.3         | 98.7%, 0.51, 0.812 | 81.0%, 3.74, 0.231 | 50.3%, 1.72, 0.254 |
| c 0.42, λ 0, root c 0.6      | 97.0%, 0.37, 0.829 | 80.3%, 3.62, 0.236 | 47.0%, 1.81, 0.231 |
| **c 0.3, λ 0, root c 1.2**   | **99.3%, 0.30, 0.884** | **79.7%, 3.42, 0.254** | **51.7%, 1.75, 0.257** |

| 1000 iterations per decision | Roark good        | Roark weak        | Barry 2-P         |
| ---------------------------- | ----------------- | ----------------- | ----------------- |
| Today: c 0.42, λ 0.3, α 0.15 | 97.7%, 1.13, 0.646 | 47.0%, 4.28, 0.107 | 46.7%, 1.70, 0.239 |
| c 0.42, λ 0                  | 98.0%, 1.00, 0.670 | 46.0%, 4.37, 0.100 | 41.0%, 1.59, 0.222 |
| c 0.3, λ 0                   | 98.3%, 0.76, 0.724 | 53.3%, 4.15, 0.129 | 37.3%, 1.74, 0.190 |
| c 0.42, λ 0, root c 0.6      | 98.3%, 0.89, 0.693 | 46.3%, 4.29, 0.105 | 43.7%, 1.68, 0.223 |
| **c 0.3, λ 0, root c 1.2**   | **99.0%, 0.73, 0.748** | **42.7%, 4.20, 0.101** | **45.3%, 1.62, 0.236** |

`c` 0.3, λ 0, root `c` 1.2 has the highest value in all three fights in this 5000 table, and is at least as good as today's in every cell there. No win rate there differs significantly from today's. At 1000 its Roark weak win rate is lower (42.7% vs 47.0%, not significant). In the two hard fights the 95% CIs are about ±5%, so wins can't separate these sets; value and deaths per win are what moved. Plain `c` 0.3, λ 0 does lose Barry 2-P significantly at 1000 (37.3%), and the root `c` brings it back to 45.3%.

**Final checks.** `tuningfinal` (136 minutes, `2026-11-06_1537.md`), `tuningstop` (6.5 minutes, `2026-11-06_1756.md`) and `tuningfresh` (41 minutes, `2026-11-06_1806.md`). On the same seeds, today's values played the same numbers again.

Neighbours of the best arm, and the two sets that keep CVaR in the search. Right picks as above, then full battles at 5000, 300 each, same seeds. Win, deaths per win, value:

| Values                       | Picks | Roark good             | Roark weak             | Barry 2-P              |
| ---------------------------- | ----- | ---------------------- | ---------------------- | ---------------------- |
| Today: c 0.42, λ 0.3, α 0.15 | 56%   | 98.7%, 0.54, 0.804     | 77.3%, 3.87, 0.209     | 51.3%, 1.77, 0.253     |
| c 0.42, λ 0.3, root c 1.2    | 98%   | 98.3%, 0.52, 0.803     | 74.7%, 3.84, 0.205     | 44.0%, 1.73, 0.225     |
| c 0.3, λ 0.1, root c 1.2     | 99%   | 99.3%, 0.34, 0.869     | 78.3%, 3.45, 0.247     | 46.3%, 1.68, 0.237     |
| **c 0.3, λ 0, root c 1.2**   | 99%   | **99.3%, 0.30, 0.884** | **79.7%, 3.42, 0.254** | **51.7%, 1.75, 0.257** |
| c 0.25, λ 0, root c 1.2      | 98%   | 98.3%, 0.30, 0.870     | 80.0%, 3.37, 0.260     | 46.3%, 1.62, 0.247     |
| c 0.35, λ 0, root c 1.2      | 99%   | 98.3%, 0.38, 0.846     | 75.0%, 3.49, 0.232     | 47.3%, 1.75, 0.236     |
| c 0.3, λ 0, root c 0.8       | 96%   | 98.7%, 0.32, 0.870     | 77.7%, 3.44, 0.246     | 46.7%, 1.71, 0.236     |
| c 0.3, λ 0, root c 1.6       | 98%   | 99.0%, 0.36, 0.860     | 81.3%, 3.28, 0.270     | 53.0%, 1.67, 0.273     |

Closer to what the app runs, 100 battles each, so direction only:

| 25,000 iterations per decision | Roark good         | Roark weak         | Barry 2-P          |
| ------------------------------ | ------------------ | ------------------ | ------------------ |
| Today: c 0.42, λ 0.3, α 0.15   | 99.0%, 0.13, 0.938 | 93.0%, 3.05, 0.332 | 46.0%, 1.78, 0.226 |
| c 0.3, λ 0, root c 1.2         | 98.0%, 0.14, 0.931 | 95.0%, 2.35, 0.438 | 46.0%, 1.87, 0.225 |
| c 0.25, λ 0, root c 1.2        | 99.0%, 0.12, 0.936 | 91.0%, 2.53, 0.381 | 52.0%, 1.85, 0.255 |

On seeds that played no part in choosing, 5000, 300 each. `quality` uses the same seeds as the tuning stages, so this is the independent check:

| Fresh seeds, 5000              | Roark good         | Roark weak         | Barry 2-P          |
| ------------------------------ | ------------------ | ------------------ | ------------------ |
| Today: c 0.42, λ 0.3, α 0.15   | 98.7%, 0.50, 0.813 | 75.0%, 3.93, 0.199 | 48.3%, 1.69, 0.248 |
| c 0.3, λ 0, root c 1.2         | 99.3%, 0.28, 0.882 | 80.0%, 3.44, 0.251 | 49.7%, 1.72, 0.253 |
| c 0.3, λ 0.1, root c 1.2       | 99.3%, 0.29, 0.877 | 82.0%, 3.56, 0.249 | 51.7%, 1.75, 0.258 |

The backend's stop rule, 8 searches each, on busy workers. Iterations, searches that stopped, time, top action's share of the visits. The fights ran up to 350,000 (`BattleConfig`'s default; the UI sends 500,000 unless you change it), the positions up to 100,000:

| Where                     | Today                       | c 0.3, λ 0, root c 1.2      |
| ------------------------- | --------------------------- | --------------------------- |
| Roark good                | 200,626, 8/8, 19.8 s, 94%   | 212,188, 8/8, 19.5 s, 96%   |
| Roark weak                | 350,000, 0/8, 41.7 s, 12%   | 350,000, 0/8, 41.5 s, 12%   |
| Barry 2-P                 | 350,000, 0/8, 28.6 s, 52%   | 350,000, 0/8, 29.6 s, 55%   |
| Dallas                    | 19,376, 8/8, 0.7 s, 98%     | 26,251, 8/8, 0.8 s, 96%     |
| Eevee 9/30, foe 9/31      | 7,501, 8/8, 0.1 s, 98%      | 11,876, 8/8, 0.1 s, 61%     |
| Eevee 15/30, foe 9/31     | 7,501, 8/8, 0.1 s, 98%      | 12,501, 8/8, 0.2 s, 60%     |
| Eevee 15/30, foe 31/31    | 64,376, 6/8, 3.0 s, 97%     | 22,188, 8/8, 0.8 s, 94%     |
| Chimchar 11/28, foe 18/31 | 7,501, 8/8, 0.1 s, 99%      | 18,438, 8/8, 0.3 s, 43%     |
| Crit, Quick Attack first  | 7,501, 8/8, 0.1 s, 69%      | 15,001, 8/8, 0.2 s, 35%     |
| Crit, immune switch       | 8,438, 8/8, 0.1 s, 92%      | 20,001, 8/8, 0.3 s, 42%     |
| Crit, Roark behind        | 47,814, 8/8, 2.1 s, 98%     | 49,376, 8/8, 2.1 s, 99%     |

- **The gain held up on fresh seeds.** Against today's, Roark good deaths go from 0.50 to 0.28 and Roark weak from 3.93 to 3.44, close to the first run's 0.54 to 0.30 and 3.87 to 3.42. Value rises by about the same as well. No win rate differs significantly from today's on either seed range, and Barry 2-P stays level.
- **It's a plateau, not a lucky peak.** The six sets with a lower tree `c` and λ 0 or 0.1 show Roark good deaths of 0.30-0.38 and Roark weak deaths of 3.28-3.49. The two sets at `c` 0.42, λ 0.3 show 0.52-0.54 and 3.84-3.87, so the gap is wider than the spread inside each group. The neighbours do beat the best arm in some cells: `c` 0.25 and root `c` 1.6 have more value in Roark weak, root `c` 1.6 in Barry 2-P. By the plan's rule alone (mean deaths per win) `c` 0.25 and root `c` 1.6 come first, at 1.76 and 1.77 against 1.82, which these battle counts can't separate.
- **The root `c` alone fixes the picks but not the battles.** Today's values with only root `c` 1.2 reach 98% right picks but play like today's: value 0.803 vs 0.804 and 0.205 vs 0.209. Their Barry 2-P is lower, 44.0% vs 51.3%, not significant. λ 0 alone takes Roark good deaths from 0.54 to 0.36 but leaves Roark weak at 3.86. Adding a root `c` gives 3.62 (`c` 0.42, root `c` 0.6), and the lower `c` as well gives 3.42.
- **Nothing shows the CVaR penalty earning anything, or a small one hurting.** In the first run λ 0.1 trails λ 0 at the same `c` and root `c` in value in all three fights, by less than the neighbours differ from each other. On fresh seeds they're level: 0.877 vs 0.882, 0.249 vs 0.251, 0.258 vs 0.253. λ 0.1's Roark weak win rate on fresh seeds passes the test against today's on its own (82.0% vs 75.0%), but not over both runs (80.2% vs 76.2%), and it's one cell of many.
- **These 7 positions chose the values and also score them,** so 99% isn't a fair estimate for new positions. The fresh seeds re-check the play in the same three fights, not new positions.
- **At 25,000** the Roark good gain is gone: every set is near the ceiling, about 0.13 deaths per win. Roark weak keeps it, 3.05 to 2.35. Barry 2-P doesn't change.
- **Barry 2-P moves with nothing here.** 44-53% across these sets at 5000, 46-52% at 25,000, and 25,000 doesn't beat 5000 for today's values. This looks like a limit of the fight or of the search as a whole, not of these values. Not measured.
- **The stop rule isn't delayed where it matters.** The longest waits are unchanged: Roark good 19.8 s vs 19.5 s, and Roark weak and Barry 2-P reach the cap under both. Small positions run up to 2.5 times the iterations, 0.2 s more at most, and Eevee 15/30, foe 31/31 gets faster, 3.0 s to 0.8 s.
- **The visits look less decided on small positions.** The top action's share falls, for example 98% to 61% and 92% to 42%, so the other actions' numbers rest on more visits and the visit bars look less one-sided. It stays the right pick (table above). Under 88% at the root, `prune_dominated` also leaves the root's other actions alone. These numbers already include that.

**Decision, 2026-11-06 (your call): `c` 0.3, λ 0, root `c` 1.2, and CVaR removed from the code since it was hurting.** It's the middle of the plateau and the only one of the three leading sets played at all of 1000, 5000 and 25,000, it costs no measurable wait in the fights, and on fresh seeds it comes first by the plan's rule (mean deaths per win 1.81, λ 0.1 1.87, today's 2.04). Its one weaker cell is Roark weak at 1000 (42.7% vs 47.0%, not significant), well below what the app runs. What changed:

1. **A separate root `c`.** `ROOT_C = 1.2` in `SearchEngine/models.py`, and one line in `_select_expand`: `node.best_action(ROOT_C) if len(path) == 1 else node.best_action()`. Every search goes through it, including the backend's.
2. **CVaR is gone.** `cvar_from_hist`, `N_BINS`, the histogram columns in `stats`, `risk_lambda` and `alpha` are removed, so `best_slot` is plain UCB. The price of a death in `evaluate_terminal` is the only risk term. `quality`'s CVaR15 column stays: it only reports how the worst 15% of battles scored, and Gate 2 uses it.

**Checks.** `pytest` 1824 passed, `pytest -m jit` 9 passed, golden snapshots unchanged. The new code plays the tested set exactly: the same picks on all 140 position searches, the same iterations on all 88 stop-rule searches, and the same results in all 900 battles at 1000.

**Measured again with these values** (`2026-11-06_1923.md`, `search quality quality25k --long`, 53 minutes). Win / value, old then new. The first table of this file now holds the new numbers:

| Iterations per decision | 200                       | 1000                       | 5000                      | 25,000                    |
| ----------------------- | ------------------------- | -------------------------- | ------------------------- | ------------------------- |
| Roark, good             | 94% / 0.515, 93% / 0.549  | 98% / 0.631, 98% / 0.736   | 99% / 0.804, 99% / 0.884  | 99% / 0.930, 98% / 0.920  |
| Roark, weak             | 8% / 0.017, **2% / 0.005** | 47% / 0.106, 44% / 0.107  | 77% / 0.209, 80% / 0.254  | 93% / 0.327, 94% / 0.435  |
| Barry 2-P               | 29% / 0.145, 27% / 0.137  | 43% / 0.219, 43% / 0.224   | 51% / 0.253, 52% / 0.257  | 48% / 0.231, 48% / 0.231  |
| Dallas                  | 99.7% / 0.984, 99.8% / 0.994 | 100% / 0.996, 99.8% / 0.996 | not run                | not run                   |

**The one clear loss is Roark weak at 200 iterations, and the root `c` causes it, not removing CVaR.** That budget wasn't in the tuning runs. Roark weak at 200, 2000 battles, same seeds:

| `c`, root `c`, no penalty | Win  | 95% CI    | Value |
| ------------------------- | ---- | --------- | ----- |
| 0.42, 0.42                | 9.2% | 8.0-10.5% | 0.019 |
| 0.3, 0.3                  | 8.7% | 7.5-10.0% | 0.019 |
| 0.3, 0.6                  | 5.8% | 4.8-6.9%  | 0.013 |
| 0.3, 1.2                  | 2.1% | 1.6-2.8%  | 0.005 |

Without the penalty and with no larger root `c`, the old 8% holds. A larger root `c` spreads 200 iterations thinly over the first moves, and by 1000 the difference is gone (44% vs 47%, not significant). The app isn't affected: its stop rule needs 5000 visits on one node, so it runs at least 5000 iterations unless stopped by hand or given a lower cap. It does matter for this plan: Step 2's baseline runs at 0.02 s, about 200 iterations. See Step 7.

**Speed.** Iterations/s rose 2% in Roark weak and Barry 2-P, 10% in Roark good and 18% in Dallas, all inside the usual 5-30% timing noise. Rollout times moved too with no rollout change, so this doesn't show a speedup from removing CVaR. Backprop did drop in all four fights (3.2 to 2.6 µs in Dallas), the step that lost its histogram update.

### Step 1b: move `_select_expand`'s hot parts into njit

Approved 2026-11-05, not started. It comes before Step 2 so the baseline and every later wall-clock number are measured on the faster search. It also raises the data rate in Step 5. No training involved, and it's worth doing whatever the gates say.

- Profile inside `_select_expand` first. The 43-81% isn't broken down yet. Candidates: `GameState` creation in `clone`, `NodeSnapshot.from_state`'s Python bench loops, `Node` creation, and the Python overhead around `best_slot`, `valid_action_mask`, `node_key` and `step_arr` at each tree level.
- Write a short note with the profile and the proposed change, and wait for your OK, because this is an architecture decision. There are two sizes: keep `Node` objects and move per-node work into njit, or keep the tree in flat arrays with selection as one njit call. The second is the bigger gain, but it also touches `backend/serializer.py`, `SearchEngine/helper.py` and everything else that reads nodes.
- MCTS stays single-threaded. `c` and `ROOT_C` don't change.

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
- `NeuralNetwork/arena.py`: full battles for an agent, where an agent is a search budget, a leaf evaluator and optional `c` / `ROOT_C`. Single-action decisions skip the search. Reports win %, deaths per win, mean value, CVaR15 of value, confidence intervals and decisions/s. Arms play the same scenarios so differences are paired. Comparison budgets are wall clock per decision, with at most 8 pinned workers and nothing else heavy running. Each worker runs at 80-85% of its speed alone, so a budget here is a little less search than the same time in the app.
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
- `c`, `ROOT_C` and `prune_dominated` were tuned for noisy rollouts. Try other values as arena arms, and change defaults only with your OK. Include a smaller `ROOT_C` at 0.02 s, where 1.2 loses to 0.3 in Roark weak (2.1% vs 8.7%, Step 1a).

Tests in `tests/test_search.py`: per-action rows add up with fractional wins and deaths, terminal leaves are exact, nodes stay valid (structural, as usual).

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
- **Full battles prune sooner than the app.** `mcts_loop` prunes every 500 iterations (`SearchEngine/my_mcts.py:278`), the backend every 2500 (`backend/main.py:260`). Low `c` sets reach `prune_dominated`'s 88% sooner, so they could score a bit differently in these tables than in the app. Not measured. Every win-rate table here uses 500, so they stay comparable.
- **Two fights never reach the stop rule.** At the first turn of Roark weak and Barry 2-P, no search stopped within 350,000 iterations, under the old values or the new ones. That took 29-42 s on a busy worker. The app keeps going to its cap, 500,000 by default in the UI, so it waits longer (not measured). Roark weak's top action still has only 12% of the visits there.
- **`quality` and the tuning stages share seeds.** Both use `100_000 * iters + i`, so re-running `quality` replays battles that helped choose the values. `tuning`'s fresh-seed stage starts 50,000 seeds later for that reason.
- **`ROOT_C` costs wins at very low budgets.** Roark weak at 200 iterations wins 2.1% with 1.2 and 8.7% with 0.3. The app runs at least 5000 unless stopped by hand or given a lower cap, so only Step 2's 0.02 s arm and anything else near 200 iterations feels it.
- **Every Pokemon costs the same.** `evaluate_terminal` only counts deaths, so losing the team's best Pokemon scores like losing its worst. It didn't cause the picks in Step 1a, but it does shape which Pokemon the search is willing to lose.
