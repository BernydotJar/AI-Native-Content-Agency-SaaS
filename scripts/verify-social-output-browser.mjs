#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
function selectPython() {
  const candidates = [
    process.env.SOCIAL_BROWSER_PYTHON,
    resolve(root, ".venv/bin/python"),
    "/tmp/ai-native-content-agency-runtime/bin/python",
    "python3.13",
    "python3.12",
    "python3.11",
    "python3",
  ].filter(Boolean);
  for (const candidate of candidates) {
    const probe = spawnSync(candidate, ["-c", "import fastapi, uvicorn, pg8000, httpx"], {
      cwd: root,
      stdio: "ignore",
    });
    if (probe.status === 0) return candidate;
  }
  const bootstrap = spawnSync("bash", ["-lc", [
    "set -euo pipefail",
    "rm -rf /tmp/agency-social-browser-python",
    "python3 -m venv /tmp/agency-social-browser-python",
    "/tmp/agency-social-browser-python/bin/python -m pip install --disable-pip-version-check --require-hashes -r backend/requirements-test.lock >/tmp/agency-social-browser-python-install.log 2>&1",
  ].join("; ")], { cwd: root, stdio: "ignore" });
  if (bootstrap.status === 0) return "/tmp/agency-social-browser-python/bin/python";
  throw new Error("No supported Python runtime is available and the hash-locked fallback could not be created.");
}

const python = selectPython();
const chromiumBin = process.env.CHROMIUM_BIN ?? "chromium";
const outputDir = resolve(root, process.env.SOCIAL_BROWSER_OUTPUT_DIR ?? "artifacts/social/generated");
const apiKey = "local-social-browser-admin-key-2026";
const xSecret = "local-social-browser-x-secret";
const instagramSecret = "local-social-browser-instagram-secret";
const children = [];
const temporary = [];

function availablePort() {
  return new Promise((resolvePort, reject) => {
    const server = createServer();
    server.unref();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        reject(new Error("Unable to allocate a local port"));
        return;
      }
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
  child.stdout.on("data", (chunk) => { child.output = `${child.output}${chunk}`.slice(-20000); });
  child.stderr.on("data", (chunk) => { child.output = `${child.output}${chunk}`.slice(-20000); });
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
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 200));
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

async function waitForDom(client, expression, message, attempts = 80) {
  for (let index = 0; index < attempts; index += 1) {
    if (await client.evaluate(expression)) return;
    await new Promise((resolveWait) => setTimeout(resolveWait, 150));
  }
  throw new Error(message);
}

async function jsonRequest(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(`${url} failed (${response.status}): ${JSON.stringify(body)}`);
  return { response, body };
}

