#!/usr/bin/env bash
# ── FundPilot: 创建数据库表结构 ──────────────────────────────
# 用法: ./scripts/db/create.sh [--drop]
# --drop: 先删除已存在的同名表再重建（危险！会清空数据）
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

SCHEMA_FILE="$ROOT/scripts/db/schema.sql"

if [ ! -f "$SCHEMA_FILE" ]; then
    echo "ERROR: schema.sql not found at $SCHEMA_FILE"
    exit 1
fi

echo "=== Creating database schema ==="
echo "  Host: $DB_HOST:$DB_PORT"
echo "  User: $DB_USER"
echo "  DB:   $DB_NAME"

if [ "${1:-}" == "--drop" ]; then
    echo ""
    echo "⚠️  WARNING: --drop mode enabled. Existing tables will be dropped!"
    echo "  Press Ctrl+C to cancel, or wait 3 seconds to continue..."
    sleep 3

    # 按依赖顺序删除所有表（外键约束需要先删子表）
    echo "  Dropping existing tables..."
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
DROP TABLE IF EXISTS
    news_sector_links,
    sector_money_flows,
    sector_realtime,
    sector_snapshots,
    fund_navs,
    fund_estimates,
    fund_advices,
    analysis_reports,
    watched_funds,
    watched_sectors,
    market_sentiments,
    news_articles,
    collect_logs,
    collector_settings,
    ai_providers,
    prompt_settings,
    sectors,
    funds
CASCADE;
    " 2>&1
    echo "  Done."
fi

# 执行建表
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SCHEMA_FILE" 2>&1

echo ""
echo "=== Schema created successfully ==="