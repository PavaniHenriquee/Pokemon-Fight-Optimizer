import path from "path"
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  // Relative asset paths, so dist/ also loads from file:// (Electron)
  base: "./",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  build: {
    // One local bundle (~500 kB); the default 500 kB warning is meant for websites
    chunkSizeWarningLimit: 1000,
  },
})