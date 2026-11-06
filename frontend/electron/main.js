// Electron main process: starts the Python backend on a free port, opens the window, and stops
// the backend when the app closes.
//
// Dev (`npm run electron:dev`): the repo's .venv, UserData/box.json, the repo's .numba_cache,
// and the Vite dev server (`electron . --dist` loads the built dist/ instead).
// Packaged: the bundled Python in resources/backend (see build_python.py), the box in
// %APPDATA%\Nuzlocke Optimizer, the Numba cache in %LOCALAPPDATA%\Nuzlocke Optimizer.
import { app, BrowserWindow, Menu, dialog, shell } from "electron";
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";

const HERE = import.meta.dirname;
const DEV = !app.isPackaged;
const DEV_URL = process.env.ELECTRON_DEV_URL || "http://localhost:5173";
const LOAD_DIST = !DEV || process.argv.includes("--dist");

let win = null;
let backend = null;
let quitting = false;
const recentLog = []; // last lines of backend output, shown if it crashes

// ─── backend ────────────────────────────────────────────────────────────────

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function backendPaths() {
  if (DEV) {
    const repo = path.resolve(HERE, "..", "..");
    const venv = path.join(repo, ".venv", "Scripts", "python.exe");
    return { python: fs.existsSync(venv) ? venv : "python", cwd: repo, env: {} };
  }
  const res = path.join(process.resourcesPath, "backend");
  const boxPath = path.join(app.getPath("userData"), "box.json");
  const seed = path.join(res, "seed", "box.json");
  if (!fs.existsSync(boxPath) && fs.existsSync(seed)) {
    fs.mkdirSync(path.dirname(boxPath), { recursive: true });
    fs.copyFileSync(seed, boxPath); // first launch starts with the box from the repo
  }
  const localAppData = process.env.LOCALAPPDATA || app.getPath("userData");
  return {
    python: path.join(res, "python", "python.exe"),
    cwd: path.join(res, "src"),
    env: {
      PBO_BOX_PATH: boxPath,
      PBO_NUZLOCKE_PATH: path.join(app.getPath("userData"), "nuzlocke.json"),
      PBO_CACHE_ROOT: path.join(localAppData, app.getName(), "numba_cache"),
    },
  };
}

function openLog() {
  const dir = path.join(app.getPath("userData"), "logs");
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, "backend.log");
  if (fs.existsSync(file)) fs.renameSync(file, path.join(dir, "backend.prev.log"));
  return fs.createWriteStream(file);
}

function startBackend(port) {
  const { python, cwd, env } = backendPaths();
  const log = openLog();
  const args = ["-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", String(port)];
  backend = spawn(python, args, {
    cwd,
    env: {
      ...process.env,
      ...env,
      PBO_EXIT_WITH_PARENT: "1", // the backend exits when this stdin pipe closes
      PYTHONUNBUFFERED: "1",
      PYTHONIOENCODING: "utf-8",
    },
    stdio: ["pipe", "pipe", "pipe"],
    windowsHide: true,
  });

  const onOutput = (chunk) => {
    log.write(chunk);
    if (DEV) process.stdout.write(chunk);
    recentLog.push(...chunk.toString().split(/\r?\n/).filter(Boolean));
    recentLog.splice(0, Math.max(0, recentLog.length - 25));
  };
  backend.stdout.on("data", onOutput);
  backend.stderr.on("data", onOutput);

  const fail = (reason) => {
    if (quitting) return;
    dialog.showErrorBox(
      "The battle engine stopped",
      `${reason}\n\n${recentLog.join("\n")}\n\nFull log: ${path.join(app.getPath("userData"), "logs", "backend.log")}`,
    );
    app.quit();
  };
  backend.on("error", (err) => fail(`Couldn't start Python (${python}): ${err.message}`));
  backend.on("exit", (code) => fail(`The backend exited with code ${code}.`));
}

function stopBackend() {
  if (!backend || backend.exitCode !== null) return;
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/pid", String(backend.pid), "/T", "/F"], { windowsHide: true });
  } else {
    backend.kill();
  }
}

// ─── window ─────────────────────────────────────────────────────────────────

function createWindow(apiUrl) {
  win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1280,
    minHeight: 720,
    show: false,
    backgroundColor: "#0b0c10", // the app's --background, so there's no white flash
    autoHideMenuBar: true,
    icon: path.join(HERE, "icon.png"),
    webPreferences: {
      preload: path.join(HERE, "preload.cjs"),
      additionalArguments: [`--pbo-api-url=${apiUrl}`],
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
    },
  });
  win.once("ready-to-show", () => win.show());

  // Links open in the normal browser, never inside the app
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (e, url) => {
    if (url !== win.webContents.getURL()) {
      e.preventDefault();
      shell.openExternal(url);
    }
  });

  if (LOAD_DIST) win.loadFile(path.join(HERE, "..", "dist", "index.html"));
  else win.loadURL(DEV_URL);
}

// ─── app lifecycle ──────────────────────────────────────────────────────────

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!win) return;
    if (win.isMinimized()) win.restore();
    win.focus();
  });

  app.whenReady().then(async () => {
    if (!DEV) Menu.setApplicationMenu(null);
    const port = await freePort();
    startBackend(port);
    createWindow(`http://127.0.0.1:${port}`);
  });

  app.on("before-quit", () => {
    quitting = true;
    stopBackend();
  });
  app.on("window-all-closed", () => app.quit());
}
