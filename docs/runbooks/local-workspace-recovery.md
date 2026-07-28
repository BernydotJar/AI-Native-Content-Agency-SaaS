# Local workspace recovery

The Cloud Sandbox checkout and SQLite database are persistent, but processes
inside the workstation container are not. A runtime recreation or container
restart therefore stops both `agency-api` and any Cloudflare Quick Tunnel.

Run the idempotent recovery command after opening the workspace:

```bash
cd /workspace
./scripts/workspace-up.sh up
```

The command forces publication switches to `false`, restores the local product,
reuses or recreates a Quick Tunnel with HTTP/2, refreshes the provider callback
URLs, restarts the API whenever the public hostname or `.env.local` changes,
and verifies both local and public health. This includes newly saved provider
credentials, so Docker Compose is not required to reload X or Instagram config.

Useful commands:

```bash
./scripts/workspace-up.sh status
./scripts/workspace-up.sh url
cat .local/product.log
cat .local/api.log
cat .local/cloudflared.log
```

## Quick Tunnel limitation

A `trycloudflare.com` Quick Tunnel is intentionally ephemeral. Recovery can be
automated, but the hostname cannot be guaranteed. A changed hostname must also
be present in each provider's OAuth redirect allowlist.

For a durable OAuth callback, use a named Cloudflare Tunnel or another stable
public hostname. Configure the same stable hostname in CampaignOS, Meta and X.
Do not store tunnel credentials or provider secrets in tracked files.

## Local identity credential

The governed workspace uses stable identities from
`.local/political-feedback-credentials.json`. It intentionally does not emit an
ephemeral credential on every restart, preserving reviewer identity and
Greenlight separation.

An ephemeral credential is emitted only when
`AGENCY_IDENTITY_CREDENTIALS_JSON` is absent. Use that mode only for an isolated
local runtime, never for the governed Instagram or X publication workflow.

## Persistencia del runtime local

El launcher local y `scripts/workspace-up.sh` usan por defecto:

```text
/workspace/.local/ai-native-content-agency-local.sqlite3
```

No uses `/tmp` para un workspace que deba sobrevivir al reemplazo del contenedor. El
repositorio ignora `.local/`, pero el volumen persistente del workspace conserva ese
archivo. `AGENCY_MEMORY_DB` puede sobrescribir la ruta cuando una prueba necesita una
base efímera explícita.

Antes de reemplazar un runtime antiguo que todavía use `/tmp`, crea un backup SQLite
consistente hacia `.local/`; copiar sólo el archivo principal mientras existe WAL puede
perder transacciones. Después del reinicio, verifica la variable efectiva del proceso y
los conteos de sesiones, auditoría y conexiones sociales. Una autorización OAuth que ya
se perdió del volumen anterior no se reconstruye a partir de logs o receipts: exige una
nueva autorización interactiva.
