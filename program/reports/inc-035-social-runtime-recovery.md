# INC-035 — Social runtime recovery and durable delivery

Updated: 2026-07-28

## Objective

Remove the operational conditions that caused the local X and Instagram OAuth records
to disappear, make the public callback recoverable after an interrupted workstation
command, and replace the unusable audited `git_push` path with a repository-owned,
verifiable GitHub Git Data delivery path.

No social publication, paid media, model effect or cloud apply belongs to this increment.

## Confirmed incident facts

The persistent workspace contains one runtime database at:

```text
/workspace/.local/ai-native-content-agency-local.sqlite3
```

Its integrity check passes, but `social_connections`, `social_oauth_states` and
`social_publication_intents` contain zero rows. A filesystem and artifact search found no
older SQLite database, WAL, backup or encrypted token record from which the two prior
connections could be reconstructed. Receipts prove prior effects but intentionally do
not contain reusable provider credentials.

The application credentials and social-token encryption keyset remain configured. The
missing user grants therefore require one new interactive OAuth authorization per
provider; fabricating or reconstructing a token from receipts would violate the security
boundary.

## Implemented recovery controls

### Persistent runtime state

The launcher continues to use `.local/ai-native-content-agency-local.sqlite3`, never
`/tmp`, for the governed workspace. The current runtime process was verified against
that exact database and reports `integrity=ok`.

### Connection-change backup watcher

`scripts/watch-social-connection-backups.py` hashes the complete ordered
`social_connections` table locally. The digest includes encrypted ciphertext so token
rotation is detected, but neither tokens nor ciphertext are written to logs. A consistent
SQLite backup is created only when the connection state changes.

Artifacts are stored privately under:

```text
/workspace/.local/social-connection-backups/
```

The backup directory uses mode `0700`; the state digest, latest-manifest pointer,
manifest and backup data use private permissions. The existing checked backup tool uses
SQLite's backup API, integrity validation, checksum manifests, atomic rename and fsync.

A real drill proved:

- first invocation: backup created;
- unchanged second invocation: no duplicate backup;
- restore into a new database: success;
- source and restored session/audit/social-connection counts: exact match;
- source and restored `PRAGMA integrity_check`: `ok`.

`workspace-up.sh up` now starts this watcher automatically. `workspace-up.sh backup`
forces an immediate check.

### Recoverable callback tunnel

The launcher now supports two modes:

1. a named Cloudflare Tunnel using the untracked
   `AGENCY_CLOUDFLARE_TUNNEL_TOKEN` plus `AGENCY_CLOUDFLARE_PUBLIC_URL` pair;
2. a Quick Tunnel fallback for laboratory use.

Named-tunnel credentials are copied to a private token file and passed to `cloudflared`
with `--token-file`, not as a raw process argument. In Quick Tunnel mode, the launcher
can now discover and adopt a live hostname from `cloudflared` logs after the parent MCP
command is interrupted. It no longer leaves `.env.local`, provider callbacks and the
live tunnel on different hostnames.

The repaired launcher adopted the live Quick Tunnel, updated both provider callbacks,
restarted the API with the current environment and verified local/public HTTP 200.
At the time of this checkpoint, both social channels report:

```text
configuration_state=ready_for_authentication
connection_state=not_connected
oauth_start_available=true
publication_execution_enabled=false
publishing_available=false
```

The current Quick Tunnel is useful for the next interactive authorization but remains
an ephemeral callback. A named tunnel and stable hostname are the durable production-like
option.

### Git delivery fallback

The audited Cloud Sandbox `git_push` helper was retested on an isolated probe branch. It
again failed before contacting GitHub because its private ownership helper starts a
nested Docker daemon that cannot create the `DOCKER` NAT chain in this environment.
This defect is outside the repository and cannot be changed by application code.

`scripts/publish-branch-via-git-data.py` provides a bounded replacement using the already
authenticated `gh api` client. It:

- refuses a dirty worktree;
- resolves an existing branch or explicit base ref;
- compares binary-safe local and remote Git trees;
- uploads exact Git blobs without shell interpolation;
- creates a tree, commit and non-forced ref update through GitHub Git Data API;
- verifies the complete resulting remote tree, including file modes;
- returns only sanitized JSON evidence and never prints the GitHub token.

## Verification completed before delivery

- complete backend suite: 320 PASS; 25 PostgreSQL-only skips expected;
- focused launcher, watcher and Git Data tests included in that suite: PASS;
- frontend suite: 54 PASS;
- lint: zero warnings/errors;
- production build: PASS;
- Chromium accessibility/reflow gate: PASS;
- shell syntax and Python compilation: PASS;
- backup creation/deduplication/restore drill: PASS;
- local product health: HTTP 200;
- public Quick Tunnel health: HTTP 200;
- persistent SQLite integrity: `ok`;
- X and Instagram OAuth start availability: true;
- all publication switches: false;
- external side effects enabled: false.


## Remote delivery evidence

The repository-owned Git Data publisher was run against remote base
`3011e3c563b28c02f9b982804c8c744c76a696a4`. Its dry-run and final comparison contained
exactly the 10 INC-035 files; seven inherited INC-032/033 artifact paths were detected in
the old local ancestry and deliberately excluded by realigning the local commit onto the
remote base before publication.

Remote implementation commit `8a913bf49b8d55a7ed86666aed924759f48b086b`
verified all 459 final remote paths and modes. Draft PR #28 targets
`agent/inc-034-modern-onboarding-trends-remote`. Workflow `30392865935` completed with
8/8 successful jobs: verify, python-locks, PostgreSQL shared state, container, workflow
lint, Helm, Terraform and supply chain.

## Remaining interactive provider gate

The provider consoles must allowlist the exact callback hostname before OAuth can finish.
This requires an authenticated Meta/X developer-console session and cannot be performed
from repository credentials. After the callbacks are updated, an administrator must use
CampaignOS to authorize X and Instagram once. The backup watcher must then create a new
manifest and the API must verify both connected accounts before any future publication
window is considered.

Release recommendation: `DENY_RELEASE`

Cloud recommendation: `DENY_APPLY`
