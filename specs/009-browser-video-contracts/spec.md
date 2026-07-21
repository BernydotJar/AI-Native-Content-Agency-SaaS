# INC-009 — Browser/video integration review and disabled contracts

## Problem

The product goal references `browser-use/video-use`, but no reviewed adapter, effect contract, credential boundary, idempotency receipt, egress policy or revocation path exists. Installing a third-party skill or invoking its helpers would grant shell, filesystem, media-upload and provider authority before those controls exist.

## Purpose

Review one exact upstream commit, preserve source integrity evidence, expose the review state safely to authenticated operators and define strict future invocation/receipt contracts while keeping execution impossible.

## Reviewed source

- Repository: `browser-use/video-use`
- Commit: `92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66`
- License: MIT
- Review date: 2026-07-21
- Installation or helper execution: none

## Actors

- viewer/auditor: inspect reviewed capability and blockers;
- operator: understand a future workflow but cannot execute it;
- approver/security reviewer: verify commit, Greenlight, egress and credential boundaries;
- integration worker: future isolated component, currently nonexistent and disabled.

## Upstream findings

- helpers invoke `ffmpeg`/`ffprobe` and write output files;
- transcription uploads local media to ElevenLabs using `ELEVENLABS_API_KEY`;
- installation downloads files and installs tools/packages into user state;
- the skill instructs persistent memory and autonomous shell/subagent workflows;
- no merged dependency lock, security policy or CI workflow exists at the reviewed commit;
- main is not protected;
- `render.py` accepts absolute and traversal paths outside the edit directory; upstream PR `#93` is open;
- no tenant binding, Greenlight, idempotency, receipt, fencing, cost or revocation contract exists.

## Invariants

- `external_effects_enabled` is always false.
- `activation_allowed` is always false for the reviewed commit.
- no upstream code or dependency is imported by the runtime.
- no execution endpoint exists.
- manifest access requires authenticated `identity:read` authority.
- tenant context is derived from the principal, never request input.
- plans contain secret references only, never values.
- paths are normalized relative virtual paths under `inputs/` or `outputs/`.
- egress hosts are exact and operation-specific.
- every future mutation requires idempotency key, Greenlight ID and positive fence.
- cost remains zero until explicit spend authorization.
- media, transcript and prompt content are untrusted.
- receipts cannot be created while disabled.

## Functional requirements

- FR-001: package immutable review metadata with exact commit and SHA-256 hashes.
- FR-002: expose authenticated read-only list/detail endpoints.
- FR-003: return `reviewed_disabled`, reason codes and required controls.
- FR-004: return server-derived tenant ID in API envelopes.
- FR-005: unknown integration uses uniform non-enumerating 404.
- FR-006: register no POST/execute route.
- FR-007: reject missing/malformed idempotency, Greenlight and fence.
- FR-008: reject absolute/traversal paths, raw secrets, unknown operations, untrusted-input omissions, unbounded size/duration and nonzero cost.
- FR-009: reject arbitrary egress.
- FR-010: future receipt schema binds plan/artifacts/provider/fence/cost but cannot be constructed while disabled.
- FR-011: OpenAPI and package verification preserve read-only behavior.
- FR-012: docs distinguish source review from activation approval.

## Acceptance criteria

- RED observed before implementation;
- exact manifest and package resource validate;
- valid review-only plan remains non-executable;
- all negative security cases fail closed;
- API proves authentication, tenant derivation, read-only OpenAPI and no audit/effect mutation;
- full SQLite/PostgreSQL/package/supply-chain regressions pass;
- no external service, binary, helper, credential or media is executed.

## Out of scope

Installation, browser automation, ffmpeg/yt-dlp, ElevenLabs, rendering, transcription, media transfer, provider credentials, package publication and activation.
