# Release compliance review — version 0.7.0

Status: repository-local controls complete; accountable human decisions blocked

Release decision: `DENY_RELEASE`

Cloud decision: `DENY_APPLY`

External providers active: zero

This review is an engineering and evidence control. It is not legal advice,
regulatory certification, a privacy opinion, or authorization to release,
deploy, delete data, contact a provider, publish content, or spend money.

## Executable evidence

Four versioned records are authoritative for this slice:

- `compliance/third-party-inventory.json`
- `compliance/privacy-decision-register.json`
- `compliance/public-claims-policy.json`
- `compliance/release-decision.json`

`scripts/verify-release-compliance.py` validates them against the live repository.
It recomputes evidence hashes, direct package versions/licenses, base-image
digests, GitHub Action SHAs, the exact `video-use` review manifest, privacy
unknowns, public copy and unresolved release blockers. Unknown keys, malformed
collections and drift fail closed.

Run:

```bash
npm run validate:compliance
```

Expected current result:

```text
compliance_state=pass
release_decision=DENY_RELEASE
third_party_components=33
active_external_providers=0
open_human_decisions=8
claim_surfaces=10
```

A passing validator proves consistency of the denial and inventory. It does not
turn the decision into `ALLOW_RELEASE`.

## Third-party inventory boundary

The machine inventory covers the direct surfaces that this repository controls:

- 19 direct npm runtime/development packages with exact lock versions and
  declared licenses;
- four direct Python runtime packages with exact hash-lock versions and
  reviewed licenses;
- two OCI base images pinned by SHA-256 digest;
- eight GitHub Actions pinned by full 40-character commit;
- one external integration candidate, `browser-use/video-use`, pinned to exact
  commit `92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66`, MIT-licensed and
  `reviewed_disabled`.

Transitive npm, Python and operating-system packages remain evidenced by
`package-lock.json`, `backend/requirements.lock` and the CycloneDX OCI SBOM
produced by `scripts/verify-supply-chain.sh`. The supply-chain license policy is
automated evidence, not a substitute for final counsel review of distribution,
notices, trademarks, patents or service terms.

See [Third-party review inventory](third-party-notices.md).

## Provider and data-transfer boundary

No external provider is active. The only named candidate is ElevenLabs Scribe
inside the disabled `video-use` source review. Its possible data category is
`media_audio`; contract, region, retention, deletion and training-use states are
all `UNKNOWN`. No credential, media or request was used.

Activating any provider requires, at minimum:

1. an exact provider contract and approved DPA/subprocessor inventory;
2. selected regions and international-transfer analysis;
3. documented training-use, telemetry, retention and deletion behavior;
4. server-side short-lived secret references and exact egress controls;
5. tenant/artifact-bound Greenlight, idempotency, fencing, receipt and
   revocation;
6. accountable privacy/legal, security and business approval.

## Privacy decision boundary

The repository does not infer facts that only accountable humans can establish.
The following remain `UNKNOWN`:

- operating entity;
- jurisdiction;
- controller/processor role;
- effective customer/tenant policy source;
- provider contract, region, retention, deletion and training use.

Seven data-policy scopes remain `unapproved` and therefore contain no invented
retention duration:

- campaign runs;
- sessions/authentication;
- audit events;
- memories;
- telemetry;
- backups;
- future provider media.

Deletion and legal-hold automation remain false. No destructive API/job exists.
The exact continuation template is in
`docs/privacy/data-classification-retention.md`.

## Public claims boundary

The claims policy scans ten public product surfaces. It rejects:

- `production-ready`;
- unsupported GDPR/HIPAA/SOC 2/PCI compliance or certification;
- legal approval/certification claims;
- guaranteed or fully secure claims;
- live or real-time research claims;
- unqualified autonomous-cycle/live-signal wording;
- automatic-publication claims.

Required disclosures preserve the actual scope: sandbox candidate, simulated
signals, no production/staging evidence, no external publication/rendering/spend,
and no legal/privacy/regulatory approval.

The prior UI phrases “Autonomous content operations”, “Launch autonomous cycle”
and “Follow the live signal” were replaced with local sandbox wording. This is a
copy correction, not a reduction in functional behavior.

Static scanning does not prove that every generated campaign statement is
legally safe. Semantic prompt-injection, groundedness, harmful-use and legal-
overclaim evaluation remains owned by `INC-010`; accountable human review remains
mandatory.

## Release decision

The machine release record denies release because these HIGH findings are
unresolved:

| Finding | State | Resume condition |
|---|---|---|
| `F-004` | external blocker | authorized staging target, reviewed plan and runtime observation |
| `F-007` | open | accountable screen-reader, rendered contrast, 400% zoom/reflow and visual review |
| `F-008` | open | authorized scheduler, KMS/encryption, immutable off-host retention and real alert delivery |
| `F-010` | open | approved jurisdiction, retention, deletion, correction, legal hold and data-subject workflow |
| `F-011` | open | semantic/adversarial release eval harness and threshold |

The decision also records:

```text
allow_release=false
allow_cloud_apply=false
allow_external_effects=false
allow_destructive_data_action=false
legal_privacy_approval=false
independent_human_approval=false
```

## Required human reviewers

The privacy/legal continuation requires three accountable roles:

- privacy/legal reviewer;
- security reviewer;
- business/data owner.

A future approval must record the exact policy source/version, effective date,
entity, customer scope, jurisdiction, controller/processor role, retention start
event and duration, deletion/correction/legal-hold behavior, backup propagation,
provider rules, uncertainty and named reviewers. Repository automation must then
be updated and independently reverified on the exact release tree.

## What this slice proves

- inventory is tied to authoritative locks/digests/SHAs;
- direct component licenses are explicit and allowlisted for this sandbox
  candidate;
- no provider is active;
- unknown privacy decisions remain unknown;
- no destructive automation is enabled;
- public copy does not contain the prohibited claims catalog;
- release/apply/effects remain denied while blockers remain;
- negative mutations fail closed.

## What this slice does not prove

- legal compliance in any jurisdiction;
- regulatory certification;
- an approved retention/deletion/legal-hold policy;
- provider contractual/privacy suitability;
- production/staging operation;
- manual accessibility approval;
- semantic safety or citation fidelity;
- authorization to release, deploy, publish, delete, contact providers or spend.
