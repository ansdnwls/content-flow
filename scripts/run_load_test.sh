#!/usr/bin/env bash
# =============================================================================
# ContentFlow — Automated Load Test Runner
# =============================================================================
# Runs Locust load tests at 100 / 500 / 1000 concurrent users and saves
# HTML + CSV reports to reports/load/.
#
# Usage:
#   chmod +x scripts/run_load_test.sh
#   ./scripts/run_load_test.sh [HOST]
#
# Arguments:
#   HOST — target server (default: http://localhost:8000)
# =============================================================================

set -euo pipefail

HOST="${1:-http://localhost:8000}"
LOCUSTFILE="tests/load/locustfile.py"
REPORT_DIR="reports/load"
RUN_TIME="60s"
SPAWN_RATE=50

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if ! command -v locust &>/dev/null; then
    echo "Error: locust is not installed. Run: pip install locust"
    exit 1
fi

mkdir -p "$REPORT_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

for USERS in 100 500 1000; do
    LABEL="${USERS}u_${TIMESTAMP}"
    echo ""
    echo -e "${YELLOW}=== Running load test: ${USERS} concurrent users ===${NC}"
    echo "  Host: $HOST"
    echo "  Duration: $RUN_TIME"
    echo "  Spawn rate: $SPAWN_RATE/s"
    echo ""

    locust \
        -f "$LOCUSTFILE" \
        --host "$HOST" \
        --users "$USERS" \
        --spawn-rate "$SPAWN_RATE" \
        --run-time "$RUN_TIME" \
        --headless \
        --html "${REPORT_DIR}/report_${LABEL}.html" \
        --csv "${REPORT_DIR}/csv_${LABEL}" \
        --only-summary \
        2>&1 | tee "${REPORT_DIR}/log_${LABEL}.txt"

    echo -e "${GREEN}[DONE] ${USERS} users — report: ${REPORT_DIR}/report_${LABEL}.html${NC}"
done

echo ""
echo "==========================================="
echo -e "${GREEN}All load tests complete.${NC}"
echo "Reports saved to: ${REPORT_DIR}/"
echo "==========================================="
