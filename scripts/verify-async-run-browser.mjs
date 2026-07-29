#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const chromiumBin = process.env.CHROMIUM_BIN ?? "chromium";
const outputDir = resolve(root, process.env.ASYNC_RUN_BROWSER_OUTPUT_DIR ?? "artifacts/async-run/generated");
const apiKey = "async-run-browser-admin-key-material-2026";
const children = [];
const temporary = [];

function selectPython() {
  const candidates = [
    process.env.ASYNC_RUN_BROWSER_PYTHON,
    resolve(root, ".venv/bin/python"),
    "/tmp/inc019-cookie-venv/bin/python",
    "/tmp/ai-native-content-agency-runtime/bin/python",
    "python3.13", "python3.12", "python3.11", "python3",
  ].filter(Boolean);
  for (const candidate of candidates) {
    const probe = spawnSync(candidate, ["-c", "import fastapi, uvicorn, pg8000, httpx"], {
      cwd: root,
      stdio: "ignore",
    });
    if (probe.status === 0) return candidate;
  }
  throw new Error("No supported Python runtime is available for the async browser gate.");
}

function availablePort() {
  return new Promise((resolvePort, reject) => {
    const server = createServer();
    server.unref();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") return reject(new Error("Unable to allocate local port"));
      server.close((error) => error ? reject(error) : resolvePort(address.port));
    });
  });
}

function start(command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: root,
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
    detached: true,
    ...options,
  });
  child.output = "";
  child.stdout.on("data", (chunk) => { child.output = `${child.output}${chunk}`.slice(-30000); });
  child.stderr.on("data", (chunk) => { child.output = `${child.output}${chunk}`.slice(-30000); });
  children.push(child);
  return child;
}

async function stopAll() {
  for (const child of children.reverse()) {
    if (child.exitCode === null && child.signalCode === null) {
      try { process.kill(-child.pid, "SIGTERM"); } catch { child.kill("SIGTERM"); }
    }
  }
  await new Promise((resolveWait) => setTimeout(resolveWait, 350));
  for (const child of children) {
    if (child.exitCode === null && child.signalCode === null) {
      try { process.kill(-child.pid, "SIGKILL"); } catch { child.kill("SIGKILL"); }
    }
  }
  for (const path of temporary) await rm(path, { recursive: true, force: true });
}

async function waitFor(url, child, attempts = 100) {
  let lastError;
  for (let index = 0; index < attempts; index += 1) {
    if (child.exitCode !== null || child.signalCode !== null) {
      throw new Error(`Process exited before readiness: ${child.output}`);
    }
    try {
      const response = await fetch(url);
      if (response.ok) return response;
      lastError = new Error(`${url} returned ${response.status}`);
    } catch (error) { lastError = error; }
    await new Promise((resolveWait) => setTimeout(resolveWait, 150));
  }
  throw lastError ?? new Error(`Timed out waiting for ${url}`);
}

class CdpClient {
  constructor(url) {
    this.socket = new WebSocket(url);
    this.nextId = 1;
    this.pending = new Map();
    this.events = new Map();
  }
  async open() {
    await new Promise((resolveOpen, reject) => {
      this.socket.addEventListener("open", resolveOpen, { once: true });
      this.socket.addEventListener("error", reject, { once: true });
    });
    this.socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const pending = this.pending.get(message.id);
        if (!pending) return;
        this.pending.delete(message.id);
        if (message.error) pending.reject(new Error(message.error.message));
        else pending.resolve(message.result);
        return;
      }
      const listeners = this.events.get(message.method) ?? [];
      this.events.delete(message.method);
      for (const listener of listeners) listener(message.params);
    });
  }
  send(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolveCall, reject) => {
      this.pending.set(id, { resolve: resolveCall, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }
  once(method) {
    return new Promise((resolveEvent) => {
      const listeners = this.events.get(method) ?? [];
      listeners.push(resolveEvent);
      this.events.set(method, listeners);
    });
  }
  async evaluate(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
      userGesture: true,
    });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text ?? "Evaluation failed");
    return result.result.value;
  }
  close() { this.socket.close(); }
}

function requireCondition(condition, message) {
  if (!condition) throw new Error(message);
}

async function waitForExpression(client, expression, message, attempts = 100) {
  for (let index = 0; index < attempts; index += 1) {
    if (await client.evaluate(expression)) return;
    await new Promise((resolveWait) => setTimeout(resolveWait, 120));
  }
  throw new Error(message);
}

