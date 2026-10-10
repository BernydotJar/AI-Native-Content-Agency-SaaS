# ADR 0010 — AI-Native Media Factory v1: hybrid, governed video generation

- **Status:** Accepted — logical target architecture; provider spending and production activation remain separately human-gated.
- **Date:** 2026-10-10
- **Decision roles:** CTO (platform/finops), Product Owner (customer outcomes), Solution Architect (contracts/trust boundaries)
- **Applies to:** AI-Native-Content-Agency-SaaS (NOT I-DO/LUMA or other workspaces)
- **Baseline:** `main` at `a9223b0`; discovery/technical QA draft PR #45 at `473d92a`
- **Previous evidence:** `docs/integrations/video-production-engine-2026-10-10.md`, `program/architecture.md`, ADR-0007/0008/0009

## Problem / intent

Media Studio currently has a workflow and read-only provider catalog but no authorized,
durable generation worker. A customer must create and deliver differentiated videos
without learning vendor endpoints, managing desktop automation, or risking uncontrolled
retries/spend. Two upstream FreeVideo gallery clips passed technical QA; **they are
not evidence of new generation in our app**.

## Decision summary

**Choose a cloud-neutral, provider-adapter architecture with a GCP serverless
deployment target for the first authorized production pilot.**

- **Product/control plane:** Keep the existing React / TypeScript frontend and
  tenant-authenticated FastAPI backend. Do not introduce a second backend or a
  generic agent framework just for video. PostgreSQL remains the shared source
  of truth; SQLite is local single-instance only.
- **Async execution:** Introduce a dedicated video-effect/job contract and
  independently deployable worker. The DB transaction/outbox owns state and
  fencing. Cloud Tasks (GCP target) wakes workers; it is not the source of truth.
  Worker actions are explicitly authorized, idempotent where the upstream permits,
  and reconciled after unknown network outcomes. Never blindly retry billable POSTs.
- **Cinematic API gateway:** Use **fal.ai** as the first platform-managed provider
  integration for interchangeable cinematic models. Initial shortlist:
  LTX-2.3 for drafts (subject to actual price/quality validation),
  Seedance 2.0 Fast for creative iterations, Seedance 2.0 standard or Kling 3 Pro
  for quality candidates. Expose capability presets, not model IDs, by default.
  Each exact model/variant must pass a license, cost, regional-data, content-policy,
  and contract review before it is enabled. Claims of model quality remain hypotheses
  until our own blind benchmark passes.
- **HeyGen specialization / BYOK:** Provide an **optional tenant-admin HeyGen
  credential import** using server-side envelope encryption (KMS-backed secret
  references), never a browser-stored key. HeyGen APIs cover digital presenters,
  avatars, video translation, brand variants, Video Agent, and its new general video
  model. HeyGen Video may be selected as the low-cost draft model where configured,
  priced and quality-approved; it is **not** the only supported video engine.
  A shared platform-managed HeyGen account is a later commercial decision.
- **Local generation:** FreeVideo/ComfyUI and LTX-2.5 are R&D/optional compatible
  GPU workers; H3ddle is a separate Apple Silicon creative-workstation candidate.
  No GPU purchase, model download, Mac agent, or local worker is required for v1.
  Weight/model licenses are distinct from open-source code licenses and must be
  cleared for SaaS and territories before commercial activation.
- **Computer Use:** Connected macOS browser bridge is for assisted, explicitly
  approved authoring/QA and vendor web UIs, not a production background
  generation backend. Browser-tab control does not imply arbitrary native
  desktop-app control. Any later desktop adapter needs identity, app allowlisting,
  isolated sessions, supervised actions and product-owned receipts.
- **Media QA + approvals:** Technical inspection (ffprobe/ffmpeg/hash/frame/audio)
  plus independent editorial/brand/identity/rights review. Technical PASS cannot
  automatically authorize creative release or social publication.
- **Security:** Never activate the previously reviewed-disabled
  `browser-use/video-use` executor to shortcut this design. Existing HIGH findings
  retain their activation gates.

## Deployment topology selected for the first authorized pilot

Existing `infra/gcp` contains a fail-closed Cloud Run / IAM / Secret Manager /
Artifact Registry / billing-budget bootstrap. It **does not yet provision** the
entire architecture below. New resources must be individually reviewed and
authorized. No infrastructure or cloud spending is created by this ADR.

