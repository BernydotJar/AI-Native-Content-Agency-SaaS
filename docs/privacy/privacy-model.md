# Privacy Model — Native / War Room

Status: authoritative product/privacy architecture record for PR #3
Model date: 2026-07-21
Runtime version: `0.7.0`
Jurisdiction: `UNKNOWN` until a customer, operating entity and deployment location are selected
Risk classification: `YELLOW / UNKNOWN`
Required human reviewer: accountable privacy/legal reviewer plus tenant data owner before production

## 1. Purpose and privacy objective

The product helps an agency team convert a client campaign brief into a reviewable package using deterministic local agents and a human Greenlight. Privacy controls must minimize collection, preserve tenant separation, prevent operational telemetry from becoming a content replica, and keep destructive retention/deletion decisions human-gated until jurisdiction and contractual obligations are known.

This model describes implemented data flows and technical controls. It does not approve a privacy notice, retention schedule, data-processing agreement, international transfer mechanism or legal basis.

## 2. Data subjects and content context

Potential data subjects include:

- agency operators, reviewers, tenant administrators and auditors;
- client contacts named in campaign briefs or reviewer notes;
- individuals mentioned in source assets, evidence, campaign content or memories;
- members of an intended audience described by a campaign;
- people visible or identifiable in future uploaded media.

The product is intended for political/community/content operations. Campaign text may reveal opinions, affiliations, civic activity, location, health, socioeconomic circumstances or other sensitive context even when no dedicated field asks for it. Sensitivity must be assessed from content and use, not only schema names.

The current runtime does not intentionally collect biometrics, precise location, payment cards, government identifiers or children's data. Free text can nevertheless contain them; the UI/API does not yet provide automated sensitive-data detection or redaction.

## 3. Data inventory and purpose

| Data set | Representative fields | Purpose | Storage | Current minimization/control |
|---|---|---|---|---|
| Identity configuration | tenant ID, subject ID, role, key ID, active flag, credential digest | authenticate and authorize named operators | server configuration/environment | no raw API key persisted; client tenant/role ignored |
| Browser sessions | tenant/subject/key ID, credential fingerprint, token/CSRF hashes, issued/expiry/revoked timestamps | same-origin browser authentication and revocation | SQLite/PostgreSQL | raw cookie/CSRF not stored; bounded TTL; revocable |
| Authentication rate state | one-way source/credential bucket hashes, timestamps/failure count | brute-force and spray resistance | SQLite/PostgreSQL | no raw IP/key; bounded window |
| Campaign brief | title, objective, audience, platforms, budget, goal, optional source asset | generate a campaign package | run payload in SQLite/PostgreSQL | field/list/body limits; no external provider call |
| Agent trace/evidence/artifacts | agent IDs, summaries, claims, sources, artifact content/IDs/hashes | explain and review deterministic output | run payload | tenant-scoped; exact hash binding |
| Greenlight | decision, exact artifacts/hashes, reviewer, note, timestamp | human governance of package | run record + audit | approver/admin only; transactionally bound |
| Tenant memory | content, metadata, confidence, timestamps/IDs | reuse relevant tenant knowledge | SQLite/PostgreSQL | namespace/tenant-scoped search; no cross-tenant query |
| Audit events | tenant, request ID, time, action, resource, actor, bounded payload | accountability and incident investigation | SQLite/PostgreSQL | tenant-scoped; no credentials/body/raw IP in security denials |
| HTTP logs | request ID, method, route template, status, duration, authenticated tenant ID | operations and correlation | process/platform log sink | no query string, body, token, subject or raw exception message |
| Metrics | bounded route/status/auth/security/session counters and latency | SLO/alerting | Prometheus endpoint/scrape system | no tenant, subject, permission, content or raw resource ID labels |
| Backups | complete database state plus strict manifest | recovery | local file in repository drill; future external storage | private mode, checksum/integrity; no URL/password in manifest |
| Build/supply-chain evidence | dependency/image metadata, checksums, SBOM/provenance | reproducibility and release audit | CI artifacts/repository outputs | should contain no tenant/client content |

## 4. Data-flow and disclosure boundaries

```text
Operator/client input
  -> FastAPI request-size and schema validation
  -> authenticated tenant/role binding
  -> tenant-scoped SQLite/PostgreSQL
  -> deterministic local orchestrator/sandbox tools
  -> reviewed artifacts and Greenlight

Operational derivative data
  -> sanitized logs (no body/query/token)
  -> low-cardinality metrics (no tenant/identity/content labels)
  -> tenant audit events (bounded actor/action/resource/payload)
  -> checksummed backup (same sensitivity as source database)
```

No active adapter transmits campaign content to a model provider, social network, browser automation service, media generator, analytics vendor or ad platform. Enabling any such transmission changes the processor/subprocessor and international-transfer boundary and requires a new privacy review and explicit human authorization.

