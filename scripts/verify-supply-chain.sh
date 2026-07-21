#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUTPUT_DIR=${OUTPUT_DIR:-$REPOSITORY_ROOT/artifacts/supply-chain/generated}
IMAGE_TAG=${IMAGE_TAG:-ai-native-content-agency:supply-chain-local}
CONTAINER_BUILDER=${CONTAINER_BUILDER:-auto}
ALLOW_DIRTY_SOURCE=${ALLOW_DIRTY_SOURCE:-false}
BASE_IMAGES_FILE="$REPOSITORY_ROOT/artifacts/supply-chain/base-images.json"
BASELINE_FILE="$REPOSITORY_ROOT/artifacts/supply-chain/vulnerability-baseline.json"
LICENSE_POLICY_FILE="$REPOSITORY_ROOT/artifacts/supply-chain/license-policy.json"
TMP_DIR=$(mktemp -d)
BUILD_ROOT="$TMP_DIR/buildah-root"
BUILD_RUNROOT="$TMP_DIR/buildah-runroot"
IMAGE_ARCHIVE="$OUTPUT_DIR/ai-native-content-agency.oci.tar"
SBOM_FILE="$OUTPUT_DIR/sbom.cdx.json"
VULNERABILITY_FILE="$OUTPUT_DIR/vulnerabilities.grype.json"
SUMMARY_FILE="$OUTPUT_DIR/policy-summary.json"
PROVENANCE_FILE="$OUTPUT_DIR/provenance.intoto.json"

cleanup() {
  if [ -d "$BUILD_ROOT" ]; then
    buildah --root "$BUILD_ROOT" --runroot "$BUILD_RUNROOT" \
      --storage-driver vfs rmi -a -f >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

log() { printf '[supply-chain] %s\n' "$*"; }

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'required command is missing: %s\n' "$1" >&2
    exit 2
  fi
}

export PATH="$HOME/.local/bin:$PATH"
for command in python3 jq sha256sum tar git syft grype cosign crane; do
  require_command "$command"
done

python3 -m unittest "$REPOSITORY_ROOT/backend/tests/test_supply_chain_policy.py" -v

SOURCE_COMMIT=$(git -C "$REPOSITORY_ROOT" rev-parse HEAD)
SOURCE_STATUS=$(git -C "$REPOSITORY_ROOT" status --porcelain --untracked-files=all)
SOURCE_DIRTY=false
if [ -n "$SOURCE_STATUS" ]; then
  SOURCE_DIRTY=true
  if [ "$ALLOW_DIRTY_SOURCE" != "true" ]; then
    printf 'source tree is dirty; commit the implementation before generating provenance\n%s\n' \
      "$SOURCE_STATUS" >&2
    exit 3
  fi
fi

