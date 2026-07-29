# Data Classification and Retention Decision Register

Status: architecture inventory; no retention/deletion policy is approved
Updated: 2026-07-21
Jurisdiction: `UNKNOWN`
Risk classification: `YELLOW / UNKNOWN`
Destructive execution: human-gated

Machine-readable status: [`compliance/privacy-decision-register.json`](../../compliance/privacy-decision-register.json). The validator requires UNKNOWN/unapproved values, null retention durations and disabled destructive automation until accountable approvals exist.

## 1. Classification levels

| Level | Definition | Handling baseline |
|---|---|---|
| `RESTRICTED_SECRET` | A value that grants access or decrypts/protects data. | Never log/audit/return; server-side only; digest/hash where verification permits; approved secret manager in real environments; rotate/revoke. |
| `CONFIDENTIAL_CLIENT` | Tenant campaign content, evidence, artifacts or knowledge. | Tenant-scoped authorization; encryption in transit/at rest in real environments; no external disclosure without contract/approval; content-aware review. |
| `CONFIDENTIAL_IDENTITY` | Tenant/user/account/access metadata. | Least privilege, tenant/admin scope, bounded audit, no public enumeration, lifecycle/retention policy. |
| `OPERATIONAL_SENSITIVE` | Security/operations evidence that can aid attack or reveal usage. | Access-controlled telemetry, minimized labels/payloads, retention bounds, tamper controls and incident purpose. |
| `PUBLIC_PRODUCT` | Deliberately public non-tenant product metadata. | Integrity/provenance controls; no secret/client data. |

A lower classification cannot be selected solely because a field name is generic. Free-text content inherits the highest plausible sensitivity of the people, campaign and source material it contains.

## 2. Current data stores and retention state

`No automatic deletion` means the runtime keeps the row/file until an explicitly authorized operator/environment action removes it. It is a gap, not an approved indefinite-retention policy.

| Record / field | Class | Purpose | Primary location | Current lifecycle | Required policy/implementation decision |
|---|---|---|---|---|---|
| Raw API key | `RESTRICTED_SECRET` | initial bearer/session authentication | supplied to server config/request only | not persisted by application; may exist in environment/secret backend | managed secret store, rotation owner, emergency revocation, configuration/log inspection |
| API-key digest/fingerprint | `CONFIDENTIAL_IDENTITY` / `OPERATIONAL_SENSITIVE` | constant-time authentication and session/key binding | in-memory config; session fingerprint | config-controlled; session row persists after logical expiry/revocation | identity lifecycle and purge schedule |
| Raw session cookie / CSRF token | `RESTRICTED_SECRET` | browser authentication/mutation verification | browser/process memory only | not persisted raw; expires/revokes logically | browser/device policy and incident revocation |
| Session/CSRF hashes and timestamps | `CONFIDENTIAL_IDENTITY` | validate/revoke sessions | `runtime_sessions` | no automatic row purge | approved security evidence window and purge job |
| Tenant ID / subject ID / role / key ID | `CONFIDENTIAL_IDENTITY` | authorization, audit and tenant isolation | config, sessions, audit | no automatic deletion | account offboarding, pseudonymization, audit/legal-hold interaction |
| Source/credential rate bucket hashes | `OPERATIONAL_SENSITIVE` | brute-force protection | SQLite `authentication_failures` or PostgreSQL `authentication_rate_limits` | old windows stop enforcement; rows may remain | short security-retention window and tested cleanup without reopening attack window |
| Campaign brief | `CONFIDENTIAL_CLIENT` | campaign package generation | `runtime_runs.payload_json` | no automatic deletion | tenant/customer retention, correction/deletion/export, legal hold |
| Agent trace/evidence/artifact content | `CONFIDENTIAL_CLIENT` | review/provenance | run payload | no automatic deletion | content lifecycle, citation/source rights, export/deletion |
| Artifact IDs/hashes | `CONFIDENTIAL_CLIENT` / `OPERATIONAL_SENSITIVE` | exact Greenlight binding | run payload/decision | retained with run | retain with governed decision/evidence; collision/algorithm migration policy |
| Greenlight reviewer/note/decision | `CONFIDENTIAL_CLIENT` / `CONFIDENTIAL_IDENTITY` | accountable approval/rejection | run payload and audit | no automatic deletion/revocation record | approval retention, correction restrictions, post-approval revocation/fencing |
| Memory content/metadata/confidence | `CONFIDENTIAL_CLIENT` | tenant knowledge reuse | `memories` | no automatic deletion | per-memory/source provenance, review, expiration and deletion |
| Audit actor/action/resource/payload | `OPERATIONAL_SENSITIVE` / `CONFIDENTIAL_IDENTITY` | security/accountability | `audit_events` | append-only through application; no automatic deletion | event-specific retention, immutable export, legal hold, pseudonymization and disposal |
| HTTP request log | `OPERATIONAL_SENSITIVE` | reliability/security correlation | stdout/platform sink | application sets no sink retention | deployment sink access, retention, redaction validation and deletion |
| Prometheus metric samples | `OPERATIONAL_SENSITIVE` | SLO/alerting | scrape/metrics backend | application sets no backend retention | metrics retention/cardinality/access; no tenant labels |
| SQLite/PostgreSQL backup | same as all source records, highest applicable class | recovery | local drill files; future backup store | no scheduler/retention/deletion | encryption/KMS, immutable/off-host copies, backup lag, retention/legal hold and verified expiry |
| Backup manifest/checksum/source digest | `OPERATIONAL_SENSITIVE` | restore integrity/evidence | adjacent manifest | retained with backup | signature/authenticity, evidence retention and safe disposal |
| SBOM/provenance/checksum/license evidence | `PUBLIC_PRODUCT` or `OPERATIONAL_SENSITIVE` | supply-chain audit | CI/artifacts/repository | workflow/provider dependent | release evidence retention and access; confirm no tenant content |
| Runtime version/health capability flags | `PUBLIC_PRODUCT` | operations/compatibility | API/metrics/image labels | version lifecycle | avoid host/infrastructure over-disclosure |

