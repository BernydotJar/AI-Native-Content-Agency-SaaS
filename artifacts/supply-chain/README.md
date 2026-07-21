# Supply-chain policy and evidence

Tracked files in this directory are reviewable inputs to the production gate:

- `base-images.json`: immutable multi-architecture base-image digests.
- `vulnerability-baseline.json`: exact, reasoned, expiring High-severity exceptions.
- `license-policy.json`: application-package license allowlist, deny tokens, and exact metadata exceptions.

`generated/` is intentionally ignored by Git. `scripts/verify-supply-chain.sh` recreates the OCI archive, CycloneDX SBOM, Grype report, policy summary, in-toto provenance, Cosign bundles, and checksums from a clean source commit. GitHub Actions retains that generated directory as the `supply-chain-evidence` artifact for 30 days.

Policy inputs must be reviewed in the same change as a base image or dependency update. Do not add a baseline entry without a reason, and do not extend the expiry without rerunning the gate against the immutable image.
