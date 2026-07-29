#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { createServer as createHttpServer } from "node:http";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { createServer as createTcpServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const chromiumBin = process.env.CHROMIUM_BIN ?? "chromium";
const apiKey = "social-oauth-browser-admin-key-2026";
const xSecret = "social-oauth-browser-x-secret";
const instagramSecret = "social-oauth-browser-instagram-secret";
const children = [];
const temporary = [];

function selectPython() {
  const candidates = [
    process.env.SOCIAL_OAUTH_BROWSER_PYTHON,
    resolve(root, ".venv/bin/python"),
    "/tmp/ai-native-content-agency-runtime/bin/python",
    "/tmp/inc019-cookie-venv/bin/python",
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
    "rm -rf /tmp/agency-social-oauth-browser-python",
    "python3 -m venv /tmp/agency-social-oauth-browser-python",
    "/tmp/agency-social-oauth-browser-python/bin/python -m pip install --disable-pip-version-check --require-hashes -r backend/requirements-test.lock >/tmp/agency-social-oauth-browser-python-install.log 2>&1",
  ].join("; ")], { cwd: root, stdio: "ignore" });
  if (bootstrap.status === 0) return "/tmp/agency-social-oauth-browser-python/bin/python";
  throw new Error("No hash-locked Python runtime is available for the OAuth browser gate.");
}

const python = selectPython();

