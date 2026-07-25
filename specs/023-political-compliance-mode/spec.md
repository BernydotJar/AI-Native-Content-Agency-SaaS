# INC-023 — Political Compliance Mode

## Status

`approved`

## Objective

Make real political organic publication an explicit, auditable and independently approved mode while keeping paid political media unavailable unless a separate ads authority is implemented and enabled.

## File-bound execution contract

- task_id: INC-023
- workstream_id: WS-08
- role: Producer -> Critic -> Security/Legal Reviewer -> Independent Verifier
- allowed_paths:
  - backend/agency_runtime/models.py
  - backend/agency_runtime/serialization.py
  - backend/agency_runtime/api.py
  - backend/agency_runtime/campaign_intelligence.py
  - backend/agency_runtime/orchestrator.py
  - backend/agency_runtime/social_publication.py
  - backend/agency_runtime/social_publication_store.py
  - backend/agency_runtime/social_publication_postgres.py
  - backend/agency_runtime/postgres.py
  - backend/tests/test_social_publication_store.py
  - backend/tests/test_social_publication_postgres.py
  - backend/tests/test_postgres_schema_cli.py
  - scripts/verify-postgresql-runtime.sh
  - backend/tests/test_political_compliance.py
  - backend/tests/test_campaign_intelligence.py
  - backend/tests/test_social_publication_api.py
  - src/lib/runtimeApi.ts
  - src/components/WorkspaceRuntime.tsx
  - src/components/PublicationConfirmationDialog.tsx
  - src/components/CampaignOutputPanel.tsx
  - related focused frontend tests
  - .env.example
  - infra/helm/ai-native-content-agency/**
  - infra/terraform/**
  - program/**
  - docs/runbooks/political-publication.md
- prohibited_paths:
  - main branch
  - provider credentials
  - production environment files
  - unrelated product areas
- write_lock: one sequential writer per file

## Contract

### Publication mode

Every brief has `publication_mode`:

- `organic` — eligible for the existing governed social-publication authority;
- `paid` — never routed through the organic publication endpoint. It requires a future ads authority and `AGENCY_POLITICAL_PAID_MEDIA_ENABLED=true`.

Commercial briefs remain backward-compatible with `organic` default.

### Political approval chain

A political run requires two accountable identities:

1. legal/electoral reviewer recorded server-side during brief creation;
2. Greenlight approver recorded server-side at approval.

The two identities must be distinct. Client-supplied reviewer names are never authoritative.

### Political publication confirmation

The final publication command requires an exact confirmation phrase derived server-side from run and channel:

`PUBLICAR POLITICA <run_id> <channel_id>`

The durable publication intent stores only the confirmation SHA-256, not the phrase. Replay requires the same binding.

### Disclosure and jurisdiction

Political publication requires:

- non-empty jurisdiction;
- non-empty disclosure;
- legal review approved by an authenticated approver/admin;
- verified evidence claims;
- `risk_report.publication_eligible=true`;
- organic publication mode;
- general and political publication kill switches enabled.

### Evidence retention

The run must contain a `political_compliance_record` artifact included in Greenlight. It records jurisdiction, mode, disclosure hash, reviewer identities, claim/source hashes and a retention state of `durable_until_governed_deletion`. No retention duration is invented while policy approval remains open.

### Safety switches

- `AGENCY_POLITICAL_CONTENT_ENABLED=false`
- `AGENCY_POLITICAL_PUBLICATION_ENABLED=false`
- `AGENCY_POLITICAL_PAID_MEDIA_ENABLED=false`

General social publication never implicitly enables any political switch.

## Acceptance criteria

- Political content creation is blocked when political content mode is disabled.
- Political organic runs require distinct legal and Greenlight reviewers.
- Paid political mode cannot reach the organic provider transport.
- Missing disclosure, jurisdiction, verified claims or compliance record blocks Greenlight/publication.
- Incorrect political confirmation phrase blocks before intent reservation and provider HTTP.
- Correct phrase is represented only by a hash in durable state/audit.
- Commercial runs remain backward-compatible.
- UI clearly distinguishes organic and paid and requires typed political confirmation.
- All switches default false in runtime, example environment, Helm and Terraform.
- No real provider call is executed by tests.
