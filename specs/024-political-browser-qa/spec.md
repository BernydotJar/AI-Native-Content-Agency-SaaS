# INC-024 — Political Browser QA and Office-Specific Messaging

Status: `review`

## Objective

Demonstrate the complete political-content authority journey in two isolated real-browser sessions without contacting a real provider, repair UX defects observed during that journey, and enforce office-specific copy for mayoral and legislative candidates.

## File-bound ownership

```yaml
task_id: INC-024
workstream_id: WS-05
role: Test Engineer / UX Reviewer / Critique Agent / Content Writer / Independent Verifier
objective: Browser-observe the political authority journey and repair reproducible UX/editorial defects.
allowed_paths:
  - .github/workflows/production-readiness.yml
  - artifacts/political-browser/**
  - backend/agency_runtime/campaign_intelligence.py
  - backend/tests/test_runtime.py
  - package.json
  - scripts/fixtures/political_browser_app.py
  - scripts/verify-political-browser.mjs
  - src/components/CampaignOutputPanel.tsx
  - src/components/CampaignOutputPanel.test.tsx
  - src/components/WorkspaceRuntime.tsx
  - src/components/WorkspaceRuntime.test.tsx
  - program/**
  - specs/024-political-browser-qa/**
read_only_paths:
  - .env.local
  - .local/**
prohibited_paths:
  - real Meta or X publication
  - raw credentials or OAuth material in evidence
  - cloud apply or paid-media spend
  - force push or protected-branch mutation
write_lock: one sequential writer across the declared paths
```

## Required journeys

1. A legal/electoral reviewer creates a grounded political run from the actual UI.
2. The durable worker visibly progresses without presenting missing downstream artifacts as failures.
3. The same reviewer is denied Greenlight with an actionable identity-separation message.
4. A second browser profile opens the same run and approves it.
5. The approved envelope contains the political compliance record and both authenticated identities.
6. The external-effect dialog requires the exact political phrase.
7. A wrong phrase keeps confirmation disabled and produces zero provider calls.
8. The exact phrase creates one mock-provider effect and one durable receipt.
9. The raw phrase never appears in SQLite or the response.
10. Screenshots and a machine-readable receipt are retained as CI artifacts.

## Editorial acceptance

- Mayoral copy references municipal governance.
- Deputy copy references legislative representation or oversight.
- Critique includes an `office_message_alignment` check.
- Unknown offices must appear literally in the rendered message.
- Source, locator, disclosure and human-review limitations remain visible.

## Safety

The browser fixture uses generated test identities and `httpx.MockTransport`. No real OAuth, social account, provider request, cloud resource or spend is permitted. The live workstation runtime remains configured with social and political publication disabled.

## Release gate

INC-024 remains `review` until the complete local regression and all eight exact-head `production-readiness` jobs pass on the published branch. Passing this increment does not authorize the neutral sandbox post or production release.
