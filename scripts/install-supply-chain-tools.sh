#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR=${INSTALL_DIR:-$HOME/.local/bin}
SYFT_VERSION=1.48.0
GRYPE_VERSION=0.116.0
COSIGN_VERSION=3.1.2
CRANE_VERSION=0.21.7
TMP_DIR=$(mktemp -d)

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

for command in curl tar sha256sum install uname; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'required bootstrap command is missing: %s\n' "$command" >&2
    exit 2
  fi
done

case "$(uname -m)" in
  aarch64|arm64)
    ANCHORE_ARCH=arm64
    COSIGN_ARCH=arm64
    CRANE_ARCH=arm64
    SYFT_SHA256=6865a3d97c4e28b4b38571c17a2bf512da4494ef1d37613c3122fce0d67e63b0
    GRYPE_SHA256=7af3eed24f469b0cf3ab5ec4508d9c12f4bb9c2c6be714f32973c7b5d63cb6a5
    COSIGN_SHA256=90e7ae0b5dfd60f20816b52c012addf7fc055ebcc7bea4ce81c428ca8518c302
    CRANE_SHA256=b6ee979d9411dfb05ce35ab9e156fe5de7def11a230764a7856ffa2eb971fa88
    ;;
  x86_64|amd64)
    ANCHORE_ARCH=amd64
    COSIGN_ARCH=amd64
    CRANE_ARCH=x86_64
    SYFT_SHA256=6cef9a7f37220d9067eaf9cfaaa2fce986e9f320a8d42cbc36658c99af78ea04
    GRYPE_SHA256=40aff724297312f91ea390d003bed8d8651c74cc7f5b26732db80b3a408d2fc5
    COSIGN_SHA256=f7622ed3cf22e55e1ae6377c080979ff77a22da9981c11df222a2e444991e7cf
    CRANE_SHA256=1a57bc98207fa1c0d04bf760699099e26f8383499bfd55b99c1b919a928a7230
    ;;
  *)
    printf 'unsupported architecture: %s\n' "$(uname -m)" >&2
    exit 2
    ;;
esac

mkdir -p "$INSTALL_DIR"
cd "$TMP_DIR"

download_verified() {
  url=$1
  file=$2
  expected=$3
  curl -fL --retry 3 --retry-delay 2 -o "$file" "$url"
  printf '%s  %s\n' "$expected" "$file" | sha256sum -c -
}

SYFT_ARCHIVE="syft_${SYFT_VERSION}_linux_${ANCHORE_ARCH}.tar.gz"
download_verified \
  "https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}/${SYFT_ARCHIVE}" \
  "$SYFT_ARCHIVE" "$SYFT_SHA256"
tar -xzf "$SYFT_ARCHIVE" syft
install -m 0755 syft "$INSTALL_DIR/syft"

GRYPE_ARCHIVE="grype_${GRYPE_VERSION}_linux_${ANCHORE_ARCH}.tar.gz"
download_verified \
  "https://github.com/anchore/grype/releases/download/v${GRYPE_VERSION}/${GRYPE_ARCHIVE}" \
  "$GRYPE_ARCHIVE" "$GRYPE_SHA256"
tar -xzf "$GRYPE_ARCHIVE" grype
install -m 0755 grype "$INSTALL_DIR/grype"

COSIGN_BINARY="cosign-linux-${COSIGN_ARCH}"
download_verified \
  "https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/${COSIGN_BINARY}" \
  "$COSIGN_BINARY" "$COSIGN_SHA256"
install -m 0755 "$COSIGN_BINARY" "$INSTALL_DIR/cosign"

CRANE_ARCHIVE="go-containerregistry_Linux_${CRANE_ARCH}.tar.gz"
download_verified \
  "https://github.com/google/go-containerregistry/releases/download/v${CRANE_VERSION}/${CRANE_ARCHIVE}" \
  "$CRANE_ARCHIVE" "$CRANE_SHA256"
tar -xzf "$CRANE_ARCHIVE" crane
install -m 0755 crane "$INSTALL_DIR/crane"

PATH="$INSTALL_DIR:$PATH"
printf 'install_dir=%s\n' "$INSTALL_DIR"
printf 'syft=%s\n' "$(syft version | awk '/Version:/{print $2; exit}')"
printf 'grype=%s\n' "$(grype version | awk '/Version:/{print $2; exit}')"
printf 'cosign=%s\n' "$(cosign version 2>/dev/null | awk '/GitVersion:/{print $2; exit}')"
printf 'crane=%s\n' "$(crane version)"
