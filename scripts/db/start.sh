#!/usr/bin/env bash
# ── FundPilot: Start PostgreSQL ────────────────────────────────────────
# Usage: ./scripts/db/start.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# Source .env if present
if [ -f "$ROOT/.env" ]; then
    set -a; source "$ROOT/.env"; set +a
fi

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

echo "=== Starting PostgreSQL ==="

# Check if already running
if command -v pg_isready &>/dev/null; then
    if pg_isready -h "$DB_HOST" -p "$DB_PORT" -q; then
        echo "PostgreSQL is already running on $DB_HOST:$DB_PORT"
        exit 0
    fi
fi

# Try common start methods
if command -v pg_ctl &>/dev/null; then
    echo "Using pg_ctl..."
    pg_ctl start -D /usr/local/var/postgresql@16 -l /tmp/postgres.log

    # Wait for it
    for _ in $(seq 1 10); do
        if pg_isready -h "$DB_HOST" -p "$DB_PORT" -q 2>/dev/null; then
            echo "PostgreSQL started on $DB_HOST:$DB_PORT"
            exit 0
        fi
        sleep 1
    done
    echo "ERROR: PostgreSQL did not become ready in 10s"
    exit 1
elif command -v brew &>/dev/null; then
    echo "Using brew services..."
    brew services start postgresql@16
    echo "PostgreSQL start initiated"
else
    echo "ERROR: Cannot start PostgreSQL. Use Docker: docker compose up -d postgres"
    exit 1
fi
