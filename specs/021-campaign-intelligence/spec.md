# INC-021 — Campaign Intelligence and Political Content Integrity

Status: approved
Owner: Orchestrator
Date: 2026-07-25

## Problem

The current writer is a deterministic English fixture and can create generic mixed-language copy. Political campaign content needs structured context, claim provenance, channel-specific Spanish copy, media direction and a fail-closed critique before Greenlight or external publication.

## Scope

### task_id: INC-021
### workstream_id: WS-13
### role: Producer / Critic / Fixer / Independent Verifier
### objective

Produce a backward-compatible structured campaign brief and meaningful eight-station artifacts for political organic content while preserving disabled-by-default external effects.

### allowed_paths

- `backend/agency_runtime/models.py`
- `backend/agency_runtime/api.py`
- `backend/agency_runtime/orchestrator.py`
- `backend/agency_runtime/campaign_intelligence.py`
- `backend/agency_runtime/serialization.py`
- `backend/tests/test_runtime.py`
- `backend/tests/test_api.py`
- `src/lib/runtimeApi.ts`
- `src/components/WorkspaceRuntime.tsx`
- `src/components/WorkspaceRuntime.test.tsx`
- `program/**`
- `specs/021-campaign-intelligence/**`

### read_only_paths

- `backend/agency_runtime/social_oauth*`
- `backend/agency_runtime/social_publication*`
- `compliance/**`

### prohibited_paths

- `.env.local`
- credentials
- external infrastructure
- protected branches
- real political publication

### write_lock

Single writer: Orchestrator. Reviewer roles are read-only.

## Brief contract

Existing commercial briefs remain valid. A `campaign_type=political` brief additionally requires:

- locale;
- jurisdiction;
- office;
- candidate_name;
- locality;
- problem;
- proposal;
- desired_action;
- disclosure;
- one or more evidence claims containing statement, source and locator.

The API rejects missing political context before run creation.

## Required station outputs

1. CEO: mission charter with campaign classification and external-effect boundaries.
2. Research: claim ledger with stable claim IDs and provenance.
3. Strategist: audience tension, message thesis, proof strategy and CTA.
4. Growth: organic objective, primary metric and guardrails; no fabricated forecast claims.
5. Writer: Spanish channel variants with hook, body, CTA, disclosure and claim map.
6. Media: Instagram carousel plan, slide copy, dimensions and alt text; rendering remains false.
7. Risk/Critique: language consistency, evidence coverage, office relevance, unsupported promotion, disclosure and publication eligibility.
8. Publisher: package only after Greenlight; no external effect.

## Safety invariants

- No unsupported factual claim may be marked supported.
- No electoral result, popularity, polling, endorsement or guarantee is invented.
- Political publication remains disabled by default.
- Greenlight and publication preparation require `publication_eligible=true` for political runs.
- Existing tenant isolation, idempotency, fencing and audit behavior remain unchanged.

## Acceptance criteria

- Political brief missing evidence returns HTTP 422.
- Valid political brief produces seven pre-Greenlight artifacts and Spanish copy.
- Every writer claim maps to a claim ledger ID.
- Risk report is explicit and publication eligible only when all required checks pass.
- Existing commercial API tests remain compatible.
- Serialization preserves new fields across restart.
- Frontend can create a structured political brief without exposing secrets.

## Validation commands

- `python -m unittest backend.tests.test_runtime -v`
- `python -m unittest backend.tests.test_api -v`
- `npm test -- --run src/components/WorkspaceRuntime.test.tsx`
- `npm run lint`
- `npm run build`
- `git diff --check`

## Human gates

- legal interpretation for a real jurisdiction;
- real candidate/campaign approval;
- Greenlight;
- enabling social publication;
- real external publication.
