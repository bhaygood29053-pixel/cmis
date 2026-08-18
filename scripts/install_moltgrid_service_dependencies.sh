#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

if [[ ${EUID} -eq 0 ]]; then
  fail "Run this installer as the normal Liquidity Scout user, not as root. It will use sudo only for systemd files."
fi

SERVICE_NAME="${LIQUIDITY_SCOUT_SERVICE_NAME:-liquidity-scout.service}"
ROBERTA_SERVICE="roberta-bridge.service"
CMIS_SERVICE="cmis-gateway.service"
DROPIN_DIR="/etc/systemd/system/${SERVICE_NAME}.d"
DROPIN_FILE="$DROPIN_DIR/10-roberta-cmis-dependencies.conf"
CURL_BIN="$(command -v curl || true)"

[[ -n "$CURL_BIN" ]] || fail "curl is required for dependency health checks."
systemctl cat "$SERVICE_NAME" >/dev/null 2>&1 || fail "$SERVICE_NAME is not installed."
systemctl cat "$ROBERTA_SERVICE" >/dev/null 2>&1 || fail "$ROBERTA_SERVICE is not installed. Install the managed Roberta bridge first."
systemctl cat "$CMIS_SERVICE" >/dev/null 2>&1 || fail "$CMIS_SERVICE is not installed. Run scripts/install_cmis_systemd.sh first."

unit_tmp="$(mktemp)"
trap 'rm -f "$unit_tmp"' EXIT

cat > "$unit_tmp" <<EOF
[Unit]
Wants=$ROBERTA_SERVICE $CMIS_SERVICE
After=$ROBERTA_SERVICE $CMIS_SERVICE

[Service]
ExecStartPre=/bin/sh -c 'for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do $CURL_BIN -fsS --max-time 2 http://127.0.0.1:8766/healthz >/dev/null && exit 0; sleep 1; done; exit 1'
ExecStartPre=/bin/sh -c 'for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do $CURL_BIN -fsS --max-time 2 http://127.0.0.1:8765/healthz >/dev/null && exit 0; sleep 1; done; exit 1'
EOF

sudo mkdir -p "$DROPIN_DIR"
sudo install -m 0644 "$unit_tmp" "$DROPIN_FILE"
sudo systemctl daemon-reload
sudo systemctl restart "$SERVICE_NAME"

printf '\n=== SERVICE DEPENDENCIES ===\n'
printf 'CMIS:    '
systemctl is-active "$CMIS_SERVICE"
printf 'Roberta: '
systemctl is-active "$ROBERTA_SERVICE"
printf 'MoltGrid: '
systemctl is-active "$SERVICE_NAME"

printf '\n=== HEALTH ===\n'
printf 'CMIS: '
"$CURL_BIN" -fsS --max-time 5 http://127.0.0.1:8765/healthz
printf '\nRoberta: '
"$CURL_BIN" -fsS --max-time 5 http://127.0.0.1:8766/healthz
printf '\n'

printf '\nInstalled %s\n' "$DROPIN_FILE"
printf 'The MoltGrid listener now waits for healthy CMIS and Roberta services before starting.\n'
