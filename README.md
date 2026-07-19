# Native / Control Room

Control plane durable para una agencia de contenido AI-native de ocho pasos. La experiencia predeterminada integra React con FastAPI y SQL; conserva misiones, corridas, artefactos, evidencia, eventos, auditoría y decisiones Greenlight. Todos los adaptadores de proveedor siguen siendo sandbox: no publican, no renderizan media, no modifican GitHub y no gastan presupuesto.

Estado al 18 de julio de 2026:

- el modo integrado UI → API es el predeterminado;
- SQLite sirve para desarrollo/pruebas aisladas y PostgreSQL 15 para Compose y el diseño cloud;
- el modo cinematográfico con timers existe sólo con `VITE_RUNTIME_MODE=demo`;
- Docker, CI y Terraform describen una base reproducible de desarrollo;
- no se ha ejecutado un `terraform apply`: el descubrimiento encontró cero cuentas de facturación GCP abiertas accesibles;
- autenticación de usuario final, reanudación durable a mitad de paso, staging y producción no están implementados.

## Arquitectura

```text
React 19 / TypeScript / Vite
  └─ JSON HTTP v1 + polling + claves idempotentes estables por comando
       └─ FastAPI
            ├─ identidad de headers sólo para test/desarrollo
            ├─ Greenlight ligado a hash SHA-256 + greenlight.v1
            ├─ orquestador sandbox de ocho pasos
            └─ SQLAlchemy + Alembic
                 ├─ SQLite (local/test)
                 └─ PostgreSQL 15 (Compose / Cloud SQL diseñado)
```

CEO, Research, Strategist, Growth, Writer, Media y Risk producen el manifiesto previo a Publisher. Publisher queda detenido hasta una decisión humana exacta. Aprobar sólo crea un manifiesto sandbox con `publication_performed=false`; rechazar bloquea Publisher.

Consulta [la arquitectura detallada](docs/architecture/production-foundation.md), [el contrato API](docs/api/control-plane-v1.md) y [el modelo de amenazas](docs/security/threat-model.md).

## Prerrequisitos

La ruta de CI y contenedor está fijada a:

- Node.js 24.4.1 y `npm`;
- Python 3.13.5 y `uv` para el toolchain de entrega;
- Docker Desktop/Engine con Compose v2 para la ruta integrada;
- Terraform 1.15.8 sólo para validar infraestructura.

El paquete Python conserva `requires-python >=3.9`; CI y la imagen usan 3.13.5 para que resolución, análisis de tipos y producción compartan intérprete.

## Inicio integrado con Docker Compose

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
curl --fail http://127.0.0.1:8080/healthz
curl --fail http://127.0.0.1:8080/readyz
python3 scripts/http_smoke.py \
  --base-url http://127.0.0.1:8080
```

Abre `http://127.0.0.1:8080`. Compose construye una sola imagen no-root, inicia PostgreSQL 15, ejecuta Alembic una vez y sólo después levanta la SPA/FastAPI.

Para detener sin borrar la base:

```bash
docker compose down
```

`docker compose down --volumes` borra la base local y sólo debe usarse si esa pérdida es intencional. Más detalles en [el runbook local](docs/runbooks/local-development.md).

## Desarrollo desde el código fuente

Instala exactamente los locks:

```bash
npm ci --ignore-scripts --no-audit --no-fund
cd backend
uv sync --frozen
cd ..
```

Terminal 1, API local con SQLite y creación automática de esquema sólo para desarrollo:

```bash
cd backend
uv run agency-control-plane
```

Terminal 2, Vite con proxy hacia `127.0.0.1:8000`:

```bash
npm run dev
```

La URL habitual es `http://localhost:5173`. La UI envía `X-Tenant-ID`, `X-Principal-ID`, `X-Correlation-ID` y `Idempotency-Key`; esos headers no son autenticación de producción.

### Modos de UI

- Integrado, predeterminado: `npm run dev`.
- Demo browser-only explícita: `VITE_RUNTIME_MODE=demo npm run dev`.

El modo integrado conserva en el navegador únicamente el ID opaco de la última corrida. Todo el contenido se vuelve a cargar desde FastAPI. Las respuestas ambiguas reintentan el mismo comando con la misma clave idempotente.

### CLI sandbox heredada

La fachada local sigue disponible y no contacta proveedores:

```bash
python3 agency.py demo
python3 agency.py demo --approve --json
python3 agency.py demo --reject
```

## Puertas de verificación

```bash
npm run lint
npm run typecheck
npm test
npm run build
npm run check:api-contract

cd backend
uv run ruff check .
uv run mypy --config-file pyproject.toml control_plane
uv run pytest tests
uv run python -m control_plane.openapi --output openapi.json --check
cd ..

scripts/validate_platform.sh
```

La última orden valida formato/configuración Terraform, pruebas mock, YAML, políticas estáticas y Compose; no autoriza un plan ni un apply real.

## GCP dev

Terraform define un bootstrap opcional y separa el entorno `dev` en una foundation administrada fuera del flujo rutinario y un estado runtime estrecho. La foundation contiene APIs/IAM, Artifact Registry, Cloud SQL PostgreSQL 15 con connector enforcement e IAM DB auth, canales de alerta y presupuesto. El runtime sólo administra Cloud Run privado, la migración y su invocador. Tres identidades WIF distintas —build, plan de recursos en sólo lectura y apply— exigen owner/repositorio/`main`/workflow/environment exactos. Plan sólo puede leer los estados requeridos y crear/borrar el `.tflock` runtime; apply sólo puede mutar el prefijo de estado runtime y usa un rol custom exacto más lectura del repositorio de imágenes, nunca `roles/run.admin`. No contiene claves de servicio ni passwords cloud.

La ejecución real está bloqueada. Las seis cuentas de facturación visibles estaban cerradas y el proyecto activo de `gcloud` es ajeno a este repositorio. No debe adoptarse ni modificarse. El proceso de reanudación está en [el runbook de GCP dev](docs/runbooks/gcp-dev-deployment.md) y exige un plan runtime guardado y una atestación independiente `ALLOW_DEV_APPLY` ligada al hash del plan, árbol Git completo, commit, imagen inmutable, workflow, actor, revisor y ejecución. Se verifica antes de autenticar y sólo entonces podría aplicarse ese archivo exacto.

## Límites conocidos

- `development_headers` sólo identifica tenant/principal en test y desarrollo; producción falla cerrada hasta que exista un adaptador de identidad verificado.
- La corrida completa se confirma en una transacción de comando. No existe cola/outbox ni reanudación durable a mitad de agente.
- Los adaptadores de Meta Ads, plataformas sociales, navegador, GitHub, Context7 y media son fixtures deterministas.
- Cloud Run dev es IAM-private. Para UI interactiva se necesita un proxy/túnel autenticado; no se añade `allUsers`.
- No hay despliegue, prueba de permisos/cuotas/costo regional, conectividad Cloud SQL IAM ni segunda planificación sin cambios mientras continúe el bloqueo externo.
- Staging y producción son registros de gate sin recursos ejecutables.

## Documentación y evidencia

- [Especificación Production Foundation V1](docs/specs/production-foundation-v1.md)
- [ADRs](docs/adr/README.md)
- [Runbook de incidentes](docs/runbooks/incident-response.md)
- [Infraestructura y rollback](infra/README.md)
- [Estado y evidencia de agentes](agent/current-state.md)
- [Matriz requisito → evidencia](agent/requirements-traceability.csv)
