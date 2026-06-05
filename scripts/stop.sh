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
    sleep 1
    # 如进程未退出，强制杀死
    if kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill -9 "$FRONTEND_PID" 2>/dev/null || true
        echo "  Force killed frontend (PID $FRONTEND_PID)"
    else
        echo "  Stopped frontend (PID $FRONTEND_PID) on port $FRONTEND_PORT"
    fi
else
    echo "  No frontend process found on port $FRONTEND_PORT"
fi

# 2. Stop backend server
echo ""
echo "[2/3] Stopping backend..."
BACKEND_PID=$(lsof -ti tcp:"$APP_PORT" 2>/dev/null || true)
if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    sleep 3
    # 如进程未退出，强制杀死（连带清理 multiprocessing 孤儿进程）
    if kill -0 "$BACKEND_PID" 2>/dev/null; then
        # 先清理 ProcessPoolExecutor 的子进程
        CHILD_PIDS=$(pgrep -P "$BACKEND_PID" 2>/dev/null || true)
        if [ -n "$CHILD_PIDS" ]; then
            kill -9 $CHILD_PIDS 2>/dev/null || true
        fi
        kill -9 "$BACKEND_PID" 2>/dev/null || true
        echo "  Force killed backend (PID $BACKEND_PID)"
    else
        echo "  Stopped backend (PID $BACKEND_PID) on port $APP_PORT"
    fi
else
    echo "  No backend process found on port $APP_PORT"
fi

# 3. Optionally stop PostgreSQL
echo ""
echo "[3/3] Database — skipped (managed separately)"
echo "  To stop PostgreSQL: ./scripts/db/stop.sh"
