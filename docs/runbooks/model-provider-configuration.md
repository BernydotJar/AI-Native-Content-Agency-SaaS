# Configuración de proveedores de modelos

Este runbook describe el catálogo server-side introducido por `INC-013` y el
gateway protocolar acotado de `INC-014`. El catálogo permite inspeccionar configuración;
el gateway permanece deshabilitado por defecto y no está conectado a los runs.

## Invariantes

- Las credenciales sólo se leen desde el entorno del proceso o un secret manager que
  las materialice como variables de entorno.
- Ninguna credencial se devuelve por API, se registra, se persiste en SQLite/PostgreSQL
  o se solicita desde el navegador.
- Los endpoints personalizados deben ser HTTPS absolutos, sin usuario, contraseña,
  query string ni fragmento.
- El nombre de modelo se trata como configuración explícita. No se inventa un modelo
  por proveedor y no se deriva de copy del frontend.
- `GET /api/v1/providers` es autenticado y sólo lectura.
- `configured=true` significa que credencial, modelo y endpoint están presentes. No
  significa que una llamada haya sido ejecutada, cobrada o aprobada.

## Variables por proveedor

| Proveedor | Credencial | Modelo | Endpoint opcional/obligatorio |
|---|---|---|---|
| OpenAI | `OPENAI_API_KEY` | `AGENCY_OPENAI_MODEL` | `AGENCY_OPENAI_BASE_URL` opcional; default oficial |
| Anthropic | `ANTHROPIC_API_KEY` | `AGENCY_ANTHROPIC_MODEL` | `AGENCY_ANTHROPIC_BASE_URL` opcional; default oficial |
| DeepSeek | `DEEPSEEK_API_KEY` | `AGENCY_DEEPSEEK_MODEL` | `AGENCY_DEEPSEEK_BASE_URL` opcional; default oficial |
| Moonshot / Kimi | `MOONSHOT_API_KEY` o `KIMI_API_KEY` | `AGENCY_MOONSHOT_MODEL` | `AGENCY_MOONSHOT_BASE_URL` opcional; default oficial |
| Llama | `LLAMA_API_KEY` | `AGENCY_LLAMA_MODEL` | `AGENCY_LLAMA_BASE_URL` obligatorio porque Llama puede servirse desde distintos hosts |

## Ejemplo local sin ejecutar inferencia

```bash
export OPENAI_API_KEY='replace-from-secret-manager'
export AGENCY_OPENAI_MODEL='gpt-5.2'

export DEEPSEEK_API_KEY='replace-from-secret-manager'
export AGENCY_DEEPSEEK_MODEL='deepseek-v4-flash'

npm run start:local
```

Después de conectar el tenant, **Configuración → Proveedores de modelos** muestra el
estado derivado del servidor. El valor de las credenciales nunca aparece.

## Estados

- `ready`: credencial, modelo y endpoint presentes.
- `missing_credential`: falta una credencial server-side.
- `missing_model`: existe credencial, pero no se eligió modelo.
- `missing_endpoint`: se requiere un endpoint explícito y no está configurado.

## Estado del gateway

`INC-014` completa clientes HTTP por protocolo, límites, allowlist, errores sanitizados
y pruebas con transportes simulados. No añade rutas de inferencia ni conecta el gateway
a `run.create`. Consulta `docs/runbooks/model-gateway.md`.

Antes de permitir inferencia real todavía se debe implementar y verificar:

1. selección explícita de proveedor activo por tenant o deployment;
2. autorización de costo/egress y presupuesto máximo;
3. intent/outbox/receipt durable sin secretos y replay económico seguro;
4. auditoría y métricas de request/response metadata sin contenido sensible;
5. circuit breaker, reconciliación de estados inciertos y revocación;
6. revisión de privacidad, términos y transferencia de datos por proveedor;
7. autorización explícita antes de usar credenciales reales o generar gasto.

Hasta que esas condiciones pasen, el runtime determinista local permanece claramente
identificado y `DENY_RELEASE` sigue vigente.
