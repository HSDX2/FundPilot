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

# 1. Stop the backend server (find by port)
echo ""
echo "[1/2] Stopping backend..."
BACKEND_PID=$(lsof -ti tcp:"$APP_PORT" 2>/dev/null || true)
if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    echo "  Stopped uvicorn (PID $BACKEND_PID) on port $APP_PORT"
else
    echo "  No backend process found on port $APP_PORT"
fi

# 2. Optionally stop PostgreSQL
echo ""
echo "[2/2] Database — skipped (managed separately)"
echo "  To stop PostgreSQL: ./scripts/db/stop.sh"
