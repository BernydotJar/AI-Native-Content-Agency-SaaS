# Implementation Audit

Fecha de corte: 21 de julio de 2026.

Este documento compara el producto actual con `proposal_and_prompt.md` y con el contrato operativo de `agency_manifesto.md`. La evidencia se refiere a archivos ejecutables o pruebas del repositorio; no a intención futura.

## Convención de estado

| Estado | Significado |
|---|---|
| **Real local** | Ejecuta lógica o persistencia real dentro del proceso o filesystem local, sin afirmar integración externa. |
| **Mock explícito** | El contrato y la experiencia existen, pero los datos o resultados son fixtures/simulaciones sin side effects. |
| **Parcial** | Sólo una parte observable del requisito está implementada o las capas aún no están conectadas. |
| **No implementado** | No hay una ruta ejecutable que satisfaga el requisito. |

## Matriz requisito → evidencia → estado

| Requisito | Evidencia actual | Estado |
|---|---|---|
| Webapp cinematográfica, oscura y single-scroll | [`src/App.tsx`](../src/App.tsx), [`src/index.css`](../src/index.css), [`src/components/CanvasBackground.tsx`](../src/components/CanvasBackground.tsx), [`src/components/GlowCard.tsx`](../src/components/GlowCard.tsx) | **Real local.** Render React, layout responsive, escena obsidian/slate, partículas y motion. |
| Topología Fabric con entrada y ocho estaciones | [`src/components/PipelineGraph.tsx`](../src/components/PipelineGraph.tsx) y su prueba | **Real local.** Sensor + CEO, Research, Strategist, Growth, Writer, Media, Risk y Publisher. |
| Estados por nodo, progreso y transmisión visual | `PipelineGraph.tsx`, estado de misión en [`src/App.tsx`](../src/App.tsx) | **Real local para UI; mock para ejecución.** Las transiciones son timers del navegador, no eventos backend. |
| Sidebar con actividad, archivos/assets y Greenlight | [`src/components/InteractiveSidebar.tsx`](../src/components/InteractiveSidebar.tsx) | **Parcial.** Hay tabs Activity/Outputs, previews y gate accesible; no hay conversación bidireccional, filesystem de artefactos ni descarga versionada. |
| Tres casos de uso: video, imagen y campaña completa | [`src/components/ControlPanel.tsx`](../src/components/ControlPanel.tsx), `src/App.tsx` | **Mock explícito.** La UI acepta parámetros/nombre de archivo y produce planes/previews sandbox; no lee binarios ni genera media. |
| Scholar NLP en tres puntos | [`src/lib/simulationRuntime.ts`](../src/lib/simulationRuntime.ts) y pruebas | **Real local como transformación determinista; contenido simulado.** Siempre devuelve reencuadre, tensión del trade-off y resolución operativa. |
| Mezcla de tendencias X/Facebook/TikTok/Instagram | `simulationRuntime.ts`, [`src/components/ToolFabricPanel.tsx`](../src/components/ToolFabricPanel.tsx) | **Mock explícito.** Cuatro señales fijas y adaptaciones deterministas; no consulta plataformas. |
| Meta Ads feedback loop | [`src/components/MetaAdsDashboard.tsx`](../src/components/MetaAdsDashboard.tsx), adaptador TS y `backend/agency_runtime/tools.py` | **Mock explícito.** Métricas/forecast sintéticos; cero creación de campañas o gasto. |
| Catálogo de ocho herramientas solicitado | `SIMULATION_TOOL_CATALOG` en `simulationRuntime.ts` y `SandboxToolset` en [`backend/agency_runtime/tools.py`](../backend/agency_runtime/tools.py) | **Mock explícito.** Contratos para trends, Meta Ads, browser, GitHub, Context7, video, image-to-video y packager; todos declaran sandbox. |
| Runtime de ocho agentes | [`backend/agency_runtime/orchestrator.py`](../backend/agency_runtime/orchestrator.py), [`backend/agency_runtime/models.py`](../backend/agency_runtime/models.py), [`backend/agency_runtime/flow_manifest.json`](../backend/agency_runtime/flow_manifest.json) | **Real local.** Flujo secuencial determinista, artefactos, estados, traza y evidencia; los adaptadores que alimentan el flujo son mocks. |
| Fachada ejecutable del runtime | [`agency.py`](../agency.py), [`backend/agency_runtime/cli.py`](../backend/agency_runtime/cli.py) | **Real local.** Demo segura por defecto y reportes humanos/JSON. No requiere `agency_swarm`. |
| Greenlight obligatorio después de Risk y antes de Publisher | Gate TS en `src/App.tsx`; gate Python en `orchestrator.py`; pruebas de ambas capas | **Real local.** Detiene trabajo local de Publisher. Aprobación sólo libera empaquetado sandbox; rechazo bloquea. Los dos gates no comparten estado. |
| Revocación/cancelación | `src/App.tsx` y [`src/App.test.tsx`](../src/App.test.tsx) | **Parcial.** La UI cancela timers pendientes durante una ejecución. El runtime Python soporta approve/reject antes del packaging, pero no revocación posterior a la aprobación. |
| Memoria Observe → Store → Search → Recall | [`backend/agency_runtime/memory.py`](../backend/agency_runtime/memory.py), pruebas de persistencia; [`src/components/MemorySkillsPanel.tsx`](../src/components/MemorySkillsPanel.tsx) | **Real local en Python; mock/local-session en UI.** SQLite conserva contenido, procedencia, confianza y tags. No hay sincronización navegador↔SQLite. |
| Provenance, confianza y evidencia | `memory.py`, `models.py`, `orchestrator.py` | **Real local.** Registros tipados y consultables. La procedencia de herramientas sigue siendo sandbox, no prueba de fuente externa. |
| Instrucciones por agente | [`agents/`](../agents) | **Parcial.** Existen ocho documentos auditables; el orquestador no los parsea ni aplica dinámicamente. |
| Base de conocimiento | [`knowledge/`](../knowledge), [`agency_manifesto.md`](../agency_manifesto.md) | **Parcial.** Corpus local con índice/procedencia; no hay retrieval ni inyección automática al runtime. |
| Skills editoriales y de plataforma | [`skills/`](../skills), toggles en `MemorySkillsPanel.tsx` | **Parcial.** Los Markdown existen y la UI aplica cuatro overlays deterministas; no hay motor general que ejecute los playbooks. |
| Creación dinámica de skills | [`backend/agency_runtime/skill_creator.py`](../backend/agency_runtime/skill_creator.py), [`backend/tests/test_skill_creator.py`](../backend/tests/test_skill_creator.py) | **Real local como utilidad aislada.** Escritura segura y atómica dentro de una raíz; sin CLI, UI ni enlace al orquestador. |
| Publicación multicanal | `CampaignPackagerTool` TS/Python | **No implementado.** Sólo manifiestos `sandbox://`; `publication_performed=false`. |
| Generación/optimización real de media | Adaptadores `VideoOptimizerTool` e `ImageToVideoTool` | **No implementado.** Se crean planes y storyboards; ningún archivo se lee o renderiza. |
| Context7, browser y GitHub en runtime | Catálogos TS/Python con estados mock | **No implementado como integración.** Los nombres representan contratos de adapter; el producto no hace llamadas, navegación ni cambios remotos. |
| API Meta Ads y métricas live | Catálogo, dashboard y forecast fixture | **No implementado.** No hay OAuth, cuenta publicitaria, mutación, polling ni spend. |
| Transporte frontend↔backend | `ProductionRuntimePanel.tsx` + `runtimeApi.ts` consumen FastAPI same-origin con cookie HttpOnly y CSRF | **Real para el vertical slice de producción.** El simulador cinematográfico original sigue como runtime paralelo. |
| Streaming de eventos | FastAPI sólo expone request/response REST; no hay SSE/WebSocket | **No implementado.** La animación web usa timers locales. |
| Persistencia de producto multiusuario | `auth.py`, `persistence.py`, memoria namespaced y pruebas de reinicio/cross-tenant | **Real local, single-node.** Runs y approvals sobreviven reinicios y se particionan por tenant; falta PostgreSQL, identidad individual y object storage. |
| Accesibilidad y reduced motion | Skip link y semántica en `src/App.tsx`; controles/tab/progressbar en componentes; media queries en `src/index.css` | **Real local, con cobertura automatizada parcial.** Falta auditoría manual completa con browser/lector de pantalla. |
| Testing y build reproducibles | Tests web/backend, `requirements*.lock`, wheel scripts, `package-lock.json`, Dockerfile y CI | **Real local.** Hash-verified Python graphs, byte-identical drift gate, wheel `--no-deps`, `pip check`, TypeScript, interaction, lint and bundle gates. |

