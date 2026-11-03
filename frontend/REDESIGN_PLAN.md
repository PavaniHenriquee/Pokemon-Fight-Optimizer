# Frontend redesign plan

Plan approved 2026-11-03. Tick a box when its phase lands; the checkpoint after Phase 2 waits for review before Setup.

## Status (execution order)

- [x] Step 0: plan saved here, memory pointer added
- [x] Phase 5: backend type fields (serializer, /pokemon-data, types.ts, tests). Deviation: the
      serializer reads type / category / power from the battle array's live slots (`Pok.TYPE1/2`,
      `Move.TYPE/CATEGORY/POWER`) instead of MoveDB/PkDB, so Hidden Power shows its IV type.
      `/pokemon-data` uses MoveDB/PkDB as planned.
- [x] Phase 1: foundation (tokens, shadcn primitives, lib/api, lib/sprites, lib/format, common components)
      Notes:
      - `lib/tree.ts` added (`orderActions`, `bestActionKey`, `pathSteps`).
      - The new shadcn files import `cn` from `@/lib/utils`; the CLI's `cn` and `next-themes` packages were uninstalled. Toasts are always dark.
      - tabs / badge / scroll-area / separator were added, then removed (unused). `dropdown-menu` is kept for Phase 3.
      - The tooltip was restyled to the popover surface.
      - `App.css` keeps only the legacy classes the Setup screen still uses, mapped to the new tokens through the alias block at the end of `:root` in `index.css`. Phase 3 removes both.
