// Runs before the page loads. Hands the page the backend URL that main.js chose; the page itself
// stays sandboxed with no Node access. Read by src/lib/api.ts as window.desktop.apiUrl.
const { contextBridge } = require("electron");

const arg = process.argv.find((a) => a.startsWith("--pbo-api-url="));

contextBridge.exposeInMainWorld("desktop", {
  apiUrl: arg ? arg.slice("--pbo-api-url=".length) : null,
});
