# FundPilot CLI Skill

Use the `fundpilot` CLI to query Chinese fund data, sector rankings, AI analysis reports, and manage data collection.

## Prerequisites

- FundPilot backend must be running (default: `http://localhost:8000`)
- Set `FUNDPILOT_URL` env var if backend is at a different address

## Quick Reference

All commands output JSON by default. Add `--table` to commands that support it for tabular output.

### Fund Queries

```
# Search funds by name
fundpilot fund search --name 新能源 --page 1 --page-size 10

# Search by type (stock/mixed/index/etf/bond/monetary/qdii)
fundpilot fund search --type stock --page 1 --page-size 10 --table

# Get fund detail by code
fundpilot fund detail 000001

# Get fund NAV history
fundpilot fund nav 000001 --start 2026-01-01 --end 2026-05-24 --table

# Get latest intraday estimate
fundpilot fund estimate 000001

# Batch estimates
fundpilot fund batch-estimate 000001,000011,110011
```

### Sector Queries

```
# Search sectors by name
fundpilot sector search --name 新能源 --category concept --table

# Get sector rankings (default: table output, top 20)
fundpilot sector rank --category industry --limit 10
fundpilot sector rank --category concept --limit 20 --table

# Get sector money flow
fundpilot sector money-flow <sector_uuid> --start 2026-05-01 --end 2026-05-24 --table
```

### AI Analysis

```
# List analysis reports
fundpilot analysis report-list --type daily --page 1

# Get latest report
fundpilot analysis report-latest --type daily

# List fund advice
fundpilot analysis advice-list --action buy --page 1

# Get latest market sentiment
fundpilot analysis sentiment-latest
```

### Collection Management

```
# Trigger a collector
fundpilot collect trigger sector_daily
fundpilot collect trigger news --sources eastmoney,jin10

# Check status (all or specific)
fundpilot collect status
fundpilot collect status fund_list

# Stop a running collector
fundpilot collect stop fund_nav

# View collection logs
fundpilot collect logs --collector news --page 1 --table

# View/update collector settings
fundpilot collect settings
fundpilot collect settings fund_list --interval 86400 --active
```

### Available Collectors

| Name | Description | Default Interval |
|------|-------------|---------|
| `fund_list` | 基金列表 | 24h |
| `etf_list` | ETF 列表 | 24h |
| `etf` | ETF 实时行情 | 30s |
| `sector` | 板块实时行情 | 60s |
| `sector_list` | 板块列表 | 24h |
| `sector_daily` | 板块每日数据 | 24h |
| `sector_money_flow` | 板块资金流向 | 24h |
| `fund_estimate` | 基金估值 | 5min |
| `fund_nav` | 基金净值 | 24h |
| `news` | 新闻采集 | 10min |
| `market_sentiment` | 市场情绪 | 24h |

### Fund Types

| Code | Meaning |
|------|---------|
| `stock` | 股票型 |
| `mixed` | 混合型 |
| `index` | 指数型 |
| `etf` | ETF |
| `bond` | 债券型 |
| `monetary` | 货币型 |
| `qdii` | QDII |

### News Sources (for `collect trigger news --sources`)

| Key | Source |
|-----|--------|
| `eastmoney` | 东方财富 |
| `jin10` | 金十数据 |
| `cls` | 财联社 |
| `wallstreetcn` | 华尔街见闻 |

## AI Usage Patterns

### Pattern 1: User asks about market conditions
Run sentiment + rank queries together to give a complete picture:
```
fundpilot analysis sentiment-latest
fundpilot sector rank --category concept --limit 10
```

### Pattern 2: User asks about a specific fund
Get fund detail + estimate + latest advice:
```
fundpilot fund detail <code>
fundpilot fund estimate <code>
```

### Pattern 3: User asks to collect data
Trigger the appropriate collector:
```
fundpilot collect trigger <collector_name>
fundpilot collect status <collector_name>
```

### Pattern 4: User asks about sectors
Search to find the sector UUID, then get details:
```
fundpilot sector search --name <keyword>
fundpilot sector rank --category concept --limit 10
```

## Important Notes

- The CLI uses the FundPilot REST API — it must be running
- `--table` flag is useful for human-readable output; omit for machine parsing
- Sector operations (money-flow, detail) require a UUID, not a name — use `sector search` to find the ID first
- Collection triggers return immediately; use `collect status` to check progress
- All commands return JSON with the structure `{"success": true, "data": ...}`
