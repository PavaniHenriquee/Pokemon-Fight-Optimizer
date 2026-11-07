// Drives the app in a hidden Electron window with real mouse events. See ../SKILL.md.
// electron driver.cjs [scenario.cjs]   SHOT_DIR = where screenshots go, APP_URL = the Vite server
const { app, BrowserWindow } = require("electron");
const fs = require("fs");
const path = require("path");

const APP_URL = process.env.APP_URL || "http://localhost:5199";
const SHOT_DIR = process.env.SHOT_DIR || process.cwd();
const scenarioArg = process.argv.slice(1).find((a) => /\.c?js$/.test(a) && !a.endsWith("driver.cjs"));
const SCENARIO = scenarioArg ? path.resolve(scenarioArg) : path.join(__dirname, "setup_scenario.cjs");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const q = JSON.stringify;

function makeHelpers(win) {
  const js = (code) => win.webContents.executeJavaScript(code);
  const TEAM = `[...document.querySelectorAll('section')].find(s => s.textContent.includes('Your team'))`;
  const OPP = `[...document.querySelectorAll('aside')].at(-1)`;

  const h = {
    win,
    js,
    sleep,
    say: (...args) => console.log(...args),

    async resize(w, height) {
      win.setContentSize(w, height);
      await sleep(400);
      h.say("viewport", (await js("[innerWidth, innerHeight]")).join("x"));
    },

    async click(x, y, button = "left") {
      win.webContents.sendInputEvent({ type: "mouseMove", x, y });
      await sleep(40);
      win.webContents.sendInputEvent({ type: "mouseDown", x, y, button, clickCount: 1 });
      win.webContents.sendInputEvent({ type: "mouseUp", x, y, button, clickCount: 1 });
      await sleep(150);
    },

    moveAway: () => win.webContents.sendInputEvent({ type: "mouseMove", x: 900, y: 12 }),

    async clickSlot(name, button) {
      const p = await js(`(() => {
        const b = [...document.querySelectorAll('aside button[title]')].find(e => e.title === ${q(name)});
        if (!b) return null;
        const r = b.getBoundingClientRect();
        return [Math.round(r.x + r.width / 2), Math.round(r.y + r.height / 2)];
      })()`);
      if (!p) throw new Error(`no box slot named ${name}`);
      await h.click(p[0], p[1], button);
    },

    async clickText(text, root = "document") {
      const p = await js(`(() => {
        const b = [...${root}.querySelectorAll('button')].find(e => e.textContent.includes(${q(text)}));
        if (!b) return null;
        const r = b.getBoundingClientRect();
        return [Math.round(r.x + r.width / 2), Math.round(r.y + r.height / 2)];
      })()`);
      if (!p) throw new Error(`no button with text ${text}`);
      await h.click(p[0], p[1]);
    },

    party: () => js(`[...${TEAM}.querySelectorAll('.font-semibold.tracking-tight')].map(e => e.textContent)`),

    async clearParty() {
      for (const member of await h.party()) await h.clickSlot(member);
    },

    // Steps the panel's own ‹ › buttons
    async trainer(name) {
      const state = () => js(`(() => { const o = ${OPP}; return {
        value: o.querySelector('input').value,
        prev: !o.querySelector('[aria-label="Previous trainer"]').disabled,
        next: !o.querySelector('[aria-label="Next trainer"]').disabled }; })()`);
      const press = (label) => js(`${OPP}.querySelector('[aria-label="${label}"]').click()`);
      let s = await state();
      while (s.prev) { await press("Previous trainer"); await sleep(40); s = await state(); }
      while (s.value !== name && s.next) { await press("Next trainer"); await sleep(40); s = await state(); }
      await sleep(200);
      return s.value === name;
    },

    // What Setup really drew. Sprite scales come from rendered widths, not from what the code asked for.
    layout: () => js(`(() => {
      const team = ${TEAM};
      const scroller = team.children[1];
      const cards = [...team.querySelectorAll('.group.relative')].map(c => {
        const r = c.getBoundingClientRect();
        const img = c.querySelector('img[alt]:not([title])');
        return Math.round(r.width) + 'x' + Math.round(r.height) + ' sprite ' + (img ? (img.getBoundingClientRect().width / 96).toFixed(2) + 'x' : 'none');
      });
      const sticksOut = [...team.querySelectorAll('[data-slot=input-group], img[title]')].filter(e => {
        const c = e.closest('.group.relative').getBoundingClientRect();
        return e.getBoundingClientRect().right > c.right + 0.5;
      }).length;
      const opp = ${OPP}.children[1];
      const oppCards = [...opp.querySelectorAll('.overflow-hidden.rounded-xl')].filter(e => !e.querySelector('[data-slot=input-group]'));
      const summary = document.querySelector('aside .min-h-0.flex-1.overflow-y-auto');
      return {
        partyScroll: scroller.scrollHeight - scroller.clientHeight,
        cards: [...new Set(cards)],
        sticksOut,
        opponentScroll: opp.scrollHeight - opp.clientHeight,
        opponentRows: oppCards.map(c => Math.round(c.getBoundingClientRect().height) + (c.scrollHeight > c.clientHeight + 1 ? ' clipped' : '')),
        summaryScroll: summary ? summary.scrollHeight - summary.clientHeight : null,
      };
    })()`),

    // A hidden window paints on capture: the first frame is one state behind
    async shot(name) {
      await sleep(250);
      await win.webContents.capturePage();
      await sleep(250);
      const file = path.join(SHOT_DIR, `${name}.png`);
      fs.writeFileSync(file, (await win.webContents.capturePage()).toPNG());
      h.say("shot", file);
    },
  };
  return h;
}

async function main() {
  fs.mkdirSync(SHOT_DIR, { recursive: true });
  const win = new BrowserWindow({
    width: 1920,
    height: 1080,
    useContentSize: true,
    show: false,
    frame: false,
    webPreferences: { backgroundThrottling: false },
  });
  const errors = [];
  win.webContents.on("console-message", (e) => {
    if (e.level === "error") errors.push(e.message);
  });
  await win.loadURL(APP_URL);
  const h = makeHelpers(win);
  for (let i = 0; i < 120; i++) {
    if (await h.js(`!!document.querySelector('aside button[title]')`)) break;
    await sleep(500);
  }
  if (!(await h.js(`!!document.querySelector('aside button[title]')`))) {
    throw new Error("the box never showed a Pokémon: is the backend up, on the test box?");
  }
  await require(SCENARIO)(h);
  console.log("console errors:", JSON.stringify(errors.slice(0, 10)));
  app.quit();
}

app.whenReady().then(() =>
  main().catch((e) => {
    console.log("DRIVER ERROR:", e.stack);
    app.exit(1);
  }),
);
