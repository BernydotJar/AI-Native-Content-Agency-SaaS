# Native / War Room

Aplicación full-stack y sandbox gobernado para operar una agencia de contenido AI-native de ocho agentes. El repositorio combina una experiencia React/TypeScript, una consola conectada a FastAPI, persistencia SQLite/PostgreSQL y un corpus local de instrucciones, conocimiento y skills.

> Estado actual: candidato sandbox full-stack `0.7.0`, verificable localmente y empaquetado como imagen OCI/Helm. La consola consume el backend durable mediante cookie HttpOnly + CSRF; la imagen usa bases fijadas por digest y produce SBOM, reporte de vulnerabilidades, provenance y firmas verificables. El simulador cinematográfico original permanece separado. No existe evidencia de deployment GCP/staging/producción. Sólo los endpoints OAuth iniciados explícitamente por un admin pueden contactar X/Meta. La publicación social está deshabilitada por defecto; sólo puede ejecutarse con flag server-side, cuenta conectada, Greenlight exacto e intent durable. El render de media y el gasto externo siguen deshabilitados. No representa aprobación legal, de privacidad ni regulatoria. El estado operacional vigente está en [`program/current-state.md`](program/current-state.md).

## Qué funciona hoy

- Espacio de trabajo React orientado a una misión gobernada: crear o abrir una ejecución, inspeccionar evidencia y artefactos, y decidir Greenlight según RBAC.
- Topología Fabric-style con sensor de entrada y ocho estaciones: CEO, Research, Strategist, Growth, Writer, Media, Risk y Publisher.
- Tema visual movido a `Configuración`; no compite con el brief ni cambia permisos, recomendaciones o autoridad política.
- Credencial de tenant solicitada una sola vez dentro de un diálogo seguro; después el navegador opera con cookie HttpOnly + CSRF y elimina el campo de la experiencia principal.
- Resultado editorial por canal con copy visible, asset, Greenlight, cuenta y publicación; Instagram muestra explícitamente el caption y el media asset pendiente.
- Configuración administrativa que deriva del servidor el estado de OpenAI, Anthropic, DeepSeek, Moonshot/Kimi, Llama, X, Instagram e integraciones revisadas, sin devolver valores secretos.
- Runtime Python de ocho agentes con artefactos, evidencia, traza, memoria tenant-scoped, persistencia durable de runs/Greenlights y un límite duro entre Risk y Publisher.
- FastAPI con identidad individual, RBAC (`viewer`, `operator`, `approver`, `admin`), bearer auth para máquinas, sesiones HttpOnly + CSRF para navegador, rate limiting durable y aislamiento cross-tenant.
- Registro autenticado y sólo lectura de candidatos de integración revisados; `video-use` está pinneado como `reviewed_disabled` y no tiene ruta de ejecución.
- Catálogo de proveedores server-side sin exponer credenciales, con estados fail-closed `ready`, `missing_credential`, `missing_model` y `missing_endpoint`.
- Pruebas de interacción, contratos de modal/foco, Chromium real a 320 CSS px, wheel hash-locked, SQLite/PostgreSQL, imagen OCI y supply chain.

## Arquitectura real

```text
React 19 + TypeScript + Vite
├── App.tsx: shell de producto y estado compartido del workspace
├── WorkspaceRuntime: sesión, brief, run y Greenlight
├── PipelineGraph: topología de ocho estaciones derivada del run
├── CampaignOutputPanel: posts, media, aprobación, cuenta y publicación por canal
├── StationInspector: estado y artefactos de la estación seleccionada
└── WorkspaceSettingsDialog: temas, providers, X, Instagram e integraciones revisadas

FastAPI + agency_runtime
├── identidad individual, RBAC, sesión HttpOnly y CSRF
├── SQLite para local/single-replica y PostgreSQL para estado compartido
├── orquestador secuencial de ocho agentes
├── Greenlight ligado a IDs/hashes de artefactos y fencing token
├── registro server-side de cinco proveedores de modelos
├── OAuth tenant-scoped de X/Instagram con tokens cifrados e integraciones revisadas
└── auditoría, métricas, backup/restore e idempotencia durable
```

