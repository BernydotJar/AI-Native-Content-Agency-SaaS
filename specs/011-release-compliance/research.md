# Research

## Existing evidence

- Repository license: MIT.
- npm: package-lock with 19 direct packages and transitive graph.
- Python: hash-locked runtime/build/test graphs; three direct runtime packages.
- OCI: two digest-pinned bases and generated CycloneDX SBOM.
- Actions: eight unique actions, each pinned to a 40-character commit.
- License policy: exact Python runtime allowlist, mappings and one reviewed
  missing-metadata exception.
- External candidate: `video-use` exact MIT commit, `reviewed_disabled`.
- Privacy model: complete architecture inventory but UNKNOWN jurisdiction/entity,
  no effective retention/deletion/legal-hold policy.
- Public copy: generally explicit sandbox language; three unqualified autonomy/
  live phrases required correction.

## Decision

Join the evidence in strict machine-readable records and require `DENY_RELEASE`.
Do not synthesize human policy values. Static claims scanning may prove the
repository copy catalog, but not semantic legality of generated content.

## Rejected alternatives

- **Infer a default jurisdiction or 365-day retention:** rejected as fabricated
  policy with legal/destructive consequences.
- **Mark privacy complete because no provider is active:** rejected because
  runs, identity, audit, memories, telemetry and backups still require policy.
- **Treat green SBOM/license checks as final legal approval:** rejected because
  notices, trademarks, patents, service terms and distribution context remain.
- **Allow exceptions for broad marketing directories:** rejected because it
  would turn claims lint into a bypass list.