## Desviaciones intencionales de la propuesta

### Vite/React en lugar de Next.js

La implementación conserva React y TypeScript, pero usa Vite 8. No hay routing de servidor, Server Components, API routes ni SSR. Para el prototipo single-page actual, Vite reduce infraestructura y mantiene el build estático; no satisface un requisito estricto de Next.js si éste fuera contractual.

### SVG/DOM propio en lugar de React Flow

La topología usa botones HTML posicionados y un SVG normalizado para edges. Esto evita otra dependencia y permite una secuencia móvil específica, pero no ofrece edición de grafos, zoom/pan, minimap, handles o el ecosistema de React Flow.

### Consola cliente/servidor junto al simulador legado

`ProductionRuntimePanel.tsx` ya ejecuta el backend durable mediante contratos HTTP tipados. `src/lib/simulationRuntime.ts` permanece para la experiencia cinematográfica preexistente. La duplicación es deliberada durante la transición y deberá retirarse sólo después de demostrar paridad de misiones, estados, memoria y Greenlight.

### Fixtures deterministas en lugar de MCP/APIs live

Los adaptadores usan nombres de las capacidades objetivo para mantener una interfaz futura, pero sus clases, estados, evidencia y copy declaran `mock`, `sandbox` o `fixture`. Esta es una decisión de seguridad y trazabilidad; no una integración parcial implícita.

