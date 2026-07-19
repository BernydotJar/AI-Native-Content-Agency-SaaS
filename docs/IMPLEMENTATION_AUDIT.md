# Historical Implementation Audit — Baseline

Fecha de corte: 17 de julio de 2026.

> Snapshot histórico, superado por Production Foundation V1 el 18 de julio de 2026. No describe el árbol actual. Consulta [`agent/reports/local-foundation-2026-07-18.md`](../agent/reports/local-foundation-2026-07-18.md), [`agent/current-state.md`](../agent/current-state.md) y la [matriz vigente](../agent/requirements-traceability.csv).

Este documento compara el estado del producto en la fecha de corte con `proposal_and_prompt.md` y con el contrato operativo de `agency_manifesto.md`. La evidencia se refiere al árbol que existía entonces; se conserva para trazabilidad de baseline.

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
| Transporte frontend↔backend | Búsqueda de `fetch`, `WebSocket`, FastAPI y clientes HTTP sin ruta de producto | **No implementado.** Las dos state machines son independientes. |
| Streaming de eventos | No hay servidor FastAPI/SSE/WebSocket | **No implementado.** La animación web usa timers locales. |
| Persistencia de producto multiusuario | SQLite local por ruta explícita | **No implementado.** No hay servicio, tenancy, auth, Postgres ni object storage. |
| Accesibilidad y reduced motion | Skip link y semántica en `src/App.tsx`; controles/tab/progressbar en componentes; media queries en `src/index.css` | **Real local, con cobertura automatizada parcial.** Falta auditoría manual completa con browser/lector de pantalla. |
| Testing y build reproducibles | Tests `src/**/*.test.*`, `backend/tests/`, scripts en [`package.json`](../package.json) | **Real local.** Gates TypeScript, interacción, Python, lint y bundle. |

## Desviaciones intencionales de la propuesta

### Vite/React en lugar de Next.js

La implementación conserva React y TypeScript, pero usa Vite 8. No hay routing de servidor, Server Components, API routes ni SSR. Para el prototipo single-page actual, Vite reduce infraestructura y mantiene el build estático; no satisface un requisito estricto de Next.js si éste fuera contractual.

### SVG/DOM propio en lugar de React Flow

La topología usa botones HTML posicionados y un SVG normalizado para edges. Esto evita otra dependencia y permite una secuencia móvil específica, pero no ofrece edición de grafos, zoom/pan, minimap, handles o el ecosistema de React Flow.

### Dos runtimes en lugar de una arquitectura cliente/servidor

`src/App.tsx` y `src/lib/simulationRuntime.ts` ejecutan la demo en el navegador. `backend/agency_runtime` ejecuta otra representación determinista desde Python. Esta separación permite probar seguridad y contratos sin levantar servicios, pero puede producir divergencia de estado, artefactos y reglas. La convergencia requiere un contrato versionado y transporte real.

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
2. Exponer el runtime mediante FastAPI u otro servicio con auth; elegir SSE/WebSocket sólo para eventos que realmente necesiten streaming.
3. Reemplazar cada fixture por un adapter separado, autenticado, observable e idempotente.
4. Vincular Greenlight a hashes/versiones exactas y hacer revocación efectiva en backend.
5. Añadir tenancy, secrets management, retención, borrado y auditoría.
6. Conectar el frontend a una única fuente de verdad y retirar la state machine duplicada cuando la paridad esté comprobada.
7. Realizar QA visual, responsive, accesible y de fallo antes de cualquier piloto con efectos externos.
