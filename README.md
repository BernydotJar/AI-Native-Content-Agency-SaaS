# Native / War Room

Webapp cinematográfica y sandbox local para representar una agencia de contenido AI-native de ocho agentes. El repositorio ya no es sólo una maqueta de frontend: contiene una experiencia React/TypeScript ejecutable, un runtime Python determinista con memoria SQLite y un corpus local de instrucciones, conocimiento y skills.

> Estado actual: vertical slice full-stack verificable y empaquetado de producción. La UI incluye una consola que consume el backend durable mediante cookie HttpOnly + CSRF; el simulador cinematográfico original permanece como sandbox separado. Ningún adaptador contacta servicios externos, publica contenido, renderiza media ni gasta presupuesto.

## Qué funciona hoy

- War Room responsive con estética obsidian/slate, partículas, glow cards, motion y transición circular de acento.
- Topología Fabric-style con sensor de entrada y ocho estaciones: CEO, Research, Strategist, Growth, Writer, Media, Risk y Publisher.
- Tres misiones de UI: video a paquete de entrega, imagen a manifiesto de motion y tesis a campaña orgánica + paid sandbox.
- Runtime TypeScript puro y determinista para mezclar señales mock de X, Facebook, TikTok e Instagram, aplicar skills y empaquetar artefactos de campaña sandbox.
- Inspector accesible por agente, outputs, progreso y Greenlight manual.
- Runtime Python de ocho agentes con artefactos, evidencia, traza, memoria tenant-scoped, persistencia durable de runs/Greenlights y un límite duro entre Risk y Publisher.
- FastAPI con bearer auth para máquinas y sesiones HttpOnly + CSRF para navegador, `/readyz`, aislamiento cross-tenant y restauración de ejecuciones después de reiniciar el servicio.
- Consola React de producción para ejecutar briefs, inspeccionar Scholar/artefactos, decidir Greenlight y consultar auditoría durable.
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

La nueva consola de producción consume estado y artefactos de FastAPI. La state machine cinematográfica original sigue ejecutándose de forma independiente hasta demostrar paridad completa antes de retirarla. Los archivos de `agents/`, `knowledge/` y `skills/` son fuentes locales auditables; el orquestador Python todavía no los carga automáticamente. Los roles y fixtures del backend están codificados y versionados en `backend/agency_runtime/`.

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
- wheel reproducible con `build`, `setuptools`, `wheel` y `pip-tools` fijados por hash
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

Pruebas reproducibles del backend:

```bash
./scripts/check-python-locks.sh
./scripts/verify-python-locks.sh
```

El primer comando confirma que los tres lockfiles se regeneran byte por byte. El segundo crea entornos limpios, construye el wheel, instala únicamente artefactos fijados por hash, ejecuta `pip check` y corre las pruebas.

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
python3 -m venv /tmp/agency-build
/tmp/agency-build/bin/python -m pip install --require-hashes   -r backend/requirements-build.lock
/tmp/agency-build/bin/python -m build --no-isolation --wheel   --outdir /tmp/agency-wheels backend