The `video-use` registry entry contains only public upstream metadata, source hashes and review findings. It contains no tenant media, transcript, credential or provider response. The reviewed upstream transcription path would disclose extracted audio to ElevenLabs, so it remains disabled pending provider/subprocessor, region, retention, deletion, training-use and data-subject review.

## 5. Privacy principles applied

### Purpose limitation

Data is used for authentication, tenant-authorized campaign preparation, human review, audit, security, operations and recovery. The repository does not implement secondary advertising profiles, sale/sharing, model training or external publication.

### Minimization

- tenant, subject, role and key ID come from server configuration rather than arbitrary request fields;
- credentials/session/CSRF are stored only as digests/hashes;
- rate limits store one-way buckets rather than raw source address/API key;
- HTTP logs exclude query/body/token and use route templates;
- metrics exclude tenant/identity/content labels;
- validation/public errors do not reflect submitted content;
- anonymous authentication failures are not assigned to an unproven tenant audit ledger;
- backup manifests store an opaque source digest rather than connection URL/path.

### Accuracy and provenance

Runs store deterministic evidence, artifact hashes and exact Greenlight state. This improves operational provenance but does not establish factual truth, legal accuracy or publication rights. Semantic groundedness/citation evals remain incomplete.

### Security and confidentiality

Server-side authentication/RBAC/tenant binding, session CSRF, durable rate limiting, request-size limits, uniform public errors, tenant-leading data access, denial audit, supply-chain gates and recovery drills are implemented. Open security findings are documented in `docs/security/threat-model.md`.

### Storage limitation

No approved retention schedule or automatic deletion engine exists. Data persists until an operator performs an explicitly authorized environment/data action. This is a release gap, not a default policy recommendation.

### Accountability

Program traceability, audit events, request IDs, backup manifests and exact-commit CI provide evidence. The audit ledger is not cryptographically signed/immutably exported and therefore is not independent proof against a database owner.

## 6. Tenant isolation and access

- Every durable business/security record is keyed or queried by server-derived tenant ID.
- Cross-tenant run access returns the same 404 contract as a missing run.
- Audit pagination is tenant-scoped.
- Browser sessions and rate buckets include tenant/credential context after authentication.
- PostgreSQL shared-state tests demonstrate cross-instance behavior and negative tenant access.
- Current defense relies primarily on application SQL predicates/composite keys. PostgreSQL Row Level Security is not implemented, and the production runtime role is not yet proven non-owner/least privilege. This is a HIGH release finding.

Tenant administrators and auditors can access operational data according to RBAC. The product does not yet expose field-level privacy roles, per-campaign access groups, legal-hold controls or delegated data-subject workflows.

## 7. Telemetry and error privacy

### Public responses

`public-error.v1` returns only a stable code, safe detail and request ID. Validation errors expose bounded field locations/types without submitted input. Authentication state, role, permission, foreign resource ID, conflict state and internal exception message are suppressed.

### HTTP logs

Application logs contain:

- timestamp;
- request ID;
- HTTP method;
- route template, not raw path/query;
- status and duration;
- authenticated tenant ID when proven.

They do not intentionally contain subject ID, API key, session/CSRF token, request/response body, campaign content or raw source IP. The hosting proxy/platform/database may produce additional logs; those require deployment review.

### Metrics

Labels are bounded to method, route template, status, auth outcome, session event and security-denial reason. Tenant, subject, key/permission, content, run ID and source address are prohibited labels.

### Audit

Tenant audit can include subject-derived actor, role and bounded resource/action context because it supports tenant accountability. Authenticated RBAC/CSRF denials are durable. Anonymous failures remain in hashed rate state/metrics/logs because tenant attribution is not proven.

## 8. Retention and deletion state

Current behavior:

- runs, audit, memories, rate-limit/session rows and backups are not subject to a product-level retention scheduler;
- sessions expire logically and can be revoked, but expired/revoked rows are not automatically purged;
- rate-limit windows stop affecting authentication after expiry, but historical rows may remain;
- no tenant deletion, campaign deletion, memory erasure, audit retention, legal hold or backup-expiry API exists;
- destructive database/file operations remain human-gated.

Production requires an approved matrix covering business need, contractual terms, jurisdiction, legal hold, audit/security obligations, backup lag and data-subject rights. Technical deletion must be tested across primary database, memory, audit, caches, backups and external processors before activation.

See `docs/privacy/data-classification-retention.md` for the decision inventory and exact blockers.

## 9. Data-subject and tenant requests

The repository has no automated access/export/correction/deletion portal. Until one is specified, a request must follow a human-controlled procedure:

