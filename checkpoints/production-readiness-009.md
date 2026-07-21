# Production Readiness Checkpoint 009

## Increment

Add immutable container inputs, SBOM generation, vulnerability/license policy, provenance evidence and local signature verification without publishing an image.

## Remediation and design decisions

1. Installed Syft `1.48.0`, Grype `0.116.0`, Cosign `3.1.2` and Crane `0.21.7` as checksum-verified local binaries.
2. Resolved the Node and Python base tags through the registry and verified Linux ARM64 and AMD64 manifests.
3. Pinned all Dockerfile base images by immutable index digest.
4. The first Python 3.12 Debian slim scan reported 7 Critical and 30 High findings.
5. Python 3.13 Debian slim reduced the result to 7 Critical and 23 High findings.
6. Python 3.13.14 on Alpine 3.23 reduced the result to 0 Critical, 5 High and 8 Medium findings and passed runtime health/readiness.
7. Adopted Alpine and adjusted non-root user creation for UID/GID `10001`.
8. Added an exact, expiring baseline rather than a blanket severity waiver.
9. Added application dependency license policy and aligned the local wheel metadata with the repository MIT license.
10. Added in-toto/SLSA-style provenance and offline Cosign signing/verification with an ephemeral key.
11. Pinned every GitHub Action in the production-readiness workflow to a full commit SHA.
12. Added CI artifact retention for supply-chain evidence without registry publication.

## Delivered

- immutable base-image references in `Dockerfile`;
- `artifacts/supply-chain/base-images.json`;
- `artifacts/supply-chain/vulnerability-baseline.json`;
- `artifacts/supply-chain/license-policy.json`;
- `scripts/install-supply-chain-tools.sh`;
- `scripts/evaluate-supply-chain.py`;
- `scripts/verify-supply-chain.sh`;
- policy unit tests;
- `docs/SUPPLY_CHAIN_SECURITY.md`;
- ADR 0005;
- SHA-pinned GitHub Actions and a supply-chain CI job.

## Verification evidence

- immutable base images: 2 exact references verified;
- required manifests: Linux AMD64 and ARM64 present for both images;
- final runtime: Python `3.13.14`, Alpine `3.23.5`;
- OCI image build/export: pass with Buildah `vfs` + `chroot`;
- CycloneDX SBOM: generated;
- Grype report: generated from the SBOM;
- vulnerability policy: 0 Critical, 5 exact accepted High, 8 Medium;
- baseline expiry: 21 August 2026;
- Python license policy: 21 packages evaluated, no policy errors;
- provenance: in-toto statement bound to a clean Git commit, immutable inputs and artifact hashes;
- Cosign: image archive and provenance signed and verified offline;
- registry publication: false;
- five policy negative/positive tests: Critical/new High/stale/expired baseline and denied/missing licenses rejected;
- application package smoke: full Alpine health/readiness/session/CSRF/run/Scholar/Greenlight/package/audit/metrics/revocation matrix pending final clean-source rerun.

## Security boundary

The five High findings remain accepted only until the stated baseline expiry or the next base-image change. They are not hidden or globally ignored. Any Critical, new High, unreviewed scanner fix, stale baseline item or expired baseline fails the gate.

The Cosign key is ephemeral and the verification skips the transparency log. This proves local artifact consistency, not production release identity.

## Remaining release gate

A production release still requires an immutable registry, protected environment approval, push by digest, keyless OIDC or KMS-backed signing, transparency-log verification, attached SBOM/provenance and deployment admission policy.

## Next highest-value increment

Replace tenant-wide static credentials with managed individual identity/RBAC and add rate limiting/credential rotation, or migrate durable state to PostgreSQL for horizontal availability before any public pilot.
