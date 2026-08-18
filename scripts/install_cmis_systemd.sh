#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

if [[ ${EUID} -eq 0 ]]; then
  fail "Run this installer as the normal Liquidity Scout user, not as root. It will use sudo only for systemd files."
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="$(id -un)"
RUN_HOME="$HOME"
PYTHON="$REPO_ROOT/.venv/bin/python"
ENV_FILE="$REPO_ROOT/.env"
UNIT_FILE="/etc/systemd/system/cmis-gateway.service"
HEALTH_URL="http://127.0.0.1:8765/healthz"

[[ -x "$PYTHON" ]] || fail "Liquidity Scout virtualenv Python was not found at $PYTHON"
command -v curl >/dev/null 2>&1 || fail "curl is required for the CMIS health check."

case "$REPO_ROOT$RUN_HOME" in
  *[[:space:]]*) fail "This installer currently requires repository and home paths without whitespace." ;;
esac

# CMIS X1 market collection reads project configuration through config.py,
# which loads the repository .env from this service's WorkingDirectory.
[[ -f "$ENV_FILE" ]] || fail "Project .env was not found at $ENV_FILE"
if ! grep -Eq '^[[:space:]]*X1_NINJA_API_KEY[[:space:]]*=[[:space:]]*.+$' "$ENV_FILE"; then
  fail "X1_NINJA_API_KEY is not configured in the project .env. Add it locally before installing CMIS."
fi

# Never kill a process that this service does not own.
if ! sudo systemctl is-active --quiet cmis-gateway.service 2>/dev/null; then
  if ss -ltn 2>/dev/null | grep -Eq '127\.0\.0\.1:8765|\[::1\]:8765|:8765[[:space:]]'; then
    fail "Port 8765 is already in use by a non-managed process. Stop the manually started CMIS gateway, then run this installer again."
  fi
fi

unit_tmp="$(mktemp)"
trap 'rm -f "$unit_tmp"' EXIT
cat > "$unit_tmp" <<EOF
[Unit]
Description=Liquidity Scout CMIS Gateway
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$REPO_ROOT
Environment=HOME=$RUN_HOME
Environment=PYTHONPATH=$REPO_ROOT
Environment=PYTHONUNBUFFERED=1
ExecStart=$PYTHON -m liquidity_scout.cmis.http --host 127.0.0.1 --port 8765
Restart=always
RestartSec=3
TimeoutStopSec=10
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

sudo install -m 0644 "$unit_tmp" "$UNIT_FILE"
sudo systemctl daemon-reload
sudo systemctl enable cmis-gateway.service >/dev/null
sudo systemctl restart cmis-gateway.service

printf '\n=== WAITING FOR CMIS HEALTH ===\n'
healthy=0
for _ in $(seq 1 30); do
  if curl -fsS --max-time 2 "$HEALTH_URL" >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 1
done

if [[ "$healthy" -ne 1 ]]; then
  printf '\n=== CMIS SERVICE STATUS ===\n' >&2
  sudo systemctl --no-pager --full status cmis-gateway.service | sed -n '1,24p' >&2 || true
  printf '\n=== CMIS RECENT LOG ===\n' >&2
  sudo journalctl -u cmis-gateway.service -n 40 --no-pager >&2 || true
  fail "CMIS did not become healthy on 127.0.0.1:8765 within 30 seconds."
fi

printf '\n=== CMIS GATEWAY SERVICE ===\n'
sudo systemctl --no-pager --full status cmis-gateway.service | sed -n '1,18p'

printf '\n=== CMIS HEALTH ===\n'
curl -fsS --max-time 5 "$HEALTH_URL"
printf '\n'

printf '\nCMIS gateway is enabled to start automatically and restart after failures.\n'
