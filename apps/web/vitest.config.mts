import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";
import { fileURLToPath } from "url";

const currentDirectory = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", setupFiles: ["./test/setup.ts"], exclude: ["e2e/**", "node_modules/**", ".next/**"] },
  resolve: { alias: { "@": path.resolve(currentDirectory, ".") } },
});
