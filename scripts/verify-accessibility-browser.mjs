#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const repositoryRoot = resolve(import.meta.dirname, "..");
const previewPort = process.env.ACCESSIBILITY_PREVIEW_PORT
  ? Number.parseInt(process.env.ACCESSIBILITY_PREVIEW_PORT, 10)
  : await availablePort();
const requestedDebugPort = process.env.ACCESSIBILITY_DEBUG_PORT
  ? Number.parseInt(process.env.ACCESSIBILITY_DEBUG_PORT, 10)
  : 0;
const chromiumBin = process.env.CHROMIUM_BIN ?? "chromium";
const outputDirectory = resolve(
  repositoryRoot,
  process.env.ACCESSIBILITY_OUTPUT_DIR ?? "artifacts/accessibility/generated",
);
const previewUrl = `http://127.0.0.1:${previewPort}`;
const processes = [];
const temporaryDirectories = [];



function availablePort() {
  return new Promise((resolvePromise, rejectPromise) => {
    const server = createServer();
    server.unref();
    server.once("error", rejectPromise);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close();
        rejectPromise(new Error("Unable to reserve an ephemeral IPv4 port"));
        return;
      }
      server.close((error) => {
        if (error) rejectPromise(error);
        else resolvePromise(address.port);
      });
    });
  });
}

function childFailure(child, name) {
  if (child.spawnError) {
    return new Error(`${name} failed to start: ${child.spawnError.message}`);
  }
  if (child.exitCode === null && child.signalCode === null) return null;
  const outcome = child.signalCode
    ? `signal ${child.signalCode}`
    : `exit code ${child.exitCode}`;
  const diagnostic = child.diagnosticOutput?.trim();
  return new Error(`${name} terminated before readiness (${outcome})${diagnostic ? `: ${diagnostic}` : ""}`);
}

function sleep(milliseconds) {
  return new Promise((resolvePromise) => setTimeout(resolvePromise, milliseconds));
}

