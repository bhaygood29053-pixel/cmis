#!/usr/bin/env bash

SERVICE="liquidity-scout.service"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$PROJECT_DIR" || exit 1

echo
echo "================================================"
echo "          X1 SENTINEL DIAGNOSTICS"
echo "================================================"
echo

STATE=$(systemctl is-active "$SERVICE" 2>/dev/null)
PID=$(systemctl show "$SERVICE" -p MainPID --value 2>/dev/null)
RESTARTS=$(systemctl show "$SERVICE" -p NRestarts --value 2>/dev/null)

if [[ "$STATE" == "active" && "$PID" != "0" ]]; then
    HEALTH="OK"
else
    HEALTH="FAILED"
fi

echo "SYSTEM HEALTH"
echo "------------------------------------------------"
printf "%-12s %s\n" "Service:" "$STATE"
printf "%-12s %s\n" "PID:" "$PID"
printf "%-12s %s\n" "Restarts:" "$RESTARTS"
printf "%-12s %s\n" "Health:" "$HEALTH"
echo

BRANCH=$(git branch --show-current 2>/dev/null)

if [[ -z "$(git status --porcelain 2>/dev/null)" ]]; then
    GIT_STATE="Clean"
else
    GIT_STATE="Modified"
fi

echo "DEVELOPMENT STATUS"
echo "------------------------------------------------"
printf "%-12s %s\n" "Branch:" "$BRANCH"
printf "%-12s %s\n" "Git:" "$GIT_STATE"
echo

if [[ -x ".venv/bin/python" ]]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

"$PYTHON" sentinel_issues.py list

echo
echo "RECENT ROBERTA ACTIVITY"
echo "------------------------------------------------"

ACTIVITY=$(journalctl     -u "$SERVICE"     -b     -n 80     --no-pager     2>/dev/null     | grep -E "New standalone|Message:|Route [0-9]|Answered successfully|ERROR|WARNING"     | tail -n 12)

if [[ -n "$ACTIVITY" ]]; then
    echo "$ACTIVITY"
else
    echo "No recent service activity found."
fi

echo
echo "RECENT ERRORS"
echo "------------------------------------------------"

ERRORS=$(journalctl     -u "$SERVICE"     -b     -p err     -n 5     --no-pager     2>/dev/null)

if [[ -n "$ERRORS" && "$ERRORS" != "-- No entries --" ]]; then
    echo "$ERRORS"
else
    echo "No recent errors."
fi

echo
echo "================================================"

if [[ "$HEALTH" == "FAILED" ]]; then
    echo "WARNING: X1 Sentinel service needs attention."
    exit 1
fi

exit 0
