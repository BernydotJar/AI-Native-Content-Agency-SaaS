#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR=${INSTALL_DIR:-$HOME/.local/bin}
HELM_VERSION=${HELM_VERSION:-4.2.0}
TERRAFORM_VERSION=${TERRAFORM_VERSION:-1.15.8}
KUBECTL_VERSION=${KUBECTL_VERSION:-1.36.2}
K3S_VERSION=${K3S_VERSION:-1.36.2+k3s1}
TMP_DIR=$(mktemp -d)

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

for command in curl tar unzip sha256sum install awk grep; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'required bootstrap command is missing: %s\n' "$command" >&2
    exit 2
  fi
done

case "$(uname -m)" in
  aarch64|arm64)
    HELM_ARCH=arm64
    TERRAFORM_ARCH=arm64
    KUBECTL_ARCH=arm64
    K3S_BINARY=k3s-arm64
    K3S_CHECKSUM=sha256sum-arm64.txt
    ;;
  x86_64|amd64)
    HELM_ARCH=amd64
    TERRAFORM_ARCH=amd64
    KUBECTL_ARCH=amd64
    K3S_BINARY=k3s
    K3S_CHECKSUM=sha256sum-amd64.txt
    ;;
  *)
    printf 'unsupported architecture: %s\n' "$(uname -m)" >&2
    exit 2
    ;;
esac

mkdir -p "$INSTALL_DIR"
cd "$TMP_DIR"

HELM_RELEASE="v${HELM_VERSION}"
HELM_ARCHIVE="helm-${HELM_RELEASE}-linux-${HELM_ARCH}.tar.gz"
curl -fL --retry 3 --retry-delay 2 -o "$HELM_ARCHIVE" \
  "https://get.helm.sh/${HELM_ARCHIVE}"
curl -fL --retry 3 --retry-delay 2 -o helm.sha256sum \
  "https://get.helm.sh/${HELM_ARCHIVE}.sha256sum"
printf '%s  %s\n' "$(awk '{print $1}' helm.sha256sum)" "$HELM_ARCHIVE" | sha256sum -c -
tar -xzf "$HELM_ARCHIVE"
install -m 0755 "linux-${HELM_ARCH}/helm" "$INSTALL_DIR/helm"

TERRAFORM_ARCHIVE="terraform_${TERRAFORM_VERSION}_linux_${TERRAFORM_ARCH}.zip"
curl -fL --retry 3 --retry-delay 2 -o "$TERRAFORM_ARCHIVE" \
  "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/${TERRAFORM_ARCHIVE}"
curl -fL --retry 3 --retry-delay 2 -o terraform_SHA256SUMS \
  "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_SHA256SUMS"
grep " ${TERRAFORM_ARCHIVE}$" terraform_SHA256SUMS > terraform.expected
sha256sum -c terraform.expected
unzip -q "$TERRAFORM_ARCHIVE" -d terraform-unpacked
install -m 0755 terraform-unpacked/terraform "$INSTALL_DIR/terraform"

KUBECTL_RELEASE="v${KUBECTL_VERSION}"
curl -fL --retry 3 --retry-delay 2 -o kubectl \
  "https://dl.k8s.io/release/${KUBECTL_RELEASE}/bin/linux/${KUBECTL_ARCH}/kubectl"
curl -fL --retry 3 --retry-delay 2 -o kubectl.sha256 \
  "https://dl.k8s.io/release/${KUBECTL_RELEASE}/bin/linux/${KUBECTL_ARCH}/kubectl.sha256"
printf '%s  %s\n' "$(cat kubectl.sha256)" kubectl | sha256sum -c -
install -m 0755 kubectl "$INSTALL_DIR/kubectl"

K3S_TAG="v${K3S_VERSION}"
K3S_ENCODED_TAG=${K3S_TAG/+/%2B}
curl -fL --retry 3 --retry-delay 2 -o "$K3S_BINARY" \
  "https://github.com/k3s-io/k3s/releases/download/${K3S_ENCODED_TAG}/${K3S_BINARY}"
curl -fL --retry 3 --retry-delay 2 -o "$K3S_CHECKSUM" \
  "https://github.com/k3s-io/k3s/releases/download/${K3S_ENCODED_TAG}/${K3S_CHECKSUM}"
grep "  ${K3S_BINARY}$" "$K3S_CHECKSUM" > k3s.expected
sha256sum -c k3s.expected
install -m 0755 "$K3S_BINARY" "$INSTALL_DIR/k3s"

PATH="$INSTALL_DIR:$PATH"
printf 'install_dir=%s\n' "$INSTALL_DIR"
printf 'helm=%s\n' "$(helm version --short)"
printf 'terraform=%s\n' "$(terraform version -json | awk -F'"' '/terraform_version/{print $4; exit}')"
printf 'kubectl=%s\n' "$(kubectl version --client=true -o json | awk -F'"' '/gitVersion/{print $4; exit}')"
printf 'k3s=%s\n' "$(k3s --version | head -n 1)"