La shell principal ya no contiene la state machine cinematográfica ni tarjetas de memoria/tooling mock. La ejecución actual sigue usando herramientas deterministas internas para research, ads, browser y media. `INC-014` implementa clientes protocolares acotados para cinco proveedores, pero el gateway permanece deshabilitado y sin ruta pública: todavía falta un intent/receipt outbound durable que impida gasto duplicado antes de conectarlo a los runs. Configuración o protocol-readiness no autorizan inferencia, gasto ni egress.

Los archivos de `agents/`, `knowledge/` y `skills/` son fuentes locales auditables. El orquestador todavía no los carga automáticamente como autoridad dinámica.

Consulta [docs/IMPLEMENTATION_AUDIT.md](docs/IMPLEMENTATION_AUDIT.md) para la matriz requisito → evidencia → estado y las desviaciones deliberadas respecto de la propuesta inicial. La evaluación exacta de `browser-use/video-use`, sus hallazgos y la lista de activación están en [docs/integrations/video-use-review.md](docs/integrations/video-use-review.md).

## Stack

### Web

- React 19 + TypeScript
- Vite 8
- Tailwind CSS 4 mediante `@tailwindcss/vite`
- Lucide React
- Manrope Variable + JetBrains Mono Variable autoalojadas
- Vitest + Testing Library + jsdom

### Runtime local

- Python 3.11 a 3.13
- Biblioteca estándar para orquestación, modelos y SQLite
- FastAPI, Pydantic y Uvicorn para el servicio HTTP
- wheel reproducible con `build`, `setuptools`, `wheel` y `pip-tools` fijados por hash
- Sin dependencia de `agency_swarm` ni de un framework externo de agentes

Durante la implementación se consultó Context7 mediante su CLI para contrastar la integración oficial de Tailwind CSS 4 con Vite y la configuración vigente de Vitest 4. Esa consulta fue tooling de desarrollo; `Context7DocsTool` dentro del producto sigue siendo un adapter mock y no hace solicitudes remotas.

## Inicio local del producto

Requiere Node.js compatible con Vite 8 y Python 3.11 a 3.13. El launcher selecciona automáticamente un intérprete soportado entre `python3`, `python3.13`, `python3.12` y `python3.11`; también puede fijarse con `AGENCY_PYTHON_BIN`.

La ruta recomendada construye el bundle, crea entornos Python efímeros con locks/hash, instala el wheel y sirve SPA + FastAPI en el mismo origen:

```bash
npm ci
npm run start:local
```

El comando escucha únicamente en `127.0.0.1:4175`, usa SQLite persistente en `.local/ai-native-content-agency-local.sqlite3` y, cuando no se proporciona `AGENCY_IDENTITY_CREDENTIALS_JSON`, imprime una identidad y credencial locales efímeras una sola vez. Úsalas desde **Iniciar sesión**. No se escriben en el repositorio ni en storage del navegador.

El runner intenta primero `requirements-build.lock`. Si el índice Python configurado todavía no contiene una versión reciente del frontend `build`, recrea el entorno y usa `requirements-local-build.lock`, un toolchain mínimo, conservador y también fijado por hashes. El runtime y el wheel de la aplicación no cambian.

`npm run preview` sirve sólo `dist/` mediante Vite. Es útil para revisión visual, pero no expone sesiones, runs, proveedores ni persistencia FastAPI y no debe usarse como evidencia del producto full-stack.

Comandos web:

```bash
npm run dev                  # frontend aislado para desarrollo
npm run build                # TypeScript + bundle de producción
npm run lint                 # análisis estático con Oxlint
npm test                     # pruebas de interacción y contratos TS
npm run preview              # inspección visual estática de dist/
npm run start:local          # producto local integrado SPA + FastAPI + SQLite
npm run verify:accessibility-browser
npm run verify:social-browser  # FastAPI + run X/Instagram + Chromium; cero egress externo
```

La configuración server-side de X/Instagram y los callbacks esperados están en
[`docs/runbooks/social-channel-readiness.md`](docs/runbooks/social-channel-readiness.md).
Definir las app keys y la clave de cifrado cambia el estado a **Lista para autenticar**. Un
admin puede completar OAuth y ver la cuenta conectada; esto todavía no habilita publicación.

