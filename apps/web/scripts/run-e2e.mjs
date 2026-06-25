import { spawn } from "node:child_process";

const baseUrl = "http://127.0.0.1:3000";

let server;

try {
  const alreadyRunning = await waitForServer(2_000);
  if (!alreadyRunning) {
    server = spawn(
      process.execPath,
      ["./node_modules/next/dist/bin/next", "dev", "--hostname", "127.0.0.1", "--port", "3000"],
      { cwd: process.cwd(), env: process.env, stdio: "inherit" },
    );
    await waitForServer(120_000, true);
  }

  const status = await runPlaywright();
  await stopServer();
  process.exit(status);
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
  await stopServer();
  process.exit(1);
}

async function runPlaywright() {
  return await new Promise((resolve) => {
    const child = spawn(
      process.execPath,
      ["./node_modules/@playwright/test/cli.js", "test"],
      { cwd: process.cwd(), env: process.env, stdio: "inherit" },
    );
    child.on("exit", (code) => resolve(code ?? 1));
  });
}

async function waitForServer(timeoutMs, required = false) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(baseUrl, { signal: AbortSignal.timeout(1_000) });
      if (response.ok) return true;
    } catch {
      // Keep polling until the timeout expires.
    }
    await delay(500);
  }
  if (required) throw new Error(`Timed out waiting for ${baseUrl}`);
  return false;
}

async function stopServer() {
  if (!server?.pid) return;
  if (process.platform === "win32") {
    await new Promise((resolve) => {
      const killer = spawn("taskkill", ["/pid", String(server.pid), "/T", "/F"], { stdio: "ignore" });
      killer.on("exit", resolve);
      killer.on("error", resolve);
    });
    return;
  }
  server.kill("SIGTERM");
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
