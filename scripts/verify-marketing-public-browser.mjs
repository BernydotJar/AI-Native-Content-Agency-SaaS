#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const repositoryRoot = resolve(import.meta.dirname, "..");
const basePath = "/AI-Native-Content-Agency-SaaS/";
const chromiumBin = process.env.CHROMIUM_BIN ?? "chromium";
const previewPort = await availablePort();
const previewOrigin = `http://127.0.0.1:${previewPort}`;
const previewUrl = `${previewOrigin}${basePath}`;
const children = [];
const temporaryDirectories = [];

function sleep(milliseconds) {
  return new Promise((resolvePromise) => setTimeout(resolvePromise, milliseconds));
}

function availablePort() {
  return new Promise((resolvePromise, rejectPromise) => {
    const server = createServer();
    server.unref();
    server.once("error", rejectPromise);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        rejectPromise(new Error("unable to reserve preview port"));
        return;
      }
      server.close((error) => error ? rejectPromise(error) : resolvePromise(address.port));
    });
  });
}

function start(command, args) {
  const child = spawn(command, args, {
    cwd: repositoryRoot,
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
    detached: true,
  });
  child.output = "";
  child.spawnError = null;
  child.on("error", (error) => { child.spawnError = error; });
  for (const stream of [child.stdout, child.stderr]) {
    stream.on("data", (chunk) => {
      child.output = `${child.output}${chunk}`.slice(-12000);
    });
  }
  children.push(child);
  return child;
}

function childFailure(child, label) {
  if (child.spawnError) return new Error(`${label} failed to start: ${child.spawnError.message}`);
  if (child.exitCode === null && child.signalCode === null) return null;
  return new Error(`${label} terminated early: ${child.output.trim()}`);
}

