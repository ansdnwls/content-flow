#!/usr/bin/env bash
# =============================================================================
# ContentFlow Automated Load Test Runner
# =============================================================================
# Runs the named Locust scenario and saves HTML + CSV reports to reports/load/.
#
# Usage:
#   chmod +x scripts/run_load_test.sh
#   ./scripts/run_load_test.sh [HOST] [SCENARIO]
#
# Arguments:
#   HOST target server (default: http://localhost:8000)
#   SCENARIO one of normal_user, spike, sustained, bulk_posting
# =============================================================================

set -euo pipefail

HOST="${1:-http://localhost:8000}"
SCENARIO="${2:-normal_user}"
LOCUSTFILE="scripts/load_test/locustfile.py"
REPORT_DIR="reports/load"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if ! command -v locust &>/dev/null; then
    echo "Error: locust is not installed. Run: pip install locust"
    exit 1
fi

PROFILE_JSON=$(SCENARIO="$SCENARIO" python - <<'PY'
import importlib.util
import json
import os
import sys
from pathlib import Path

path = Path("scripts/load_test/locustfile.py")
spec = importlib.util.spec_from_file_location("contentflow_locustfile", path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)
print(json.dumps(module.profile_as_dict(os.environ["SCENARIO"])))
PY
)

USERS=$(python -c 'import json, sys; print(json.loads(sys.argv[1])["users"])' "$PROFILE_JSON")
SPAWN_RATE=$(python -c 'import json, sys; print(json.loads(sys.argv[1])["spawn_rate"])' "$PROFILE_JSON")
RUN_TIME=$(python -c 'import json, sys; print(json.loads(sys.argv[1])["run_time"])' "$PROFILE_JSON")

mkdir -p "$REPORT_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LABEL="${SCENARIO}_${TIMESTAMP}"
echo ""
echo -e "${YELLOW}=== Running load test: ${SCENARIO} ===${NC}"
echo "  Host: $HOST"
echo "  Users: $USERS"
echo "  Spawn rate: $SPAWN_RATE/s"
echo "  Duration: $RUN_TIME"
echo ""

LOAD_TEST_SCENARIO="$SCENARIO" \
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

echo ""
echo "==========================================="
echo -e "${GREEN}All load tests complete.${NC}"
echo "Reports saved to: ${REPORT_DIR}/"
echo "==========================================="
