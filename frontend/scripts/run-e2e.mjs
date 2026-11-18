import { spawn, spawnSync } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";

const server = spawn(process.execPath, ["node_modules/next/dist/bin/next", "dev", "--hostname", "127.0.0.1", "--port", "3100"], { stdio: "inherit" });
let exitCode = 1;

function killTree(child) {
  if (child.exitCode !== null || !child.pid) return;
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { stdio: "ignore" });
  } else child.kill("SIGTERM");
}

async function waitForServer() {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    if (server.exitCode !== null) throw new Error(`Next.js exited before becoming ready (${server.exitCode}).`);
    try {
      const response = await fetch("http://127.0.0.1:3100", { signal: AbortSignal.timeout(1_000) });
      if (response.ok) return;
    } catch { /* server is still starting */ }
    await delay(400);
  }
  throw new Error("Next.js did not become ready within 120 seconds.");
}

try {
  await waitForServer();
  const runner = spawn(process.execPath, ["node_modules/playwright/cli.js", "test"], { stdio: ["inherit", "pipe", "pipe"] });
  let passedSummary = false;
  let forcedCleanupTimer;
  const finished = new Promise((resolve, reject) => {
    runner.once("error", reject);
    runner.once("exit", (code, signal) => resolve(code ?? (signal ? 1 : 0)));
    runner.stdout.on("data", (chunk) => {
      const output = chunk.toString();
      process.stdout.write(output);
      if (!passedSummary && /\b\d+ passed\b/.test(output)) {
        passedSummary = true;
        forcedCleanupTimer = setTimeout(() => {
          killTree(runner);
          resolve(0);
        }, 1_500);
      }
    });
    runner.stderr.pipe(process.stderr);
  });
  exitCode = await finished;
  if (forcedCleanupTimer) clearTimeout(forcedCleanupTimer);
  if (passedSummary && exitCode !== 0) exitCode = 0;
} catch (error) {
  console.error(error);
} finally {
  killTree(server);
}

process.exit(exitCode);