```text
[Authenticated agency client / tenant]
         |
         v
[React Studio on existing FastAPI control-plane / GCP Cloud Run target]
  - Brand profile / brief / script / shot list / references
  - tenant RBAC + ownership + evidence/consent
  - quoted max-cost budget + independent approval
  - generation history + compare candidates
         |
         v
[PostgreSQL canonical state: GCP Cloud SQL target]
  - video_job + shot + attempt + reservation + media_asset
  - transactional outbox + lease/fencing + audit + idempotency
         |
         +---> [Cloud Tasks wakeup (at least once)]
                    |
                    v
             [Separate Cloud Run video-effect worker]
                - versioned VideoProviderAdapter interface
                - secure backend-only egress to approved host
                - platform fal adapter / tenant HeyGen adapter
                - cancellation and UNKNOWN reconciliation
                - no direct final-publication permission
                    |
                  [provider queue/webhook/poll]
                    |
                    v
             [Private GCS Media Vault]
                - verified download, mime/bytes/SHA-256
                - immutable original, provenance/license
                - tenant scope, signed bounded delivery URLs
                    |
                    v
              [QA: deterministic + creative reviewer]
                    |
                    v
              [Human Greenlight -> existing publication controls]

R&D only: [GPU ComfyUI / FreeVideo / LTX] [Apple Silicon H3ddle]
Assisted only: [Cloud Sandbox browser-approved Computer Use]
```

Additional platform services selected when deployment is authorized:
- Google Cloud Run (control plane and worker), Cloud SQL for PostgreSQL,
  Cloud Storage (GCS), Cloud Tasks, Secret Manager with KMS envelope encryption,
  Cloud Logging / OpenTelemetry W3C distributed tracing, and Cloud Monitoring.
- Production media must not reside solely in the current JPEG/SQLite media vault;
  separate immutable video bytes from SQL metadata and retention records.
- Separate environments and service identities; private buckets and principle
  of least privilege. No credentials/PII/raw prompts in structured tracing.
- GCP billing budgets provide notifications, **not a kill switch**. Product-level
  cost reservations and feature flags are the real spend controls.
- Do not deploy Cloud Run backed by ephemeral SQLite. The GCP bootstrap requires
  a persistent database approval/gate. Cloudflare may be an edge/domain layer
  but is not execution/state authority.

## Stable product-level job contract (vendor neutral)

```text
VideoGenerationRequest {
  tenant_id: server_authenticated;
  project_id; campaign_id; source_artifact_id; source_artifact_sha256;
  intent: cinematic | avatar | localized | storyboard_preview;
  brief_id; shot_id; prompt_version; prompt;
  references: governed_media_asset_ids[];
  desired_duration_s; aspect_ratio; delivery_profile; locale;
  routing_policy: automatic | explicit_authorized_provider;
  quote_id; max_cost_micros; approval_id;
  idempotency_key;
}

VideoGenerationState {
  queued | reserving | submitting | provider_processing |
  retrieving | qa_pending | review_pending | approved |
  failed | cancelled | unknown;
}

VideoGenerationReceipt {
  provider; exact_model_or_engine; model_revision_or_version_when_available;
  external_request_id; provider_status; attempts; cost_quoted; cost_actual;
  parameters_hash; input_asset_hashes; output_asset_id; output_sha256;
  technical_qa_result; creative_review_record;
  retention_policy; provenance; timestamp;
}
```

Validation bounds on prompt, clip length, resolution, egress, assets and quotas
are fixed and server-enforced. An automatic retry may occur only before an
external billable request is known to have been accepted, or when the provider
has a proven idempotency/lookup contract. An uncertain submission stays
`unknown` pending read reconciliation. Callback signatures/identities must be
verified; fallback polling is rate bounded. Cloud Tasks delivery is assumed
at-least-once.

The orchestrator selects **capabilities and quality tiers**, not arbitrary
model strings supplied by an LLM or browser. Provider credentials and payment
method never belong to an agent's ambient tool context. Tenant isolation is
enforced throughout queue, storage, callback and export paths.

## Product scope — first sellable video MVP

One coherent UI journey (Spanish first, multilingual-ready):

```text
Campaign > Media Studio > New Video
  > Brief or approved script + brand + reference assets
  > Choose use case: Cinematic / Presenter / Translate
  > Choose economy or premium profile (or guided automatic selection)
  > Display concrete provider, input privacy notice and max expected spend
  > Explicit "Generate" confirmation
  > Job status and progress (reload-safe, retries visible)
  > Preview two authorized candidates / compare shot quality
  > Download/replace shot/revise
  > Technical QA + editorial approve
  > Export MP4 or hand off to separately approved publication
```

MVP IN:
- platform-managed fal provider connection and HeyGen tenant-admin BYOK;
- text-to-video, image-to-video, 16:9 + 9:16 presets, bounded short shots;
- secure async history, cancel/request reconciliation, immutable media;
- cost quote, tenant/campaign cap, redacted receipts;
- two demo journeys: cinematic shot and presenter/avatar explainer;
- independent QA and existing publication Greenlight.

MVP OUT:
- unlimited desktop-UI automation, H3ddle integration, on-prem GPU provisioning;
- training/fine-tuning models, community marketplace, arbitrary raw API endpoints;
- automatic production publication, unlimited video minutes, uncontrolled reruns;
- full nonlinear video editing suite and guaranteed quality from one generation.

