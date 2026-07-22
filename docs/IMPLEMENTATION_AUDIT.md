# Implementation Audit

Fecha de corte: 22 de julio de 2026.

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
| Espacio de trabajo oscuro y responsive | [`src/App.tsx`](../src/App.tsx), [`src/index.css`](../src/index.css), [`src/components/CanvasBackground.tsx`](../src/components/CanvasBackground.tsx) | **Real local.** Shell de producto, misión gobernada, configuración progresiva, partículas decorativas y layout responsive. |
| Topología Fabric con entrada y ocho estaciones | [`src/components/PipelineGraph.tsx`](../src/components/PipelineGraph.tsx) y su prueba | **Real local.** Sensor + CEO, Research, Strategist, Growth, Writer, Media, Risk y Publisher. |
| Estados por nodo, progreso y transmisión visual | `PipelineGraph.tsx`, [`src/App.tsx`](../src/App.tsx), [`src/components/WorkspaceRuntime.tsx`](../src/components/WorkspaceRuntime.tsx) | **Real para el runtime durable.** La topología deriva de `run.agent_states`; ya no usa timers de una state machine paralela. |
| Actividad, artefactos y Greenlight | [`src/components/WorkspaceRuntime.tsx`](../src/components/WorkspaceRuntime.tsx), `runtimeApi.ts` | **Real local y durable.** El workspace crea/abre runs, lista artefactos versionados, consulta auditoría y aplica approve/reject/revoke según RBAC. Descarga de archivos binarios aún no existe. |
| Brief de campaña y ejecución gobernada | [`src/components/WorkspaceRuntime.tsx`](../src/components/WorkspaceRuntime.tsx), [`backend/agency_runtime/api.py`](../backend/agency_runtime/api.py) | **Real local para el vertical slice durable.** Crea un run tenant-scoped y produce artefactos deterministas; ingesta de video/imagen y media real siguen no implementadas. |
| Scholar NLP en tres puntos | `research_dossier.payload.scholar`, [`src/components/RunContextPanel.tsx`](../src/components/RunContextPanel.tsx), pruebas backend | **Real como transformación determinista del runtime.** Expone reencuadre, tensión y resolución; aún no usa un proveedor de modelos externo. |
| Señales y canales externos | [`backend/agency_runtime/tools.py`](../backend/agency_runtime/tools.py), [`src/components/OperationalFabricPanel.tsx`](../src/components/OperationalFabricPanel.tsx) | **No implementado como integración externa.** Las fixtures backend siguen deterministas y la UI ya no las presenta como proveedores conectados. |
| Meta Ads feedback loop | [`backend/agency_runtime/tools.py`](../backend/agency_runtime/tools.py) | **No implementado como integración.** El frontend legacy fue retirado; no hay OAuth, mutación, polling ni gasto. |
| Fabric de herramientas y proveedores | [`backend/agency_runtime/providers.py`](../backend/agency_runtime/providers.py), [`src/components/OperationalFabricPanel.tsx`](../src/components/OperationalFabricPanel.tsx), `SandboxToolset` backend | **Parcial.** Cinco proveedores de modelos tienen configuración server-side real y secret-free; las herramientas de research/media/ads/browser continúan deterministas y sin egress. |
| Runtime de ocho agentes | [`backend/agency_runtime/orchestrator.py`](../backend/agency_runtime/orchestrator.py), [`backend/agency_runtime/models.py`](../backend/agency_runtime/models.py), [`backend/agency_runtime/flow_manifest.json`](../backend/agency_runtime/flow_manifest.json) | **Real local.** Flujo secuencial determinista, artefactos, estados, traza y evidencia; los adaptadores que alimentan el flujo son mocks. |
| Fachada ejecutable del runtime | [`agency.py`](../agency.py), [`backend/agency_runtime/cli.py`](../backend/agency_runtime/cli.py) | **Real local.** Demo segura por defecto y reportes humanos/JSON. No requiere `agency_swarm`. |
| Greenlight obligatorio después de Risk y antes de Publisher | `orchestrator.py`, `persistence.py`, `WorkspaceRuntime.tsx` y pruebas SQLite/PostgreSQL | **Real y compartido.** La UI consume la misma autoridad durable del backend; approve/reject/revoke usan idempotencia y fencing. |
| Revocación/cancelación | `WorkspaceRuntime.tsx`, API Greenlight y pruebas de idempotencia | **Real local y durable.** Revocación incrementa fencing token, conserva evidencia e invalida autoridad anterior. |
| Memoria y contexto aplicado | [`backend/agency_runtime/memory.py`](../backend/agency_runtime/memory.py), pruebas de persistencia; [`src/components/RunContextPanel.tsx`](../src/components/RunContextPanel.tsx) | **Real local en Python.** SQLite/PostgreSQL conservan contexto tenant-scoped; la UI muestra evidencia y decisiones aplicadas, no el algoritmo Observe/Store/Search/Recall. |
| Provenance, confianza y evidencia | `memory.py`, `models.py`, `orchestrator.py` | **Real local.** Registros tipados y consultables. La procedencia de herramientas sigue siendo sandbox, no prueba de fuente externa. |
| Instrucciones por agente | [`agents/`](../agents) | **Parcial.** Existen ocho documentos auditables; el orquestador no los parsea ni aplica dinámicamente. |
| Base de conocimiento | [`knowledge/`](../knowledge), [`agency_manifesto.md`](../agency_manifesto.md) | **Parcial.** Corpus local con índice/procedencia; no hay retrieval ni inyección automática al runtime. |
| Skills editoriales y de plataforma | [`skills/`](../skills) | **Parcial.** Los Markdown existen como fuentes auditables; el frontend legacy de toggles fue retirado y el runtime todavía no los carga como motor general. |
| Creación dinámica de skills | [`backend/agency_runtime/skill_creator.py`](../backend/agency_runtime/skill_creator.py), [`backend/tests/test_skill_creator.py`](../backend/tests/test_skill_creator.py) | **Real local como utilidad aislada.** Escritura segura y atómica dentro de una raíz; sin CLI, UI ni enlace al orquestador. |
| Publicación multicanal | `CampaignPackagerTool` TS/Python | **No implementado.** Sólo manifiestos `sandbox://`; `publication_performed=false`. |
| Generación/optimización real de media | Adaptadores `VideoOptimizerTool` e `ImageToVideoTool` | **No implementado.** Se crean planes y storyboards; ningún archivo se lee o renderiza. |
| Browser/video e integraciones revisadas | registro `video-use` pinneado, API GET-only, `OperationalFabricPanel.tsx` | **Revisado y deshabilitado.** No existe executor, navegación, render, upload ni cambio remoto. |
| API Meta Ads y métricas live | `backend/agency_runtime/tools.py` y límites de integración | **No implementado.** No hay OAuth, cuenta publicitaria, mutación, polling ni spend; el dashboard mock fue retirado. |
| Transporte frontend↔backend | [`src/components/WorkspaceRuntime.tsx`](../src/components/WorkspaceRuntime.tsx) + `runtimeApi.ts` consumen FastAPI same-origin con cookie HttpOnly y CSRF | **Real para el único frontend activo.** La state machine cinematográfica y `ProductionRuntimePanel` fueron retirados en `INC-013`. |
| Streaming de eventos | FastAPI sólo expone request/response REST; no hay SSE/WebSocket | **No implementado.** La animación web usa timers locales. |
| Persistencia de producto multiusuario | `auth.py`, `persistence.py`, `postgres.py`, memoria namespaced, backup/restore y pruebas de reinicio/cross-tenant | **Real local para SQLite y PostgreSQL.** Runs, approvals, sesiones, rate limits y memoria sobreviven reinicios y se particionan por tenant. Los drills SQLite/PostgreSQL ya restauran estado representativo; PostgreSQL runtime/migration authority separation está implementada en `INC-012` pero no verificada en el worktree actual. Siguen faltando object storage, backup productivo programado/cifrado/inmutable, failover y capacidad medida. |
| Accesibilidad y reduced motion | Skip link y semántica en `src/App.tsx`; controles/tab/progressbar en componentes; media queries en `src/index.css` | **Real local, con cobertura automatizada parcial.** Falta auditoría manual completa con browser/lector de pantalla. |
| Testing y build reproducibles | Tests web/backend, `requirements*.lock`, wheel scripts, `package-lock.json`, Dockerfile y CI | **Real local.** Hash-verified Python graphs, byte-identical drift gate, wheel `--no-deps`, `pip check`, TypeScript, interaction, lint and bundle gates. |
| Release compliance y claims | `compliance/*.json`, `scripts/verify-release-compliance.py`, `backend/tests/test_release_compliance.py` | **Real local como gate de denegación.** Inventaría 33 componentes directos/build/candidato, valida licencias/digests/SHAs, cero proveedores activos, decisiones de privacidad UNKNOWN/unapproved y copy pública. Resultado `DENY_RELEASE`; no es asesoría ni certificación. |

