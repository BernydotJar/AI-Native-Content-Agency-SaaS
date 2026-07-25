#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const outputDir = resolve(root, "artifacts/social-publication/generated");
const children = [];
const temporary = [];
const apiKey = "browser-publication-admin-key-material-2026";

function pythonBin() {
  for (const candidate of [process.env.PUBLICATION_BROWSER_PYTHON, "/tmp/inc019-cookie-venv/bin/python", "/tmp/ai-native-content-agency-runtime/bin/python", "python3.13", "python3.12", "python3.11", "python3"].filter(Boolean)) {
    const probe = spawnSync(candidate, ["-c", "import fastapi,uvicorn,httpx,pg8000"], { cwd: root, stdio: "ignore" });
    if (probe.status === 0) return candidate;
  }
  throw new Error("No supported Python runtime is available.");
}

function freePort() {
  return new Promise((resolvePort, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close((error) => error ? reject(error) : resolvePort(address.port));
    });
  });
}

function start(command, args, options = {}) {
  const child = spawn(command, args, { cwd: root, env: process.env, stdio: ["ignore", "pipe", "pipe"], detached: true, ...options });
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
  await new Promise((resolveWait) => setTimeout(resolveWait, 300));
  for (const path of temporary) await rm(path, { recursive: true, force: true });
}

async function waitFor(url, child, attempts = 100) {
  let lastError;
  for (let index = 0; index < attempts; index += 1) {
    if (child.exitCode !== null || child.signalCode !== null) throw new Error(`Process exited: ${child.output}`);
    try {
      const response = await fetch(url);
      if (response.ok) return response;
      lastError = new Error(`${url} returned ${response.status}`);
    } catch (error) { lastError = error; }
    await new Promise((resolveWait) => setTimeout(resolveWait, 150));
  }
  throw lastError ?? new Error(`Timed out waiting for ${url}`);
}

