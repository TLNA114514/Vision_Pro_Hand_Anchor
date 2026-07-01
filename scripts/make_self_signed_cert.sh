#!/usr/bin/env bash
set -euo pipefail

LAN_IP="${1:-}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="$ROOT_DIR/certs"
CERT_PATH="$CERT_DIR/localhost.pem"
KEY_PATH="$CERT_DIR/localhost-key.pem"
CONFIG_PATH="$(mktemp)"

mkdir -p "$CERT_DIR"

cleanup() {
  rm -f "$CONFIG_PATH"
}
trap cleanup EXIT

cat > "$CONFIG_PATH" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
CN = localhost

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
IP.1 = 127.0.0.1
EOF

if [[ -n "$LAN_IP" ]]; then
  cat >> "$CONFIG_PATH" <<EOF
IP.2 = $LAN_IP
EOF
fi

openssl req \
  -x509 \
  -nodes \
  -days 365 \
  -newkey rsa:2048 \
  -keyout "$KEY_PATH" \
  -out "$CERT_PATH" \
  -config "$CONFIG_PATH"

chmod 600 "$KEY_PATH"

echo
echo "Created:"
echo "  $CERT_PATH"
echo "  $KEY_PATH"
echo
echo "On Vision Pro, Safari may warn that this certificate is not trusted."
echo "For quick testing, open the page and proceed if Safari allows it."
echo "For cleaner testing, use a trusted local certificate or tunnel."
