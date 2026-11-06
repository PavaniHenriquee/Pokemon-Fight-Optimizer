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
  lasting consequences. That gives a natural reason to explore risk-aware
  search instead of only maximizing wins.
- Performance constraints tight enough to justify real profiling and
  optimization work, since it needs a lot of iterations because of the
  randomness it needs to run at an acceptable time and not take hours.

The domain is Pokemon because I know its rules well and they're precisely
defined, which let me focus on the algorithm and engine architecture instead
of also having to invent and balance a game from scratch. Also because of the
randomness it has, since most MCTS algorithms are based on deterministic games

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
   - **Risk priced into the result**: a win that loses a Pokemon scores far
     below a clean win (0.57 against 1.0) and each further death lowers it more,
     so picking by average score already avoids needless deaths.
   - **More exploration at the root**: a safe first move that needs follow-up
     moves gets enough visits to show its real value.

3. **Frontend + Backend** (`frontend/`, `backend/`) — A FastAPI + WebSocket
   backend runs MCTS in a background thread and streams the live search tree;
   a React/TypeScript frontend visualizes it (win-rate per branch, expected
   deaths, bench state, item/ability info) and lets you continue search from
   any explored node with adjusted HP values.

A neural network component (`NeuralNetwork/`) is planned to eventually
replace random rollouts, framed as a single-player prediction problem (
so only for Nuzlockes and not for competitive games like VGC).

## Tried and removed: CVaR

The search used to penalize actions whose worst outcomes sat far below their
average, using CVaR (Conditional Value at Risk) over a histogram of outcomes per
action. The goal was safer runs. It didn't work, and in some positions it caused
the risk it was meant to avoid.

The histogram counted every visit, including random rollout moves and bad lines
still being explored. So a safe move that needed follow-up moves looked risky,
and the penalty then kept it from being searched enough to correct that. In one
test position a switch with no deaths in 300 played-out battles got 1% of the
visits, while a move with about a 6% chance of a needless death got 98%.

Removing the penalty, with a lower exploration constant in the tree and a larger
one at the root, gave these results:

| | With CVaR | Without |
| --- | --- | --- |
| Right first move, in 7 test positions | 56% | 99% |
| Roark, good team: win, deaths per win | 98.7%, 0.50 | 99.3%, 0.28 |
| Roark, weak team: win, deaths per win | 75.0%, 3.93 | 80.0%, 3.44 |
| Barry: win, deaths per win | 48.3%, 1.69 | 49.7%, 1.72 |

The fights are 300 battles each at 5000 iterations per decision, on seeds that
played no part in choosing the values. The win rate changes aren't statistically
significant, and the 7 positions also helped choose the values, so 99% won't
carry over to new positions. A small penalty played about the same as none, so
there was no reason to keep it.

The larger root constant has its own cost at very low budgets: at 200 iterations
per decision the weak-team win rate falls from about 8% to 2%. By default the
tool runs at least 5000. The full tables are in `NN_PLAN.md`, Step 1a.

## Status

The first game I'm targeting is Renegade Platinum, a ROM hack by Drayano, where
it is a more difficult version of the base game, but also not extra challenging,
whereas i can still be able to manually check if the results are expected
and realistic

This is an active, incrementally-built side project — not a finished
Pokemon simulator. Right now the objective is all trainers(their Pokemon,
abilities, moves and items) until the 1st gym badge of Renegade Platinum.

**Working:**

- Core damage/type/stat-stage calculations
- All abilities of opposing trainers until 1st gym, a growing move list and items
- Full MCTS search loop, live tree visualization, through local server
- Trainer AI (approximating in-game AI decision logic)

**Not yet implemented:**

- Many Gen IV moves and abilities and respective effects(status effects,
  hazards, weather-linked abilities, etc.)
- Neural network policy/value network
- Desktop packaging

Engine completeness is the main focus right now, want to be able to play the game
with this tool by the side to check for effectiveness of the results and bugs.

## Tech

- **Engine**: Python, Numba (`@njit`), NumPy — flat-array, JIT-compiled
  simulation with no Python-object overhead in the hot path
- **Search**: MCTS with UCB1, with a larger exploration constant at the root
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
(Vite dev server) in separate terminal windows. After both terminals are running
open the URL shown in the frontend terminal

## Sources & Inspiration

Mechanic accuracy for the battle engine is checked against these references
rather than memory or guesswork:

- **[Bulbapedia](https://bulbapedia.bulbagarden.net/)** — move, ability, and
  item data, and Gen IV-specific mechanic details.
- **[Pokemow](https://pokemow.com/Gen4/TrainerAI/)** — Source for the trainer
  AI of the base game
- **[pokeplatinum](https://github.com/pret/pokeplatinum)** — Decompilation of
  Pokemon Platinum. Also source for trainer AI and general Gen IV mechanics
- **[Pokemon Showdown](https://github.com/smogon/pokemon-showdown)** — the
  reference implementation used to cross-check tricky mechanic interactions
  (its source is also the origin of the sprite/icon assets fetched at
  runtime for the frontend).
- **[PokeAPI](https://pokeapi.co/)** — sprite assets used in the frontend.

The MCTS design was informed by general Monte Carlo Tree Search literature (UCB1
selection, standard in game-playing AI like chess/Go engines). CVaR, a
risk-adjustment technique from quantitative finance/decision theory, was tried
and removed (see above).

## Notes

This is a solo hobby project developed outside working hours, primarily for
learning. It is not affiliated with or endorsed by Nintendo/Game Freak/The
Pokemon Company. No game assets are redistributed; sprites/icons are fetched
at runtime from public community sources (PokeAPI, Pokemon Showdown) for
local display only.
