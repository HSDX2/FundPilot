#!/usr/bin/env bash
# ── FundPilot: Stop PostgreSQL ─────────────────────────────────────────
# Usage: ./scripts/db/stop.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if [ -f "$ROOT/.env" ]; then
    set -a; source "$ROOT/.env"; set +a
fi

DB_PORT="${DB_PORT:-5432}"

echo "=== Stopping PostgreSQL ==="

if command -v pg_ctl &>/dev/null; then
    echo "Using pg_ctl..."
    pg_ctl stop -D /usr/local/var/postgresql@16 2>/dev/null || true
    echo "PostgreSQL stopped"
elif command -v brew &>/dev/null; then
    echo "Using brew services..."
    brew services stop postgresql@16
    echo "PostgreSQL stopped"
else
    echo "ERROR: Cannot stop PostgreSQL. Stop manually or use Docker."
    exit 1
fi
