#!/usr/bin/env bash
# ── FundPilot: Stop all services ───────────────────────────────────────
# Usage: ./scripts/stop.sh [--docker]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "${1:-}" == "--docker" ]]; then
    echo "=== Stopping FundPilot (Docker) ==="
    cd "$ROOT"
    docker compose down
    echo "All services stopped."
    exit 0
fi

# ── Local mode ─────────────────────────────────────────────────────────
echo "=== Stopping FundPilot (local) ==="

# Source .env if present
if [ -f "$ROOT/.env" ]; then
    set -a; source "$ROOT/.env"; set +a
fi

APP_PORT="${APP_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# 1. Stop frontend dev server
echo ""
echo "[1/3] Stopping frontend..."
FRONTEND_PID=$(lsof -ti tcp:"$FRONTEND_PORT" 2>/dev/null || true)
if [ -n "$FRONTEND_PID" ]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
    echo "  Stopped frontend (PID $FRONTEND_PID) on port $FRONTEND_PORT"
else
    echo "  No frontend process found on port $FRONTEND_PORT"
fi

# 2. Stop backend server
echo ""
echo "[2/3] Stopping backend..."
BACKEND_PID=$(lsof -ti tcp:"$APP_PORT" 2>/dev/null || true)
if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    echo "  Stopped backend (PID $BACKEND_PID) on port $APP_PORT"
else
    echo "  No backend process found on port $APP_PORT"
fi

# 3. Optionally stop PostgreSQL
echo ""
echo "[3/3] Database — skipped (managed separately)"
echo "  To stop PostgreSQL: ./scripts/db/stop.sh"