async function run() {
  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });
  const apiPort = await availablePort();
  const baseUrl = `http://127.0.0.1:${apiPort}`;
  const work = await mkdtemp(join(tmpdir(), "agency-social-browser-"));
  temporary.push(work);
  const identity = JSON.stringify([{
    tenant_id: "social-browser-tenant",
    subject_id: "social-browser-admin",
    role: "admin",
    key_id: "social-browser-admin-v1",
    api_key: apiKey,
    active: true,
  }]);
  const api = start(python, [
    "-m", "uvicorn", "agency_runtime.api:app",
    "--host", "127.0.0.1",
    "--port", String(apiPort),
  ], {
    env: {
      ...process.env,
      PYTHONPATH: resolve(root, "backend"),
      AGENCY_STATIC_DIR: resolve(root, "dist"),
      AGENCY_MEMORY_DB: join(work, "runtime.sqlite3"),
      AGENCY_IDENTITY_CREDENTIALS_JSON: identity,
      AGENCY_SESSION_COOKIE_SECURE: "false",
      AGENCY_X_CONSUMER_KEY: "local-social-browser-x-key",
      AGENCY_X_CONSUMER_SECRET: xSecret,
      AGENCY_X_REDIRECT_URI: `${baseUrl}/api/v1/social-channels/x/oauth/callback`,
      AGENCY_INSTAGRAM_APP_ID: "local-social-browser-instagram-app-id",
      AGENCY_INSTAGRAM_APP_SECRET: instagramSecret,
      AGENCY_INSTAGRAM_REDIRECT_URI: `${baseUrl}/api/v1/social-channels/instagram/oauth/callback`,
    },
  });
  await waitFor(`${baseUrl}/healthz`, api);

  const authHeaders = {
    Authorization: `Bearer ${apiKey}`,
    "Content-Type": "application/json",
  };
  const created = await jsonRequest(`${baseUrl}/api/v1/runs`, {
    method: "POST",
    headers: {
      ...authHeaders,
      "Idempotency-Key": "social-browser-create-0001",
      "X-Request-ID": "social-browser-create-0001",
    },
    body: JSON.stringify({
      title: "Community impact campaign",
      objective: "Show the visible X and Instagram campaign output",
      audience: "community supporters",
      platforms: ["x", "instagram"],
      budget_cents: 0,
      campaign_goal: "community_engagement",
    }),
  });
  const runId = created.body.run_id;
  await jsonRequest(`${baseUrl}/api/v1/runs/${runId}/greenlight/approve`, {
    method: "POST",
    headers: {
      ...authHeaders,
      "Idempotency-Key": "social-browser-approve-0001",
      "X-Request-ID": "social-browser-approve-0001",
    },
    body: JSON.stringify({ reviewer: "social-browser-admin", note: "Browser evidence approval" }),
  });
  const session = await jsonRequest(`${baseUrl}/api/v1/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Request-ID": "social-browser-session-0001" },
    body: JSON.stringify({ api_key: apiKey }),
  });
  const setCookie = session.response.headers.get("set-cookie") ?? "";
  const cookiePair = setCookie.split(";", 1)[0];
  const separator = cookiePair.indexOf("=");
  requireCondition(separator > 0, "Browser session cookie was not issued");
  const cookieName = cookiePair.slice(0, separator);
  const cookieValue = cookiePair.slice(separator + 1);

  const userData = await mkdtemp(join(tmpdir(), "agency-social-chromium-"));
  temporary.push(userData);
  const chromium = start(chromiumBin, [
    "--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
    "--remote-debugging-port=0", `--user-data-dir=${userData}`, "about:blank",
  ]);
  let debugPort;
  for (let index = 0; index < 100; index += 1) {
    try {
      const text = await (await import("node:fs/promises")).readFile(join(userData, "DevToolsActivePort"), "utf8");
      debugPort = Number.parseInt(text.split(/\r?\n/)[0], 10);
      if (debugPort) break;
    } catch { /* retry */ }
    await new Promise((resolveWait) => setTimeout(resolveWait, 150));
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
    width: 1440, height: 1200, deviceScaleFactor: 1, mobile: false,
  });
  await client.send("Network.setCookie", {
    name: cookieName,
    value: cookieValue,
    url: baseUrl,
    httpOnly: true,
    sameSite: "Strict",
  });
  const loaded = client.once("Page.loadEventFired");
  await client.send("Page.navigate", { url: baseUrl });
  await loaded;
  await waitForDom(
    client,
    `document.body.innerText.includes('social-browser-tenant conectado')`,
    "Authenticated workspace did not load",
  );
  const runInputFound = await client.evaluate(`(() => {
    const input = [...document.querySelectorAll('input')].find((candidate) => candidate.placeholder === 'run-…');
    if (!input) return false;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(input, ${JSON.stringify(runId)});
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  })()`);
  requireCondition(runInputFound, "Run lookup input was not available");
  await new Promise((resolveWait) => setTimeout(resolveWait, 250));
  const submitted = await client.evaluate(`(() => {
    const input = [...document.querySelectorAll('input')].find((candidate) => candidate.placeholder === 'run-…');
    const button = input?.closest('form')?.querySelector('button[type="submit"]');
    if (!button || button.disabled) return { submitted: false, disabled: button?.disabled ?? null, value: input?.value ?? '' };
    button.click();
    return { submitted: true, disabled: false, value: input.value };
  })()`);
  requireCondition(submitted.submitted, `Run lookup could not submit: ${JSON.stringify(submitted)}`);
  try {
    await waitForDom(
      client,
      `document.body.innerText.toLowerCase().includes('vista previa de instagram') && document.body.innerText.toLowerCase().includes('lista para autenticar')`,
      "Social campaign output did not become visible",
    );
  } catch (error) {
    const visibleText = await client.evaluate(`document.body.innerText.slice(0, 12000)`);
    throw new Error(`${error.message}; visible text: ${visibleText}`);
  }
  await client.evaluate(`document.querySelector('#campaign-output').scrollIntoView({ block: 'start' })`);
  await new Promise((resolveWait) => setTimeout(resolveWait, 250));

  const outputState = await client.evaluate(`(() => {
    const output = document.querySelector('#campaign-output');
    const text = output?.innerText ?? '';
    const normalized = text.toLowerCase();
    const publishButtons = [...(output?.querySelectorAll('button') ?? [])].filter((button) => button.textContent?.includes('Publicar'));
    return {
      text,
      horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      xVisible: normalized.includes('vista previa de x') && normalized.includes('lista para autenticar'),
      instagramVisible: normalized.includes('vista previa de instagram'),
      captionVisible: normalized.includes('community impact campaign'),
      assetPending: normalized.includes('asset visual pendiente') && normalized.includes('imagen, reel o carrusel pendiente'),
      stagesVisible: ['copy', 'asset', 'greenlight', 'cuenta', 'publicación'].every((label) => normalized.includes(label)),
      publishButtons: publishButtons.map((button) => ({ disabled: button.disabled, text: button.textContent?.trim() })),
    };
  })()`);
  requireCondition(outputState.xVisible, `X readiness was not visible: ${JSON.stringify(outputState)}`);
  requireCondition(outputState.instagramVisible, "Instagram preview was not visible");
  requireCondition(outputState.captionVisible, "Generated campaign copy was not visible");
  requireCondition(outputState.assetPending, "Instagram media requirement was not visible");
  requireCondition(outputState.stagesVisible, "Publication readiness stages were incomplete");
  requireCondition(outputState.publishButtons.length === 2 && outputState.publishButtons.every((item) => item.disabled), "Publish actions were not safely disabled");
  requireCondition(!outputState.horizontalOverflow, "Social output introduced horizontal overflow");
  requireCondition(!outputState.text.includes(xSecret) && !outputState.text.includes(instagramSecret), "A social secret appeared in the output DOM");

  const screenshot = await client.send("Page.captureScreenshot", {
    format: "png", fromSurface: true, captureBeyondViewport: false,
  });
  await writeFile(join(outputDir, "social-output-1440px.png"), Buffer.from(screenshot.data, "base64"));

  await client.evaluate(`(() => {
    const button = [...document.querySelectorAll('button')].find((candidate) => candidate.textContent?.trim() === 'Configuración');
    button?.click();
  })()`);
  await waitForDom(client, `document.body.innerText.includes('Canales de publicación')`, "Social channel settings did not open");
  const settingsState = await client.evaluate(`(() => {
    const dialog = document.querySelector('[role="dialog"]');
    const text = dialog?.innerText ?? '';
    const normalized = text.toLowerCase();
    return {
      text,
      hasX: normalized.includes('x account authorized by the tenant'),
      hasInstagram: normalized.includes('instagram professional account'),
      readyCount: (normalized.match(/lista para autenticar/g) ?? []).length,
      envNames: ['AGENCY_X_CONSUMER_KEY', 'AGENCY_X_CONSUMER_SECRET', 'AGENCY_INSTAGRAM_APP_ID', 'AGENCY_INSTAGRAM_APP_SECRET'].every((name) => text.includes(name)),
    };
  })()`);
  requireCondition(settingsState.hasX && settingsState.hasInstagram, "Both social channels were not visible in Settings");
  requireCondition(settingsState.readyCount >= 2, "Both channels were not ready for authentication");
  requireCondition(settingsState.envNames, "Required server environment names were not visible");
  requireCondition(!settingsState.text.includes(xSecret) && !settingsState.text.includes(instagramSecret), "A social secret appeared in Settings");

  await writeFile(join(outputDir, "social-output-evidence.json"), `${JSON.stringify({
    runId,
    outputState: { ...outputState, text: undefined },
    settingsState: { ...settingsState, text: undefined },
    externalRequestsPerformed: false,
    limitations: [
      "OAuth callbacks, access-token storage and real publication are not implemented in this readiness increment.",
      "The screenshot is automated evidence for later human visual review, not a human accessibility approval.",
    ],
  }, null, 2)}\n`);
  requireCondition(!api.output.includes(xSecret) && !api.output.includes(instagramSecret), "Runtime logs leaked social secrets");
  console.log("social_output_x_visible=pass");
  console.log("social_output_instagram_visible=pass");
  console.log("social_output_instagram_media_gate=pass");
  console.log("social_output_publish_disabled=pass");
  console.log("social_output_settings_readiness=pass");
  console.log(`social_output_artifact=${outputDir}`);
  client.close();
}

try {
  await run();
} finally {
  await stopAll();
}
