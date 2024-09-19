import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      crypto: "empty-module",
    },
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
});
