// Runs the real desktop entry point (frontend/electron/main.js), prints its window's state and quits.
// userData goes to a temp folder first, so the installed app's lock, data and logs stay out of it.
const { app } = require("electron");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { pathToFileURL } = require("url");

app.setPath("userData", fs.mkdtempSync(path.join(os.tmpdir(), "pbo-check-window-")));

app.on("browser-window-created", (_, win) => {
  win.once("show", async () => {
    await new Promise((r) => setTimeout(r, 1500));
    const display = require("electron").screen.getDisplayMatching(win.getBounds());
    console.log(JSON.stringify({
      maximized: win.isMaximized(),
      fullscreen: win.isFullScreen(),
      contentSize: win.getContentSize(),
      restoresTo: win.getNormalBounds(),
      workArea: display.workAreaSize,
    }));
    app.quit();
  });
});

const main = path.resolve(__dirname, "..", "..", "..", "..", "frontend", "electron", "main.js");
import(pathToFileURL(main).href);
