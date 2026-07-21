# Video Use integration review — disabled by design

## Decision

`browser-use/video-use` was reviewed at exact upstream commit
`92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66` on 2026-07-21. The reviewed
source is MIT-licensed, but it is **not installed, imported, executed or enabled**
in this product. The runtime status is `reviewed_disabled` and all three effect
flags remain false:

```json
{
  "activation_allowed": false,
  "execution_available": false,
  "external_effects_enabled": false
}
```

The authoritative machine-readable evidence is packaged at
`backend/agency_runtime/integration_reviews/video_use.json`. It records the
upstream commit, SHA-256 hashes for the reviewed tree, observed capabilities,
dependencies, findings and activation requirements.

## What was reviewed

The upstream project is a conversation-driven video editing skill. Its helpers
can:

- extract and render media with `ffmpeg`/`ffprobe`;
- upload extracted audio to ElevenLabs Scribe;
- write transcripts, edit decision lists, previews and final video files;
- optionally download assets with `yt-dlp`;
- instruct an agent to install dependencies, persist project memory and spawn
  additional shell-capable agents for animation work.

No helper, installer, binary, API credential, media input or external provider
was invoked during this review. Repository metadata and source files were read
only from the exact pinned commit.

## Blocking findings

| ID | Severity | Finding | Activation consequence |
|---|---|---|---|
| `VIDEO-USE-001` | HIGH | `helpers/render.py` accepts absolute paths and parent traversal outside the edit directory. Upstream PR `#93` proposes a fix but was not merged into the reviewed commit. | A patched, independently reviewed commit with fail-closed containment is mandatory. |
| `VIDEO-USE-002` | HIGH | `helpers/transcribe.py` uploads locally extracted audio to ElevenLabs using `ELEVENLABS_API_KEY`. | Provider contract, DPA/subprocessor review, jurisdiction, retention, deletion and exact egress are mandatory. |
| `VIDEO-USE-003` | HIGH | Upstream has no tenant/campaign binding, durable idempotency, Greenlight binding, fencing, receipt, cost ceiling or revocation contract compatible with this product. | A product-owned isolated adapter/outbox contract must exist before effects. |
| `VIDEO-USE-004` | MEDIUM | The reviewed commit has no merged dependency lock, repository CI workflow, security policy or protected default branch. | Dependencies and binaries must be hash/digest pinned and independently scanned. |
| `VIDEO-USE-005` | MEDIUM | The skill instructs persistent local memory and autonomous shell/subagent activity. | Ambient filesystem, credentials and agent authority must be removed by isolation. |

These findings do not affect the currently selected deterministic sandbox because
no upstream code is present in its execution path.

## Product-owned review contract

`backend/agency_runtime/integrations.py` defines a dependency-free contract for
future design review. It is not an adapter implementation.

A review-only invocation plan requires:

- exact integration and operation allowlists;
- server-derived tenant, campaign and workspace identifiers;
- a bounded idempotency key;
- exact Greenlight identifier and positive fencing token;
- canonical virtual paths under `inputs/` and `outputs/` only;
- secret references only, never secret values;
- operation-specific exact egress hosts;
- exact classification of media, transcript and prompt as untrusted;
- bounded input/output sizes, duration and attempts;
- zero authorized cost.

The only reviewed operations are:

| Operation | Secret references | Network hosts | Execution |
|---|---|---|---|
| `render_video` | none | none | denied |
| `transcribe_media` | `secret://elevenlabs/api-key` | `api.elevenlabs.io` | denied |

Even a valid plan has `execution_permitted=false`. `IntegrationRegistry.execute`
and receipt construction always raise `IntegrationDisabledError`.

## Read-only runtime surface

Authenticated identities with `identity:read` may inspect the review through:

- `GET /api/v1/integrations`
- `GET /api/v1/integrations/{integration_id}`

The tenant in each response is derived from the authenticated principal. There
is no POST, execute, transcribe, render, upload, download or credential endpoint.
Unknown identifiers use the existing uniform non-enumerating error contract.
Review reads do not write tenant audit events because they create no mutation or
authority change.

## Future receipt shape

The repository defines the fields an effect receipt would need to bind:

- integration and operation;
- tenant, campaign and workspace;
- digest of the idempotency key;
- Greenlight identifier and fencing token;
- input and output SHA-256 digests;
- provider request identifier;
- cost and completion timestamp.

This type is intentionally unconstructable through the registry while execution
is disabled. A type definition is not evidence that any provider action occurred.

## Activation checklist

Activation requires a new bounded increment and all of the following:

1. Select a patched exact upstream commit and verify every reviewed file hash.
2. Hash-lock Python/Node dependencies and digest-pin external binaries/images.
3. Run in a separate non-root worker with read-only inputs, a bounded output
   root, no host mounts and no ambient credentials.
4. Enforce operation-specific egress at the network boundary.
5. Inject short-lived secret references only after an authorized job begins.
6. Bind tenant, campaign, workspace, exact reviewed artifacts and human
   Greenlight to a durable outbound command.
7. Use provider idempotency, a transactional outbox, fencing, cancellation,
   revocation and immutable receipts.
8. Bound bytes, duration, concurrency, retries, CPU/memory, storage and cost.
9. Treat page/media/transcript/prompt content as hostile and pass semantic
   prompt-injection, harmful-use and legal-overclaim evaluations.
10. Approve provider privacy terms, regions, subprocessors, training use,
    retention, deletion and data-subject handling.
11. Add low-cardinality metrics, sanitized logs, incident response, rollback,
    cleanup and restore/deletion exercises.
12. Obtain explicit authorization for external effects and any spend.

Until every item is evidenced, the only valid operational state is
`reviewed_disabled`.

## Verification

The repository gates prove the review boundary without invoking the integration:

- hash-locked wheel tests validate manifest packaging and all fail-closed plan
  cases;
- API tests validate authentication, tenant derivation, uniform errors and
  GET-only OpenAPI;
- the non-root production image smoke validates the same manifest and absence of
  an execution route;
- full package output retains `external_side_effects_enabled=false`.