## Verificación registrada

Ejecutado el 17 de julio de 2026:

| Comando | Resultado observado |
|---|---|
| `rtk test npm run lint` | Oxlint completó sin hallazgos. Se usa este wrapper porque `rtk lint` no es compatible con el parser de esta configuración. |
| `rtk test npm test` | 28 tests frontend/runtime TS aprobados. |
| `rtk test npm run build` | TypeScript y bundle Vite completados. |
| `npm run preview -- --host 127.0.0.1 --port 4175` + `curl` | El artefacto de producción respondió `HTTP/1.1 200 OK` y sirvió los bundles generados. |
| `cd backend && python3 -m unittest discover -s tests -v` | 16 tests Python aprobados: runtime, memoria, fachada, flow manifest y creador de skills. |
| `python3 agency.py demo --approve --json` | `completed`, 8 agentes/evidencias, manifiesto sandbox y todos los side effects externos en cero. |

Context7 se usó fuera del runtime, mediante la CLI oficial, para recuperar documentación versionada de Tailwind CSS y Vitest durante la implementación. Esto no cambia el estado **mock** del adapter `Context7DocsTool` del producto.

La verificación automatizada no sustituye QA visual/manual. El browser integrado devolvió una lista vacía de instancias, por lo que la QA visual interactiva no fue ejecutable en este cierre. Tampoco se validó con lector de pantalla, dispositivos físicos ni cuentas externas.

## Trabajo necesario para una integración real

1. Definir esquemas versionados para brief, eventos, artefactos, evidencia, memoria y Greenlight.
2. Conectar el frontend al servicio autenticado y elegir SSE/WebSocket sólo para eventos que realmente necesiten streaming.
3. Reemplazar cada fixture por un adapter separado, autenticado, observable e idempotente.
4. Implementar revocación efectiva del Greenlight en backend.
5. Integrar un IdP administrado con SSO/MFA, lifecycle provisioning, retención/borrado y auditoría exportable.
6. Conectar el frontend a una única fuente de verdad y retirar la state machine duplicada cuando la paridad esté comprobada.
7. Realizar QA visual, responsive, accesible y de fallo antes de cualquier piloto con efectos externos.

## Production Readiness increments — 21 July 2026