mkdir -p "$OUTPUT_DIR"
rm -f "$IMAGE_ARCHIVE" "$SBOM_FILE" "$VULNERABILITY_FILE" "$SUMMARY_FILE" \
  "$PROVENANCE_FILE" "$OUTPUT_DIR"/*.sigstore.json "$OUTPUT_DIR/cosign.pub" \
  "$OUTPUT_DIR/SHA256SUMS"

log "validating immutable base-image references and platform manifests"
python3 - "$REPOSITORY_ROOT/Dockerfile" "$BASE_IMAGES_FILE" <<'PY'
import json
import sys
from pathlib import Path

dockerfile = Path(sys.argv[1]).read_text(encoding="utf-8")
base_images = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))["images"]
for image, digest in base_images.items():
    reference = f"{image}@{digest}"
    if reference not in dockerfile:
        raise SystemExit(f"Dockerfile is missing pinned base image: {reference}")
print(f"pinned_base_images={len(base_images)}")
PY

while IFS=$'\t' read -r image digest; do
  resolved=$(crane digest "${image}@${digest}")
  [ "$resolved" = "$digest" ] || {
    printf 'base image digest mismatch for %s: expected %s, got %s\n' \
      "$image" "$digest" "$resolved" >&2
    exit 4
  }
  manifest="$TMP_DIR/manifest-$(printf '%s' "$image" | tr '/:' '__').json"
  crane manifest "${image}@${digest}" > "$manifest"
  python3 - "$manifest" "$image" <<'PY'
import json
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
platforms = {
    (item.get("platform", {}).get("os"), item.get("platform", {}).get("architecture"))
    for item in manifest.get("manifests", [])
}
required = {("linux", "amd64"), ("linux", "arm64")}
missing = required - platforms
if missing:
    raise SystemExit(f"{sys.argv[2]} missing required platforms: {sorted(missing)}")
PY
done < <(jq -r '.images | to_entries[] | [.key,.value] | @tsv' "$BASE_IMAGES_FILE")

build_with_docker() {
  require_command docker
  docker info >/dev/null
  docker buildx version >/dev/null
  docker buildx build --provenance=false --sbom=false \
    --output "type=oci,dest=$IMAGE_ARCHIVE" --tag "$IMAGE_TAG" "$REPOSITORY_ROOT"
  SCAN_SOURCE="oci-archive:$IMAGE_ARCHIVE"
  BUILDER_NAME=docker-buildx
}

build_with_buildah() {
  require_command buildah
  mkdir -p "$BUILD_ROOT" "$BUILD_RUNROOT"
  export BUILDAH_ISOLATION=chroot
  buildah --root "$BUILD_ROOT" --runroot "$BUILD_RUNROOT" --storage-driver vfs \
    bud --isolation chroot --format docker --layers=false --tag "$IMAGE_TAG" "$REPOSITORY_ROOT"
  buildah --root "$BUILD_ROOT" --runroot "$BUILD_RUNROOT" --storage-driver vfs \
    push --format oci "$IMAGE_TAG" "oci-archive:$IMAGE_ARCHIVE:ai-native-content-agency"
  SCAN_SOURCE="oci-archive:$IMAGE_ARCHIVE"
  BUILDER_NAME=buildah
}

log "building immutable OCI image artifact"
case "$CONTAINER_BUILDER" in
  docker) build_with_docker ;;
  buildah) build_with_buildah ;;
  auto)
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
      build_with_docker
    else
      build_with_buildah
    fi
    ;;
  *)
    printf 'unsupported CONTAINER_BUILDER: %s\n' "$CONTAINER_BUILDER" >&2
    exit 2
    ;;
esac

ARCHIVE_ENTRIES_FILE="$TMP_DIR/oci-archive-entries.txt"
tar -tf "$IMAGE_ARCHIVE" > "$ARCHIVE_ENTRIES_FILE"
grep -Fxq 'oci-layout' "$ARCHIVE_ENTRIES_FILE"
grep -Fxq 'index.json' "$ARCHIVE_ENTRIES_FILE"

log "generating CycloneDX SBOM with Syft"
syft scan "$SCAN_SOURCE" -o "cyclonedx-json=$SBOM_FILE"

log "scanning SBOM with Grype"
grype "sbom:$SBOM_FILE" -o json > "$VULNERABILITY_FILE"

log "enforcing vulnerability and application-license policy"
python3 "$REPOSITORY_ROOT/scripts/evaluate-supply-chain.py" \
  --sbom "$SBOM_FILE" \
  --vulnerabilities "$VULNERABILITY_FILE" \
  --baseline "$BASELINE_FILE" \
  --license-policy "$LICENSE_POLICY_FILE" \
  --summary "$SUMMARY_FILE"

log "creating local SLSA-style provenance statement"
python3 - "$IMAGE_ARCHIVE" "$SBOM_FILE" "$VULNERABILITY_FILE" "$SUMMARY_FILE" \
  "$BASE_IMAGES_FILE" "$PROVENANCE_FILE" "$BUILDER_NAME" "$SOURCE_COMMIT" \
  "$SOURCE_DIRTY" <<'PY'
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

image = Path(sys.argv[1])
sbom = Path(sys.argv[2])
vulnerabilities = Path(sys.argv[3])
summary = Path(sys.argv[4])
base_images_path = Path(sys.argv[5])
output = Path(sys.argv[6])
builder_name = sys.argv[7]
source_commit = sys.argv[8]
source_dirty = sys.argv[9].lower() == "true"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


base_images = json.loads(base_images_path.read_text(encoding="utf-8"))["images"]
now = datetime.now(timezone.utc).isoformat()
statement = {
    "_type": "https://in-toto.io/Statement/v1",
    "subject": [
        {
            "name": image.name,
            "digest": {"sha256": digest(image)},
        }
    ],
    "predicateType": "https://slsa.dev/provenance/v1",
    "predicate": {
        "buildDefinition": {
            "buildType": "https://github.com/BernydotJar/AI-Native-Content-Agency-SaaS/build/container@v1",
            "externalParameters": {
                "builder": builder_name,
                "dockerfile": "Dockerfile",
                "networkPublication": False,
                "sourceDirty": source_dirty,
            },
            "internalParameters": {},
            "resolvedDependencies": [
                {
                    "uri": f"pkg:docker/{name}",
                    "digest": {"sha256": value.split(":", 1)[1]},
                }
                for name, value in sorted(base_images.items())
            ]
            + [
                {
                    "uri": "git+https://github.com/BernydotJar/AI-Native-Content-Agency-SaaS.git",
                    "digest": {"gitCommit": source_commit},
                }
            ],
        },
        "runDetails": {
            "builder": {"id": f"local:{builder_name}"},
            "metadata": {
                "invocationId": source_commit,
                "startedOn": now,
                "finishedOn": now,
            },
            "byproducts": [
                {"name": sbom.name, "digest": {"sha256": digest(sbom)}},
                {
                    "name": vulnerabilities.name,
                    "digest": {"sha256": digest(vulnerabilities)},
                },
                {"name": summary.name, "digest": {"sha256": digest(summary)}},
            ],
        },
    },
}
output.write_text(json.dumps(statement, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

log "signing and verifying OCI archive and provenance offline with an ephemeral Cosign key"
export COSIGN_PASSWORD=local-supply-chain-verification-only
cosign generate-key-pair --output-key-prefix "$TMP_DIR/cosign" >/dev/null
cp "$TMP_DIR/cosign.pub" "$OUTPUT_DIR/cosign.pub"
for artifact in "$IMAGE_ARCHIVE" "$PROVENANCE_FILE"; do
  name=$(basename "$artifact")
  bundle="$OUTPUT_DIR/${name}.sigstore.json"
  cosign sign-blob --yes --key "$TMP_DIR/cosign.key" --bundle "$bundle" "$artifact" >/dev/null
  cosign verify-blob --key "$TMP_DIR/cosign.pub" --bundle "$bundle" \
    --insecure-ignore-tlog "$artifact" >/dev/null
done
unset COSIGN_PASSWORD

(
  cd "$OUTPUT_DIR"
  sha256sum \
    "$(basename "$IMAGE_ARCHIVE")" \
    "$(basename "$SBOM_FILE")" \
    "$(basename "$VULNERABILITY_FILE")" \
    "$(basename "$SUMMARY_FILE")" \
    "$(basename "$PROVENANCE_FILE")" > SHA256SUMS
)

printf 'builder=%s\n' "$BUILDER_NAME"
printf 'source_commit=%s\n' "$SOURCE_COMMIT"
printf 'source_dirty=%s\n' "$SOURCE_DIRTY"
printf 'image_archive=%s\n' "$IMAGE_ARCHIVE"
printf 'sbom=%s\n' "$SBOM_FILE"
printf 'vulnerability_report=%s\n' "$VULNERABILITY_FILE"
printf 'policy_summary=%s\n' "$SUMMARY_FILE"
printf 'provenance=%s\n' "$PROVENANCE_FILE"
printf 'cosign_offline_verification=pass\n'
printf 'registry_publication=false\n'
