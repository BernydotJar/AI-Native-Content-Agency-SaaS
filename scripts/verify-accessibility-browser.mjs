#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const repositoryRoot = resolve(import.meta.dirname, "..");
const portOffset = process.pid % 1000;
const previewPort = Number.parseInt(
  process.env.ACCESSIBILITY_PREVIEW_PORT ?? String(41000 + portOffset),
  10,
);
const debugPort = Number.parseInt(
  process.env.ACCESSIBILITY_DEBUG_PORT ?? String(43000 + portOffset),
  10,
);
const chromiumBin = process.env.CHROMIUM_BIN ?? "chromium";
const outputDirectory = resolve(
  repositoryRoot,
  process.env.ACCESSIBILITY_OUTPUT_DIR ?? "artifacts/accessibility/generated",
);
const previewUrl = `http://127.0.0.1:${previewPort}`;
const debugUrl = `http://127.0.0.1:${debugPort}`;
const processes = [];

function sleep(milliseconds) {
  return new Promise((resolvePromise) => setTimeout(resolvePromise, milliseconds));
}

async function waitFor(url, attempts = 80) {
  let lastError;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
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

function start(command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: repositoryRoot,
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
    detached: true,
    ...options,
  });
  processes.push(child);
  child.stdout.on("data", (chunk) => process.stderr.write(chunk));
  child.stderr.on("data", (chunk) => process.stderr.write(chunk));
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
  await mkdir(outputDirectory, { recursive: true });
  start("npm", ["run", "preview", "--", "--host", "127.0.0.1", "--port", String(previewPort)]);
  await waitFor(previewUrl);

  start(chromiumBin, [
    "--headless=new",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--log-level=3",
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=/tmp/agency-accessibility-chromium-${process.pid}`,
    "about:blank",
  ]);
  await waitFor(`${debugUrl}/json/version`);
  const targets = await (await waitFor(`${debugUrl}/json/list`)).json();
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

  const reflow = await client.evaluate(`(() => {
    const root = document.documentElement;
    const themeButtons = [...document.querySelectorAll('button[aria-label^="Tema "]')];
    return {
      innerWidth: window.innerWidth,
      clientWidth: root.clientWidth,
      scrollWidth: root.scrollWidth,
      horizontalOverflow: root.scrollWidth > root.clientWidth,
      themeButtons: themeButtons.map((button) => {
        const rect = button.getBoundingClientRect();
        return { name: button.getAttribute('aria-label'), width: rect.width, height: rect.height };
      }),
    };
  })()`);
  requireCondition(reflow.innerWidth === 320, `Expected a 320 CSS px viewport, observed ${reflow.innerWidth}`);
  requireCondition(reflow.clientWidth >= 300 && reflow.clientWidth <= reflow.innerWidth, `Unexpected usable viewport width: ${JSON.stringify(reflow)}`);
  requireCondition(!reflow.horizontalOverflow, `Horizontal overflow detected: ${JSON.stringify(reflow)}`);
  requireCondition(reflow.themeButtons.length === 5, "Expected five discoverable theme controls");
  requireCondition(
    reflow.themeButtons.every((button) => button.height >= 44 && button.width >= 44),
    `Theme target smaller than 44 CSS px: ${JSON.stringify(reflow.themeButtons)}`,
  );

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
    status: [...document.querySelectorAll('[role="status"]')].map((node) => node.textContent).find((text) => text?.includes('entitlement')) ?? '',
  })`);
  requireCondition(premiumResult.theme === "red", `Locked premium changed the theme: ${JSON.stringify(premiumResult)}`);
  requireCondition(premiumResult.disabled === "true", "Premium did not expose aria-disabled=true");
  requireCondition(premiumResult.status.includes("entitlement de pago"), "Premium lock was not announced");

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
  requireCondition(themeAxNodes.length === 5, `Expected five theme buttons in AX tree, got ${themeAxNodes.length}`);
  const greenAx = themeAxNodes.find((node) => axNodeName(node) === "Tema verde");
  const premiumAx = themeAxNodes.find((node) => axNodeName(node) === "Tema premium");
  requireCondition(axProperty(greenAx, "pressed") === "true", "Selected theme was not pressed in the AX tree");
  requireCondition(axProperty(premiumAx, "disabled") === true, "Premium lock was not disabled in the AX tree");

  const screenshot = await client.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: false,
  });
  await writeFile(
    resolve(outputDirectory, "inc-008-320px-green-reduced-motion.png"),
    Buffer.from(screenshot.data, "base64"),
  );

  const evidence = {
    chromium: await client.evaluate("navigator.userAgent"),
    previewUrl,
    viewport: reflow,
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
    resolve(outputDirectory, "inc-008-browser-evidence.json"),
    `${JSON.stringify(evidence, null, 2)}\n`,
  );
  console.log("accessibility_browser_reflow_320=pass");
  console.log("accessibility_browser_skip_link=pass");
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
