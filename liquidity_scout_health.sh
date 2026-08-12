#!/usr/bin/env bash

SERVICE="liquidity-scout.service"

echo "=== Liquidity Scout Health ==="

STATE=$(systemctl is-active "$SERVICE" 2>/dev/null)
PID=$(systemctl show "$SERVICE" -p MainPID --value)
RESTARTS=$(systemctl show "$SERVICE" -p NRestarts --value)

echo "Service:  $STATE"
echo "PID:      $PID"
echo "Restarts: $RESTARTS"

if [[ "$STATE" == "active" ]] && [[ "$PID" != "0" ]]; then
    echo "Health:   OK"
    exit 0
else
    echo "Health:   FAILED"
    exit 1
fi
