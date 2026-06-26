import { defineConfig } from "vite";

// ローカル収録ツール。ビルド出力は dist/、開発は `npm run dev`。
export default defineConfig({
  base: "./",
  server: {
    host: "127.0.0.1",
    port: 5180,
  },
  build: {
    outDir: "dist",
    target: "es2022",
  },
});
