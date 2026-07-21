# ADR 0005: Immutable Image Evidence and Expiring Vulnerability Baselines

- Status: Accepted
- Date: 21 July 2026

## Context

The production package previously relied on mutable base-image tags and produced no retained SBOM, vulnerability policy result, provenance statement or signature evidence. A simple severity threshold was also insufficient: it would either fail permanently on upstream findings with no compatible fix or silently ignore new vulnerabilities through a broad waiver.

The local workstation cannot use nested Docker reliably, while CI can. The same policy must therefore work with Docker and a daemonless local builder.

## Decision

1. Pin every Dockerfile base image by immutable index digest and verify Linux AMD64 and ARM64 manifests with Crane.
2. Use Python 3.13.14 on Alpine 3.23 for backend build/runtime because it materially reduces the observed Critical/High surface while preserving application behavior.
3. Build and export the final image as OCI through Docker Buildx in CI or Buildah `vfs`/`chroot` locally.
4. Generate a CycloneDX SBOM with Syft and a Grype JSON report.
5. Reject every Critical finding and forbid Critical baseline entries.
6. Require every High finding to match an exact package type, package, version, CVE and severity in an expiring baseline; scanner-reported fixes require an explicit compatibility exception.
7. Reject stale baseline entries so exceptions cannot accumulate invisibly.
8. Evaluate application-level Python licenses against an explicit allow/deny policy; retain operating-system licenses in the SBOM for legal review.
9. Require a clean Git tree, then generate an in-toto statement with the SLSA provenance predicate, source commit, immutable inputs and artifact hashes.
10. Sign and verify the image archive and provenance with an ephemeral Cosign key for local evidence only.
11. Pin GitHub Actions to full commit SHAs and retain generated CI evidence for 30 days.
12. Do not publish an image or claim production signing identity in this increment.

## Consequences

### Positive

- Base-image drift is prevented.
- New Critical/High findings fail the gate instead of being absorbed by a severity count.
- Accepted High findings are explicit, version-specific and time-limited.
- SBOM, vulnerability, provenance and signature evidence are reproducible locally and in CI.
- The policy works without a Docker daemon on the workstation.
- Moving to Alpine removed all observed Critical findings and reduced observed High findings from 30 to 5 versus the evaluated Python 3.12 Debian slim runtime.

### Negative

- The supply-chain gate downloads scanner databases and rebuilds the image, so it is slower than unit tests.
- Alpine/musl compatibility must remain part of package verification.
- NVD/CPE matches may report issues without vendor-fixed packages; human review remains necessary.
- Offline Cosign verification lacks public transparency and does not establish a production release identity.
- Generated evidence is intentionally not committed and must be retained by CI or a future registry.

## Follow-up

A production release workflow must push by digest to an immutable registry, sign through protected keyless OIDC or KMS identity, attach SBOM/provenance to the digest, verify Rekor transparency evidence, and require deployment admission to validate issuer, identity and provenance.