Para una identidad local estable, define `AGENCY_IDENTITY_CREDENTIALS_JSON` antes de ejecutar `npm run start:local`. El runner rechaza hosts no loopback y no activa proveedores externos.

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
- publicación real de X, Instagram, LinkedIn, Facebook o TikTok; X/Instagram ya tienen OAuth y tokens cifrados, pero no existe todavía una ruta de publicación;
- navegador/Puppeteer, GitHub y Context7 durante el runtime de producto;
- generación, edición o lectura real de video e imagen;
- streaming SSE/WebSocket;
- proveedor administrado de identidad, SSO y MFA;
- almacenamiento de objetos, sincronización cloud y deployment administrado;
- ingestión automática de `agents/`, `knowledge/` y `skills/` por el orquestador.

Antes de activar servicios externos deben añadirse contratos versionados, autenticación, idempotencia, reintentos acotados, auditoría, revocación y un gate de aprobación ligado a la versión exacta de los artefactos.

## Verificación

Gate ejecutado el 17 de julio de 2026 en el entorno local del repositorio:

```bash
python3 scripts/validate-program-state.py
npm run validate:compliance
npm run validate:operability
npm run lint
npm test
npm run build
./scripts/verify-python-locks.sh
python3 agency.py demo --approve --json
```

`validate:compliance` cruza locks, licencias directas, digests, Actions, el
candidato `video-use`, decisiones de privacidad, claims públicos y blockers. El
resultado esperado sigue siendo `DENY_RELEASE`; un PASS demuestra consistencia
del gate, no aprobación legal o autorización de release. Consulta
[`docs/compliance/release-compliance-review.md`](docs/compliance/release-compliance-review.md)
y el [inventario de terceros](docs/compliance/third-party-notices.md).

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
export AGENCY_IDENTITY_CREDENTIALS_JSON='[
  {"tenant_id":"local-tenant","subject_id":"operator-1","role":"admin","key_id":"operator-1-v1","api_key":"replace-with-a-strong-local-key","active":true}
]'
export AGENCY_LOGIN_MAX_FAILURES=5
export AGENCY_LOGIN_SOURCE_MAX_FAILURES=50
export AGENCY_LOGIN_WINDOW_SECONDS=300
export FORWARDED_ALLOW_IPS=127.0.0.1
export AGENCY_SESSION_COOKIE_SECURE=false  # sólo para HTTP local
/tmp/agency-runtime/bin/agency-api
```

No uses una instalación editable como sustituto del gate reproducible. `./scripts/verify-python-locks.sh` automatiza el build, `pip check` y las pruebas en entornos efímeros.

Para rotar una credencial, publica una nueva entrada activa con otro `key_id`, actualiza los clientes y luego marca la anterior `active=false`. El siguiente reinicio/redeploy rechaza tanto la bearer key anterior como las sesiones creadas con ella. Configura `FORWARDED_ALLOW_IPS` únicamente con proxies conocidos; nunca confíes en `*` si el edge no elimina headers reenviados del cliente.

Endpoints iniciales:

- `GET /healthz`
- `GET /readyz`
- `GET /metrics`
- `POST /api/v1/sessions`
- `GET /api/v1/sessions/current`
- `DELETE /api/v1/sessions/current`
- `GET /api/v1/me`
- `GET /api/v1/providers`
- `GET /api/v1/integrations`
- `GET /api/v1/integrations/{integration_id}`
- `GET /api/v1/social-channels`
- `GET /api/v1/social-channels/{channel_id}`
- `POST /api/v1/social-channels/{channel_id}/oauth/start`
- `GET /api/v1/social-channels/x/oauth/callback`
- `GET /api/v1/social-channels/instagram/oauth/callback`
- `DELETE /api/v1/social-channels/{channel_id}/connection`
- `GET /api/v1/audit-events`
- `POST /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `POST /api/v1/runs/{run_id}/greenlight/approve`
- `POST /api/v1/runs/{run_id}/greenlight/reject`
- `POST /api/v1/runs/{run_id}/greenlight/revoke`