## Quality, FinOps and release acceptance

Minimum technical export profile for customer-facing demo:
H.264 MP4, 1280x720 or higher (unless a specific vertical preset),
24 fps or higher, full-stream decode, compatible audio when requested,
correct duration/aspect ratio, signed hash and rights metadata. These
are encoding gates, **not** proof of artistic quality.

Creative QA dimensions scored 1–5: subject consistency, physics/interaction,
camera/art direction, brief adherence, brand safety/rights and audio alignment.
A sample passes editorial acceptance only if no blocking defect and the
human reviewer assigns an overall score >= 4/5. Blind comparison is required
to decide a default engine; benchmark prompts and seeds are versioned.

FinOps:
- quote is computed per engine, profile, time, quality, audio, reference options
  and current price/version; quotes expire and promotions are never hardcoded;
- user must approve worst-case authorized charge before submission;
- per-tenant and per-campaign limits, concurrency quotas, independent revocation,
  and post hoc reconciliation;
- no automatic re-generation that can exceed a cost reservation.

Separate production activation gate requires:
1. authorized cloud billing, tenant/data-region, secrets, vendor DPA/terms;
2. no outstanding HIGH issues for the enabled adapter;
3. exact-once/UNKNOWN and callback adversarial tests, worker crash/restart tests;
4. cross-tenant access/isolation and key rotation/revocation tests;
5. 2 real *new* end-to-end generated clips in an authorized staging environment;
6. QA/edit/export/human Greenlight proof and bounded spend receipts;
7. independent Graph Harness review, security check, trace and rollback evidence.

Existing package/script gates can pass while release remains blocked;
`DENY_RELEASE` is not overridden by an ADR or by a successful technical QA.

## Financial reference (not a quote)

As of 2026-10-10, HeyGen publicly advertises its new **HeyGen Video**
at an introductory starting price of USD 0.01/second through October,
from USD 0.02/second standard, with detailed mode-specific rates requiring
verification. Its independent API avatar/video translation pricing is a
different product; never infer a single rate for all HeyGen operations.

fal lists Seedance 2.0 720p with audio at USD 0.3034/second,
and 720p Fast with audio at USD 0.2419/second, subject to current terms and
input-specific charges. Provider-advertised quality rankings are
**not independent acceptance evidence**. All vendor prices are dynamic.

Sources (reviewed 2026-10-10):
- https://developers.heygen.com/heygen-video-1.0-catalog
- https://help.heygen.com/en/articles/10060327-heygen-api-pricing-explained
- https://fal.ai/models/bytedance/seedance-2.0/text-to-video
- https://fal.ai/models/fal-ai/ltx-2.3/text-to-video
- https://fal.ai/models/fal-ai/kling-video/v3/pro/image-to-video
- https://github.com/FlashML-org/FreeVideo
- https://github.com/AlexanderIstomin/h3ddle

## Roles and delivery

| Decision | Product Owner | CTO | Solution Architect | Release/Reviewer |
| --- | --- | --- | --- | --- |
| Outcomes/presets and demo acceptance | Accountable | Consulted | Consulted | Consulted |
| Operating cost/caps and cloud selection | Consulted | Accountable | Responsible for enforcement | Gated |
| Identity/data architecture/job contracts | Consulted | Accountable | Responsible | Verifies evidence |
| Vendor enablement and model licensing | Consulted | Accountable | Responsible | Legal/security approval |
| Editorial, brand and rights release | Accountable | Consulted | Implements gates | Human approver |
| Build and CI/QA/Graph Evidence | Defines acceptance | Oversees | Responsible | Independent verifier |

Delivery sequence (no feature is silently enabled):
- **Slice A: Contract / vault** — accepted ADR, admin BYOK + price/approval contract,
  explicit states and untrusted-input negative tests.
- **Slice B: Worker / media** — provider fal + HeyGen adapters, effect/outbox,
  reconciliation, storage, distributed tracing, upload + metadata.
- **Slice C: Sellable experience** — creative UI, preview, quality/eval, export,
  two paid-authorized staging renders, operator documentation.
- **Slice D (after usage evidence):** optional local GPU provider and specialized
  macOS-assisted workflows only if marginal cost and reliability justify them.

## Alternatives rejected

1. **HeyGen-only backend:** convenient but constrains cost/quality/model evolution.
2. **ComfyUI/FreeVideo local-only production:** no available GPU; model license,
   scheduling, ops and durability would block time to market.
3. **Desktop Computer Use as universal backend:** interactive, approval-dependent,
   workstation-tied, not multi-tenant reproducible infrastructure.
4. **Direct browser -> provider API:** leaks secrets and bypasses governance.
5. **New microservice fleet or Kubernetes-first GPU cluster:** unjustified current
   product scope and operating cost; retain modular monolith plus one worker.
6. **Automated publication after render:** violates independent Greenlight control.
