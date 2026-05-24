#!/usr/bin/env bash
# ── FundPilot: Start all services ──────────────────────────────────────
# Usage: ./scripts/start.sh [--docker]
#
# Without flags: starts PostgreSQL + backend using local Python venv
# --docker:      starts all services via docker-compose
# ────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "${1:-}" == "--docker" ]]; then
    echo "=== Starting FundPilot (Docker) ==="
    cd "$ROOT"
    docker compose up -d
    echo ""
    echo "Services started. Check status: ./scripts/status.sh"
    echo "Backend:  http://localhost:${APP_PORT:-8000}"
    echo "Database: localhost:${DB_PORT:-5432}"
    exit 0
fi

# ── Local mode ─────────────────────────────────────────────────────────
echo "=== Starting FundPilot (local) ==="

# Source .env if present
if [ -f "$ROOT/.env" ]; then
    set -a; source "$ROOT/.env"; set +a
fi

# 1. Start PostgreSQL (if not running)
echo ""
echo "[1/2] Checking database..."
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

if command -v pg_isready &>/dev/null; then
    if pg_isready -h "$DB_HOST" -p "$DB_PORT" -q; then
        echo "  PostgreSQL is already running on $DB_HOST:$DB_PORT"
    else
        echo "  PostgreSQL is NOT running. Start it with:"
        echo "    pg_ctl start -D /usr/local/var/postgresql@16"
        echo "  or: brew services start postgresql@16"
        echo "  or: ./scripts/db/start.sh"
        echo ""
        echo "  Attempting pg_ctl start..."
        if pg_ctl start -D /usr/local/var/postgresql@16 -l /tmp/postgres.log 2>/dev/null; then
            echo "  PostgreSQL started."
        else
            echo "  ERROR: Could not start PostgreSQL. Please start it manually."
            exit 1
        fi
    fi
else
    echo "  WARNING: pg_isready not found. Make sure PostgreSQL is running on $DB_HOST:$DB_PORT"
fi

# 2. Start backend
echo ""
echo "[2/2] Starting backend..."
cd "$ROOT/backend"

if [ ! -d ".venv" ]; then
    echo "  Virtualenv not found. Run: python -m venv .venv && pip install -e ."
    exit 1
fi

PYTHON=".venv/bin/python"
APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-8000}"

echo "  Starting on $APP_HOST:$APP_PORT..."
"$PYTHON" -m uvicorn app.main:app --host "$APP_HOST" --port "$APP_PORT" --reload
