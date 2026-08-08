import http from "node:http";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const host = "127.0.0.1";
const port = 3000;
const scriptDir = dirname(fileURLToPath(import.meta.url));
const projectDir = resolve(scriptDir, "../..");
const webDir = join(projectDir, "apps", "web");

process.env.NODE_ENV = "production";
process.env.NEXT_PUBLIC_API_URL ??= "http://127.0.0.1:4010/api/v1";
process.env.NEXT_PUBLIC_DATA_BROWSER_V2 ??= "true";

await import("./mock-api.mjs");

const { default: next } = await import("next");
const app = next({ dev: false, dir: webDir, hostname: host, port });
const handle = app.getRequestHandler();

await app.prepare();

const server = http.createServer((request, response) => handle(request, response));
server.on("error", (error) => {
  console.error("MacroLens local preview failed:", error);
  process.exitCode = 1;
});
server.listen(port, host, () => {
  console.log(`MacroLens local preview: http://localhost:${port}/data`);
});