python3 -m venv /tmp/agency-runtime
/tmp/agency-runtime/bin/python -m pip install --require-hashes   -r backend/requirements.lock
/tmp/agency-runtime/bin/python -m pip install --no-deps /tmp/agency-wheels/*.whl
export AGENCY_MEMORY_DB=/tmp/agency-runtime.sqlite3
export AGENCY_TENANT_API_KEYS_JSON='{"local-tenant":"replace-with-a-strong-local-key"}'
export AGENCY_SESSION_COOKIE_SECURE=false  # sólo para HTTP local
/tmp/agency-runtime/bin/agency-api
```

No uses una instalación editable como sustituto del gate reproducible. `./scripts/verify-python-locks.sh` automatiza el build, `pip check` y las pruebas en entornos efímeros.

Endpoints iniciales:

- `GET /healthz`
- `GET /readyz`
- `GET /metrics`
- `POST /api/v1/sessions`
- `GET /api/v1/sessions/current`
- `DELETE /api/v1/sessions/current`
- `GET /api/v1/me`
- `GET /api/v1/audit-events`
- `POST /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `POST /api/v1/runs/{run_id}/greenlight/approve`
- `POST /api/v1/runs/{run_id}/greenlight/reject`

Los clientes máquina pueden usar `Authorization: Bearer <key>`. El navegador intercambia la key una sola vez en `/api/v1/sessions`, recibe una cookie HttpOnly/SameSite=Strict y usa un CSRF rotatorio mantenido sólo en memoria. El tenant se deriva de la credencial o sesión configurada por el servidor; nunca de un header o campo elegido por el cliente.

El dossier de Research incluye Scholar con `Reencuadre Cognitivo`, `Tensión del Trade-off` y `Resolución Operativa`. El Greenlight conserva los IDs y hashes exactos de los siete artefactos revisados, además de canales y presupuesto autorizados. Publisher sólo crea un manifiesto sandbox y mantiene `publication_performed=false`.

El servicio persiste runs, trazas, evidencia, artefactos y Greenlights en SQLite por `(tenant_id, run_id)`, y también particiona la memoria por tenant. Esta etapa usa una sola réplica con PVC y estrategia `Recreate`; PostgreSQL, identidad individual y RBAC siguen siendo requisitos para escalamiento horizontal o un piloto público.

## Consola de producción

`ProductionRuntimePanel` usa `src/lib/runtimeApi.ts` contra el mismo origen. La API key no entra al bundle ni se escribe en `localStorage`/`sessionStorage`; se limpia del formulario después del intercambio. Una recarga recupera la sesión HttpOnly y rota el CSRF mediante `/api/v1/sessions/current`.

La consola permite ejecutar el flujo real, mostrar Scholar, revisar IDs de artefactos, aprobar/rechazar y consultar el ledger. Sigue siendo sandbox respecto de research, media, ads y publicación externa. Consulta [ADR 0003](docs/adr/0003-browser-session-boundary.md).

## Observabilidad y auditoría

Cada respuesta incluye `X-Request-ID`. Los logs de aplicación son JSON y registran route templates, no query strings, headers ni cuerpos. `/metrics` expone contadores Prometheus sin labels de tenant, run o contenido. Las mutaciones `run.created` y `greenlight.*` se guardan en un ledger tenant-scoped dentro de la misma transacción SQLite que modifica el run.

Consulta [Runtime Operations](docs/OPERATIONS.md) para el contrato de logs, métricas, paginación de auditoría y alertas iniciales; y [ADR 0002](docs/adr/0002-observability-and-audit-ledger.md) para las decisiones y limitaciones.

## Dependencias Python reproducibles

Los grafos de runtime, test y build se declaran en `backend/requirements*.in` y se resuelven en lockfiles con versiones y hashes exactos. Docker, CI y verificación local construyen el mismo wheel, instalan locks con `--require-hashes`, instalan la aplicación con `--no-deps` y ejecutan `pip check`.

```bash
./scripts/check-python-locks.sh
./scripts/verify-python-locks.sh
```

Las actualizaciones se realizan únicamente mediante `./scripts/update-python-locks.sh`. Consulta [Python Dependency Locking](docs/DEPENDENCY_LOCKING.md) y [ADR 0004](docs/adr/0004-reproducible-python-dependency-graph.md).

## Verificación del paquete de producción

Helm y la imagen completa pueden validarse localmente con un único comando. El script acepta Docker o Buildah; en workstations con overlay anidado se recomienda Buildah con `vfs` y aislamiento `chroot`:

```bash
CONTAINER_BUILDER=buildah \
HELM_BIN=/home/agent/.local/bin/helm \
./scripts/verify-production-package.sh
```

La verificación lint/renderiza Helm, construye el wheel y la imagen multi-stage con locks hash-verified, inicia el artefacto como usuario no root y prueba health, readiness, SPA, sesión HttpOnly, CSRF, API, artefactos, Greenlight, auditoría, métricas y revocación. Consulta [Environment and Dependency Remediation](docs/ENVIRONMENT_REMEDIATION.md) para versiones, fuentes, fallos evaluados y reversión.
