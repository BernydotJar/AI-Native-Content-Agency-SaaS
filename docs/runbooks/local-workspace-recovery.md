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
starts the social-connection backup watcher, starts the configured named Cloudflare
Tunnel or falls back to a Quick Tunnel, refreshes the provider callback URLs, restarts
the API whenever the public hostname or `.env.local` changes, and verifies both local
and public health. This includes newly saved provider credentials, so Docker Compose
is not required to reload X or Instagram config.

Useful commands:

```bash
./scripts/workspace-up.sh status
./scripts/workspace-up.sh url
./scripts/workspace-up.sh backup
cat .local/product.log
cat .local/api.log
cat .local/cloudflared.log
```

## Quick Tunnel limitation

A `trycloudflare.com` Quick Tunnel is intentionally ephemeral. Recovery can be
automated, but the hostname cannot be guaranteed. A changed hostname must also
be present in each provider's OAuth redirect allowlist.

For a durable OAuth callback, configure a named Cloudflare Tunnel and its stable
hostname in the untracked `.env.local` file:

```bash
AGENCY_CLOUDFLARE_TUNNEL_TOKEN=
AGENCY_CLOUDFLARE_PUBLIC_URL=https://campaignos.example.com
```

Both values are required together. `workspace-up.sh` copies the token to a private
`0600` file and starts `cloudflared` with `--token-file`, so the token is not placed in
the process arguments or logs. Configure the same stable hostname in Meta and X. Never
store tunnel credentials or provider secrets in tracked files.

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


## Backup automático de conexiones sociales

`workspace-up.sh up` inicia `scripts/watch-social-connection-backups.py`. El watcher
calcula un digest local de la tabla `social_connections`, incluyendo el ciphertext pero
sin imprimirlo. Sólo crea un backup SQLite consistente cuando ese estado cambia: nueva
cuenta, rotación de token o desconexión. Los backups y manifests quedan en:

```text
/workspace/.local/social-connection-backups/
```

El manifest más reciente se registra en
`.local/latest-social-backup-manifest`; los archivos usan permisos privados. El watcher
no sustituye un backup productivo cifrado/off-host, pero protege el workspace persistente
contra otra pérdida por reemplazo del runtime. Para forzar una comprobación inmediata:

```bash
./scripts/workspace-up.sh backup
```

Antes de restaurar, detén el API y sigue el runbook de backup/restore. Nunca copies sólo
el archivo SQLite principal cuando existe WAL.
