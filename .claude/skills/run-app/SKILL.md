---
name: run-app
description: Launch and drive this project's real app (React frontend + FastAPI backend) with a throwaway box, click through it with real mouse events, measure the layout and take screenshots at chosen window sizes. Use this whenever asked to run, start, open or screenshot the app, or to check that a frontend, Setup, Tracker, box or Electron change really works and looks right, even if the user doesn't say "run". It keeps the user's real UserData files safe, so prefer it to starting dev.bat or electron:dev.
---

# Run the app

Runs the real frontend and backend on their own ports, with temp data files, and drives the page from a hidden Electron window. Nothing needs installing: it uses the project's `.venv` and `frontend/node_modules`.

Two choices protect the user's data, so keep them:

- **Temp data files.** `UserData/box.json` and `nuzlocke.json` hold the user's real run, and just picking a trainer writes `last_trainer`. `PBO_BOX_PATH` and `PBO_NUZLOCKE_PATH` send all of that elsewhere.
- **Own ports (8765 and 5199).** The user may have `dev.bat` running on 8000 and 5173 at the same time. On those ports the test would edit their real run.

## Steps

Run these from the repo root in the Bash tool. Set `RUN` to a folder in the session's scratchpad.

1. **Make the temp data:**
   ```bash
   RUN="<scratchpad>/run-app"; mkdir -p "$RUN/shots"
   cp .claude/skills/run-app/scripts/test_box.json "$RUN/box.json"; rm -f "$RUN/nuzlocke.json"
   ```

2. **Start the backend**, as a background command (shell variables don't carry over, so spell out the path):
   ```bash
   PBO_BOX_PATH="<RUN>/box.json" PBO_NUZLOCKE_PATH="<RUN>/nuzlocke.json" NUMBA_DISABLE_JIT=1 .venv/Scripts/python.exe -m uvicorn backend.main:app --port 8765
   ```
   `NUMBA_DISABLE_JIT=1` skips the warm-up compile, so it's ready in seconds, but a search crawls. To test a search, leave it out and allow about 2 minutes.

3. **Start the frontend**, as another background command:
   ```bash
   cd frontend && VITE_API_URL=http://127.0.0.1:8765 npx vite --port 5199 --strictPort
   ```

4. **Wait until both answer:**
   ```bash
   for i in $(seq 1 60); do curl -sf http://127.0.0.1:8765/box >/dev/null && curl -sf http://localhost:5199/ >/dev/null && break; ping -n 2 127.0.0.1 >/dev/null; done; curl -s http://127.0.0.1:8765/box | head -c 40
   ```
   It should print the start of the test box. Foreground `sleep` is blocked, hence the `ping`.

5. **Drive it.** With no scenario it runs `scripts/setup_scenario.cjs`, which fills the party on Setup and picks a trainer:
   ```bash
   env -u ELECTRON_RUN_AS_NODE SHOT_DIR="<RUN>/shots" frontend/node_modules/.bin/electron .claude/skills/run-app/scripts/driver.cjs [my_scenario.cjs]
   ```
   The `env -u` matters: the VS Code environment sets `ELECTRON_RUN_AS_NODE`, and Electron then starts as plain Node and fails with "Cannot find module 'electron'".

6. **Look at the PNGs in `shots/` with the Read tool**, and read the printed layout numbers and console errors. A page can render its shell while something is broken.

7. **Stop the servers** by port, in PowerShell. Only these two ports, never 8000 or 5173:
   ```powershell
   Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 8765,5199 } | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
   ```
   The two background tasks then report as failed (exit code 127 from Bash, 255 from PowerShell). That's this kill, not a problem.

## Writing a scenario

A scenario is a CommonJS file that exports `async (h) => { ... }`. Write it in the scratchpad unless it's worth keeping. Pass an absolute path. `scripts/setup_scenario.cjs` is a short example.

| Helper | What it does |
|---|---|
| `h.resize(w, h)` | Sets the viewport, and can go larger than the screen because the window is hidden |
| `h.clickSlot(name, button?)` | Clicks a Pokémon in the box, by its display name |
| `h.click(x, y, button?)` | Real mouse move and click at viewport coordinates |
| `h.clickText(text, root?)` | Finds a button by its text and clicks it for real |
| `h.moveAway()` | Parks the cursor on the top bar, so no hover card is left open |
| `h.party()` | Names on the party cards, in order |
| `h.clearParty()` | Empties the party through the box |
| `h.trainer(name)` | Selects a trainer with the panel's ‹ › buttons, and returns whether it was found |
| `h.layout()` | Measures Setup: scrolling, card sizes, sprite scales, overflow and clipping |
| `h.shot(name)` | Saves `SHOT_DIR/name.png` |
| `h.js(code)` | Runs code in the page and returns the result |
| `h.sleep(ms)`, `h.say(...)` | Waits, prints |

## Getting a real answer

- **Measure as well as look.** A screenshot can hide a sprite drawn at the wrong size, so compare what `h.layout()` reports with what the code asks for. That's how flex-shrunk sprites were caught here.
- **Test the sizes that matter:** 1920×1080 (full screen) and 1920×1000 (maximized) with 6 party cards come first, since that's how the app is used. Then 1440×900 and 1280×720 (the minimum) should stay usable. Viewing a single size misses most layout bugs.
- **Try the sprites that fill their frame**, Gyarados and Onix, when checking for overlaps. The test box has both.
- `h.shot` captures twice on purpose. A hidden window paints on capture, so the first frame is one state behind.
- **The backend remembers its last search.** A new page shows that search's status and replays any error it ended with, so restart the backend before trusting a toast or a "Done" in the top bar. A failed search also prints its traceback in the backend's output.
- **A screenshot can lag behind the page**, most of all after several quick steps. One run showed a dropdown still open after the page had moved on to the box editor, and others showed no dropdown though it was open. So wait before `h.shot` and read the state through `h.js` too. If the picture doesn't show what the check was about, the check doesn't count: rerun it alone. A sprite measured inside an open dropdown reads a little small (15.2px for 16px), because its zoom-in animation stays paused.
- This PC runs at 150% Windows scaling, so a 1920×1080 viewport gives a 2880×1620 PNG. Sizes in `h.layout()` are CSS pixels, the same ones a full HD monitor at 100% shows.

## Testing the desktop window itself

The steps above load the page in a plain window, which skips `frontend/electron/main.js`. To check `main.js` itself (window size, maximizing, starting the backend), run the real entry point with the Vite server from step 3 still up. It starts its own backend on a free port and needs the same temp data:

```bash
env -u ELECTRON_RUN_AS_NODE PBO_BOX_PATH="<RUN>/box.json" PBO_NUZLOCKE_PATH="<RUN>/nuzlocke.json" NUMBA_DISABLE_JIT=1 ELECTRON_DEV_URL=http://localhost:5199 frontend/node_modules/.bin/electron .claude/skills/run-app/scripts/check_window.cjs
```

It prints the window's state and quits. Its userData goes to a temp folder, so it can't touch the installed app's data or logs. The window is really shown, so it appears on the user's screen for a few seconds.