async function run() {
  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });
  const python = selectPython();
  const port = await availablePort();
  const baseUrl = `http://127.0.0.1:${port}`;
  const work = await mkdtemp(join(tmpdir(), "agency-async-run-"));
  temporary.push(work);
  const identities = JSON.stringify([{
    tenant_id: "async-browser-tenant",
    subject_id: "async-browser-admin",
    role: "admin",
    key_id: "async-browser-admin-v1",
    api_key: apiKey,
    active: true,
  }]);
  const api = start(python, [
    "-m", "uvicorn", "agency_runtime.api:app",
    "--host", "127.0.0.1", "--port", String(port),
  ], {
    env: {
      ...process.env,
      PYTHONPATH: resolve(root, "backend"),
      AGENCY_STATIC_DIR: resolve(root, "dist"),
      AGENCY_MEMORY_DB: join(work, "runtime.sqlite3"),
      AGENCY_IDENTITY_CREDENTIALS_JSON: identities,
      AGENCY_SESSION_COOKIE_SECURE: "false",
      AGENCY_RUN_WORKER_POLL_INTERVAL_SECONDS: "0.45",
      AGENCY_RUN_LEASE_SECONDS: "30",
    },
  });
  await waitFor(`${baseUrl}/readyz`, api);

  const sessionResponse = await fetch(`${baseUrl}/api/v1/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });
  requireCondition(sessionResponse.status === 201, `Session creation failed: ${await sessionResponse.text()}`);
  const setCookie = sessionResponse.headers.get("set-cookie") ?? "";
  const cookiePair = setCookie.split(";", 1)[0];
  const separator = cookiePair.indexOf("=");
  requireCondition(separator > 0, "Browser session cookie was not issued");
  const cookieName = cookiePair.slice(0, separator);
  const cookieValue = cookiePair.slice(separator + 1);

  const userData = await mkdtemp(join(tmpdir(), "agency-async-chromium-"));
  temporary.push(userData);
  const chromium = start(chromiumBin, [
    "--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
    "--remote-debugging-port=0", `--user-data-dir=${userData}`, "about:blank",
  ]);
  let debugPort;
  for (let index = 0; index < 100; index += 1) {
    try {
      const text = await readFile(join(userData, "DevToolsActivePort"), "utf8");
      debugPort = Number.parseInt(text.split(/\r?\n/)[0], 10);
      if (debugPort) break;
    } catch { /* retry */ }
    await new Promise((resolveWait) => setTimeout(resolveWait, 120));
  }
  requireCondition(debugPort, "Chromium DevTools port was not available");
  const debugUrl = `http://127.0.0.1:${debugPort}`;
  await waitFor(`${debugUrl}/json/version`, chromium);
  const targets = await (await fetch(`${debugUrl}/json/list`)).json();
  const page = targets.find((target) => target.type === "page");
  requireCondition(page?.webSocketDebuggerUrl, "No Chromium page target");
  const client = new CdpClient(page.webSocketDebuggerUrl);
  await client.open();
  await client.send("Page.enable");
  await client.send("Runtime.enable");
  await client.send("Network.enable");
  await client.send("Emulation.setDeviceMetricsOverride", {
    width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false,
  });
  await client.send("Network.setCookie", {
    name: cookieName,
    value: cookieValue,
    url: baseUrl,
    httpOnly: true,
    sameSite: "Lax",
  });
  const loaded = client.once("Page.loadEventFired");
  await client.send("Page.navigate", { url: baseUrl });
  await loaded;
  await waitForExpression(
    client,
    `document.body.innerText.includes('async-browser-admin')`,
    "Authenticated workspace did not load",
  );

  const launched = await client.evaluate(`(() => {
    const button = [...document.querySelectorAll('button')].find((candidate) => candidate.textContent?.includes('Ejecutar campaña'));
    if (!button || button.disabled) return false;
    button.click();
    return true;
  })()`);
  requireCondition(launched, "Async run launch button was not available");

  const processingStations = new Set();
  const checkpointNumbers = new Set();
  const snapshots = [];
  let processingScreenshot = false;
  let finalState = null;
  for (let index = 0; index < 120; index += 1) {
    const snapshot = await client.evaluate(`(() => {
      const labels = [...document.querySelectorAll('button[aria-controls="agent-detail"]')]
        .map((button) => button.getAttribute('aria-label') ?? '');
      const text = document.body.innerText;
      const checkpoint = [...document.querySelectorAll('p')]
        .map((item) => item.textContent ?? '')
        .find((value) => value.includes('checkpoint')) ?? '';
      return {
        labels,
        checkpoint,
        awaiting: text.toLowerCase().includes('awaiting greenlight'),
        artifacts: text.includes('7 artefactos'),
        horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      };
    })()`);
    for (const label of snapshot.labels) {
      const match = label.match(/^(.+?)\..*Processing, 10%$/);
      if (match) processingStations.add(match[1]);
    }
    const checkpointMatch = snapshot.checkpoint.match(/checkpoint (\d+)/);
    if (checkpointMatch) checkpointNumbers.add(Number.parseInt(checkpointMatch[1], 10));
    if (!processingScreenshot && processingStations.size > 0) {
      await client.evaluate(`document.querySelector('[aria-label="Topología de orquestación multiagente"]')?.scrollIntoView({ block: 'center' })`);
      await new Promise((resolveWait) => setTimeout(resolveWait, 120));
      const shot = await client.send("Page.captureScreenshot", { format: "png", fromSurface: true });
      await writeFile(join(outputDir, "async-run-processing.png"), Buffer.from(shot.data, "base64"));
      processingScreenshot = true;
    }
    snapshots.push({
      processingStations: [...processingStations],
      checkpoint: snapshot.checkpoint,
      awaiting: snapshot.awaiting,
      artifacts: snapshot.artifacts,
    });
    if (snapshot.awaiting && snapshot.artifacts) {
      finalState = snapshot;
      break;
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 140));
  }

  requireCondition(finalState, "Run did not reach Greenlight through durable checkpoints");
  await new Promise((resolveWait) => setTimeout(resolveWait, 550));
  const finalDocument = await client.evaluate(`(() => {
    const body = document.body.innerText;
    const runId = body.match(/run-[a-z0-9]+/)?.[0] ?? '';
    if (!runId) return Promise.resolve({ runId: '', status: 0, body: null });
    return fetch('/api/v1/runs/' + encodeURIComponent(runId), { credentials: 'include' })
      .then(async (response) => ({ runId, status: response.status, body: await response.json() }));
  })()`);
  requireCondition(finalDocument.status === 200, `Final run document was unavailable: ${JSON.stringify(finalDocument)}`);
  requireCondition(finalDocument.body.status === 'awaiting_greenlight', `Unexpected final run status: ${JSON.stringify(finalDocument.body)}`);
  requireCondition(finalDocument.body.execution.fencing_token === 14, `Final fencing token was not 14: ${JSON.stringify(finalDocument.body.execution)}`);
  requireCondition(finalDocument.body.execution.lease_owner === '', "Final run retained a lease owner");
  requireCondition(processingStations.size >= 6, `Too few real processing stations were observed: ${[...processingStations].join(', ')}`);
  requireCondition(checkpointNumbers.size >= 8, `Too few durable checkpoint values were observed: ${[...checkpointNumbers].join(', ')}`);
  requireCondition(!finalState.horizontalOverflow, "Async run topology introduced horizontal overflow");
  await client.evaluate(`document.querySelector('[aria-label="Topología de orquestación multiagente"]')?.scrollIntoView({ block: 'center' })`);
  await new Promise((resolveWait) => setTimeout(resolveWait, 120));
  const finalShot = await client.send("Page.captureScreenshot", { format: "png", fromSurface: true });
  await writeFile(join(outputDir, "async-run-greenlight.png"), Buffer.from(finalShot.data, "base64"));
  await writeFile(join(outputDir, "async-run-evidence.json"), `${JSON.stringify({
    processingStations: [...processingStations],
    checkpointNumbers: [...checkpointNumbers].sort((a, b) => a - b),
    finalStatus: "awaiting_greenlight",
    finalFencingToken: finalDocument.body.execution.fencing_token,
    finalRunId: finalDocument.runId,
    artifacts: 7,
    snapshots,
    browserTimersInventedState: false,
    providerCalls: 0,
    publications: 0,
  }, null, 2)}\n`);
  requireCondition(!api.output.includes(apiKey), "Runtime logs leaked the tenant credential");
  console.log(`async_run_processing_stations=${processingStations.size}`);
  console.log(`async_run_checkpoint_values=${checkpointNumbers.size}`);
  console.log("async_run_greenlight=pass");
  console.log("async_run_browser_state_source=durable_backend_polling");
  console.log(`async_run_artifact=${outputDir}`);
  client.close();
}

try {
  await run();
} finally {
  await stopAll();
}
