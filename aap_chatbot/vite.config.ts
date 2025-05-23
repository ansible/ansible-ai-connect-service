import { configDefaults, defineConfig } from "vitest/config";
import { resolve } from "path";
import dts from "vite-plugin-dts";
import react from "@vitejs/plugin-react";
import cleanPlugin from "vite-plugin-clean";
import { viteStaticCopy } from "vite-plugin-static-copy";

// https://vitejs.dev/guide/build.html#library-mode
export default defineConfig({
  build: {
    lib: {
      entry: resolve(__dirname, "src/index.tsx"),
      name: "ansible-chatbot",
      fileName: "ansible-chatbot",
    },
    rollupOptions: {
      // make sure to externalize deps that shouldn't be bundled
      // into your library
      external: ["react"],
    },
  },
  define: {
    global: "globalThis",
  },
  test: {
    browser: {
      name: "chromium",
      enabled: true,
      provider: "playwright",
      viewport: { width: 1920, height: 1080 },
    },
    setupFiles: "./src/setupTests.ts",
    coverage: {
      provider: "v8",
      exclude: [
        ...configDefaults.exclude,
        "**/*.d.ts",
        "**/*.test.ts",
        "**/*.test.tsx",
        "src/index.tsx",
        "src/reportWebVitals.ts",
      ],
      reporter: ["text", "html", "lcov"],
    },
  },
  plugins: [
    cleanPlugin(),
    react(),
    dts(),
    viteStaticCopy({
      targets: [
        {
          src: "src/public/lightspeed.svg",
          dest: "public/",
        },
        {
          src: "src/public/lightspeed_dark.svg",
          dest: "public/",
        },
        {
          src: "src/public/user_logo.png",
          dest: "public/",
        },
      ],
    }),
  ],
});
