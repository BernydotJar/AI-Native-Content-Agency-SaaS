# Software Supply-Chain Security

Verified on 21 July 2026.

## Scope

This repository now produces locally verifiable supply-chain evidence for the unified React/FastAPI container without publishing an image or using production credentials.

The gate covers:

- immutable container base-image references;
- multi-architecture manifest verification for Linux AMD64 and ARM64;
- an exported OCI image archive;
- a CycloneDX JSON SBOM;
- a Grype vulnerability report;
- an exact, expiring Critical/High vulnerability policy;
- an application dependency license policy;
- an in-toto/SLSA-style provenance statement;
- offline Cosign signing and verification of the image archive and provenance;
- SHA-256 checksums for retained evidence.

It does not publish to a registry, sign through a production KMS, create a transparency-log entry, deploy, spend money, or change protected branches.

## Toolchain

`scripts/install-supply-chain-tools.sh` installs checksum-verified release binaries into `$HOME/.local/bin` by default:

| Tool | Version | Purpose |
|---|---:|---|
| Syft | 1.48.0 | CycloneDX SBOM generation |
| Grype | 0.116.0 | Vulnerability matching |
| Cosign | 3.1.2 | Blob signing and verification |
| Crane | 0.21.7 | Registry manifest and digest inspection |

Both Linux ARM64 and AMD64 are supported. The installer embeds the official release checksums for each supported artifact and fails before installation when a checksum differs.

## Immutable base images

The Dockerfile references the following image indexes by digest:

- `node:22-bookworm-slim@sha256:6c74791e557ce11fc957704f6d4fe134a7bc8d6f5ca4403205b2966bd488f6b3`;
- `python:3.13-alpine3.23@sha256:9fdbf2e3e82628351513560b121e2ee6ce31cac212be9e070c5a5e2769fb5e76`.

The expected references are stored in `artifacts/supply-chain/base-images.json`. The gate verifies that each exact reference appears in the Dockerfile, resolves to the expected digest, and includes Linux AMD64 and ARM64 manifests.

The runtime moved from Python 3.12 on Debian slim to Python 3.13.14 on Alpine 3.23 after evidence showed that the Alpine image reduced the observed surface from 7 Critical and 30 High findings to 0 Critical and 5 High findings while preserving the full runtime contract.

## Run the gate

```bash
./scripts/install-supply-chain-tools.sh
export PATH="$HOME/.local/bin:$PATH"
CONTAINER_BUILDER=buildah ./scripts/verify-supply-chain.sh
```

Use `CONTAINER_BUILDER=docker` in an environment with Docker Buildx; it exports the same OCI archive format as the Buildah path. The local workstation uses Buildah with `vfs` storage and `chroot` isolation because nested Docker overlay/network setup is not supported by the host.

Generated evidence is written to `artifacts/supply-chain/generated/` and intentionally ignored by Git. CI uploads that directory as the `supply-chain-evidence` artifact for 30 days.

Expected files:

- `ai-native-content-agency.oci.tar`;
- `sbom.cdx.json`;
- `vulnerabilities.grype.json`;
- `policy-summary.json`;
- `provenance.intoto.json`;
- `ai-native-content-agency.oci.tar.sigstore.json`;
- `provenance.intoto.json.sigstore.json`;
- `cosign.pub`;
- `SHA256SUMS`.

## Vulnerability policy

`artifacts/supply-chain/vulnerability-baseline.json` is an exact, time-bounded acceptance list.

The evaluator fails when:

- any Critical finding exists;
- a High finding is not in the exact baseline;
- a baseline entry no longer appears and has not been removed;
- the baseline has expired;
- a scanner-reported High fix lacks an explicit compatibility exception;
- a baseline entry lacks a review reason.

The current baseline expires on **21 August 2026**. It contains five High findings for Python 3.13.14 and Alpine `sqlite-libs 3.51.2-r0`. The scanner reported no stable compatible correction for four findings; the fifth listed only Python 3.15.0. Each exception must be reviewed when the Python/Alpine digest changes or before the expiry date, whichever occurs first.

The current verified summary is:

```text
Critical: 0
High: 5 accepted exact matches
Medium: 8 reported
```

A baseline is not a statement that a vulnerability is harmless. It is a temporary, reviewable record that no compatible fixed artifact was available at verification time. Runtime mitigations include a non-root UID, Kubernetes read-only root filesystem, no external publication adapters, and application-owned SQLite files.

## License policy

`artifacts/supply-chain/license-policy.json` evaluates application dependencies cataloged as Python packages. It rejects missing metadata unless an exact package/version exception exists, rejects denied copyleft/source-available tokens, and rejects any license not explicitly allowed.

The current gate evaluates 21 Python packages:

- MIT-family: 12;
- BSD-3-Clause: 6;
- PSF-2.0: 1;
- MIT application package: 1;
- one exact metadata exception for `annotated-types@0.7.0`.

Operating-system package licenses are retained in the SBOM for legal review but are not treated as application dependency licensing decisions by this automated gate.

## Provenance and signatures

The gate creates an in-toto statement using the SLSA provenance predicate. It records:

- the clean Git commit used for the build;
- immutable base-image digests;
- the builder type;
- the image archive digest;
- SBOM, vulnerability report and policy-summary digests;
- that registry publication was disabled;
- that the source tree was clean (`sourceDirty=false`).

For local verification, Cosign generates an ephemeral password-protected key, signs the image archive and provenance, and verifies both signatures offline. The private key is deleted with the temporary directory. The retained public key and bundles demonstrate that the artifacts produced in that invocation were internally consistent.

Offline verification intentionally skips the public transparency log. These signatures are development evidence, not a production identity. A production release must use one of:

- keyless OIDC signing from a protected GitHub Actions environment;
- a KMS-backed signing key with audited access;
- a formally managed offline release key.

## CI

All GitHub Actions in `.github/workflows/production-readiness.yml` are pinned to full commit SHAs. The `supply-chain` job:

1. installs the checksum-verified scanner/signing toolchain;
2. builds and exports the immutable OCI image with Docker Buildx;
3. generates and evaluates evidence;
4. uploads evidence for 30 days even when the policy fails.

CI does not push an image. Registry credentials are not required.

## Update procedure

When a base image or dependency changes:

1. resolve the tag with Crane;
2. verify AMD64 and ARM64 manifests;
3. update the Dockerfile and `base-images.json` together;
4. run the full package smoke;
5. run the supply-chain gate;
6. review every changed vulnerability and license finding;
7. remove stale baseline entries rather than preserving them;
8. set a short, explicit expiry on any unavoidable High exception;
9. review and commit only policy/configuration files, not generated archives.

## Remaining production release controls

The repository still requires a controlled promotion workflow before an external production release:

- immutable registry repository and retention policy;
- protected environment approval;
- registry push by digest, never by mutable tag alone;
- keyless or KMS-backed Cosign identity;
- transparency-log verification;
- provenance and SBOM attachment to the registry digest;
- deployment policy that verifies signature, issuer, identity and provenance;
- approved Python/npm package mirrors or an organization repository policy;
- scheduled vulnerability re-scan and baseline expiry enforcement.
