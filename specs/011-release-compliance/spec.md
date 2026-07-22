# INC-011 — Release compliance, privacy and third-party review

## Problem

Technical gates and privacy notes exist, but no executable release decision
joins third-party inventory, license evidence, provider/data disclosures, public
claims and accountable human approvals. Green CI must not be mistaken for legal,
privacy or production approval.

## Objective

Create a versioned fail-closed compliance control that proves safe
repository-local review, rejects unsupported public claims and preserves unknown
jurisdiction, retention, deletion, legal-hold and provider decisions as explicit
human blockers.

## Invariants

- Technical verification is not legal advice or regulatory certification.
- Unknown jurisdiction/entity/controller-role values are never inferred.
- No retention duration is invented while policy is unapproved.
- No destructive deletion/legal-hold automation or external provider is enabled.
- Direct dependencies, base images, Actions and reviewed external candidates are
  tied to lock/hash evidence.
- Public surfaces qualify autonomy/live/production/effect claims as local sandbox.
- Release, apply, external effects and destructive actions remain denied while
  required approvals or HIGH blockers remain open.

## Requirements

1. Machine-readable third-party inventory cross-checks repository license,
   npm/Python direct dependencies, OCI bases, GitHub Actions and `video-use`.
2. Privacy register records UNKNOWN/unapproved decisions, data classes,
   providers, reviewers and resume conditions.
3. Claims policy scans exact public surfaces and rejects legal, compliance,
   production, live-research, guaranteed-security and unqualified autonomy copy.
4. Release decision requires `DENY_RELEASE`, `DENY_APPLY`, no effects and no
   destructive action while blockers remain.
5. A stdlib validator rejects schema drift, stale evidence, duplicate IDs,
   enabled unknown providers, invented retention, unsupported approvals, missing
   disclosures and prohibited copy.
6. CI/tests execute the validator and negative mutations.
7. Documentation distinguishes proof, unknowns and accountable approvals.

## Acceptance

- Validator and negative fixtures pass.
- UI removes unqualified autonomous/live language.
- Full frontend/backend/PostgreSQL/package/infra/supply-chain regression passes.
- `LEGAL-001` remains proven.
- `LEGAL-002` becomes strongly evidenced but human-blocked.
- Static `LEGAL-003` claims control is proven; semantic/human review remains with
  INC-010/accountable reviewers.
- No provider, destructive operation, deployment, publication or spend occurs.

## Out of scope

Selecting jurisdiction/entity, approving retention/deletion/legal hold, legal
advice, provider contracts/DPAs, data-subject execution, provider activation,
release, merge or cloud apply.
