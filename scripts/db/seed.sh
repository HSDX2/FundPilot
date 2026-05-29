#!/usr/bin/env bash
# ── FundPilot: 插入初始数据 ──────────────────────────────────
# 用法: ./scripts/db/seed.sh
#
# 插入 collector_settings 默认配置。
# 已存在的数据不会被覆盖（ON CONFLICT DO NOTHING）。
# ────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# 从 .env 读取数据库配置（如果存在）
if [ -f "$ROOT/.env" ]; then
    set -a; source "$ROOT/.env"; set +a
fi

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-fundpilot}"
DB_PASSWORD="${DB_PASSWORD:-change-me}"
DB_NAME="${DB_NAME:-fundpilot}"

export PGPASSWORD="$DB_PASSWORD"

SEED_FILE="$ROOT/scripts/db/seed.sql"

if [ ! -f "$SEED_FILE" ]; then
    echo "ERROR: seed.sql not found at $SEED_FILE"
    exit 1
fi

echo "=== Seeding initial data ==="
echo "  Host: $DB_HOST:$DB_PORT"
echo "  User: $DB_USER"
echo "  DB:   $DB_NAME"

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SEED_FILE" 2>&1

echo ""
echo "=== Seed completed ==="