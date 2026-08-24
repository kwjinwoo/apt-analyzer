import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

const frontendRoot = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  root: frontendRoot,
  build: {
    outDir: "../src/apt_analyzer/web/static",
    emptyOutDir: true,
    rollupOptions: {
      input: fileURLToPath(new URL("./src/main.ts", import.meta.url)),
      output: {
        entryFileNames: "assets/apt-analyzer-web.js",
        assetFileNames: "assets/apt-analyzer-web[extname]",
      },
    },
  },
  test: {
    environment: "node",
  },
});