class Cdp {
  constructor(url) { this.socket = new WebSocket(url); this.id = 1; this.pending = new Map(); this.events = new Map(); }
  async open() {
    await new Promise((resolveOpen, reject) => {
      this.socket.addEventListener("open", resolveOpen, { once: true });
      this.socket.addEventListener("error", reject, { once: true });
    });
    this.socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const pending = this.pending.get(message.id); if (!pending) return;
        this.pending.delete(message.id);
        if (message.error) {
          pending.reject(new Error(message.error.message));
        } else {
          pending.resolve(message.result);
        }
      } else {
        const listeners = this.events.get(message.method) ?? [];
        this.events.delete(message.method);
        listeners.forEach((listener) => listener(message.params));
      }
    });
  }
  send(method, params = {}) {
    const id = this.id++;
    return new Promise((resolveCall, reject) => {
      this.pending.set(id, { resolve: resolveCall, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }
  once(method) {
    return new Promise((resolveEvent) => {
      const listeners = this.events.get(method) ?? [];
      listeners.push(resolveEvent); this.events.set(method, listeners);
    });
  }
  async eval(expression) {
    const result = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true, userGesture: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text ?? "Evaluation failed");
    return result.result.value;
  }
  close() { this.socket.close(); }
}

function requireValue(value, message) { if (!value) throw new Error(message); }
async function waitDom(client, expression, message, attempts = 100) {
  for (let index = 0; index < attempts; index += 1) {
    if (await client.eval(expression)) return;
    await new Promise((resolveWait) => setTimeout(resolveWait, 150));
  }
  throw new Error(message);
}

async function jsonRequest(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(`${url} failed (${response.status}): ${JSON.stringify(body)}`);
  return { response, body };
}

async function run() {
  await rm(outputDir, { recursive: true, force: true });
  await mkdir(outputDir, { recursive: true });
  const port = await freePort();
  const base = `http://127.0.0.1:${port}`;
  const work = await mkdtemp(join(tmpdir(), "agency-publication-browser-")); temporary.push(work);
  const callFile = join(work, "provider-calls.txt");
  await writeFile(callFile, "0");
  const providerCalls = async () => Number.parseInt(await readFile(callFile, "utf8"), 10);
  const api = start(pythonBin(), ["-m", "uvicorn", "scripts.fixtures.social_publication_browser_app:app", "--host", "127.0.0.1", "--port", String(port)], {
    env: { ...process.env, PYTHONPATH: `${resolve(root, "backend")}:${root}`, AGENCY_FIXTURE_DB_PATH: join(work, "runtime.sqlite3"), AGENCY_FIXTURE_STATIC_DIR: resolve(root, "dist"), AGENCY_FIXTURE_CALL_FILE: callFile },
  });
  await waitFor(`${base}/readyz`, api);

  const auth = { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" };
  const created = await jsonRequest(`${base}/api/v1/runs`, {
    method: "POST", headers: { ...auth, "Idempotency-Key": "browser-publication-run-001" },
    body: JSON.stringify({ title: "Browser exact-once campaign", objective: "Confirm a governed external effect", audience: "campaign operators", platforms: ["x", "instagram"], budget_cents: 0, campaign_goal: "verification" }),
  });
  const runId = created.body.run_id;
  await jsonRequest(`${base}/api/v1/runs/${runId}/greenlight/approve`, {
    method: "POST", headers: { ...auth, "Idempotency-Key": "browser-publication-greenlight-001" },
    body: JSON.stringify({ reviewer: "browser-publication-admin", note: "Browser gate approval" }),
  });
  const session = await jsonRequest(`${base}/api/v1/sessions`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ api_key: apiKey }),
  });
  const pair = (session.response.headers.get("set-cookie") ?? "").split(";", 1)[0];
  const separator = pair.indexOf("="); requireValue(separator > 0, "Session cookie missing");

  const userData = await mkdtemp(join(tmpdir(), "agency-publication-chromium-")); temporary.push(userData);
  const chromium = start(process.env.CHROMIUM_BIN ?? "chromium", ["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--remote-debugging-port=0", `--user-data-dir=${userData}`, "about:blank"]);
  let debugPort;
  for (let index = 0; index < 100; index += 1) {
    try { debugPort = Number.parseInt((await readFile(join(userData, "DevToolsActivePort"), "utf8")).split(/\r?\n/)[0], 10); if (debugPort) break; } catch { /* retry */ }
    await new Promise((resolveWait) => setTimeout(resolveWait, 120));
  }
  requireValue(debugPort, "Chromium debug port missing");
  const debug = `http://127.0.0.1:${debugPort}`; await waitFor(`${debug}/json/version`, chromium);
  const page = (await (await fetch(`${debug}/json/list`)).json()).find((target) => target.type === "page");
  requireValue(page?.webSocketDebuggerUrl, "No Chromium page target");
  const client = new Cdp(page.webSocketDebuggerUrl); await client.open();
  await client.send("Page.enable"); await client.send("Runtime.enable"); await client.send("Network.enable");
  await client.send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false });
  await client.send("Network.setCookie", { name: pair.slice(0, separator), value: pair.slice(separator + 1), url: base, httpOnly: true, sameSite: "Lax" });
  const loaded = client.once("Page.loadEventFired"); await client.send("Page.navigate", { url: base }); await loaded;
  await waitDom(client, `document.body.innerText.includes('browser-publication-admin')`, "Authenticated workspace did not load");

  const loadedRun = await client.eval(`(() => { const input=[...document.querySelectorAll('input')].find(i=>i.placeholder==='run-…'); if(!input)return false; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(runId)}); input.dispatchEvent(new Event('input',{bubbles:true})); input.dispatchEvent(new Event('change',{bubbles:true})); return true; })()`);
  requireValue(loadedRun, "Run lookup input missing");
  await new Promise((resolveWait) => setTimeout(resolveWait, 180));
  requireValue(await client.eval(`(() => { const input=[...document.querySelectorAll('input')].find(i=>i.placeholder==='run-…'); const button=input?.closest('form')?.querySelector('button[type="submit"]'); if(!button||button.disabled)return false; button.click(); return true; })()`), "Run lookup could not submit");
  await waitDom(client, `document.body.innerText.includes('Browser exact-once campaign') && document.body.innerText.includes('Autoridad exact-once habilitada')`, "Publication-ready output did not load");
  await client.eval(`document.querySelector('#campaign-output')?.scrollIntoView({block:'start'})`);
  await new Promise((resolveWait) => setTimeout(resolveWait, 200));

  const before = await providerCalls(); requireValue(before === 0, "Provider called before confirmation");
  const buttonState = await client.eval(`(() => [...document.querySelectorAll('button')].filter(b=>b.textContent?.trim()==='Publicar').map(b=>({disabled:b.disabled,title:b.title})))()`);
  requireValue(
    buttonState.length === 2
      && buttonState.filter((item) => item.disabled === false && item.title === 'Listo para publicar').length === 1
      && buttonState.filter((item) => item.disabled === true && item.title === 'Falta asset visual').length === 1,
    `Unexpected publish buttons: ${JSON.stringify(buttonState)}`,
  );
  await client.eval(`([...document.querySelectorAll('button')].find(b=>b.textContent?.trim()==='Publicar' && !b.disabled)).click()`);
  await waitDom(client, `document.querySelector('[role="dialog"]')?.innerText.includes('Publicar en X')`, "Confirmation dialog did not open");
  const stillZero = await providerCalls(); requireValue(stillZero === 0, "Provider called on first click");
  const confirmation = await client.send("Page.captureScreenshot", { format: "png", fromSurface: true });
  await writeFile(join(outputDir, "publication-confirmation.png"), Buffer.from(confirmation.data, "base64"));
  await client.eval(`([...document.querySelectorAll('button')].find(b=>b.textContent?.includes('Confirmar publicación externa'))).click()`);
  await waitDom(client, `document.body.innerText.includes('Receipt durable registrado') && !document.querySelector('[role="dialog"]')`, "Publication did not complete");
  const oneCall = await providerCalls(); requireValue(oneCall === 1, "Expected exactly one provider call");

  await client.eval(`([...document.querySelectorAll('button')].find(b=>b.textContent?.trim()==='Publicar' && !b.disabled)).click()`);
  await waitDom(client, `document.querySelector('[role="dialog"]')?.innerText.includes('Publicar en X')`, "Replay dialog did not open");
  await client.eval(`([...document.querySelectorAll('button')].find(b=>b.textContent?.includes('Confirmar publicación externa'))).click()`);
  await waitDom(client, `!document.querySelector('[role="dialog"]')`, "Replay dialog did not close");
  const afterReplay = await providerCalls(); requireValue(afterReplay === 1, "Replay caused a second provider call");
  const publications = await jsonRequest(`${base}/api/v1/runs/${runId}/social-publications`, { headers: { Authorization: `Bearer ${apiKey}` } });
  requireValue(publications.body.publications.length === 1 && publications.body.publications[0].status === "succeeded", "Durable publication receipt missing");

  const finalShot = await client.send("Page.captureScreenshot", { format: "png", fromSurface: true });
  await writeFile(join(outputDir, "publication-succeeded.png"), Buffer.from(finalShot.data, "base64"));
  await writeFile(join(outputDir, "social-publication-evidence.json"), `${JSON.stringify({ runId, providerCallsBeforeConfirmation: before, providerCallsAfterSuccess: oneCall, providerCallsAfterDifferentKeyReplay: afterReplay, durableIntentCount: publications.body.publications.length, durableStatus: publications.body.publications[0].status, instagramBlockedWithoutApprovedMedia: buttonState.some((item) => item.disabled && item.title === "Falta asset visual"), realProviderHttp: false }, null, 2)}\n`);
  requireValue(!api.output.includes(apiKey) && !api.output.includes("browser-x-user-token"), "Fixture leaked a credential");
  console.log("social_publication_confirmation_gate=pass");
  console.log("social_publication_provider_calls_before_confirmation=0");
  console.log("social_publication_provider_calls_after_success=1");
  console.log("social_publication_different_key_replay_calls=1");
  console.log("social_publication_instagram_media_gate=pass");
  console.log("social_publication_provider_http=mock_transport_only");
  console.log(`social_publication_artifact=${outputDir}`);
  client.close();
}

try { await run(); } finally { await stopAll(); }
