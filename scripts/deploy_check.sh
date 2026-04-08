#!/usr/bin/env bash
# =============================================================================
# ContentFlow — Pre-Deploy Validation Script
# =============================================================================
# Checks environment variables, database connectivity, Redis connectivity,
# and application health before a production deployment.
#
# Usage:
#   chmod +x scripts/deploy_check.sh
#   ./scripts/deploy_check.sh
#
# Exit codes:
#   0 — all checks passed
#   1 — one or more checks failed
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

pass() { echo -e "  ${GREEN}[PASS]${NC} $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; FAIL=$((FAIL + 1)); }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; WARN=$((WARN + 1)); }

# ---------------------------------------------------------------------------
# 1. Required Environment Variables
# ---------------------------------------------------------------------------
echo ""
echo "=== 1. Environment Variables ==="

REQUIRED_VARS=(
    "SUPABASE_URL"
    "SUPABASE_ANON_KEY"
    "SUPABASE_SERVICE_ROLE_KEY"
    "REDIS_URL"
    "TOKEN_ENCRYPTION_KEY"
    "OAUTH_STATE_SECRET"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [ -n "${!var:-}" ]; then
        pass "$var is set"
    else
        fail "$var is NOT set"
    fi
done

OPTIONAL_VARS=(
    "SENTRY_DSN"
    "YOUTUBE_API_KEY"
    "YT_FACTORY_BASE_URL"
    "YT_FACTORY_API_KEY"
    "ANTHROPIC_API_KEY"
    "GOOGLE_CLIENT_ID"
    "GOOGLE_CLIENT_SECRET"
    "META_CLIENT_ID"
    "META_CLIENT_SECRET"
    "TIKTOK_CLIENT_KEY"
    "TIKTOK_CLIENT_SECRET"
    "X_CLIENT_ID"
    "X_CLIENT_SECRET"
)

for var in "${OPTIONAL_VARS[@]}"; do
    if [ -n "${!var:-}" ]; then
        pass "$var is set"
    else
        warn "$var is not set (optional)"
    fi
done

# ---------------------------------------------------------------------------
# 2. Python Environment
# ---------------------------------------------------------------------------
echo ""
echo "=== 2. Python Environment ==="

if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 --version 2>&1)
    pass "Python found: $PY_VERSION"
else
    fail "python3 not found"
fi

if python3 -c "import app.main" 2>/dev/null; then
    pass "app.main importable"
else
    fail "Cannot import app.main — check dependencies"
fi

if python3 -c "import celery" 2>/dev/null; then
    pass "celery importable"
else
    fail "Cannot import celery — check dependencies"
fi

# ---------------------------------------------------------------------------
# 3. Redis Connectivity
# ---------------------------------------------------------------------------
echo ""
echo "=== 3. Redis Connectivity ==="

if [ -n "${REDIS_URL:-}" ]; then
    if python3 -c "
import redis, sys
try:
    r = redis.from_url('${REDIS_URL}', socket_timeout=5)
    r.ping()
    print('ok')
except Exception as e:
    print(f'error: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null; then
        pass "Redis is reachable"
    else
        fail "Cannot connect to Redis at \$REDIS_URL"
    fi
else
    fail "REDIS_URL not set — skipping connectivity check"
fi

# ---------------------------------------------------------------------------
# 4. Supabase Connectivity
# ---------------------------------------------------------------------------
echo ""
echo "=== 4. Supabase Connectivity ==="

if [ -n "${SUPABASE_URL:-}" ] && [ -n "${SUPABASE_ANON_KEY:-}" ]; then
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
        "${SUPABASE_URL}/rest/v1/" \
        -H "apikey: ${SUPABASE_ANON_KEY}" \
        -H "Authorization: Bearer ${SUPABASE_ANON_KEY}" \
        --connect-timeout 5 2>/dev/null || echo "000")

    if [ "$HTTP_STATUS" -ge 200 ] && [ "$HTTP_STATUS" -lt 400 ]; then
        pass "Supabase REST API reachable (HTTP $HTTP_STATUS)"
    else
        fail "Supabase REST API returned HTTP $HTTP_STATUS"
    fi
else
    fail "SUPABASE_URL or SUPABASE_ANON_KEY not set"
fi

# ---------------------------------------------------------------------------
# 5. Linting
# ---------------------------------------------------------------------------
echo ""
echo "=== 5. Code Quality ==="

if command -v ruff &>/dev/null; then
    if ruff check app/ --quiet 2>/dev/null; then
        pass "ruff lint passed"
    else
        fail "ruff lint errors found"
    fi
else
    warn "ruff not installed — skipping lint check"
fi

# ---------------------------------------------------------------------------
# 6. Test Suite
# ---------------------------------------------------------------------------
echo ""
echo "=== 6. Tests ==="

if command -v pytest &>/dev/null; then
    if pytest tests/ --tb=no -q 2>/dev/null; then
        pass "All tests passed"
    else
        fail "Some tests failed"
    fi
else
    warn "pytest not installed — skipping test check"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "==========================================="
echo -e "  ${GREEN}PASSED${NC}: $PASS"
echo -e "  ${RED}FAILED${NC}: $FAIL"
echo -e "  ${YELLOW}WARNED${NC}: $WARN"
echo "==========================================="

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}Deploy check FAILED. Fix issues above before deploying.${NC}"
    exit 1
else
    echo -e "${GREEN}Deploy check PASSED. Ready to deploy.${NC}"
    exit 0
fi
