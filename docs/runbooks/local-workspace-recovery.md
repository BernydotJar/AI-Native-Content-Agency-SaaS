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
URLs, restarts the API only when the public hostname changes, and verifies both
local and public health.

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
