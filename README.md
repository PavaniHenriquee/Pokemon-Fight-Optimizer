# Pokemon Battle Optimizer

A decision-support tool that uses Monte Carlo Tree Search (MCTS) to recommend
battle actions in a Nuzlocke-style Pokemon playthrough, where losing a Pokemon
is permanent. Built as a personal learning project to go deep on search
algorithms, performance-critical Python, and risk-aware decision making —
using, for now a Generation IV Pokemon battle engine as the test domain, the same way
chess or Go are often used as clean, rule-bound sandboxes for search/AI work.

## Why this project

I wanted to build something with:

- A simulation environment complex enough to have real edge cases and bugs.
- A search problem with genuine stakes — in a Nuzlocke, a bad decision have
  lasting consequences. That makes plain expected-value
  optimization insufficient, and gives a natural reason to explore
  risk-adjusted search instead of vanilla MCTS.
- Performance constraints tight enough to justify real profiling and
  optimization work, since it needs a lot of iterations because of the
  randomness it needs to run at an acceptable time and not take hours.

The domain is Pokemon because I know its rules well and they're precisely
defined, which let me focus on the algorithm and engine architecture instead
of also having to invent and balance a game from scratch. Also because of the
randomness it has, since most MCTS algorithyms are based on deterministic games

## Architecture

Three layers, all built from scratch:

1. **Battle Engine** (`Engine/`, `Models/`, `DataBase/`) — A Generation IV
   Pokemon battle simulator. State is a single flat `int32` NumPy array
   (`battle_array`), passed through `@njit`-compiled functions with no Python
   object overhead in the hot path. Currently implements a growing subset of
   Gen IV moves, abilities, and items (see Status below).

2. **Search Engine** (`SearchEngine/`) — MCTS over the battle engine, with:
   - Rollouts compiled with Numba for speed (synchronous search is now
     faster than the earlier multiprocess-parallel version, since the
     rollouts themselves stopped being the bottleneck).
   - **CVaR-based risk-adjusted node selection**: instead of picking actions
     purely by average outcome, the tree tracks a histogram of outcomes per
     node and penalizes actions whose worst-case tail is significantly worse
     than their average — appropriate for a domain where the downside
     (a fainted/dead Pokemon) is asymmetric and irreversible.

3. **Frontend + Backend** (`frontend/`, `backend/`) — A FastAPI + WebSocket
   backend runs MCTS in a background thread and streams the live search tree;
   a React/TypeScript frontend visualizes it (win-rate per branch, expected
   deaths, bench state, item/ability info) and lets you continue search from
   any explored node with adjusted HP values.

A neural network component (`NeuralNetwork/`) is planned to eventually
replace random rollouts, framed as a single-player prediction problem (the
opponent's behavior comes from a deterministic trainer-AI model, not
self-play).

## Status

The first game i'm doing it for is the Drayano Renegade Platinum where
it is a more difficult version of the game, but also not super challenging,
whereas i can still be able to manually check if the results are expected
and realistic

This is an active, incrementally-built side project — not a finished
Pokemon simulator. Right now the objective is all trainers(their Pokemon,
abilities, moves and items) until the 1st gym badge of Renegade Platinum.

**Working:**

- Core damage/type/stat-stage calculations
- All abilities of opposing trainers until 1st gym, a growing move list and items
- Full MCTS + CVaR search loop, live tree visualization
- Trainer AI (approximating in-game AI decision logic)

**Not yet implemented:**

- Many Gen IV moves and abilities and respective effects(status effects,
  hazards, weather-linked abilities, etc.)
- Neural network policy/value network
- Desktop packaging

Engine completeness is intentionally prioritized over further performance
work or rollout quality — an incomplete simulation is a bigger source of
error than raw search speed right now.

## Tech

- **Engine**: Python, Numba (`@njit`), NumPy — flat-array, JIT-compiled
  simulation with no Python-object overhead in the hot path
- **Search**: MCTS with UCB1 + CVaR risk penalty, histogram-based tail-risk
  tracking
- **Backend**: FastAPI, WebSocket streaming
- **Frontend**: React, TypeScript, Vite, Tailwind
- **Profiling**: py-spy (flamegraphs), kernprof/line_profiler

## Running locally

Requires Python 3.x and Node.js installed.

One-time setup:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

cd frontend
npm install
cd ..
```

Then start both servers:

```
dev.bat  //Or just double click the file
```

This opens the backend (`uvicorn backend.main:app`, port 8000) and frontend
(Vite dev server) in separate terminal windows.

## Sources & Inspiration

Mechanic accuracy for the battle engine is checked against these references
rather than memory or guesswork:

- **[Bulbapedia](https://bulbapedia.bulbagarden.net/)** — move, ability, and
  item data, and Gen IV-specific mechanic details.
- **[Smogon](https://www.smogon.com/)** — competitive mechanic breakdowns,
  particularly for Gen IV-specific interactions and edge cases not always
  well documented elsewhere.
- **[Pokemow](https://pokemow.com/Gen4/TrainerAI/)** — Source for the trainer
  AI of the base game
- **[pokeplatinum](https://github.com/pret/pokeplatinum)** — Decompilation of
  Pokemon Platinum. Also source for trainer AI and general Gen IV mechanics
- **[Pokemon Showdown](https://github.com/smogon/pokemon-showdown)** — the
  reference implementation used to cross-check tricky mechanic interactions
  (its source is also the origin of the sprite/icon assets fetched at
  runtime for the frontend).
- **[PokeAPI](https://pokeapi.co/)** — sprite assets used in the frontend.

The MCTS + risk-adjusted search design was informed by general Monte Carlo
Tree Search literature (UCB1 selection, standard in game-playing AI like
chess/Go engines) and by CVaR (Conditional Value at Risk), a risk-adjustment
technique from quantitative finance/decision theory, adapted here to penalize
actions with a high chance of a bad worst-case outcome.

## Notes

This is a solo hobby project developed outside working hours, primarily for
learning. It is not affiliated with or endorsed by Nintendo/Game Freak/The
Pokemon Company. No game assets are redistributed; sprites/icons are fetched
at runtime from public community sources (PokeAPI, Pokemon Showdown) for
local display only.