## 3. Retention decisions that are intentionally unresolved

The following values must not be invented by implementation:

- campaign/run retention duration;
- audit/security-log retention duration;
- session/rate-row purge window;
- backup frequency, retention generations and geographic copies;
- legal-hold override and release;
- customer termination grace/export/delete period;
- data-subject request response/verification process;
- media/source-asset retention;
- provider/subprocessor retention and model-training use;
- production telemetry retention.

Decision inputs required:

1. operating entity and controller/processor role;
2. tenant/customer contract and service promises;
3. deployment and data-subject jurisdictions;
4. business purpose and measured recovery/SLO needs;
5. security/incident evidence needs;
6. legal hold, litigation/regulatory obligations;
7. backup architecture and deletion propagation lag;
8. external providers and their deletion guarantees;
9. accountable privacy/legal, security and business owners.

## 4. Deletion and correction invariants

A future deletion/correction implementation must:

- authenticate and authorize the requester server-side;
- bind the operation to the authoritative tenant;
- provide preview/dry-run counts and stable scope identifiers;
- distinguish correction, logical restriction, purge and irreversible destruction;
- check legal hold and audit policy before mutation;
- prevent cross-tenant predicates and pooled-connection leakage;
- be idempotent and concurrency-safe;
- record request, approver, scope, reason, timestamps, result and failures without copying deleted content into the audit event;
- define whether the audit event itself is retained/pseudonymized;
- propagate to memories, run payloads, search/index/cache, telemetry and every provider;
- mark affected backups and enforce deletion at approved expiry/rewrite points;
- verify with negative cross-tenant and restore-after-deletion tests;
- provide rollback only where legally/operationally permitted;
- require explicit human authority for destructive production execution.

No such destructive API/job exists in version `0.7.0`.

## 5. Backup-specific retention boundary

A backup is not exempt from privacy/security policy. It contains all tenant/identity/audit data present at its recovery point.

Required production controls:

- separate least-privilege backup identity;
- TLS and encryption at rest with controlled keys;
- immutable/off-host copy protected from runtime compromise;
- manifest authenticity/signature in addition to checksum;
- inventory of backup time, schema/application version and tenant scope;
- RPO/RTO-derived schedule and monitored success/staleness;
- periodic isolated restore and application-read verification;
- approved retention/expiry and deletion evidence;
- legal-hold behavior;
- incident access logging;
- treatment of deleted/corrected records until backup expiry;
- documented emergency restore approval and post-restore reconciliation.

The repository demonstrates local integrity and restore mechanics only.

## 6. Telemetry retention boundary

Application minimization does not control platform defaults. Before staging/production, inspect and record:

- ingress/proxy access logs and whether they include full path/query/headers/source address;
- application stdout destination and retention;
- Kubernetes/cloud audit logs;
- database statement/error/connection logs;
- metrics labels, exemplars and retention;
- traces if introduced;
- CI/deployment logs and artifacts;
- backup job logs;
- support/incident exports.

Any telemetry containing a credential, cookie, CSRF token, request/response body, campaign content or database URL is a release-blocking defect.

## 7. Human decision template

```yaml
policy_id:
operating_entity:
customer_or_tenant_scope:
jurisdiction:
data_class_or_record:
purpose:
retention_start_event:
retention_duration:
legal_hold_override:
correction_rule:
deletion_rule:
backup_propagation_rule:
external_provider_rule:
access_roles:
monitoring_and_evidence:
effective_date:
source_and_version:
risk_classification: GREEN | YELLOW | RED | UNKNOWN
uncertainty:
privacy_legal_reviewer:
security_reviewer:
business_data_owner:
implementation_owner:
```

## 8. Current decision

```yaml
jurisdiction: UNKNOWN
source: repository architecture and runtime behavior only
version_or_effective_date: 2026-07-21; no retention policy effective
playbook_rule: >
  Preserve data without silent destructive automation while the policy is
  unresolved, minimize new collection, keep external effects disabled, and
  require explicit accountable human review before implementing or executing
  retention/deletion/legal-hold behavior.
risk_classification: YELLOW / UNKNOWN
uncertainty:
  - entity, customer terms and jurisdiction are not selected
  - no production providers or environment are authorized
  - political/client free text can change sensitivity materially
  - recovery and legal evidence needs are not measured/approved
required_human_reviewer:
  - privacy/legal reviewer
  - tenant/customer data owner
  - security and operations reviewer
```

This register is an input to human policy, not legal advice or authorization to retain/delete data.