function availablePort() {
  return new Promise((resolvePort, reject) => {
    const server = createTcpServer();
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
  child.stdout.on("data", (chunk) => { child.output = `${child.output}${chunk}`.slice(-30000); });
  child.stderr.on("data", (chunk) => { child.output = `${child.output}${chunk}`.slice(-30000); });
  children.push(child);
  return child;
}

async function stopAll(provider) {
  if (provider) await new Promise((resolveClose) => provider.close(resolveClose));
  for (const child of children.reverse()) {
    if (child.exitCode === null && child.signalCode === null) {
      try { process.kill(-child.pid, "SIGTERM"); } catch { child.kill("SIGTERM"); }
    }
  }
  await new Promise((resolveWait) => setTimeout(resolveWait, 300));
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
      if (response.ok) return;
      lastError = new Error(`${url} returned ${response.status}`);
    } catch (error) {
      lastError = error;
    }
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
  const apiPort = await availablePort();
  const providerPort = await availablePort();
  const baseUrl = `http://127.0.0.1:${apiPort}`;
  const providerBase = `http://localhost:${providerPort}`;
  const work = await mkdtemp(join(tmpdir(), "agency-social-oauth-browser-"));
  temporary.push(work);
  const appPath = join(work, "oauth_browser_app.py");
  const encryptionKey = Buffer.alloc(32, 17).toString("base64url");
  const identity = JSON.stringify([{
    tenant_id: "oauth-browser-tenant",
    subject_id: "oauth-browser-admin",
    role: "admin",
    key_id: "oauth-browser-admin-v1",
    api_key: apiKey,
    active: true,
  }]);

  await writeFile(appPath, `
import httpx
import os
import uvicorn
from pathlib import Path
from agency_runtime.api import create_app


def provider(request: httpx.Request) -> httpx.Response:
    if request.url.host == "api.x.com" and request.url.path == "/oauth/request_token":
        return httpx.Response(200, text="oauth_token=x-request-token&oauth_token_secret=x-request-secret&oauth_callback_confirmed=true")
    if request.url.host == "api.x.com" and request.url.path == "/oauth/access_token":
        return httpx.Response(200, text="oauth_token=x-access-token&oauth_token_secret=x-access-secret&user_id=x-account-001&screen_name=connected_x")
    if request.url.host == "api.instagram.com" and request.url.path == "/oauth/access_token":
        return httpx.Response(200, json={"access_token": "instagram-access-token", "user_id": 17841401005573906, "expires_in": 3600})
    if request.url.host == "graph.instagram.com" and request.url.path == "/me":
        return httpx.Response(200, json={"id": "17841401005573906", "username": "connected.instagram", "account_type": "BUSINESS"})
    raise AssertionError("unexpected provider request: {}".format(request.url))

app = create_app(
    database_path=os.environ["OAUTH_BROWSER_DATABASE"],
    static_dir=Path(os.environ["AGENCY_STATIC_DIR"]),
    identity_credentials=__import__("json").loads(os.environ["AGENCY_IDENTITY_CREDENTIALS_JSON"]),
    session_cookie_secure=False,
    session_cookie_samesite="lax",
    social_environment=os.environ,
    social_oauth_transport=httpx.MockTransport(provider),
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ["OAUTH_BROWSER_PORT"]))
`, "utf8");

  const api = start(python, [appPath], {
    env: {
      ...process.env,
      PYTHONPATH: resolve(root, "backend"),
      OAUTH_BROWSER_PORT: String(apiPort),
      OAUTH_BROWSER_DATABASE: join(work, "runtime.sqlite3"),
      AGENCY_STATIC_DIR: resolve(root, "dist"),
      AGENCY_IDENTITY_CREDENTIALS_JSON: identity,
      AGENCY_X_CONSUMER_KEY: "oauth-browser-x-key",
      AGENCY_X_CONSUMER_SECRET: xSecret,
      AGENCY_X_REDIRECT_URI: `${baseUrl}/api/v1/social-channels/x/oauth/callback`,
      AGENCY_INSTAGRAM_APP_ID: "oauth-browser-instagram-app",
      AGENCY_INSTAGRAM_APP_SECRET: instagramSecret,
      AGENCY_INSTAGRAM_REDIRECT_URI: `${baseUrl}/api/v1/social-channels/instagram/oauth/callback`,
      AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON: JSON.stringify({ "oauth-browser-v1": encryptionKey }),
      AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID: "oauth-browser-v1",
      AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID: "",
    },
  });
  await waitFor(`${baseUrl}/healthz`, api);

  const provider = createHttpServer((request, response) => {
    const current = new URL(request.url ?? "/", providerBase);
    const target = current.searchParams.get("target");
    if (!target || !target.startsWith(`${baseUrl}/api/v1/social-channels/`)) {
      response.writeHead(400, { "Content-Type": "text/plain" });
      response.end("invalid target");
      return;
    }
    response.writeHead(302, { Location: target, "Cache-Control": "no-store" });
    response.end();
  });
  await new Promise((resolveListen, reject) => {
    provider.once("error", reject);
    provider.listen(providerPort, "127.0.0.1", resolveListen);
  });

  const userData = await mkdtemp(join(tmpdir(), "agency-social-oauth-chromium-"));
  temporary.push(userData);
  const chromium = start(chromiumBin, [
    "--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
    "--remote-debugging-port=0", `--user-data-dir=${userData}`, "about:blank",
  ]);
  let debugPort;
  for (let index = 0; index < 100; index += 1) {
    try {
      const { readFile } = await import("node:fs/promises");
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

  await client.send("Page.navigate", { url: `${baseUrl}/healthz` });
  await waitForExpression(client, `location.origin === ${JSON.stringify(baseUrl)} && location.pathname === '/healthz'`, "Application origin did not load");
  const opened = await client.evaluate(`fetch('/api/v1/sessions', {
    method: 'POST', credentials: 'include', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({api_key: ${JSON.stringify(apiKey)}})
  }).then(async response => ({status: response.status, body: await response.json()}))`);
  requireCondition(opened.status === 201, `Browser session did not open: ${JSON.stringify(opened)}`);
  const resumed = await client.evaluate(`fetch('/api/v1/sessions/current', {
    credentials: 'include'
  }).then(async response => ({status: response.status, body: await response.json()}))`);
  requireCondition(resumed.status === 200, `Browser session did not resume: ${JSON.stringify(resumed)}`);
  const csrf = resumed.body.csrf_token;

  const cookies = await client.send("Network.getAllCookies");
  const sessionCookie = cookies.cookies.find((cookie) => cookie.name === "agency_session");
  requireCondition(sessionCookie?.httpOnly === true, "Session cookie is not HttpOnly");
  requireCondition(sessionCookie?.sameSite === "Lax", `Session cookie is not SameSite=Lax: ${JSON.stringify(sessionCookie)}`);

  const startX = await client.evaluate(`fetch('/api/v1/social-channels/x/oauth/start', {
    method: 'POST', credentials: 'include', headers: {'X-CSRF-Token': ${JSON.stringify(csrf)}}
  }).then(async response => ({status: response.status, body: await response.json()}))`);
  requireCondition(startX.status === 201, `X OAuth did not start: ${JSON.stringify(startX)}`);
  const xToken = new URL(startX.body.authorization_url).searchParams.get("oauth_token");
  requireCondition(xToken === "x-request-token", "X request token was not issued");
  const xCallback = `${baseUrl}/api/v1/social-channels/x/oauth/callback?oauth_token=${encodeURIComponent(xToken)}&oauth_verifier=browser-verifier`;
  await client.send("Page.navigate", { url: `${providerBase}/authorize?target=${encodeURIComponent(xCallback)}` });
  await waitForExpression(client, `location.search.includes('social_channel=x') && location.search.includes('status=connected')`, "X OAuth callback did not retain the browser session");
  const xConnected = await client.evaluate(`fetch('/api/v1/social-channels/x', {credentials: 'include'}).then(async response => ({status: response.status, body: await response.json()}))`);
  requireCondition(xConnected.status === 200 && xConnected.body.channel.connection_state === "connected", `X account was not connected: ${JSON.stringify(xConnected)}`);
  requireCondition(xConnected.body.channel.connected_account.account_username === "connected_x", "Unexpected X account metadata");

  await client.send("Page.navigate", { url: `${baseUrl}/healthz` });
  await waitForExpression(client, `location.pathname === '/healthz'`, "Neutral same-origin page did not reload");
  const afterX = await client.evaluate(`fetch('/api/v1/sessions/current', {
    credentials: 'include'
  }).then(async response => ({status: response.status, body: await response.json()}))`);
  requireCondition(afterX.status === 200, `Browser session did not survive X callback: ${JSON.stringify(afterX)}`);
  const csrfAfterX = afterX.body.csrf_token;
  const disconnected = await client.evaluate(`fetch('/api/v1/social-channels/x/connection', {
    method: 'DELETE', credentials: 'include', headers: {'X-CSRF-Token': ${JSON.stringify('__CSRF_AFTER_X__')}}
  }).then(async response => ({status: response.status, body: await response.json()}))`.replace('__CSRF_AFTER_X__', csrfAfterX));
  requireCondition(disconnected.status === 200, `X disconnect failed: ${JSON.stringify(disconnected)}`);

  const afterDisconnect = await client.evaluate(`fetch('/api/v1/sessions/current', {
    credentials: 'include'
  }).then(async response => ({status: response.status, body: await response.json()}))`);
  requireCondition(afterDisconnect.status === 200, `Browser session did not resume after disconnect: ${JSON.stringify(afterDisconnect)}`);
  const csrfInstagram = afterDisconnect.body.csrf_token;
  const startInstagram = await client.evaluate(`fetch('/api/v1/social-channels/instagram/oauth/start', {
    method: 'POST', credentials: 'include', headers: {'X-CSRF-Token': ${JSON.stringify(csrfInstagram)}}
  }).then(async response => ({status: response.status, body: await response.json()}))`);
  requireCondition(startInstagram.status === 201, `Instagram OAuth did not start: ${JSON.stringify(startInstagram)}`);
  const state = new URL(startInstagram.body.authorization_url).searchParams.get("state");
  requireCondition(state?.length >= 32, "Instagram OAuth state was not issued");
  const instagramCallback = `${baseUrl}/api/v1/social-channels/instagram/oauth/callback?code=browser-instagram-code&state=${encodeURIComponent(state)}#_`;
  await client.send("Page.navigate", { url: `${providerBase}/authorize?target=${encodeURIComponent(instagramCallback)}` });
  await waitForExpression(client, `location.search.includes('social_channel=instagram') && location.search.includes('status=connected')`, "Instagram OAuth callback did not retain the browser session");
  const instagramConnected = await client.evaluate(`fetch('/api/v1/social-channels/instagram', {credentials: 'include'}).then(async response => ({status: response.status, body: await response.json()}))`);
  requireCondition(instagramConnected.status === 200 && instagramConnected.body.channel.connection_state === "connected", `Instagram account was not connected: ${JSON.stringify(instagramConnected)}`);
  requireCondition(instagramConnected.body.channel.connected_account.account_username === "connected.instagram", "Unexpected Instagram account metadata");

  requireCondition(!api.output.includes(xSecret) && !api.output.includes(instagramSecret), "OAuth runtime logs leaked a social secret");
  console.log("social_oauth_cookie_samesite_lax=pass");
  console.log("social_oauth_x_cross_site_callback=pass");
  console.log("social_oauth_instagram_cross_site_callback=pass");
  console.log("social_oauth_provider_http=mock_transport_only");
  client.close();
  return provider;
}

let provider;
try {
  provider = await run();
} finally {
  await stopAll(provider);
}
