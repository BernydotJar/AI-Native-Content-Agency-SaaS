# Autoridad exact-once para publicación social

Estado: implementada y **deshabilitada por defecto**. Los gates locales y CI utilizan
`httpx.MockTransport`; no realizan publicaciones reales en X ni Instagram.

## Activación explícita

La conexión OAuth de una cuenta no habilita publicación. El operador debe configurar:

```dotenv
AGENCY_SOCIAL_PUBLICATION_ENABLED=true
```

Además deben existir:

- claves de cifrado social server-side;
- aplicación y callback configurados para el canal;
- cuenta exacta conectada y autorizada;
- run completado con Greenlight activo;
- artefacto `copy_deck` incluido en el envelope de Greenlight;
- para Instagram, un artefacto `publication_media` aprobado con URL HTTPS y SHA-256.

Helm y Terraform usan `false` por defecto. La revisión de proveedor, privacidad, cuota,
cuenta sandbox, despliegue y gasto continúa siendo un gate humano.

## Flujo de autoridad

1. El navegador envía únicamente referencias: run, canal, artefacto, media opcional,
   Greenlight ID/fence e idempotency key. No puede enviar copy ni media URL arbitrarios.
2. El servidor carga el run y reconstruye el copy desde la variante aprobada del
   `copy_deck`.
3. Se verifican cuenta, canal, Greenlight activo, envelope de artefactos y hashes.
4. Antes de descifrar tokens o tocar red, se persiste un intent `pending`.
5. La identidad del efecto liga tenant, cuenta, canal, run, artefacto/hash, media/hash,
   Greenlight/fence y presupuesto. `(tenant_id, binding_digest)` es único.
6. Sólo la reserva ejecutora descifra tokens y contacta el host fijo del proveedor.
7. El resultado se persiste como receipt sanitizado; un replay compatible devuelve el
   mismo receipt sin una segunda llamada.
8. El evento de auditoría usa un ID determinista. Si el receipt quedó durable pero el append
   de auditoría falló, el replay repara el evento sin volver a contactar al proveedor.

Una clave de idempotencia diferente no crea otro efecto cuando el binding es idéntico.
La identidad económica del efecto prevalece sobre la clave elegida por el cliente.

## Estados

```text
pending -> succeeded
pending -> failed
pending -> unknown
pending -> revoked
unknown -> succeeded  # sólo reconciliación humana
```

- `succeeded`: contiene ID del post y receipt bounded; es replayable.
- `failed`: rechazo conocido antes de éxito; bloquea retry automático.
- `unknown`: timeout, 5xx, respuesta ambigua o fallo de persistencia posterior a una
  posible creación. **Nunca se reintenta automáticamente.**
- `revoked`: autoridad pendiente invalidada por disconnect o revocación de Greenlight.

Disconnect y Greenlight revocation sólo revocan `pending`. Nunca borran ni ocultan
`succeeded` o `unknown`.

## Protocolos

### X

- host fijo: `api.x.com`;
- endpoint: `POST /2/tweets`;
- OAuth 1.0a user context con consumer key/secret y access token/secret server-side;
- un 4xx conocido queda `failed`;
- timeout, 5xx o respuesta sin post ID queda `unknown`.

### Instagram

- host fijo: `graph.instagram.com`;
- `POST /{ig_user_id}/media` con media aprobada;
- el container ID se persiste antes de `POST /{ig_user_id}/media_publish`;
- si el segundo paso es ambiguo, el intent queda `unknown` conservando el container ID.

El runtime actual no genera ni registra un `publication_media` real; por ello Instagram
permanece bloqueado aunque la cuenta esté conectada y el flag esté habilitado.

## Confirmación humana

La primera pulsación en **Publicar** sólo abre un diálogo que identifica canal, cuenta,
artefacto, media y control Greenlight. El proveedor se contacta únicamente después de
**Confirmar publicación externa**. Durante la solicitud no se puede cerrar el diálogo.

## Reconciliación de `unknown`

La alerta `AgencySocialPublicationUnknown` dispara ante cualquier incremento del contador
`unknown` en 15 minutos.

1. No reintente ni modifique el intent.
2. Verifique en la consola autorizada del proveedor usando canal, cuenta, artifact hash,
   Greenlight y request evidence; no copie tokens ni contenido al incidente.
3. Si el post existe, use:

```http
POST /api/v1/social-publications/{intent_id}/reconcile
Idempotency-Key: <opaque command key>
```

con `provider_post_id`, `provider_request_id` y una nota operativa. Sólo se almacenan el
SHA-256 de la clave, el SHA-256 de la nota y el digest del binding de reconciliación. Un
replay con la misma evidencia devuelve el mismo estado sin duplicar el evento de auditoría;
evidencia distinta queda en conflicto.
4. Si la ausencia está probada, mantenga el intent original y abra una remediación
   aprobada; nunca lo restablezca silenciosamente a `pending`.

Consulte también [Incident Response](incident-response.md#social-publication-outcome-unknown).

## Datos persistidos

Se almacenan IDs, SHA-256, estado, fencing token, container/post IDs y receipt sanitizado.
No se almacenan:

- idempotency key en claro;
- copy del post;
- media URL;
- access/refresh tokens o secrets;
- bodies completos del proveedor;
- nota de reconciliación en claro.

El rol PostgreSQL runtime tiene `SELECT`, `INSERT` y `UPDATE` sobre intents. No tiene
`DELETE`, `TRUNCATE`, ownership ni DDL.

## Métricas y auditoría

```text
agency_social_publications_total{outcome="succeeded|replayed|blocked|rejected|unknown|reconciled"}
```

La métrica no tiene etiquetas de tenant, cuenta, contenido ni URL.

Eventos auditables:

- `social.publication_succeeded`;
- `social.publication_reconciled`;
- `social.publication_intents_revoked`;
- `social.disconnected` con cantidad de intents pendientes revocados.

## Verificación sin efectos reales

```bash
python -m unittest backend.tests.test_social_publication
python -m unittest backend.tests.test_social_publication_api
./scripts/verify-postgresql-runtime.sh
npm run verify:social-publication-browser
CONTAINER_BUILDER=buildah ./scripts/verify-production-package.sh
```

Los tests verifican reserva previa, una sola ejecución, replay con claves distintas,
reparación de auditoría, reconciliación idempotente, `unknown`, revocación, segundo paso
humano, orden de locks sin deadlock y cero HTTP real de proveedor. El package smoke transmite
un fixture por stdin a un contenedor efímero derivado de la imagen exacta; el fixture no forma
parte del Dockerfile ni del artefacto final y bloquea sockets además de usar MockTransport.