- [x] Phase 2: app shell + Analyze 3-pane workspace
      Notes:
      - Action cards: moves then switches, each sorted by visits (user's choice). The 1–9 shortcuts follow that order.
      - Type badges are PokeAPI Scarlet/Violet sprites (`typeSprite`); the colored text badge is the fallback.
        `fetch_sprites.py` must also fetch `sprites/types/{1..18}.png`.
      - Fixed after the first review: Setup didn't scroll (its wrapper wasn't a flex column); the connection dot
        showed offline (a disposed StrictMode socket's late close event).
      - The party strip shows only real party members (no empty pokéball padding).
      - The center column is capped at 1080px.
      - Done early from Phase 4: WebSocket reconnect, the "Waiting for backend" screen, data fetched after the first connection (this also stops a backend-less start from loading the box as `[]`), 127.0.0.1 default.
      - Search-crash toast from the WS `error` field (`types.ts` was missing it).
- [x] Checkpoint: Analyze screen reviewed
- [x] Phase 3: Setup workspace
      Notes:
      - Layout: Box rail | team | opponent.
      - `BoxView` is now the rail; its editor is a Dialog with a sprite preview.
      - `PokemonSlots` exports `LevelStepper` / `NameSelect` / `MoveSelect` / `ItemSelect`, also used by the box editor.
      - The box's Save shows an "unsaved" dot, and save errors show a toast.
      - `App.css` and the legacy alias block in `index.css` were removed.
      - The IV inputs lost their +/- steppers (6 plain number fields in a row).
- [x] Gamey box + editor (user request after Phase 3)
      - The box rail is a PC box: pages of 30 (6×5) on a striped wallpaper that changes hue per page, and icons hop on hover.
        A summary panel below the grid shows the hovered Pokémon, or the selected one when nothing is hovered.
        Click selects, double-click (or "Add to party") adds to the team. Release takes two clicks.
      - The editor (`BoxEditor.tsx`) is a Summary-screen dialog:
        - Profile panel: animated sprite, ♂/♀/— toggle, level slider.
        - INFO: species, ability pills from `pokemonAbilities` (new additive `/pokemon-data` field), 5×5 nature grid.
        - MOVES: type-colored slot cards and a move list.
        - STATS: IV sliders, live stats colored by nature, Hidden Power (same rule as `Pokemon.hidden_power`).
      - Changing the species keeps the ability only if the new species can have it, else it picks that species' first ability.
- [x] Numba cache for the backend (user request, together with Phase 3)
      - `Utils/jit_cache.py` (`source_hash`, `cache_dir`, `use_cache`) is called from `backend/__init__.py`.
      - The cache lives in `.numba_cache/backend/<hash of DataBase, Engine, Models, SearchEngine, Utils, backend>`; old hashes are deleted. `NUMBA_CACHE_ON=0` opts out; nothing happens under pytest (JIT off).
      - Startup warm-up: the lifespan runs a 300-iteration throwaway search in a thread (`_warm_up`, through `_build_battle`, which is shared with /start). The WebSocket sends `compiling` while it runs, and the top bar shows "Compiling engine…".
      - Measured: 0.6s with a warm cache.
      - `test_jit_smoke` uses the shared `cache_dir` (same `.numba_cache/tests/<hash>` folder as before).
      - For Electron: point the cache at a user-writable folder (%LOCALAPPDATA%) when packaged.
- [x] Phase 4: Electron readiness
      - `vite.config.ts`: `base: "./"` (dist/index.html uses `./assets/...`), `chunkSizeWarningLimit: 1000`.
      - `fetch_sprites.py` (repo root, stdlib + `DataBase.PkDB.sprite_id`): 2,614 files, ~45 MB, 16 parallel
        downloads, skips files it has, writes through `.part` files. `frontend/public/sprites/` is gitignored.
      - 4 item icons don't exist under our slug (Bright Powder, Never-Melt Ice, Silver Powder, Twisted Spoon):
        Showdown names them without hyphens (`brightpowder`, ...). Same miss online; not fixed yet.
      - Favicon `public/icon.svg` (the top bar's mark). The Vite template `favicon.svg` / `icons.svg` are still
        in `public/` (gitignored), unused.
      - Verified: the build served from a sub-folder with every non-local request blocked; Setup and Analyze
        load all images locally.
      - Already done in Phase 2: WS reconnect, offline state.
      - Left for the Electron shell step: the Numba cache in a user-writable folder (%LOCALAPPDATA%) when packaged.
- [x] After Phase 4 (user OK): the 4 item icon slugs (`ITEM_SLUG_OVERRIDES` in sprites.ts and fetch_sprites.py),
      `import.meta.dirname` in vite.config.ts, the Vite template `favicon.svg` / `icons.svg` removed (`git rm`).
- [x] Phase 6: Electron app (user choices: bundled Python, box in %APPDATA% seeded from UserData/box.json,
      NSIS installer)
      - `frontend/electron/main.js`: free port → `python -m uvicorn backend.main:app`, then the window
        (1440×900, min 1280×720). Single instance. Python output goes to `%APPDATA%\Nuzlocke Optimizer\logs\backend.log`;
        if it dies, an error box shows the last lines. On quit: `taskkill /T /F`.
      - `preload.cjs` passes the URL as `window.desktop.apiUrl` (read by `lib/api.ts`; the browser keeps VITE_API_URL / :8000).
      - Backend opt-ins only Electron sets: `PBO_BOX_PATH`, `PBO_CACHE_ROOT` (Utils/jit_cache.py),
        `PBO_EXIT_WITH_PARENT=1` (exits when the stdin pipe closes, so a crashed Electron leaves no Python).
      - `electron/build_python.py`: python.org embeddable 3.15.2, `pip install --target --only-binary` of
        fastapi / uvicorn / websockets / httptools / numba / numpy pinned to `pip freeze` of the .venv
        (`uvicorn[standard]` wants PyYAML, which has no 3.15 wheel), BACKEND_DIRS as .py + .pyc, a smoke import.
        Skips the Python part when the version and pins didn't change.
      - Sizes: installer ~204 MB, installed ~650 MB (backend 250 MB, page + sprites 43 MB, Electron the rest).
      - Running Electron from a process that inherits VS Code's `ELECTRON_RUN_AS_NODE=1` starts plain Node;
        a normal terminal is fine.
- [x] PP lookup fix for Mud-Slap / Will-O-Wisp: `_MOVE_ID_TO_MAX_PP` is keyed by the MoveDB `name` field,
      and `test_max_pp_covers_every_move` covers every move.

---


## Context

The backend is ready for a first build; the frontend isn't. It works, but it looks unfinished, and a few things will break once it's packaged in Electron. What I found in `frontend/src`:

- **Three competing styling layers.** `App.css` has hand-written classes (`.badge`, `.popup-panel`, `.btn`), the components use Tailwind `slate-*` utilities, and most of `BattleView.tsx` (1,000 lines) is inline `style={{}}`.
- **Broken theme tokens.** `App.css`'s `:root` overrides shadcn's `--accent`, `--muted` and `--border` with unrelated values, and the `.dark` class is never applied. As a result, shadcn popovers (the combobox dropdowns) render with the light palette on a dark page.
- **Vite template leftovers** in `index.css`: `#root { text-align:center; border-inline }`, `--social-bg`, `#social`, the h2/code rules, and an 18px root font.
- **Duplicated code.** `WinRing` exists 3×, `hpColor`/`hpRange` 3×, the sprite URL builders 4×, `itemIcon` 3×, and the formatted iterations input 3×.
- **Not desktop-shaped.** A centered 4xl "MCTS" title, a wrapping header, everything stacked vertically, and outcomes in a modal.
- **Electron blockers.** `http://localhost:8000` is hard-coded in 3 files. The build uses absolute asset paths. The WebSocket never reconnects, so a window that opens before Python finishes starting stays offline forever. `alert()` is used for errors. All sprites load from GitHub and Showdown at runtime.

Decisions you made:
- **Look:** dark pro tool (Linear/Raycast style) with Pokémon accents.
- **Analyze layout:** a 3-pane workspace.
- **Electron prep:** central API config, asset paths, toasts, and sprites bundled for offline use.
- **Backend:** additive, read-only type fields are OK.

The Electron shell itself is a later step.

Ground rules for this work:
- State, effects, fetch calls and navigation logic stay as they are.
- Markup and styling get rewritten.
- The teaching comments in `App.tsx` stay.
- `hpRange`'s bracket strings stay exactly the same (frontend convention).
- "Best action" stays "most visits".
- Win probability stays the primary metric; visits stay visually secondary.

---

## Step 0: Save this plan for later sessions (do first)

- Copy this plan to `frontend/REDESIGN_PLAN.md` and add a **Status** checklist at the top, in execution order:
  Phase 5 (backend fields) → 1 (foundation) → 2 (shell + Analyze, then the checkpoint) → 3 (Setup) → 4 (Electron readiness). Each phase gets ticked off as it lands.
- Save a `project` memory pointing to `frontend/REDESIGN_PLAN.md`, so a new session picks up where the last one stopped.

## Phase 1: Foundation (tokens, shared modules)

**Theme.** `index.css` becomes the single source of tokens:
- Add `class="dark"` on `<html>` in `index.html` and define one dark palette under shadcn's names (`--background`, `--card`, `--popover`, `--primary`, `--muted`, `--accent`, `--border`, `--ring`), so every shadcn component picks it up.
- Base: cool neutral surfaces (oklch around 0.16 / 0.20 / 0.24, hue 260), hairline borders `oklch(1 0 0 / 8%)`, and a violet primary accent (already used for the primary buttons). The mint `--accent` and the yellow title go.
- Semantic tokens in `@theme`, so Tailwind generates the utilities:
  - `--win-high/mid/low` (green/amber/red, the same thresholds as today: >0.65, >0.4)
  - `--hp-high/mid/low` (>0.5, >0.25)
  - 17 Gen IV type colors as `--type-<name>` (`bg-type-fire` and so on)
  - status colors (BRN/PAR/SLP/FRZ/PSN/TOX)
- Typography: Geist (already installed), a 14px base for a dense desktop tool, `tabular-nums` on every number.
- Thin dark scrollbars, visible focus rings, `select-none` on the app chrome.
- Remove the template leftovers listed above. `App.css` is emptied and its import dropped once every class it defines is replaced.

**shadcn primitives** via `npx shadcn add`: `dialog`, `tooltip`, `tabs`, `badge`, `scroll-area`, `separator`, `dropdown-menu`, `sonner` (toasts). `lucide-react` (already a dependency) replaces the unicode glyphs (▶ ■ ← ✕ ⋯ ★ ⚠).

**New shared modules** (each replaces the duplicated copies):
- `src/lib/api.ts`:
  - `API_URL` / `WS_URL` from `import.meta.env.VITE_API_URL`. The default is `http://127.0.0.1:8000`, not `localhost`: on Windows, Chromium may try `::1` first, while uvicorn binds 127.0.0.1.
  - `getJSON` / `postJSON` helpers that throw on non-OK responses.
- `src/lib/sprites.ts`: every sprite source (battle front/back animated and static, gen-7 icon, item icon, trainer). Each builder returns an ordered list of URLs: local file first, then the current remote URL as fallback. Local paths use `import.meta.env.BASE_URL`.
- `src/lib/format.ts`:
  - `hpTier`, `hpRange` (strings unchanged), `winTier`, `formatTime`, number formatting.
  - `displayName()` prettifies the DB names in display only: `Mr_mime`→"Mr. Mime", `Nidoran_f`→"Nidoran♀", `Ho_oh`→"Ho-Oh", `Deoxys_attack`→"Deoxys-Attack", and so on. Lookup keys stay the raw names.
- `src/components/common/`:
  - `Sprite`: an `<img>` that walks its URL list on error, with pixelated rendering.
  - `WinRing` and `WinBar`.
  - `HpBar`.
  - `TypeBadge`, `StatusBadge`, `StageChips`, `VolatileChips`.
  - `MoveList`: the hover-card move list, duplicated 2× today.
  - `IterationsInput`: the formatted number input, duplicated 3× today.

## Phase 2: App shell and the Analyze workspace

**Shell** (`App.tsx` render plus a new `components/TopBar.tsx`):
- Full-height window (`h-screen`); the panes scroll, the page doesn't. Designed for 1280×720 up to 1920×1080 and beyond.
- 48px top bar:
  - Left: app mark and name.
  - Next to it: Setup / Analyze segmented tabs.
  - Right: the run cluster. It has a connection dot with a tooltip, the animated iteration counter (current logic), elapsed time, the `IterationsInput`, and Start/Stop with icons.
  - A 2px progress line under the bar shows iterations / max iterations.
- The duplicate iterations input in the empty Analyze state goes. That state becomes a proper empty-state card with a single Start button.
- Toasts (`sonner`) replace both `alert()` calls. `ContinueModal` gets an error toast too: today it fails silently and doesn't check `res.ok`.
- Keyboard: `Esc` clears the selection or closes the dialog, `Backspace` / `Alt+←` goes back one step, and `1`–`9` picks an action card. Keys are ignored while an input has focus.

**Analyze = 3 panes**, `grid-cols-[240px_minmax(0,1fr)_380px]`:
- **Left, Path rail** (new `components/PathRail.tsx`):
  - Derived from `pathIds` + `nodeMap`. For each step, find the parent's action whose `nodes` contain the child.
  - Each step shows the turn, the action taken, the opponent's reply (`opp_move`), and win% at that node.
  - Root at the top. Clicking a step runs `setPathIds(prev.slice(0, i + 1))`.
  - Pure frontend, no new data.
- **Center, Battle + actions** (`BattleView.tsx` and `ActionPanel.tsx` rewritten on the shared components):
  - **Field strip:** turn, weather with turns left, Gravity, each side's conditions, and the opponent's trainer items as icons with tooltips. Event line: "Opp used X", the death phase, or Baton Pass.
  - **Battle stage:** a subtle gradient stage with the opponent at top-right and my Pokémon at bottom-left. Each has an info plate: display name, level, type badges, status, item icon, HP bar with bracket text, stages, volatiles. The party strip shows icons, a mini HP bar and status; its hover card keeps the existing details.
  - **Recommendation hero:** "Best: Water Gun", with a large win%, expected deaths next to it, and visits small.
  - **Move cards (4 columns):** a type color stripe, name, a physical/special/status icon, power, PP x/y, win% as a large number plus a bar, deaths, and outcome count. Visits stay the faint bottom bar. The best card gets an accent ring and a "Best" pill; the selected card gets a ring.
  - **Switch cards:** icon, name, mini HP bar, win%.
  - **Terminal node:** a result card.
  - **Footer:** "Continue from here" (opens `ContinueModal`, now a shadcn `Dialog`) and "Restart search".
- **Right, Outcome inspector**: `NodePopup.tsx` is reworked into `OutcomeInspector.tsx`, a panel instead of a modal.
  - Header: the selected action with its aggregate win% / deaths / visits.
  - Outcome cards sorted by visits, each with a share-of-rollouts bar, the opponent's move, both Pokémon's HP bracket, status and stages, win%, and an Explore button.
  - Empty state: "Select an action to see its outcomes".
  - Single-outcome actions still navigate directly (existing `handleActionClick`).

**Checkpoint: I stop here and show you the Analyze screen before touching Setup.**

## Phase 3: Setup workspace

`ConfigureView.tsx`, `PokemonSlots.tsx` and `BoxView.tsx`, with the layout `grid-cols-[260px_minmax(0,1fr)_380px]`:
- **Box rail (left, always visible):**
  - Search filter and an icon grid. Clicking an entry adds it to the team (when there's room and it isn't already in); this replaces the separate "Add from box" grid.
  - A `dropdown-menu` on each cell for Edit/Delete, and a "+ New" button.
  - The explicit Save button stays, now with an "unsaved changes" dot.
  - `BoxEntryModal` becomes a shadcn `Dialog` with a two-column form.
- **My team (center):** a responsive grid of cards (2 columns at 1280, 3 at 1920+). Each card has:
  - sprite with the stats hover card (existing `calculateStats`)
  - name, level stepper, type badges, ability · nature
  - 4 move comboboxes with a type dot per move
  - item combobox and a remove button
- **Opponent (right):**
  - Trainer combobox with the trainer sprite.
  - Chips for terrain (not shown anywhere today) and trainer items.
  - 6 compact read-only rows: icon, name, level, types, move chips, item.
- Loading skeletons while `/pokemon-data` loads.

## Phase 4: Electron readiness

- `vite.config.ts`: `base: './'`, so `dist/` loads from `file://`.
- **WebSocket reconnect** with backoff (1s → 5s cap). Once connected, `/trainers`, `/pokemon-data` and `/box` are fetched again if they haven't loaded yet.
- **Backend-offline state:** "Waiting for backend…" covers the app until the first connection, instead of half-loaded screens.
- **Offline sprites:**
  - New root script `fetch_sprites.py` (stdlib only, next to `generate_constants.py`). It reads the ids via `DataBase.PkDB.sprite_id` over `PokIdToName`, the items from `ItemDB.json` (same name→file rule as today), and the trainer sprites from `TrainerDB.json`.
  - It downloads into `frontend/public/sprites/{front,back,front-static,back-static,icons,items,trainers}/`, skips files it already has, and tolerates 404s (some forms have no animated sprite; `Sprite` falls back to static).
  - Size: about 505 Pokémon × 4 + 58 items + 13 trainers, roughly 20–40 MB.
  - Default: **gitignored**, and you run the script before building. Say so if you'd rather commit the files.
- `index.html` gets a proper favicon and title.

## Phase 5: Backend additions (read-only, additive)

- `backend/serializer.py`:
  - `_MOVE_INFO = {getattr(MoveName, e["name"].upper()): e for e in moveDB.values()}`, the same key rule as `Models/move.py:58`.
  - `_extract_moves` entries gain `type`, `category`, `power`.
  - Move actions gain `move_type`, `category`, `power` (`null` for Struggle and switches).
  - `_pok` gains `types` and `level`; `_bench_entry` gains `types`. Types come from `pkDB[PokIdToName[id].capitalize()]["type"]`, the same rule as `DataBase/PkDB.py:558`.
- `backend/main.py` `/pokemon-data` gains `moveInfo` (`{name: {type, category, power, accuracy, pp}}`) and `pokemonTypes` (`{name: [types]}`), for the Setup screen.
- `frontend/src/types.ts` is kept in sync. New fields are optional where a payload can lack them.
- `tests/test_backend.py`: `test_pokemon_data` and `test_serialize_node_is_json_ready` assert the new keys, for example that Ember is Fire/Special/40 and Charmander's types are `["Fire"]`.

This phase lands first in practice: phases 2 and 3 use the type data.

---

## Files touched

- **Rewritten (markup and styles):** `App.tsx` (render only), `BattleView.tsx`, `ActionPanel.tsx`, `ContinueModal.tsx`, `ConfigureView.tsx`, `PokemonSlots.tsx`, `BoxView.tsx`, `index.css`, `App.css` (emptied).
- **Reworked:** `NodePopup.tsx` → `OutcomeInspector.tsx`.
- **New:**
  - `lib/api.ts`, `lib/sprites.ts`, `lib/format.ts`
  - `components/common/*`, `components/TopBar.tsx`, `components/PathRail.tsx`
  - the shadcn `ui/*` adds
  - `fetch_sprites.py`
- **Config and backend:** `vite.config.ts`, `index.html`, `frontend/.gitignore`, `backend/serializer.py`, `backend/main.py`, `tests/test_backend.py`.

## Verification

1. `cd frontend && npm install` (no `node_modules` in this checkout), then `npm run build` (tsc and the Vite build) and `npm run lint`.
2. `pytest` for the backend field tests. No `@njit` code changes, so `-m jit` isn't needed.
3. `python fetch_sprites.py`, then `dev.bat`. Check:
   - At 1280×720 and 1920×1080: no page scroll, panes scroll independently.
   - The combobox dropdowns are dark.
   - Path rail navigation, inspector selection, the death and Baton Pass phases (scenario: a fainted active), the terminal node, Continue from here, keyboard shortcuts.
   - Box add/edit/delete/save (on a copy of `UserData/box.json`).
4. Backend offline: start the frontend first, then uvicorn. The "Waiting for backend" state should clear on its own.
5. `npm run build` + `npx vite preview --base ./`, and open `dist/index.html` through a file-style base to confirm the relative assets and local sprites load with the network off.

## Noticed, not changing (needs your call)

- **PP lookup bug.** `serializer.py` `_MOVE_ID_TO_MAX_PP` looks up MoveDB with `raw_name.replace("_"," ").title()`, which misses **Mud-Slap** and **Will-O-Wisp** (the MoveDB keys have hyphens). I checked all 222 moves: only those two mismatch. For those moves the action card hides PP, and the hover lists show `cur/cur`. Several trainers up to Roark run Mud-Slap. The fix is a one-liner: derive the map from the new `_MOVE_INFO`. Not included unless you OK it.
- **Display-name gap.** Snapshot names come from `PokIdToName[...].capitalize()` (`Mr_mime`, `Ho_oh`). The plan only prettifies them in the frontend (`displayName`); the payload stays as it is.
