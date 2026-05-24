#!/usr/bin/env bash
# ── FundPilot: Check service status ────────────────────────────────────
# Usage: ./scripts/status.sh [--docker]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "${1:-}" == "--docker" ]]; then
    echo "=== FundPilot Status (Docker) ==="
    cd "$ROOT"
    docker compose ps
    echo ""
    echo "Logs: docker compose logs -f [service]"
    exit 0
fi

# ── Local mode ─────────────────────────────────────────────────────────
# Source .env if present
if [ -f "$ROOT/.env" ]; then
    set -a; source "$ROOT/.env"; set +a
fi

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
APP_PORT="${APP_PORT:-8000}"

echo "=== FundPilot Status ==="
echo ""

# Database
echo "── Database ──"
if command -v pg_isready &>/dev/null; then
    if pg_isready -h "$DB_HOST" -p "$DB_PORT" -q; then
        echo "  PostgreSQL:  RUNNING  ($DB_HOST:$DB_PORT)"
    else
        echo "  PostgreSQL:  STOPPED"
    fi
else
    echo "  PostgreSQL:  UNKNOWN (pg_isready not available)"
fi

# Backend
echo ""
echo "── Backend ──"
BACKEND_PID=$(lsof -ti tcp:"$APP_PORT" 2>/dev/null || true)
if [ -n "$BACKEND_PID" ]; then
    echo "  API Server:  RUNNING  (port $APP_PORT, PID $BACKEND_PID)"
    echo "  Health:      $(curl -s http://localhost:$APP_PORT/health 2>/dev/null || echo 'unreachable')"
else
    echo "  API Server:  STOPPED"
fi

echo ""
echo "── Endpoints ──"
echo "  API:     http://localhost:$APP_PORT/api/v1"
echo "  Health:  http://localhost:$APP_PORT/health"
echo "  Docs:    http://localhost:$APP_PORT/docs"
