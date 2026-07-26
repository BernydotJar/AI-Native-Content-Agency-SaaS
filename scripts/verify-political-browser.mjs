#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const outputDir = resolve(root, "artifacts/political-browser/generated");
const legalKey = "browser-political-legal-key-material-2026";
const approverKey = "browser-political-approver-key-material-2026";
const children = [];
const temporary = [];

function requireValue(value, message) { if (!value) throw new Error(message); }
function sleep(ms) { return new Promise((resolveWait) => setTimeout(resolveWait, ms)); }
function pythonBin() {
  for (const candidate of [process.env.POLITICAL_BROWSER_PYTHON, "/tmp/ai-native-content-agency-runtime/bin/python", "python3.13", "python3.12", "python3.11", "python3"].filter(Boolean)) {
    if (spawnSync(candidate, ["-c", "import fastapi,uvicorn,httpx,pg8000"], { cwd: root, stdio: "ignore" }).status === 0) return candidate;
  }
  throw new Error("No supported Python runtime is available.");
}
function freePort() {
  return new Promise((resolvePort, reject) => {
    const server = createServer(); server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address(); server.close((error) => error ? reject(error) : resolvePort(address.port));
    });
  });
}
function start(command, args, options = {}) {
  const child = spawn(command, args, { cwd: root, env: process.env, stdio: ["ignore", "pipe", "pipe"], detached: true, ...options });
  child.output = "";
  child.stdout.on("data", (chunk) => { child.output = `${child.output}${chunk}`.slice(-30000); });
  child.stderr.on("data", (chunk) => { child.output = `${child.output}${chunk}`.slice(-30000); });
  children.push(child); return child;
}
async function stopAll() {
  for (const child of children.reverse()) {
    if (child.exitCode === null && child.signalCode === null) {
      try { process.kill(-child.pid, "SIGTERM"); } catch { child.kill("SIGTERM"); }
    }
  }
  await sleep(400);
  for (const path of temporary) await rm(path, { recursive: true, force: true });
}
async function waitFor(url, child, attempts = 160) {
  let lastError;
  for (let index = 0; index < attempts; index += 1) {
    if (child.exitCode !== null || child.signalCode !== null) throw new Error(`Process exited: ${child.output}`);
    try { const response = await fetch(url); if (response.ok) return response; lastError = new Error(`${url} returned ${response.status}`); }
    catch (error) { lastError = error; }
    await sleep(200);
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
        if (message.error) pending.reject(new Error(message.error.message));
        else pending.resolve(message.result);
        return;
      }
      const listeners = this.events.get(message.method) ?? []; this.events.delete(message.method); listeners.forEach((listener) => listener(message.params));
    });
  }
  send(method, params = {}) {
    const id = this.id++;
    return new Promise((resolveCall, reject) => { this.pending.set(id, { resolve: resolveCall, reject }); this.socket.send(JSON.stringify({ id, method, params })); });
  }
  once(method) { return new Promise((resolveEvent) => { const listeners = this.events.get(method) ?? []; listeners.push(resolveEvent); this.events.set(method, listeners); }); }
  async eval(expression) {
    const result = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true, userGesture: true });
    if (result.exceptionDetails) {
      const detail = result.exceptionDetails.exception?.description ?? result.exceptionDetails.text ?? "Evaluation failed";
      throw new Error(detail);
    }
    return result.result.value;
  }
  close() { this.socket.close(); }
}
async function waitDom(client, expression, message, attempts = 200) {
  for (let index = 0; index < attempts; index += 1) { if (await client.eval(expression)) return; await sleep(180); }
  throw new Error(message);
}
async function openBrowser(base, name) {
  const userData = await mkdtemp(join(tmpdir(), `agency-political-${name}-`)); temporary.push(userData);
  const chromium = start(process.env.CHROMIUM_BIN ?? "chromium", ["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--remote-debugging-port=0", `--user-data-dir=${userData}`, "about:blank"]);
  let debugPort;
  for (let index = 0; index < 240; index += 1) {
    try { debugPort = Number.parseInt((await readFile(join(userData, "DevToolsActivePort"), "utf8")).split(/\r?\n/)[0], 10); if (debugPort) break; } catch { /* retry */ }
    await sleep(150);
  }
  requireValue(debugPort, `${name}: Chromium debug port missing`);
  const debug = `http://127.0.0.1:${debugPort}`; await waitFor(`${debug}/json/version`, chromium);
  const page = (await (await fetch(`${debug}/json/list`)).json()).find((target) => target.type === "page");
  requireValue(page?.webSocketDebuggerUrl, `${name}: page target missing`);
  const client = new Cdp(page.webSocketDebuggerUrl); await client.open();
  await client.send("Page.enable"); await client.send("Runtime.enable"); await client.send("Network.enable");
  await client.send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1200, deviceScaleFactor: 1, mobile: false });
  const loaded = client.once("Page.loadEventFired"); await client.send("Page.navigate", { url: base }); await loaded;
  await waitDom(client, `document.body.innerText.includes('Conectar espacio')`, `${name}: workspace did not load`);
  return client;
}
async function screenshot(client, filename) {
  const shot = await client.send("Page.captureScreenshot", { format: "png", fromSurface: true, captureBeyondViewport: false });
  await writeFile(join(outputDir, filename), Buffer.from(shot.data, "base64"));
}
async function login(client, key, subject) {
  await client.eval(`([...document.querySelectorAll('button')].find((b)=>b.textContent?.includes('Conectar espacio'))).click()`);
  await waitDom(client, `document.querySelector('[role="dialog"]')?.innerText.includes('Conectar este navegador')`, "connection dialog missing");
  requireValue(await client.eval(`(() => { const input=document.querySelector('[role="dialog"] input[type="password"]'); if(!input)return false; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(key)}); input.dispatchEvent(new Event('input',{bubbles:true})); input.dispatchEvent(new Event('change',{bubbles:true})); return true; })()`), "credential input missing");
  await sleep(100);
  await client.eval(`document.querySelector('[role="dialog"] button[type="submit"]')?.click()`);
  await waitDom(client, `document.body.innerText.includes(${JSON.stringify(subject)}) && !document.querySelector('[role="dialog"]')`, `session for ${subject} did not open`);
}
const setField = (label, value) => `(() => { const label=[...document.querySelectorAll('label')].find((item)=>item.textContent?.trim().startsWith(${JSON.stringify(label)})); const control=label?.querySelector('input,textarea,select'); if(!control)return false; const proto=control instanceof HTMLSelectElement?HTMLSelectElement.prototype:control instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto,'value').set.call(control,${JSON.stringify(value)}); control.dispatchEvent(new Event('input',{bubbles:true})); control.dispatchEvent(new Event('change',{bubbles:true})); return true; })()`;
async function fillPoliticalBrief(client) {
  requireValue(await client.eval(setField("Tipo de campaña", "political")), "campaign type missing"); await sleep(120);
  const fields = [
    ["Idioma y región", "es-GT"], ["Título de campaña", "Prueba técnica de cumplimiento"], ["Segmento objetivo", "Operadores de un sandbox técnico"],
    ["Resultado esperado", "Validar trazabilidad y separación de autoridad sin publicar contenido real"], ["Modo de publicación política", "organic"],
    ["Jurisdicción", "Guatemala"], ["Cargo", "alcalde"], ["Candidato o candidatura", "Candidatura técnica de prueba"],
    ["Territorio", "Municipio de prueba"], ["Problema público", "La información pública está fragmentada"],
    ["Propuesta concreta", "Publicar un tablero mensual verificable"], ["Acción ciudadana", "Consultar la metodología y enviar observaciones"],
    ["Disclosure", "Prueba técnica; no corresponde a una campaña electoral."], ["Afirmación respaldada", "La prueba propone un tablero mensual verificable."],
    ["Fuente", "Documento técnico de prueba"], ["Página, sección o locator", "Sección 1"], ["Revisión legal", "approved"], ["Estado de verificación", "verified"],
  ];
  for (const [label, value] of fields) { requireValue(await client.eval(setField(label, value)), `field missing: ${label}`); }
  requireValue(await client.eval(`(() => { const label=[...document.querySelectorAll('label')].find((item)=>item.textContent?.trim()==='Instagram'); const input=label?.querySelector('input[type="checkbox"]'); if(!input)return false; if(input.checked)input.click(); return !input.checked; })()`), "Instagram toggle missing");
}
async function loadRun(client, runId) {
  requireValue(await client.eval(`(() => { const input=[...document.querySelectorAll('input')].find((item)=>item.placeholder==='run-…'); if(!input)return false; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(runId)}); input.dispatchEvent(new Event('input',{bubbles:true})); input.dispatchEvent(new Event('change',{bubbles:true})); return true; })()`), "run lookup missing");
  await sleep(100); await client.eval(`([...document.querySelectorAll('button')].find((b)=>b.textContent?.includes('Abrir ejecución'))).click()`);
  await waitDom(client, `document.body.innerText.includes(${JSON.stringify(runId)})`, "run did not load");
}
async function jsonRequest(url, key) {
  const response = await fetch(url, { headers: { Authorization: `Bearer ${key}` } }); const body = await response.json();
  if (!response.ok) throw new Error(`${url} failed (${response.status}): ${JSON.stringify(body)}`); return body;
}

