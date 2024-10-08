/// <reference types="vitest" />
/// <reference types="vite/client" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      crypto: "empty-module",
    },
    // https://stackoverflow.com/questions/73143071/vitest-unexpected-token-export
    mainFields: ["module"],
  },
  server: {
    port: 3000,
  },
  define: {
    global: "globalThis",
  },
  build: {
    assetsDir: "static/chatbot/",
  },
  test: {
    globals: true,
    environment: "happy-dom",
    // https://stackoverflow.com/questions/78989267/vitest-unknown-file-extension-css
    pool: "vmThreads",
    setupFiles: "./src/setupTests.ts",
  },
});
