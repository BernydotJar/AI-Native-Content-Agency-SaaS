# Ejecución asíncrona durable de campañas

El producto crea campañas con `Prefer: respond-async`. El servidor persiste primero el
run en estado `queued`, devuelve `202 Accepted` y permite que el navegador observe cada
checkpoint mediante `GET /api/v1/runs/{run_id}`. La topología no calcula porcentajes ni
simula estaciones: representa únicamente `agent_states` persistidos por el backend.

## Contrato HTTP

```http
POST /api/v1/runs
Prefer: respond-async
Idempotency-Key: <clave estable>
```

Una creación nueva devuelve:

```text
202 Accepted
Preference-Applied: respond-async
Location: /api/v1/runs/<run_id>
```

La reproducción compatible de la misma clave devuelve el documento original con
`X-Command-Replayed: true`. El cliente debe abrir `Location` o consultar el `run_id` para
observar el estado actual.

Sin `Prefer: respond-async`, el endpoint mantiene el contrato síncrono anterior para
clientes máquina compatibles. La SPA usa siempre el contrato asíncrono.

## Estados y checkpoints

```text
queued -> running -> awaiting_greenlight -> completed | rejected | revoked | failed
```

Cada estación previa a Publisher registra dos checkpoints reales:

1. `processing`, progreso `10`, sin artefacto todavía;
2. `ready`, progreso `100`, con el artefacto durable correspondiente.

CEO, Research, Strategist, Growth, Writer, Media y Risk producen catorce checkpoints.
Después de Risk, Publisher queda `waiting_greenlight`; no se empaqueta ni publica nada.

El documento `execution` contiene:

- `state` y `next_station`;
- `lease_owner` y `lease_expires_at`;
- `fencing_token` monotónico;
- `attempts` y `checkpointed_at`;
- `failure_detail` limitado al tipo de excepción.

## Lease, fencing y recuperación

Antes de ejecutar un checkpoint, el worker adquiere un lock durable por tenant/run,
persiste un lease con expiración e incrementa el fencing token. La finalización del
checkpoint requiere el estado de run esperado y registra `run.checkpointed` con el mismo
fence. Dos réplicas PostgreSQL pueden competir, pero el lock advisory serializa la
transición y evita artefactos duplicados.

Si el proceso termina después del claim, otro worker no puede continuar hasta que el
lease expire. Tras la expiración, reclama con un fencing token superior y reejecuta sólo
el checkpoint que no llegó a persistirse. Las estaciones ya `ready` se omiten.

Los adaptadores usados por estas estaciones siguen siendo deterministas y sandbox-only.
No hay llamadas a modelos, publicación social, render multimedia ni gasto externo.

## Configuración

```dotenv
AGENCY_RUN_WORKER_POLL_INTERVAL_SECONDS=0.35
AGENCY_RUN_LEASE_SECONDS=30
```

Límites:

- dispatch: `0.05` a `60` segundos;
- lease: `5` a `300` segundos.

El intervalo controla cuándo el worker busca el siguiente checkpoint; no modifica ni
inventa el progreso. Para múltiples réplicas use PostgreSQL. SQLite es adecuado para el
runner local de un solo proceso.

## Diagnóstico

`GET /readyz` devuelve `durable_run_worker=true` cuando el loop está activo.

Consulte el run y la auditoría:

```bash
curl -H "Authorization: Bearer $KEY" "$BASE/api/v1/runs/$RUN_ID"
curl -H "Authorization: Bearer $KEY" "$BASE/api/v1/audit-events?limit=100"
```

Señales relevantes:

- `run.created`: run persistido y recibo de comando creado;
- `run.checkpointed`: transición durable con station, attempt y fencing token;
- `run.failed`: excepción sanitizada; no se intenta Greenlight;
- `greenlight.approved|rejected|revoked`: decisión humana posterior a Risk.

Un lease activo no debe borrarse manualmente. Verifique primero que el propietario no
esté ejecutando y espere su expiración. La recuperación normal asigna un fence nuevo.