async function run() {
  await rm(outputDir, { recursive: true, force: true }); await mkdir(outputDir, { recursive: true });
  const port = await freePort(); const base = `http://127.0.0.1:${port}`;
  const work = await mkdtemp(join(tmpdir(), "agency-political-browser-")); temporary.push(work);
  const database = join(work, "runtime.sqlite3"); const callFile = join(work, "provider-calls.txt"); await writeFile(callFile, "0");
  const providerCalls = async () => Number.parseInt(await readFile(callFile, "utf8"), 10);
  const fixturePythonPath = process.env.POLITICAL_BROWSER_USE_INSTALLED === "1"
    ? root
    : `${resolve(root, "backend")}:${root}`;
  const api = start(pythonBin(), ["-m", "uvicorn", "scripts.fixtures.political_browser_app:app", "--host", "127.0.0.1", "--port", String(port)], {
    env: { ...process.env, PYTHONPATH: fixturePythonPath, AGENCY_FIXTURE_DB_PATH: database, AGENCY_FIXTURE_STATIC_DIR: resolve(root, "dist"), AGENCY_FIXTURE_CALL_FILE: callFile },
  });
  await waitFor(`${base}/readyz`, api);
  const legal = await openBrowser(base, "legal"); const approver = await openBrowser(base, "approver");
  await login(legal, legalKey, "legal.reviewer@browser.test"); await fillPoliticalBrief(legal);
  await sleep(500);
  const formDiagnostic = await legal.eval(`(() => { const button=[...document.querySelectorAll('button')].find((b)=>b.textContent?.includes('Ejecutar campaña')); const form=button?.closest('form'); if(!form)return {buttonFound:Boolean(button),formFound:false}; return {buttonDisabled:button.disabled,formValid:form.checkValidity(),invalidCount:form.querySelectorAll(':invalid').length}; })()`);
  requireValue(formDiagnostic.formValid === true && formDiagnostic.buttonDisabled === false && formDiagnostic.invalidCount === 0, `political form invalid: ${JSON.stringify(formDiagnostic)}`);
  console.log("political_browser_form_valid=pass");
  await legal.eval(`([...document.querySelectorAll('button')].find((b)=>b.textContent?.includes('Ejecutar campaña'))).click()`);
  await sleep(1200);
  const transientOutput = await legal.eval(`document.body.innerText`);
  requireValue(!transientOutput.includes('Writer no produjo un copy deck utilizable'), "running state displayed a false Writer failure");
  requireValue(transientOutput.includes('El copy todavía se está generando'), "running copy progress state missing");
  const runId = await legal.eval(`([...document.querySelectorAll('input')].find((item)=>item.placeholder==='run-…'))?.value`); requireValue(runId?.startsWith("run-"), "run id missing");
  let durableRun;
  let previousStatus = "";
  for (let attempt = 0; attempt < 240; attempt += 1) {
    durableRun = await jsonRequest(`${base}/api/v1/runs/${runId}`, legalKey);
    if (durableRun.status !== previousStatus) { console.log(`political_browser_run_status=${durableRun.status}`); previousStatus = durableRun.status; }
    if (!["queued", "running"].includes(durableRun.status)) break;
    await sleep(500);
  }
  requireValue(durableRun?.status === "awaiting_greenlight", `political run durable status=${durableRun?.status}`);
  await waitDom(legal, `document.body.innerText.toLowerCase().includes('awaiting greenlight')`, "political run durable state reached Greenlight but UI did not update", 80);
  requireValue(await providerCalls() === 0, "provider called during campaign creation");
  await screenshot(legal, "01-legal-review-awaiting-greenlight.png");
  await legal.eval(`([...document.querySelectorAll('button')].find((b)=>b.textContent?.includes('Approve artefactos'))).click()`);
  await waitDom(legal, `document.querySelector('[role="alert"], [role="status"]')?.innerText.includes('identidades diferentes')`, "reviewer separation message is not specific or actionable");
  requireValue(await providerCalls() === 0, "provider called during rejected same-subject approval");
  await screenshot(legal, "02-same-reviewer-blocked.png");

  await login(approver, approverKey, "greenlight.approver@browser.test"); await loadRun(approver, runId);
  await approver.eval(`([...document.querySelectorAll('button')].find((b)=>b.textContent?.includes('Approve artefactos'))).click()`);
  await waitDom(approver, `document.body.innerText.toLowerCase().includes('completed') && document.body.innerText.includes('Revocar Greenlight')`, "independent Greenlight did not complete");
  await approver.eval(`document.querySelector('#campaign-output')?.scrollIntoView({block:'start'})`); await sleep(200);
  await screenshot(approver, "03-independent-greenlight.png");
  const run = await jsonRequest(`${base}/api/v1/runs/${runId}`, approverKey);
  const record = run.artifacts.find((item) => item.kind === "political_compliance_record");
  const copyDeck = run.artifacts.find((item) => item.kind === "copy_deck");
  const riskReport = run.artifacts.find((item) => item.kind === "risk_report");
  requireValue(record, "political compliance record missing");
  requireValue(copyDeck?.payload?.variants?.x, "X political copy variant missing");
  requireValue(riskReport?.payload?.publication_eligible === true, "Critique did not mark grounded political content eligible");
  requireValue(record.payload.legal_reviewer === "legal.reviewer@browser.test", "legal reviewer binding mismatch");
  requireValue(record.payload.greenlight_approver === "greenlight.approver@browser.test", "Greenlight approver binding mismatch");
  requireValue(await providerCalls() === 0, "provider called before final confirmation");

  const publishState = await approver.eval(`(() => [...document.querySelectorAll('button')].filter((b)=>b.textContent?.trim()==='Publicar').map((b)=>({disabled:b.disabled,title:b.title})))()`);
  requireValue(publishState.some((item) => !item.disabled && item.title === "Listo para publicar"), `publish button not ready: ${JSON.stringify(publishState)}`);
  await approver.eval(`([...document.querySelectorAll('button')].find((b)=>b.textContent?.trim()==='Publicar'&&!b.disabled)).click()`);
  await waitDom(approver, `document.querySelector('[role="dialog"]')?.innerText.includes('Confirmación política obligatoria')`, "political confirmation dialog missing");
  const phrase = `PUBLICAR POLITICA ${runId} x`;
  requireValue(await providerCalls() === 0, "provider called on first publish click");
  requireValue(await approver.eval(`([...document.querySelectorAll('[role="dialog"] button')].find((b)=>b.textContent?.includes('Confirmar publicación externa')))?.disabled === true`), "confirmation button must start disabled");
  requireValue(await approver.eval(setField("Frase de confirmación política", "PUBLICAR POLITICA incorrecta x")), "political phrase input missing"); await sleep(80);
  requireValue(await approver.eval(`([...document.querySelectorAll('[role="dialog"] button')].find((b)=>b.textContent?.includes('Confirmar publicación externa')))?.disabled === true`), "wrong phrase enabled external effect");
  requireValue(await approver.eval(setField("Frase de confirmación política", phrase)), "political phrase input missing"); await sleep(80);
  requireValue(await approver.eval(`([...document.querySelectorAll('[role="dialog"] button')].find((b)=>b.textContent?.includes('Confirmar publicación externa')))?.disabled === false`), "exact phrase did not enable confirmation");
  await screenshot(approver, "04-political-confirmation.png");
  await approver.eval(`([...document.querySelectorAll('[role="dialog"] button')].find((b)=>b.textContent?.includes('Confirmar publicación externa'))).click()`);
  await waitDom(approver, `document.body.innerText.includes('Receipt durable registrado') && !document.querySelector('[role="dialog"]')`, "political publication did not complete");
  requireValue(await providerCalls() === 1, "expected exactly one mock provider call");
  await screenshot(approver, "05-verified-publication-receipt.png");

  const publications = await jsonRequest(`${base}/api/v1/runs/${runId}/social-publications`, approverKey);
  requireValue(publications.publications.length === 1 && publications.publications[0].status === "succeeded", "durable publication receipt missing");
  const databaseBytes = await readFile(database); requireValue(!databaseBytes.includes(Buffer.from(phrase)), "raw political confirmation persisted in database");
  requireValue(!api.output.includes(legalKey) && !api.output.includes(approverKey), "fixture leaked browser credentials");
  await writeFile(join(outputDir, "political-browser-evidence.json"), `${JSON.stringify({
    runId,
    legalReviewer: record.payload.legal_reviewer,
    greenlightApprover: record.payload.greenlight_approver,
    reviewerSeparation: true,
    complianceRecordIncludedInGreenlight: run.greenlight.approved_artifact_ids.includes(record.artifact_id),
    wrongPhraseBlocked: true,
    providerCallsBeforeConfirmation: 0,
    providerCallsAfterConfirmation: 1,
    durableIntentCount: publications.publications.length,
    durableStatus: publications.publications[0].status,
    rawConfirmationPersisted: false,
    providerTransport: "mock_only",
    copyVariant: copyDeck.payload.variants.x,
    critique: {
      decision: riskReport.payload.decision,
      publicationEligible: riskReport.payload.publication_eligible,
      checks: riskReport.payload.checks,
      limitations: riskReport.payload.limitations,
    },
    artifactKinds: run.artifacts.map((item) => item.kind),
  }, null, 2)}\n`);
  console.log("political_browser_running_copy_state=pass");
  console.log("political_browser_two_identity_gate=pass");
  console.log("political_browser_compliance_record=pass");
  console.log("political_browser_wrong_phrase_blocked=pass");
  console.log("political_browser_provider_calls_before_confirmation=0");
  console.log("political_browser_provider_calls_after_confirmation=1");
  console.log("political_browser_raw_confirmation_persisted=false");
  console.log(`political_browser_artifact=${outputDir}`);
  legal.close(); approver.close();
}

try { await run(); } finally { await stopAll(); }