async function waitFor(url, child, name, attempts = 80) {
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const failure = childFailure(child, name);
    if (failure) throw failure;
    try {
      const response = await fetch(url);
      if (response.ok) return response;
      lastError = new Error(`${url} returned ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await sleep(250);
  }
  throw lastError ?? new Error(`Timed out waiting for ${url}`);
}

async function waitForPreview(child, attempts = 80) {
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const failure = childFailure(child, "Vite preview");
    if (failure) throw failure;
    try {
      const response = await fetch(previewUrl);
      const body = response.ok ? await response.text() : "";
      const expectedBundle = body.includes(
        "Native / War Room — Autonomous Campaign Intelligence",
      )
        && body.includes('id="root"')
        && body.includes('/assets/')
        && !body.includes('/src/main.tsx');
      await sleep(50);
      const postResponseFailure = childFailure(child, "Vite preview");
      if (postResponseFailure) throw postResponseFailure;
      if (response.ok && expectedBundle) return;
      lastError = new Error(
        response.ok
          ? `${previewUrl} did not serve the expected application bundle`
          : `${previewUrl} returned ${response.status}`,
      );
    } catch (error) {
      lastError = error;
    }
    await sleep(200);
  }
  throw lastError ?? new Error(`Timed out waiting for the Vite preview at ${previewUrl}`);
}

async function waitForDevToolsPort(
  child,
  userDataDirectory,
  attempts = Number.parseInt(process.env.CHROMIUM_STARTUP_ATTEMPTS ?? "240", 10),
) {
  if (!Number.isInteger(attempts) || attempts < 1 || attempts > 480) {
    throw new Error("CHROMIUM_STARTUP_ATTEMPTS must be an integer between 1 and 480");
  }
  const portFile = join(userDataDirectory, "DevToolsActivePort");
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const failure = childFailure(child, "Chromium");
    if (failure) throw failure;
    try {
      const [portLine] = (await readFile(portFile, "utf8")).trim().split(/\r?\n/);
      const port = Number.parseInt(portLine, 10);
      if (Number.isInteger(port) && port > 0 && port <= 65535) return port;
      lastError = new Error(`Chromium wrote an invalid DevTools port: ${portLine}`);
    } catch (error) {
      if (error?.code !== "ENOENT") lastError = error;
    }
    await sleep(250);
  }
  throw lastError ?? new Error("Timed out waiting for Chromium DevToolsActivePort");
}

function start(command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: repositoryRoot,
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
    detached: true,
    ...options,
  });
  child.diagnosticOutput = "";
  child.spawnError = null;
  child.on("error", (error) => {
    child.spawnError = error;
  });
  processes.push(child);
  child.stdout.on("data", (chunk) => {
    child.diagnosticOutput = `${child.diagnosticOutput}${chunk}`.slice(-16000);
    process.stderr.write(chunk);
  });
  child.stderr.on("data", (chunk) => {
    child.diagnosticOutput = `${child.diagnosticOutput}${chunk}`.slice(-16000);
    process.stderr.write(chunk);
  });
  return child;
}

async function stopProcesses() {
  for (const child of processes.reverse()) {
    if (child.exitCode === null && child.signalCode === null) {
      try { process.kill(-child.pid, "SIGTERM"); } catch { child.kill("SIGTERM"); }
    }
  }
  await sleep(500);
  for (const child of processes) {
    if (child.exitCode === null && child.signalCode === null) {
      try { process.kill(-child.pid, "SIGKILL"); } catch { child.kill("SIGKILL"); }
    }
  }
  for (const directory of temporaryDirectories) {
    await rm(directory, { recursive: true, force: true });
  }
}

class CdpClient {
  constructor(url) {
    this.socket = new WebSocket(url);
    this.nextId = 1;
    this.pending = new Map();
    this.events = new Map();
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
      const listeners = this.events.get(message.method) ?? [];
      this.events.delete(message.method);
      for (const listener of listeners) listener(message.params);
    });
  }

  send(method, params = {}) {
    const id = this.nextId;
    this.nextId += 1;
    return new Promise((resolvePromise, rejectPromise) => {
      this.pending.set(id, { resolve: resolvePromise, reject: rejectPromise });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  once(method) {
    return new Promise((resolvePromise) => {
      const listeners = this.events.get(method) ?? [];
      listeners.push(resolvePromise);
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
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.text ?? "Runtime evaluation failed");
    }
    return result.result.value;
  }

  close() {
    this.socket.close();
  }
}

function requireCondition(condition, message) {
  if (!condition) throw new Error(message);
}

async function press(client, key, code = key) {
  const virtualKeyCode = key === "Tab" ? 9 : key === " " ? 32 : 13;
  const common = {
    key,
    code,
    windowsVirtualKeyCode: virtualKeyCode,
    nativeVirtualKeyCode: virtualKeyCode,
  };
  await client.send("Input.dispatchKeyEvent", {
    type: "rawKeyDown",
    ...common,
  });
  if (key === "Enter" || key === " ") {
    await client.send("Input.dispatchKeyEvent", {
      type: "char",
      ...common,
      text: key === "Enter" ? "\r" : " ",
      unmodifiedText: key === "Enter" ? "\r" : " ",
    });
  }
  await client.send("Input.dispatchKeyEvent", {
    type: "keyUp",
    ...common,
  });
  await sleep(400);
}

function axNodeName(node) {
  return node.name?.value ?? "";
}

function axProperty(node, name) {
  return node.properties?.find((property) => property.name === name)?.value?.value;
}

async function run() {
  await rm(outputDirectory, { recursive: true, force: true });
  await mkdir(outputDirectory, { recursive: true });
  const preview = start("npm", [
    "run",
    "preview",
    "--",
    "--host",
    "127.0.0.1",
    "--port",
    String(previewPort),
    "--strictPort",
  ]);
  await waitForPreview(preview);

  const userDataDirectory = await mkdtemp(
    join(tmpdir(), "agency-accessibility-chromium-"),
  );
  temporaryDirectories.push(userDataDirectory);
  const chromium = start(chromiumBin, [
    "--headless=new",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--log-level=2",
    `--remote-debugging-port=${requestedDebugPort}`,
    `--user-data-dir=${userDataDirectory}`,
    "about:blank",
  ]);
  const debugPort = requestedDebugPort || await waitForDevToolsPort(
    chromium,
    userDataDirectory,
  );
  const debugUrl = `http://127.0.0.1:${debugPort}`;
  await waitFor(`${debugUrl}/json/version`, chromium, "Chromium");
  const targets = await (
    await waitFor(`${debugUrl}/json/list`, chromium, "Chromium")
  ).json();
  const pageTarget = targets.find((target) => target.type === "page");
  requireCondition(pageTarget?.webSocketDebuggerUrl, "No Chromium page target was available");

  const client = new CdpClient(pageTarget.webSocketDebuggerUrl);
  await client.open();
  await client.send("Page.enable");
  await client.send("Runtime.enable");
  await client.send("Accessibility.enable");
  await client.send("Emulation.setDeviceMetricsOverride", {
    width: 320,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false,
  });
  const loaded = client.once("Page.loadEventFired");
  await client.send("Page.navigate", { url: previewUrl });
  await loaded;
  await sleep(500);

  const initialReflow = await client.evaluate(`(() => {
    const root = document.documentElement;
    return {
      innerWidth: window.innerWidth,
      clientWidth: root.clientWidth,
      scrollWidth: root.scrollWidth,
      horizontalOverflow: root.scrollWidth > root.clientWidth,
      themeButtonCount: document.querySelectorAll('button[aria-label^="Tema "]').length,
      credentialFieldCount: document.querySelectorAll('input[type="password"]').length,
    };
  })()`);
  requireCondition(initialReflow.innerWidth === 320, `Expected a 320 CSS px viewport, observed ${initialReflow.innerWidth}`);
  requireCondition(initialReflow.clientWidth >= 300 && initialReflow.clientWidth <= initialReflow.innerWidth, `Unexpected usable viewport width: ${JSON.stringify(initialReflow)}`);
  requireCondition(!initialReflow.horizontalOverflow, `Horizontal overflow detected: ${JSON.stringify(initialReflow)}`);
  requireCondition(initialReflow.themeButtonCount === 0, "Theme controls leaked into the primary mission flow");
  requireCondition(initialReflow.credentialFieldCount === 0, "Tenant credential field leaked into the primary workspace");

  await client.evaluate("document.body.focus()");
  await press(client, "Tab", "Tab");
  const firstFocus = await client.evaluate(`({
    tag: document.activeElement?.tagName,
    text: document.activeElement?.textContent?.trim(),
    href: document.activeElement?.getAttribute('href'),
  })`);
  requireCondition(firstFocus.href === "#main-content", `Skip link was not first: ${JSON.stringify(firstFocus)}`);
  await press(client, "Enter", "Enter");
  const skipResult = await client.evaluate(`({
    hash: location.hash,
    activeId: document.activeElement?.id ?? '',
  })`);
  requireCondition(skipResult.hash === "#main-content", `Skip link did not navigate: ${JSON.stringify(skipResult)}`);
  requireCondition(skipResult.activeId === "main-content", `Skip link did not move focus: ${JSON.stringify(skipResult)}`);

  const settingsFound = await client.evaluate(`(() => {
    const button = [...document.querySelectorAll('button')].find((candidate) => candidate.textContent?.trim() === 'Configuración');
    if (!button) return false;
    button.focus();
    return true;
  })()`);
  requireCondition(settingsFound, "El disparador de Configuración no estaba disponible");
  await press(client, "Enter", "Enter");
  await sleep(100);

  const settingsState = await client.evaluate(`(() => {
    const root = document.documentElement;
    const dialog = document.querySelector('[role="dialog"][aria-labelledby="workspace-settings-title"]');
    const themeButtons = [...document.querySelectorAll('button[aria-label^="Tema "]')];
    return {
      dialogPresent: Boolean(dialog),
      activeLabel: document.activeElement?.getAttribute('aria-label') ?? '',
      horizontalOverflow: root.scrollWidth > root.clientWidth,
      credentialFieldCount: document.querySelectorAll('input[type="password"]').length,
      themeButtons: themeButtons.map((button) => {
        const rect = button.getBoundingClientRect();
        return { name: button.getAttribute('aria-label'), width: rect.width, height: rect.height };
      }),
    };
  })()`);
  requireCondition(settingsState.dialogPresent, "El diálogo de Configuración no abrió");
  requireCondition(settingsState.activeLabel === "Cerrar configuración del espacio", `El foco de Configuración no entró al diálogo: ${JSON.stringify(settingsState)}`);
  requireCondition(!settingsState.horizontalOverflow, `Configuración introdujo overflow horizontal: ${JSON.stringify(settingsState)}`);
  requireCondition(settingsState.credentialFieldCount === 0, "Provider credential field appeared in browser settings");
  requireCondition(settingsState.themeButtons.length === 5, "Se esperaban cinco controles de tema dentro de Configuración");
  requireCondition(
    settingsState.themeButtons.every((button) => button.height >= 44 && button.width >= 44),
    `Theme target smaller than 44 CSS px: ${JSON.stringify(settingsState.themeButtons)}`,
  );

  await client.evaluate(`document.querySelector('button[aria-label="Tema rojo"]').focus()`);
  await press(client, "Enter", "Enter");
  const redSelection = await client.evaluate(`({
    theme: document.documentElement.dataset.theme,
    pressed: document.querySelector('button[aria-label="Tema rojo"]').getAttribute('aria-pressed'),
  })`);
  requireCondition(redSelection.theme === "red" && redSelection.pressed === "true", `Keyboard theme activation failed: ${JSON.stringify(redSelection)}`);

  await client.evaluate(`document.querySelector('button[aria-label="Tema premium"]').focus()`);
  await press(client, "Enter", "Enter");
  const premiumResult = await client.evaluate(`({
    theme: document.documentElement.dataset.theme,
    disabled: document.querySelector('button[aria-label="Tema premium"]').getAttribute('aria-disabled'),
    explanation: document.querySelector('button[aria-label="Tema premium"]').textContent?.trim() ?? '',
  })`);
  requireCondition(premiumResult.theme === "red", `Locked premium changed the theme: ${JSON.stringify(premiumResult)}`);
  requireCondition(premiumResult.disabled === "true", "Premium did not expose aria-disabled=true");
  requireCondition(premiumResult.explanation.includes("Requiere entitlement premium"), "Premium lock explanation was not discoverable");

  await client.send("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-reduced-motion", value: "reduce" }],
  });
  await client.evaluate(`(() => {
    window.__agencyViewTransitionCalls = 0;
    const original = document.startViewTransition?.bind(document);
    if (original) {
      Object.defineProperty(document, 'startViewTransition', {
        configurable: true,
        value: (...args) => {
          window.__agencyViewTransitionCalls += 1;
          return original(...args);
        },
      });
    }
  })()`);
  await client.evaluate(`document.querySelector('button[aria-label="Tema verde"]').focus()`);
  await press(client, "Enter", "Enter");
  const reducedMotion = await client.evaluate(`({
    theme: document.documentElement.dataset.theme,
    matches: matchMedia('(prefers-reduced-motion: reduce)').matches,
    viewTransitionCalls: window.__agencyViewTransitionCalls,
  })`);
  requireCondition(reducedMotion.matches, "Reduced-motion emulation was not active");
  requireCondition(reducedMotion.theme === "green", "Reduced-motion theme change did not complete");
  requireCondition(reducedMotion.viewTransitionCalls === 0, `View Transition ran under reduced motion: ${JSON.stringify(reducedMotion)}`);

  const axTree = await client.send("Accessibility.getFullAXTree");
  const themeAxNodes = axTree.nodes.filter(
    (node) => node.role?.value === "button" && axNodeName(node).startsWith("Tema "),
  );
  const settingsDialogAx = axTree.nodes.find(
    (node) => node.role?.value === "dialog" && axNodeName(node) === "Administración del espacio",
  );
  requireCondition(Boolean(settingsDialogAx), "El diálogo de Configuración no apareció en el árbol de accesibilidad");
  requireCondition(themeAxNodes.length === 5, `Expected five theme buttons in AX tree, got ${themeAxNodes.length}`);
  const greenAx = themeAxNodes.find((node) => axNodeName(node) === "Tema verde");
  const premiumAx = themeAxNodes.find((node) => axNodeName(node) === "Tema premium");
  requireCondition(axProperty(greenAx, "pressed") === "true", "Selected theme was not pressed in the AX tree");
  requireCondition(axProperty(premiumAx, "disabled") === true, "Premium lock was not disabled in the AX tree");

  await press(client, "Escape", "Escape");
  await sleep(50);
  const settingsClosed = await client.evaluate(`({
    dialogPresent: Boolean(document.querySelector('[role="dialog"][aria-labelledby="workspace-settings-title"]')),
    activeText: document.activeElement?.textContent?.trim() ?? '',
  })`);
  requireCondition(!settingsClosed.dialogPresent, "El diálogo de Configuración no cerró con Escape");
  requireCondition(settingsClosed.activeText === "Configuración", `El foco no volvió a Configuración: ${JSON.stringify(settingsClosed)}`);

  const connectFound = await client.evaluate(`(() => {
    const button = [...document.querySelectorAll('button')].find((candidate) => candidate.textContent?.trim() === 'Conectar espacio');
    if (!button) return false;
    button.focus();
    return true;
  })()`);
  requireCondition(connectFound, "El disparador Conectar espacio no estaba disponible");
  await press(client, "Enter", "Enter");
  await sleep(50);
  const credentialDisclosure = await client.evaluate(`({
    dialogPresent: Boolean(document.querySelector('[role="dialog"][aria-labelledby="connect-workspace-title"]')),
    credentialFieldCount: document.querySelectorAll('input[type="password"]').length,
    activeType: document.activeElement?.getAttribute('type') ?? '',
  })`);
  requireCondition(credentialDisclosure.dialogPresent, "El diálogo de conexión no abrió");
  requireCondition(credentialDisclosure.credentialFieldCount === 1, `Expected one disclosed credential field: ${JSON.stringify(credentialDisclosure)}`);
  requireCondition(credentialDisclosure.activeType === "password", `Credential field did not receive focus: ${JSON.stringify(credentialDisclosure)}`);
  await press(client, "Escape", "Escape");
  await sleep(50);
  const credentialClosed = await client.evaluate(`({
    dialogPresent: Boolean(document.querySelector('[role="dialog"][aria-labelledby="connect-workspace-title"]')),
    credentialFieldCount: document.querySelectorAll('input[type="password"]').length,
    activeText: document.activeElement?.textContent?.trim() ?? '',
  })`);
  requireCondition(!credentialClosed.dialogPresent && credentialClosed.credentialFieldCount === 0, "Credential disclosure did not close cleanly");
  requireCondition(credentialClosed.activeText === "Conectar espacio", `El foco no volvió a Conectar espacio: ${JSON.stringify(credentialClosed)}`);

  const screenshot = await client.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: false,
  });
  await writeFile(
    resolve(outputDirectory, "inc-013-product-workspace-320px.png"),
    Buffer.from(screenshot.data, "base64"),
  );

  const evidence = {
    chromium: await client.evaluate("navigator.userAgent"),
    previewUrl,
    viewport: initialReflow,
    settingsDisclosure: settingsState,
    credentialDisclosure: { opened: credentialDisclosure, closed: credentialClosed },
    skipLink: { firstFocus, result: skipResult },
    keyboardThemeSelection: redSelection,
    premiumLocked: premiumResult,
    reducedMotion,
    accessibilityTree: {
      themeButtons: themeAxNodes.map((node) => ({
        name: axNodeName(node),
        pressed: axProperty(node, "pressed"),
        disabled: axProperty(node, "disabled"),
      })),
    },
    limitations: [
      "Automated Chromium evidence is not a human screen-reader review.",
      "The screenshot is an artifact for later human visual review, not a visual PASS claim.",
      "No persistent deployment or production browser was exercised.",
    ],
  };
  await writeFile(
    resolve(outputDirectory, "inc-013-browser-evidence.json"),
    `${JSON.stringify(evidence, null, 2)}\n`,
  );
  console.log("accessibility_browser_reflow_320=pass");
  console.log("accessibility_browser_skip_link=pass");
  console.log("accessibility_browser_progressive_disclosure=pass");
  console.log("accessibility_browser_keyboard_theme=pass");
  console.log("accessibility_browser_premium_lock=pass");
  console.log("accessibility_browser_reduced_motion=pass");
  console.log("accessibility_browser_ax_tree=pass");
  console.log(`accessibility_browser_artifact=${outputDirectory}`);
  client.close();
}

try {
  await run();
} finally {
  await stopProcesses();
}
