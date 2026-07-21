# Native / War Room

Webapp cinematográfica y sandbox local para representar una agencia de contenido AI-native de ocho agentes. El repositorio ya no es sólo una maqueta de frontend: contiene una experiencia React/TypeScript ejecutable, un runtime Python determinista con memoria SQLite y un corpus local de instrucciones, conocimiento y skills.

> Estado actual: vertical slice backend verificable y empaquetado de producción con autenticación tenant-scoped y persistencia SQLite durable. La UI cinematográfica todavía ejecuta su simulación en el navegador y no consume la API. Ningún adaptador contacta servicios externos, publica contenido, renderiza media ni gasta presupuesto.

## Qué funciona hoy

- War Room responsive con estética obsidian/slate, partículas, glow cards, motion y transición circular de acento.
- Topología Fabric-style con sensor de entrada y ocho estaciones: CEO, Research, Strategist, Growth, Writer, Media, Risk y Publisher.
- Tres misiones de UI: video a paquete de entrega, imagen a manifiesto de motion y tesis a campaña orgánica + paid sandbox.
- Runtime TypeScript puro y determinista para mezclar señales mock de X, Facebook, TikTok e Instagram, aplicar skills y empaquetar artefactos de campaña sandbox.
- Inspector accesible por agente, outputs, progreso y Greenlight manual.
- Runtime Python de ocho agentes con artefactos, evidencia, traza, memoria tenant-scoped, persistencia durable de runs/Greenlights y un límite duro entre Risk y Publisher.
- FastAPI con bearer auth por tenant, `/readyz`, aislamiento cross-tenant y restauración de ejecuciones después de reiniciar el servicio.
- `DynamicSkillCreator` para crear borradores Markdown locales dentro de una raíz explícita, con validación de slug, protección contra traversal/symlinks y overwrite opt-in.
- Biblioteca local con instrucciones por agente, base de conocimiento y skills editoriales/de plataforma.
- Pruebas de interacción frontend y pruebas unitarias del runtime, memoria, fachada y creador de skills.

## Arquitectura real

```text
React 19 + TypeScript + Vite
├── UI cinematográfica y accesible
├── state machine de misiones en App.tsx
├── contratos/fixtures puros en src/lib/simulationRuntime.ts
└── sin fetch, WebSocket ni llamada al backend

agency.py + FastAPI
└── backend/agency_runtime
    ├── orquestador secuencial de ocho agentes
    ├── Greenlight ligado a IDs y hashes de artefactos
    ├── bearer auth con identidad tenant derivada del servidor
    ├── SQLite durable: runs, approvals y memoria por tenant
    ├── adaptadores deterministas sandbox
    └── creador seguro de borradores de skill

Contenido operativo local
├── agents/*/instructions.md
├── knowledge/*.md
└── skills/*.md
```

La UI y Python modelan el mismo concepto, pero la UI todavía no consume el estado ni los artefactos de la API en tiempo de ejecución. Los archivos de `agents/`, `knowledge/` y `skills/` son fuentes locales auditables; el orquestador Python todavía no los carga automáticamente. Los roles y fixtures del backend están codificados y versionados en `backend/agency_runtime/`.

Consulta [docs/IMPLEMENTATION_AUDIT.md](docs/IMPLEMENTATION_AUDIT.md) para la matriz requisito → evidencia → estado y las desviaciones deliberadas respecto de la propuesta inicial.

## Stack

### Web

- React 19 + TypeScript
- Vite 8
- Tailwind CSS 4 mediante `@tailwindcss/vite`
- Lucide React
- Manrope Variable + JetBrains Mono Variable autoalojadas
- Vitest + Testing Library + jsdom

### Runtime local

- Python 3.10 o superior
- Biblioteca estándar para orquestación, modelos y SQLite
- FastAPI, Pydantic y Uvicorn para el servicio HTTP
- `setuptools` para empaquetado
- Sin dependencia de `agency_swarm` ni de un framework externo de agentes

Durante la implementación se consultó Context7 mediante su CLI para contrastar la integración oficial de Tailwind CSS 4 con Vite y la configuración vigente de Vitest 4. Esa consulta fue tooling de desarrollo; `Context7DocsTool` dentro del producto sigue siendo un adapter mock y no hace solicitudes remotas.

## Inicio local de la webapp

Requiere una versión moderna de Node.js compatible con Vite 8.

```bash
npm install
npm run dev
```

Vite mostrará la URL disponible, normalmente `http://localhost:5173`.

Comandos web:

```bash
npm run dev       # servidor de desarrollo
npm run build     # TypeScript + bundle de producción
npm run lint      # análisis estático con Oxlint
npm test          # pruebas de interacción y runtime TS
npm run preview   # previsualizar dist/
```

## Ejecutar el sandbox Python

La fachada `agency.py` añade `backend/` al path local y no requiere instalación editable para la demo.

```bash
python3 agency.py demo
python3 agency.py demo --approve --json
python3 agency.py demo --reject
```

Sin una decisión, el flujo termina en `awaiting_greenlight` y Publisher permanece en `waiting_greenlight`. `--approve` crea sólo un manifiesto sandbox en memoria; `--reject` bloquea Publisher. Para verificar persistencia SQLite local se puede suministrar una ruta explícita:

```bash
python3 agency.py demo --db /tmp/native-agency-memory.sqlite3 --json
```

Pruebas del backend:

```bash
cd backend
python3 -m unittest discover -s tests -v
```

## Agentes, conocimiento y skills

La secuencia canónica es:

1. CEO define objetivo, audiencia y restricciones.
2. Research produce evidencia sintética con procedencia.
3. Strategist convierte el contexto en decisiones de canal.
4. Growth proyecta un envelope de adquisición sandbox.
5. Writer prepara el copy deck.
6. Media prepara planes de video e imagen; no renderiza archivos.
7. Risk valida el paquete y habilita la decisión humana.
8. Publisher sólo empaqueta después del Greenlight.

El contrato operativo y sus límites están en [agency_manifesto.md](agency_manifesto.md). Las instrucciones por rol viven en `agents/`; el conocimiento trazable en `knowledge/`; y los playbooks editoriales y de plataforma en `skills/`.

`DynamicSkillCreator` está implementado y probado como utilidad Python local. Puede escribir un `.md` validado dentro de una raíz elegida por el llamador, pero todavía no tiene comando CLI, pantalla web ni integración automática con el orquestador.

## Greenlight

Hay dos gates locales, no conectados entre sí:

- En la web, las tareas de Publisher quedan diferidas después de Risk hasta que una persona activa Greenlight. Revocarlo durante la ejecución cancela timers pendientes y marca Publisher para atención.
- En Python, `AgencyOrchestrator.start()` se detiene antes de Publisher. `approve()` registra revisor, nota y decisión y permite crear un manifiesto sandbox; `reject()` mantiene el empaquetador sin invocar.

En ninguno de los dos casos Greenlight equivale a publicar, comprar medios ni autorizar una API externa.

## Límites de integración

Las siguientes capacidades son contratos mock o representaciones visuales, no conexiones activas:

- Meta Ads MCP y gasto publicitario;
- APIs de X, LinkedIn, Facebook, TikTok, Instagram o cualquier publisher;
- navegador/Puppeteer, GitHub y Context7 durante el runtime de producto;
- generación, edición o lectura real de video e imagen;
- transporte frontend→FastAPI y streaming SSE/WebSocket;
- identidad de usuario final, RBAC y proveedor externo de autenticación;
- PostgreSQL, almacenamiento de objetos y sincronización cloud;
- ingestión automática de `agents/`, `knowledge/` y `skills/` por el orquestador.

Antes de activar servicios externos deben añadirse contratos versionados, autenticación, idempotencia, reintentos acotados, auditoría, revocación y un gate de aprobación ligado a la versión exacta de los artefactos.

## Verificación

Gate ejecutado el 17 de julio de 2026 en el entorno local del repositorio:

```bash
rtk test npm run lint
rtk test npm test
rtk test npm run build

cd backend
python3 -m unittest discover -s tests -v
cd ..
python3 agency.py demo --approve --json
```

La demo JSON reporta de forma explícita cero llamadas de red, navegaciones, cambios en GitHub, renders, publicaciones y gasto publicitario. El browser integrado no expuso una instancia durante este cierre, por lo que la QA visual interactiva quedó pendiente.

## API de ejecución

El mismo runtime Python ya está disponible mediante FastAPI. La imagen de producción sirve la SPA y la API en el puerto `8080`:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e . httpx
export AGENCY_MEMORY_DB=/tmp/agency-runtime.sqlite3
export AGENCY_TENANT_API_KEYS_JSON='{"local-tenant":"replace-with-a-strong-local-key"}'
.venv/bin/agency-api
```

Endpoints iniciales:

- `GET /healthz`
- `GET /readyz`
- `GET /metrics`
- `GET /api/v1/me`
- `GET /api/v1/audit-events`
- `POST /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `POST /api/v1/runs/{run_id}/greenlight/approve`
- `POST /api/v1/runs/{run_id}/greenlight/reject`

Todos los endpoints `/api/v1/*` requieren `Authorization: Bearer <key>`. El tenant se deriva de la credencial configurada en el servidor; nunca de un header o campo elegido por el cliente.

El dossier de Research incluye Scholar con `Reencuadre Cognitivo`, `Tensión del Trade-off` y `Resolución Operativa`. El Greenlight conserva los IDs y hashes exactos de los siete artefactos revisados, además de canales y presupuesto autorizados. Publisher sólo crea un manifiesto sandbox y mantiene `publication_performed=false`.

El servicio persiste runs, trazas, evidencia, artefactos y Greenlights en SQLite por `(tenant_id, run_id)`, y también particiona la memoria por tenant. Esta etapa usa una sola réplica con PVC y estrategia `Recreate`; PostgreSQL, identidad individual y RBAC siguen siendo requisitos para escalamiento horizontal o un piloto público.

## Observabilidad y auditoría

Cada respuesta incluye `X-Request-ID`. Los logs de aplicación son JSON y registran route templates, no query strings, headers ni cuerpos. `/metrics` expone contadores Prometheus sin labels de tenant, run o contenido. Las mutaciones `run.created` y `greenlight.*` se guardan en un ledger tenant-scoped dentro de la misma transacción SQLite que modifica el run.

Consulta [Runtime Operations](docs/OPERATIONS.md) para el contrato de logs, métricas, paginación de auditoría y alertas iniciales; y [ADR 0002](docs/adr/0002-observability-and-audit-ledger.md) para las decisiones y limitaciones.

## Verificación del paquete de producción

Helm y la imagen completa pueden validarse localmente con un único comando. El script acepta Docker o Buildah; en workstations con overlay anidado se recomienda Buildah con `vfs` y aislamiento `chroot`:

```bash
CONTAINER_BUILDER=buildah \
HELM_BIN=/home/agent/.local/bin/helm \
./scripts/verify-production-package.sh
```

La verificación lint/renderiza Helm, construye la imagen multi-stage, inicia el artefacto como usuario no root y prueba health, readiness, bearer auth, SPA, API, siete artefactos y el gate de Publisher. Consulta [Environment and Dependency Remediation](docs/ENVIRONMENT_REMEDIATION.md) para versiones, fuentes, fallos evaluados y reversión.
