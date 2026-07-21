# INC-007 — Backend-first operator journey review

Date: 2026-07-21
Branch: `agent/inc-007-operator-journey`
Stacked base: `agent/inc-005-operability@ca9caf80320c3279d631f6b08d8f37f0508035be`
Verifier repair commit: `bdd908c9cfcbb81c5620229b9a31b0c3fe1fc33a`
Implementation commit: `4f101221d3ddfb426aded5e7f4caec9c87985b32`
Status: `CHECKPOINT_COMPLETED — EXACT_REMOTE_CI_PASS`
External effects: none

## Review contract

```yaml
task_id: INC-007
workstream_id: WS-05
producer: Frontend Engineer
critic: Security and Production UX Reviewer
fixer: Frontend Engineer
independent_verifier: package/runtime gate plus remote CI pending
objective: >
  Make the backend-backed production console understandable and recoverable
  for non-technical operators without turning frontend role state into authority.
human_gates:
  - merge
  - production deployment
  - external publication or spend
  - manual accessibility acceptance
```

## Delivered behavior

- Named secure-session restoration state before signed-out controls appear.
- Server-issued role guidance for viewer, operator, approver and admin.
- Viewer and approver tenant-scoped run lookup without create authority.
- Operator create authority without Greenlight decision controls.
- Approver/admin exact Greenlight decision and revocation controls.
- Stable UI states for `401`, `403`, `404`, `409`, `422`, `429`, `500` and `503`.
- Request IDs shown for support while raw backend detail and permission names remain hidden.
- `Retry-After` parsed into bounded retry guidance.
- Ambiguous create retry preserves the same idempotency key.
- Conflict/not-found recovery can reload a known run from the backend.
- Session expiry clears run, audit, lookup and command-key state.
- Audit loading, empty, success and degraded states.
- Publication remains visibly and behaviorally disabled.

## Critic findings and repair

| ID | Severity | Finding | Repair | State |
|---|---|---|---|---|
| C-007-01 | MEDIUM | A restoring HttpOnly session was indistinguishable from signed-out state. | Added explicit restoration phase and live status. | closed |
| C-007-02 | HIGH | All authenticated roles saw mutation controls, encouraging predictable forbidden calls and misleading users. | Added role-derived guidance and disabled/omitted controls while retaining server authorization as authority. | closed |
| C-007-03 | MEDIUM | Approvers/viewers could not load an existing run because only creators could obtain a run in the UI. | Added tenant-scoped GET-by-ID lookup available to authenticated roles. | closed |
| C-007-04 | MEDIUM | Generic error rendering reflected backend detail and collapsed conflict, rate limit and dependency states. | Added bounded status classifier, request correlation and non-reflection tests. | closed |
| C-007-05 | MEDIUM | A `401` could leave protected run/audit/idempotency state in memory. | Centralized fail-closed protected-state clearing. | closed |
| C-007-06 | LOW | Package verifier referenced an unset `PYTHON_BIN` under `set -u`. | Added explicit default and command preflight. | closed |

No CRITICAL or HIGH finding remains open within this slice. Global release findings remain unchanged.

## Verification evidence

```text
Focused component/client contracts       PASS — 20/20
Frontend full regression                 PASS — 48/48
Oxlint                                    PASS — 0 warnings, 0 errors
TypeScript/Vite production build         PASS
Program validator                        PASS — 79 requirements, 12 tasks
Production package                       PASS — Buildah vfs/chroot non-root runtime
Helm and operability contract            PASS
Session/RBAC/Greenlight/audit smoke       PASS
External side effects                    false
Actionlint                               PASS
Gitleaks current worktree                PASS — zero findings
git diff --check                         PASS
```

The exact base `ca9caf8` passed all eight GitHub Actions jobs in run `29873483636`. Those results establish the stacked base only; they do not substitute for exact-head CI on this increment.

## Accessibility boundary

Automated tests prove labels, roles, disabled controls, live status text and minimum control sizing encoded in the component. They do not prove:

- manual keyboard order;
- screen-reader behavior;
- contrast measurement;
- 400% zoom/reflow;
- reduced-motion review;
- mobile visual quality.

Those remain release evidence under `INC-008` / `F-007`.

## Delivery boundary

```text
specified: yes
implemented: 4f101221d3ddfb426aded5e7f4caec9c87985b32
tested_local: yes
package_verified_local: yes
reviewed_local: yes
committed: yes
pushed: yes — a3cff4305c4f1f98158bdda5d416e5f7544bff47
remote_sha_verified: yes
draft_pr: yes — #6
exact_head_ci: yes — run 29874536962, 8/8
merged: no
deployed: no
```

## Exact continuation condition

Publish this closure checkpoint and require its documentation-only exact-head CI. Then start `INC-008` from the verified branch head; manual accessibility evidence remains a separate release gate.