1. identify operating entity, customer/tenant and jurisdiction;
2. verify requester authority without recording excess identity evidence;
3. identify relevant tenant/run/memory/audit/backup scope;
4. check legal hold and contractual constraints;
5. export/correct/delete only through reviewed tools;
6. preserve an auditable decision record without retaining unnecessary submitted identity documents;
7. verify primary and downstream/backups according to the approved policy;
8. obtain accountable privacy/legal sign-off where required.

No destructive action is authorized by this document.

## 10. Privacy risk register

| ID | Risk | Current control | Residual / required action | Classification |
|---|---|---|---|---|
| P-001 | Free text contains sensitive/political/personal data not anticipated by schema. | Tenant scope, no external adapters, body limits, human review. | Add content warning/classification/redaction workflow and customer policy. | HIGH open |
| P-002 | Cross-tenant disclosure through application/database defect. | Composite keys, tenant-leading predicates, uniform 404 and negative tests. | Add RLS/least-privilege role and independent leakage red team. | HIGH open |
| P-003 | Error/log/metric reflects content or credentials. | Uniform redacted errors, route logs, bounded metrics, tests. | Verify proxy/platform/database telemetry in staging. | MEDIUM deployment |
| P-004 | Audit stores excess identity/security detail. | Bounded payload; no token/body/raw IP. | Define audit purpose/retention, pseudonymization and immutable export. | MEDIUM open |
| P-005 | Data retained indefinitely or deleted inconsistently. | No silent auto-deletion; destructive actions human-gated. | Approve policy and implement/test primary, backup and processor deletion. | HIGH open |
| P-006 | Backup copied without encryption/access controls. | Private local files, checksums, URL/password redaction, restore drill. | Encrypted immutable off-host storage, least privilege, retention/monitoring. | HIGH deployment |
| P-007 | Future provider/browser/publisher receives data without review. | All external adapters disabled; exact `video-use` source/egress review is packaged read-only with no executor. | Provider contract, subprocessor/transfer/training/telemetry/deletion review and explicit activation per adapter. | Controlled until activation |
| P-008 | Operator/admin over-access inside tenant. | RBAC and tenant audit. | Field/campaign scoping, periodic access review and managed identity lifecycle. | MEDIUM open |
| P-009 | Political campaign output used for harmful profiling/targeting or unsupported claims. | Deterministic sandbox, zero spend/publication, Greenlight. | Product policy, semantic/legal evals and accountable review before effects. | HIGH open |
| P-010 | Data-subject request cannot be fulfilled completely. | Manual inventory and human gate. | Implement verified export/correction/deletion and backup handling after policy. | HIGH open |

## 11. External parties and subprocessors

Active runtime data disclosures to external content/model/social/media providers: **none**.

Infrastructure, source hosting and CI services may process repository/build metadata according to the environment owner; the repository does not contain a complete contractual vendor inventory. A production deployment must record:

- operating entity/controller/processor roles;
- tenant/customer contract role;
- cloud/region/database/log/backup providers;
- model/browser/media/social providers;
- purpose and data categories per provider;
- retention, training/use, telemetry and deletion terms;
- transfer locations/mechanisms where applicable;
- incident/subprocessor notification obligations;
- effective dates and accountable reviewer.

## 12. Legal/privacy decision record

```yaml
jurisdiction: UNKNOWN
source:
  - repository runtime and program evidence
  - customer/deployment facts not yet selected
version_or_effective_date: 2026-07-21 architecture model; no legal policy effective
playbook_rule: >
  Do not infer legal basis, retention, notice, consent, transfer authority or
  sensitive-data permissibility. Identify jurisdiction and accountable entity,
  obtain source-specific human legal/privacy review, then implement the approved
  technical policy.
risk_classification: YELLOW / UNKNOWN
uncertainty:
  - operating entity and customer contract are unknown
  - deployment region and providers are unknown
  - campaign data categories vary by tenant/content
  - no approved retention/deletion schedule exists
required_human_reviewer:
  - accountable privacy/legal reviewer
  - tenant/customer data owner
  - security/operations reviewer for technical enforcement
```

## 13. Production privacy gates

A production-ready declaration requires at minimum:

- identified jurisdiction, entity roles and data inventory approved by humans;
- published customer/operator notices and contracts reviewed outside this agent;
- approved retention/deletion/legal-hold matrix;
- tested tenant export/correction/deletion, including backups and processors;
- managed identity and periodic access review;
- PostgreSQL RLS or equivalent independently verified defense-in-depth plus non-owner runtime role;
- encrypted scheduled backups and telemetry retention controls;
- staging verification of proxy/platform/database logs;
- provider/subprocessor review before each external adapter;
- semantic/legal-overclaim and harmful-use evals;
- zero open CRITICAL/HIGH privacy/security findings for the release scope.

This model documents risk and technical boundaries; it does not constitute legal approval.
