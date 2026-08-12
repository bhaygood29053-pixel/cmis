#!/usr/bin/env bash

SERVICE="liquidity-scout.service"

echo "========================================"
echo "       LIQUIDITY SCOUT STATUS"
echo "========================================"

STATE=$(systemctl is-active "$SERVICE" 2>/dev/null)
PID=$(systemctl show "$SERVICE" -p MainPID --value)
RESTARTS=$(systemctl show "$SERVICE" -p NRestarts --value)
STARTED=$(systemctl show "$SERVICE" -p ActiveEnterTimestamp --value)
MEMORY=$(systemctl show "$SERVICE" -p MemoryCurrent --value)

if [[ "$MEMORY" =~ ^[0-9]+$ ]]; then
    MEMORY_MB=$((MEMORY / 1024 / 1024))
else
    MEMORY_MB="N/A"
fi

echo "Service:   $STATE"
echo "PID:       $PID"
echo "Restarts:  $RESTARTS"
echo "Memory:    ${MEMORY_MB} MB"
echo "Started:   $STARTED"

if [[ "$STATE" == "active" ]] && [[ "$PID" != "0" ]]; then
    echo "Health:    OK"
else
    echo "Health:    FAILED"
fi

echo
echo "----- Latest Activity -----"

journalctl -u "$SERVICE" -n 15 --no-pager -o cat

echo "========================================"