Los clientes máquina pueden usar `Authorization: Bearer <key>`. El navegador intercambia la key una sola vez en `/api/v1/sessions`, recibe una cookie HttpOnly/SameSite=Lax —necesaria para callbacks OAuth GET de nivel superior— y usa un CSRF rotatorio mantenido sólo en memoria. El tenant, sujeto, rol, `key_id` y cualquier entitlement allowlisted se derivan de la credencial o sesión configurada por el servidor; nunca de un header o campo elegido por el cliente. `viewer` puede leer runs/auditoría, `operator` también crea runs, `approver` decide o revoca Greenlight y `admin` reúne ambos permisos. La configuración legacy `AGENCY_TENANT_API_KEYS_JSON` sigue disponible sólo para migración y puede desactivarse en Helm.

El dossier de Research incluye Scholar con `Reencuadre Cognitivo`, `Tensión del Trade-off` y `Resolución Operativa`. Las mutaciones de runs y Greenlight requieren `Idempotency-Key`: un retry compatible devuelve el documento original, mientras que una reutilización incompatible falla con un 409 uniforme sin guardar la key cruda. El Greenlight conserva IDs/hashes exactos, canales, presupuesto y un fencing token; puede revocarse sin borrar evidencia, invalidando tokens anteriores. Publisher sólo crea un manifiesto sandbox y mantiene `publication_performed=false`.

El servicio persiste runs, trazas, evidencia, artefactos, Greenlights, sesiones y contadores de abuso en SQLite o PostgreSQL, siempre bajo claves tenant-scoped. Las credenciales, cookies y CSRF nunca se persisten en claro. La rotación admite claves superpuestas por sujeto y revoca bearer/sesiones derivados cuando una clave deja de estar activa. SQLite queda limitado a local/single-replica. PostgreSQL soporta estado compartido; el schema se inicializa con un comando operador separado y los pods sólo validan con un rol runtime no propietario. El repositorio ya incluye drills efímeros de backup/restore, pero todavía faltan backup productivo programado/cifrado/inmutable, failover, capacidad medida, un IdP administrado, SSO/MFA y almacenamiento de objetos antes de un piloto público.

## Espacio de trabajo de producto

`WorkspaceRuntime` usa `src/lib/runtimeApi.ts` contra el mismo origen. La credencial de tenant no entra al bundle ni se escribe en `localStorage`/`sessionStorage`; sólo existe dentro del diálogo de conexión y se limpia después del intercambio. Una recarga recupera la sesión HttpOnly y rota el CSRF mediante `/api/v1/sessions/current`.

La experiencia permite crear o abrir una ejecución, inspeccionar los posts finales por canal, ver el media requirement de Instagram, aprobar/rechazar/revocar Greenlight y consultar auditoría. X e Instagram muestran Copy → Asset → Greenlight → Cuenta → Publicación. Un admin puede iniciar OAuth, volver con la misma sesión, ver metadata de la cuenta y desconectarla; tokens y secretos permanecen cifrados server-side. No existe ruta de publicación: research, media, ads y efectos de publicación siguen sin egress hasta que exista un adapter con intent/receipt durable. Consulta [ADR 0003](docs/adr/0003-browser-session-boundary.md) y el [runbook social](docs/runbooks/social-channel-readiness.md).

Los temas accesibles azul, rojo, verde y naranja viven en **Configuración**. El tema premium sólo se activa cuando la identidad activa entrega el entitlement exacto `theme:premium`; falla cerrado, se revoca al refrescar identidad y no usa storage persistente. Esto no implementa checkout, facturación ni DRM. Consulta [Accessible campaign themes](docs/design-system/accessibility-themes.md).

## Observabilidad y auditoría

Cada respuesta incluye `X-Request-ID`. Los logs de aplicación son JSON y registran route templates, no query strings, headers ni cuerpos. `/metrics` expone contadores Prometheus sin labels de tenant, run o contenido. Las mutaciones `run.created` y `greenlight.*` se guardan en un ledger tenant-scoped dentro de la misma transacción SQLite que modifica el run.

Consulta [Runtime Operations](docs/OPERATIONS.md) para el contrato de logs, métricas, paginación de auditoría y alertas iniciales; [Runtime Backup and Restore](docs/runbooks/runtime-backup-restore.md) para los drills SQLite/PostgreSQL y sus gates humanos; y [ADR 0002](docs/adr/0002-observability-and-audit-ledger.md) para las decisiones y limitaciones.