| Capability | Evidence | Status |
|---|---|---|
| Network-addressable backend | `backend/agency_runtime/api.py` exposes health, readiness, identity, run creation/read, approval, and rejection via FastAPI. | **Real local and packaged.** |
| Brief → governed campaign package vertical slice | `backend/tests/test_api.py` executes brief → seven pre-gate artifacts → Scholar → Risk → Greenlight → sandbox package. | **Real local with mock external evidence.** |
| Scholar three-part explanation | `research_dossier.payload.scholar` contains cognitive reframing, trade-off tension, and operational resolution. | **Real deterministic transformation.** |
| Artifact-bound Greenlight | `Greenlight` records exact artifact IDs and SHA-256-derived hashes, authorized channels, and budget. | **Real and durable.** Revocation after approval remains missing. |
| Individual identity and RBAC | `auth.py`, `test_identity_access.py`, session persistence and frontend identity display derive tenant/subject/role/key ID server-side and enforce viewer/operator/approver/admin permissions. | **Real local and packaged.** Static application-managed identities; managed IdP, SSO and MFA remain open. |
| Tenant isolation | Run store uses `(tenant_id, run_id)` and memory uses tenant namespaces; cross-tenant reads return `404`. | **Verified.** |
| Durable authentication abuse controls | `authentication_failures`, separate credential/source thresholds, aggregate metrics, trusted-proxy configuration and negative tests. | **Real single-node.** Raw keys and sources are not persisted; shared/distributed limiter and ingress/WAF controls remain open. |
| Durable run persistence | `persistence.py` serializes the complete execution and restores it before later decisions. | **Verified across multiple service restarts.** |
| Unified production process | Multi-stage image serves React and FastAPI as non-root UID `10001`; packaged smoke covers health, readiness, auth, SPA and API. | **Verified with Buildah vfs/chroot.** |
| Kubernetes state and secrets | Helm requires individual identity from an existing Secret, permits legacy-key removal, configures trusted proxies/rate limits, provisions a PVC, uses one replica and `Recreate`, and rejects unsafe bounds/scaling. | **Helm lint/template and negative guards verified locally.** |
| Horizontal high availability | SQLite remains a single-writer store. | **Missing; requires shared database adapter.** |
| Structured observability | `observability.py`, `/metrics`, request middleware, Helm scrape annotations, and sanitization tests. | **Real local.** Metrics are process-local; no external exporter or distributed tracing. |
| Durable audit export | Transactional `audit_events` plus tenant-scoped cursor endpoint and restart tests. | **Real local.** Application append-only; no hash chain, retention engine, immutable archive, or SIEM export. |
| Browser-safe frontend session | `runtime_sessions`, `/api/v1/sessions*`, `runtimeApi.ts`, `ProductionRuntimePanel.tsx`, and session/storage tests. | **Real local and packaged.** HttpOnly/SameSite/CSRF/rotation/revocation plus active-key revalidation; no SSO/MFA. |
| Reproducible Python graph | Three `.in` files, three hash locks, locked pip-tools/build toolchain, wheel verification scripts, Docker and CI. | **Verified across Python 3.11 lock generation, Python 3.13 CI verification and Python 3.13.14 Alpine image runtime.** |
| Supply-chain evidence and policy | Digest-pinned bases, SHA-pinned Actions, Syft SBOM, Grype policy, license policy, in-toto provenance, Cosign verification and CI retention. | **Verified locally without publication.** 0 Critical; 5 exact High exceptions expire 21 August 2026. Production registry/KMS or keyless signing remains open. |
| Local Terraform/Kubernetes validation | Checksum-pinned Terraform/kubectl/K3s, `verify-local-infrastructure.sh`, agentless K3s API, Terraform apply/destroy, Helm server dry-run. | **Real API/admission validation.** Pod scheduling is not claimed because host cgroups are read-only; executable image is verified separately. |

Verification on 21 July 2026: Oxlint passed, 33 frontend tests passed, Vite production build passed, 40 Python tests passed from the hash-locked `agency-runtime` 0.6.0 wheel, all locks regenerated byte-identically, actionlint passed, Helm lint/template and identity/rate-limit safety guards passed, and the Python 3.13.14 Alpine package passed individual identity, RBAC, HttpOnly session, CSRF, run, Greenlight, package, audit, metrics and revocation smoke. K3s agentless accepted the rendered identity/Secret/proxy/rate-limit deployment through a real Kubernetes API, and Terraform plan/apply/destroy plus cleanup passed without Secret values entering state. Supply-chain evidence was regenerated against clean source commit `bba84937b020c9e4bc8a962f2627675633e3a43f`; OCI, SBOM, Grype policy, provenance, Cosign verification and 5/5 checksums passed without registry publication. Docker's nested daemon remains unavailable; the documented Buildah `vfs` + `chroot` alternative completed the image and runtime smoke.
