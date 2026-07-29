# Gateway de modelos

`INC-014` implementa clientes HTTP reales para los protocolos de cinco proveedores,
pero mantiene la ejecución automática y las rutas de inferencia deshabilitadas hasta
que exista un intent/receipt outbound durable.

## Estado aprobado

```text
protocol_clients=implemented
execution_enabled=false_by_default
automatic_run_integration=false
durable_outbound_receipt=false
public_completion_route=absent
real_provider_calls_in_tests=zero
```

El endpoint autenticado `GET /api/v1/providers` expone únicamente configuración y el
estado seguro del gateway. Nunca expone credenciales, prompts, respuestas o headers de
autorización.

## Protocolos implementados

| Proveedor | Contrato HTTP | Autenticación |
|---|---|---|
| OpenAI | `POST /v1/responses` | `Authorization: Bearer …` |
| Anthropic | `POST /v1/messages` | `x-api-key` + `anthropic-version` |
| DeepSeek | `POST /chat/completions` compatible con OpenAI | `Authorization: Bearer …` |
| Moonshot / Kimi | `POST /v1/chat/completions` compatible con OpenAI | `Authorization: Bearer …` |
| Llama | `POST {AGENCY_LLAMA_BASE_URL}/chat/completions` compatible con OpenAI | `Authorization: Bearer …` |

Los modelos siguen siendo configuración explícita. El catálogo recomienda Kimi K3,
DeepSeek V4 Flash/Pro, modelos OpenAI/Anthropic fijados por deployment y Llama 4 para
endpoints compatibles; ninguna recomendación activa el proveedor.

## Política fail-closed

La construcción del gateway exige:

- `AGENCY_MODEL_EXECUTION_ENABLED=true` exacto;
- un `AGENCY_MODEL_PROVIDER` allowlisted;
- proveedor completamente configurado;
- `AGENCY_MODEL_EGRESS_ALLOWED_HOSTS` con el host exacto;
- endpoint HTTPS sin usuario, contraseña, query ni fragmento;
- ningún IP literal, `localhost` o dominio `.local`;
- límites válidos de input, output, respuesta y timeout.

El cliente usa:

- `trust_env=false` para ignorar proxies del entorno;
- redirects deshabilitados;
- un solo intento, sin retry automático;
- lectura streaming con límite de bytes;
- errores públicos sanitizados;
- parsing estricto por protocolo.

## Variables de política

| Variable | Default | Límite |
|---|---:|---:|
| `AGENCY_MODEL_EXECUTION_ENABLED` | `false` | `true` o `false` exacto |
| `AGENCY_MODEL_PROVIDER` | vacío | proveedor allowlisted |
| `AGENCY_MODEL_EGRESS_ALLOWED_HOSTS` | vacío | lista CSV de hosts exactos |
| `AGENCY_MODEL_MAX_INPUT_CHARS` | `12000` | 1–200000 |
| `AGENCY_MODEL_MAX_OUTPUT_TOKENS` | `512` | 1–8192 |
| `AGENCY_MODEL_MAX_RESPONSE_BYTES` | `1048576` | 64–8388608 |
| `AGENCY_MODEL_TIMEOUT_SECONDS` | `30` | 1–120 |

## Receipt en memoria

Una respuesta válida produce un receipt sanitizado con:

- proveedor y modelo;
- request ID del proveedor;
- tokens de entrada/salida/total;
- SHA-256 del request canónico;
- SHA-256 del output.

El receipt no contiene prompt, texto generado, credencial ni headers. Sin embargo,
actualmente sólo existe en memoria durante la llamada. Por eso
`durable_outbound_receipt=false` y el gateway no se conecta todavía a `run.create`.

## Por qué no se conecta al run todavía

La ejecución actual calcula la orquestación antes de guardar el receipt durable del
comando. Si una llamada externa cobrara y el proceso fallara antes de persistir, un
replay podría volver a cobrar. Activarla en ese punto violaría idempotencia económica.

El siguiente incremento debe:

1. persistir un intent outbound antes de la llamada;
2. enlazarlo a tenant, run, comando, provider, modelo, payload hash y presupuesto;
3. adquirir una autoridad/fence exclusiva;
4. guardar receipt exitoso antes de completar el run;
5. reutilizar receipts compatibles en replays;
6. bloquear estados `pending/unknown` sin volver a llamar;
7. permitir reconciliación humana de estados inciertos;
8. registrar costo/tokens sin contenido sensible;
9. añadir revocación y circuit breaker;
10. obtener autorización explícita antes de usar credenciales reales o generar gasto.

## Verificación

Todas las pruebas del gateway usan `httpx.MockTransport`. No realizan DNS, red,
inferencia, upload, publicación ni gasto. La imagen productiva exige que el gateway
esté deshabilitado y que no existan rutas `/api/v1/model-completions` o
`/api/v1/providers/execute`.