## Dependencias Python reproducibles

Los grafos de runtime, test y build se declaran en `backend/requirements*.in` y se resuelven en lockfiles con versiones y hashes exactos. Docker, CI y verificación local construyen el mismo wheel, instalan locks con `--require-hashes`, instalan la aplicación con `--no-deps` y ejecutan `pip check`.

```bash
./scripts/check-python-locks.sh
./scripts/verify-python-locks.sh
```

Las actualizaciones se realizan únicamente mediante `./scripts/update-python-locks.sh`. Consulta [Python Dependency Locking](docs/DEPENDENCY_LOCKING.md) y [ADR 0004](docs/adr/0004-reproducible-python-dependency-graph.md).

## Verificación local de infraestructura

Terraform y Kubernetes se validan contra un control plane K3s real y efímero:

```bash
./scripts/install-local-infra-tools.sh
export PATH="$HOME/.local/bin:$PATH"
./scripts/verify-local-infrastructure.sh
```

El gate ejecuta Terraform plan/apply/destroy, Helm y `dry-run=server`, mantiene el Secret fuera del state y limpia todo. K3s se ejecuta en modo agentless porque el cgroup heredado de esta workstation es read-only para kubelet; por ello valida API/admission/orquestación, no scheduling de pods. El runtime de la imagen se valida por separado con Buildah. Consulta [Local Infrastructure Validation](docs/LOCAL_INFRASTRUCTURE_VALIDATION.md).

## Verificación del paquete de producción

Helm y la imagen completa pueden validarse localmente con un único comando. El script acepta Docker o Buildah; en workstations con overlay anidado se recomienda Buildah con `vfs` y aislamiento `chroot`:

```bash
CONTAINER_BUILDER=buildah \
HELM_BIN=/home/agent/.local/bin/helm \
./scripts/verify-production-package.sh
```

La verificación lint/renderiza Helm, prueba guards negativos de identidad y rate limiting, construye el wheel y la imagen multi-stage con locks hash-verified, inicia el artefacto como usuario no root y prueba identidad individual, separación RBAC, health, readiness, SPA, sesión HttpOnly, CSRF, API, artefactos, Greenlight, auditoría, métricas y revocación. Consulta [Environment and Dependency Remediation](docs/ENVIRONMENT_REMEDIATION.md) para versiones, fuentes, fallos evaluados y reversión.

## Verificación de supply chain

La imagen usa Node y Python/Alpine fijados por digest. El gate genera SBOM CycloneDX, reporte Grype, política exacta y expirable de vulnerabilidades, validación de licencias Python, provenance in-toto/SLSA y firmas Cosign offline:

```bash
./scripts/install-supply-chain-tools.sh
export PATH="$HOME/.local/bin:$PATH"
CONTAINER_BUILDER=buildah ./scripts/verify-supply-chain.sh
```

El resultado verificado contiene cero hallazgos Critical, cinco High aceptados por coincidencia exacta hasta el 21 de agosto de 2026 y ocho Medium reportados. Cualquier Critical, High nuevo, fix reportado sin excepción explícita, excepción obsoleta o baseline vencida falla. Los artefactos generados se ignoran en Git y CI los retiene durante 30 días; no se publica ninguna imagen. Consulta [Software Supply-Chain Security](docs/SUPPLY_CHAIN_SECURITY.md) y [ADR 0005](docs/adr/0005-supply-chain-evidence-and-policy.md).

## Graph Harness SDLC

Development execution is governed by the canonical Graph Harness SDLC runtime pinned in `vendor/graph-harness-sdlc`. The SaaS keeps its domain-specific specs and task ledgers, then projects them into a typed execution graph with append-only evidence, dependency readiness, production gates and localized repair.

```bash
git submodule update --init --recursive
npm run validate:program
npm run validate:graph
```

`program/graph-harness.project.json` and `program/graph-harness.state.json` are generated projections. `program/graph-harness.events.jsonl` is the persistent execution ledger. A valid application build does not by itself close a feature; the current-revision graph gates must also pass.
