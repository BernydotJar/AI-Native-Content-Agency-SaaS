#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR=${INSTALL_DIR:-$HOME/.local/bin}
ACTIONLINT_VERSION=${ACTIONLINT_VERSION:-1.7.12}
TMP_DIR=$(mktemp -d)

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

for command in curl tar sha256sum install grep uname; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'required bootstrap command is missing: %s\n' "$command" >&2
    exit 2
  fi
done

case "$(uname -m)" in
  aarch64|arm64) ACTIONLINT_ARCH=arm64 ;;
  x86_64|amd64) ACTIONLINT_ARCH=amd64 ;;
  *)
    printf 'unsupported architecture: %s\n' "$(uname -m)" >&2
    exit 2
    ;;
esac

mkdir -p "$INSTALL_DIR"
cd "$TMP_DIR"
TAG="v${ACTIONLINT_VERSION}"
ARCHIVE="actionlint_${ACTIONLINT_VERSION}_linux_${ACTIONLINT_ARCH}.tar.gz"
BASE_URL="https://github.com/rhysd/actionlint/releases/download/${TAG}"

curl -fL --retry 3 --retry-delay 2 -o "$ARCHIVE" "$BASE_URL/$ARCHIVE"
curl -fL --retry 3 --retry-delay 2 -o checksums.txt \
  "$BASE_URL/actionlint_${ACTIONLINT_VERSION}_checksums.txt"
grep " ${ARCHIVE}$" checksums.txt > expected
sha256sum -c expected
tar -xzf "$ARCHIVE"
install -m 0755 actionlint "$INSTALL_DIR/actionlint"

PATH="$INSTALL_DIR:$PATH"
printf 'install_dir=%s\n' "$INSTALL_DIR"
printf 'actionlint=%s\n' "$(actionlint -version | head -n 1)"