async function waitForHttp(url, child, label, attempts = 100) {
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const failure = childFailure(child, label);
    if (failure) throw failure;
    try {
      const response = await fetch(url);
      if (response.ok) return response;
      lastError = new Error(`${url} returned ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await sleep(200);
  }
  throw lastError ?? new Error(`timed out waiting for ${label}`);
}

async function waitForDevToolsPort(child, userDataDirectory, attempts = 240) {
  const portFile = join(userDataDirectory, "DevToolsActivePort");
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const failure = childFailure(child, "Chromium");
    if (failure) throw failure;
    try {
      const [line] = (await readFile(portFile, "utf8")).trim().split(/\r?\n/);
      const port = Number.parseInt(line, 10);
      if (Number.isInteger(port) && port > 0) return port;
      lastError = new Error(`invalid Chromium DevTools port: ${line}`);
    } catch (error) {
      if (error?.code !== "ENOENT") lastError = error;
    }
    await sleep(250);
  }
  throw lastError ?? new Error("timed out waiting for Chromium DevTools port");
}

class CdpClient {
  constructor(url) {
    this.socket = new WebSocket(url);
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
  }

  async open() {
    await new Promise((resolvePromise, rejectPromise) => {
      this.socket.addEventListener("open", resolvePromise, { once: true });
      this.socket.addEventListener("error", rejectPromise, { once: true });
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
      for (const listener of this.listeners.get(message.method) ?? []) listener(message.params);
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolvePromise, rejectPromise) => {
      this.pending.set(id, { resolve: resolvePromise, reject: rejectPromise });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  on(method, listener) {
    const listeners = this.listeners.get(method) ?? [];
    listeners.push(listener);
    this.listeners.set(method, listeners);
  }

  async evaluate(expression) {
    const response = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
      userGesture: true,
    });
    if (response.exceptionDetails) {
      throw new Error(response.exceptionDetails.exception?.description ?? response.exceptionDetails.text ?? "browser evaluation failed");
    }
    return response.result.value;
  }

  close() { this.socket.close(); }
}

async function waitForCondition(client, expression, label, attempts = 80) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (await client.evaluate(expression)) return;
    await sleep(125);
  }
  throw new Error(`timed out waiting for ${label}`);
}

async function cleanup() {
  for (const child of children.reverse()) {
    if (child.exitCode === null && child.signalCode === null) {
      try { process.kill(-child.pid, "SIGTERM"); } catch { child.kill("SIGTERM"); }
    }
  }
  await sleep(250);
  for (const child of children) {
    if (child.exitCode === null && child.signalCode === null) {
      try { process.kill(-child.pid, "SIGKILL"); } catch { child.kill("SIGKILL"); }
    }
  }
  for (const directory of temporaryDirectories) await rm(directory, { recursive: true, force: true });
}

async function run() {
  const preview = start("npm", ["run", "preview", "--", "--host", "127.0.0.1", "--port", String(previewPort), "--strictPort"]);
  const response = await waitForHttp(previewUrl, preview, "Vite preview");
  const html = await response.text();
  if (!html.includes(`${basePath}assets/`) || html.includes("/src/main.tsx")) {
    throw new Error("preview did not serve the built GitHub Pages bundle under the repository base path");
  }

  const userDataDirectory = await mkdtemp(join(tmpdir(), "marketing-demo-chromium-"));
  temporaryDirectories.push(userDataDirectory);
  const chromium = start(chromiumBin, [
    "--headless=new",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--log-level=2",
    "--remote-debugging-port=0",
    `--user-data-dir=${userDataDirectory}`,
    "about:blank",
  ]);
  const debugPort = await waitForDevToolsPort(chromium, userDataDirectory);
  const debugOrigin = `http://127.0.0.1:${debugPort}`;
  await waitForHttp(`${debugOrigin}/json/version`, chromium, "Chromium");
  const targets = await (await waitForHttp(`${debugOrigin}/json/list`, chromium, "Chromium")).json();
  const target = targets.find((item) => item.type === "page");
  if (!target?.webSocketDebuggerUrl) throw new Error("Chromium page target unavailable");

  const client = new CdpClient(target.webSocketDebuggerUrl);
  await client.open();
  const requests = [];
  client.on("Network.requestWillBeSent", ({ request }) => requests.push(request.url));
  await client.send("Network.enable");
  await client.send("Page.enable");
  await client.send("Runtime.enable");
  await client.send("Page.navigate", { url: previewUrl });

  await waitForCondition(client, `document.body?.innerText.includes("Demo pública")`, "public demo badge");
  await waitForCondition(client, `document.body?.innerText.includes("PUBLIC DEMO / LOCAL")`, "isolated public hero");
  const initial = await client.evaluate(`(() => ({
    loginFields: document.querySelectorAll('input[type="password"]').length,
    privateApiText: document.body.innerText.includes("Conecta el espacio"),
    sampleSignal: document.body.innerText.includes("Cómo explicar propuestas complejas con claridad"),
  }))()`);
  if (initial.loginFields !== 0 || initial.privateApiText || !initial.sampleSignal) {
    throw new Error(`public boundary mismatch before interaction: ${JSON.stringify(initial)}`);
  }

  const prepared = await client.evaluate(`(() => {
    const button = [...document.querySelectorAll('button')].find((item) => item.textContent?.includes('Preparar piloto'));
    if (!button) return false;
    button.click();
    return true;
  })()`);
  if (!prepared) throw new Error("unable to find public trend-to-pilot action");
  await waitForCondition(client, `document.querySelector('input[aria-label="Título de campaña"]')?.value.includes("Cómo explicar propuestas complejas con claridad")`, "trend seed in mission form");

  const executed = await client.evaluate(`(() => {
    const button = [...document.querySelectorAll('button')].find((item) => item.textContent?.includes('Ejecutar demo local'));
    if (!button || button.disabled) return false;
    button.click();
    return true;
  })()`);
  if (!executed) throw new Error("public demo execution action is missing or disabled");

  await waitForCondition(client, `document.body?.innerText.includes("Demo local completada")`, "local completion notice");
  await waitForCondition(client, `document.body?.innerText.includes("Vista previa local")`, "local channel output");
  const result = await client.evaluate(`(() => ({
    eightStations: [...document.querySelectorAll('button')].filter((item) => item.textContent?.includes('/ READY')).length,
    localOutput: document.body.innerText.includes('Sin efectos externos'),
    privatePublishButton: [...document.querySelectorAll('button')].some((item) => item.textContent?.trim() === 'Publicar'),
    privateLogin: document.body.innerText.includes('Iniciar sesión') || document.querySelectorAll('input[type="password"]').length > 0,
  }))()`);
  const apiRequests = requests.filter((url) => {
    try { return new URL(url).pathname.startsWith("/api/"); } catch { return false; }
  });
  if (result.eightStations < 8 || !result.localOutput || result.privatePublishButton || result.privateLogin || apiRequests.length) {
    throw new Error(`public demo browser contract failed: ${JSON.stringify({ ...result, apiRequests })}`);
  }

  console.log(JSON.stringify({
    marketing_public_browser: "pass",
    url: previewUrl,
    stations_ready: result.eightStations,
    private_api_requests: apiRequests.length,
    external_publish_controls: result.privatePublishButton ? 1 : 0,
  }));
  client.close();
}

try {
  await run();
} finally {
  await cleanup();
}
