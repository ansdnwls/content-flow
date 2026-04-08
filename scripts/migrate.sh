#!/usr/bin/env bash
# =============================================================================
# ContentFlow — Production Migration Script
# =============================================================================
# Runs Alembic migrations with pre-flight checks and optional backup.
#
# Usage:
#   ./scripts/migrate.sh                    # upgrade to head
#   ./scripts/migrate.sh upgrade head       # explicit upgrade
#   ./scripts/migrate.sh downgrade -1       # rollback one revision
#   ./scripts/migrate.sh current            # show current revision
#   ./scripts/migrate.sh history            # show migration history
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

COMMAND="${1:-upgrade}"
TARGET="${2:-head}"

# ---------------------------------------------------------------------------
# 1. Pre-flight checks
# ---------------------------------------------------------------------------
echo ""
echo "=== Pre-flight checks ==="

if [ -z "${SUPABASE_DB_URL:-}" ]; then
    echo -e "${RED}[FAIL]${NC} SUPABASE_DB_URL is not set"
    echo "  Set it to your Supabase direct connection string:"
    echo "  export SUPABASE_DB_URL=postgresql://postgres:...@db.xxx.supabase.co:5432/postgres"
    exit 1
fi
echo -e "${GREEN}[PASS]${NC} SUPABASE_DB_URL is set"

if ! command -v alembic &>/dev/null; then
    echo -e "${RED}[FAIL]${NC} alembic is not installed. Run: pip install alembic"
    exit 1
fi
echo -e "${GREEN}[PASS]${NC} alembic is installed"

# ---------------------------------------------------------------------------
# 2. Show current state
# ---------------------------------------------------------------------------
echo ""
echo "=== Current migration state ==="
alembic current 2>&1 || true

# ---------------------------------------------------------------------------
# 3. Optional backup prompt (upgrade only)
# ---------------------------------------------------------------------------
if [ "$COMMAND" = "upgrade" ]; then
    echo ""
    echo -e "${YELLOW}=== Backup reminder ===${NC}"
    echo "  Ensure you have a recent database backup before proceeding."
    echo "  Supabase Dashboard > Database > Backups"
    echo ""
    read -r -p "Continue with migration? [y/N] " confirm
    if [[ ! "$confirm" =~ ^[yY]$ ]]; then
        echo "Migration cancelled."
        exit 0
    fi
fi

# ---------------------------------------------------------------------------
# 4. Run migration
# ---------------------------------------------------------------------------
echo ""
echo "=== Running: alembic $COMMAND $TARGET ==="
alembic "$COMMAND" "$TARGET"

# ---------------------------------------------------------------------------
# 5. Verify
# ---------------------------------------------------------------------------
echo ""
echo "=== Post-migration state ==="
alembic current

echo ""
echo -e "${GREEN}Migration complete.${NC}"