## Desviaciones intencionales de la propuesta

### Vite/React en lugar de Next.js

La implementación conserva React y TypeScript, pero usa Vite 8. No hay routing de servidor, Server Components, API routes ni SSR. Para el prototipo single-page actual, Vite reduce infraestructura y mantiene el build estático; no satisface un requisito estricto de Next.js si éste fuera contractual.

### SVG/DOM propio en lugar de React Flow

La topología usa botones HTML posicionados y un SVG normalizado para edges. Esto evita otra dependencia y permite una secuencia móvil específica, pero no ofrece edición de grafos, zoom/pan, minimap, handles o el ecosistema de React Flow.

### Única shell cliente/servidor

`INC-013` retiró `ProductionRuntimePanel`, `ControlPanel`, `MemorySkillsPanel`, `ToolFabricPanel`, `MetaAdsDashboard`, `InteractiveSidebar` y `simulationRuntime`. `App.tsx` y `WorkspaceRuntime.tsx` son ahora la única experiencia activa y consumen la autoridad durable de FastAPI.

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
| Horizontal high availability | `postgres.py` supplies bounded pooled shared state and cross-instance tests. | **Partial.** The shared adapter is verified locally, but no scheduler workload, failover, soak, capacity or managed-database evidence exists. |
| Structured observability | `observability.py`, `/metrics`, request middleware, Helm scrape annotations, and sanitization tests. | **Real local.** Metrics are process-local; no external exporter or distributed tracing. |
| Durable audit export | Transactional `audit_events` plus tenant-scoped cursor endpoint and restart tests. | **Real local.** Application append-only; no hash chain, retention engine, immutable archive, or SIEM export. |
| Browser-safe frontend session | `runtime_sessions`, `/api/v1/sessions*`, `runtimeApi.ts`, `WorkspaceRuntime.tsx` y pruebas de sesión/modal/storage. | **Real local and packaged.** HttpOnly/SameSite/CSRF/rotation/revocation, progressive disclosure y revalidación de clave activa; no SSO/MFA. |
| Reproducible Python graph | Three `.in` files, three hash locks, locked pip-tools/build toolchain, wheel verification scripts, Docker and CI. | **Verified across Python 3.11 lock generation, Python 3.13 CI verification and Python 3.13.14 Alpine image runtime.** |
| Supply-chain evidence and policy | Digest-pinned bases, SHA-pinned Actions, Syft SBOM, Grype policy, license policy, in-toto provenance, Cosign verification and CI retention. | **Verified locally without publication.** 0 Critical; 5 exact High exceptions expire 21 August 2026. Production registry/KMS or keyless signing remains open. |
| Local Terraform/Kubernetes validation | Checksum-pinned Terraform/kubectl/K3s, `verify-local-infrastructure.sh`, agentless K3s API, Terraform apply/destroy, Helm server dry-run. | **Real API/admission validation.** Pod scheduling is not claimed because host cgroups are read-only; executable image is verified separately. |

Current operational evidence is maintained in [`program/current-state.md`](../program/current-state.md) and [`program/evidence-register.jsonl`](../program/evidence-register.jsonl). At baseline commit `b9e88fe91dd6db7894dcf5825ca63c2294f52377`, local Oxlint, 33 frontend tests and the Vite production build passed; draft PR #3 reported all eight repository jobs successful on the same SHA. Those jobs cover the locked wheel/backend suite, PostgreSQL shared-state and migration verification, container, Helm, Terraform and supply-chain gates. This is exact-commit local/CI evidence, not staging, GCP, pod-scheduling, alert, backup/restore or production-runtime evidence.
