# FundPilot 架构文档

> 最后更新: 2026-05-29

---

## 一、项目目录结构

```
/Users/yew/Program/FundPilot/
├── backend/
│   ├── app/
│   │   ├── main.py                        # FastAPI 入口 + 生命周期
│   │   ├── core/                          # 全局基础设施
│   │   │   ├── config.py                  # pydantic-settings 配置
│   │   │   ├── constants.py               # 枚举 + 采集器元信息
│   │   │   ├── database.py                # SQLAlchemy 异步引擎 + Session 工厂
│   │   │   ├── response.py                # 统一响应 ApiResponse
│   │   │   ├── errors.py                  # 异常类 + 错误码
│   │   │   ├── auth.py                    # API Key 认证中间件
│   │   │   └── task_lock.py               # 任务去重锁
│   │   │
│   │   ├── models/                        # SQLAlchemy ORM 模型（19 张表）
│   │   │   ├── __init__.py                # 注册所有模型
│   │   │   ├── base.py                    # 基类 + TimestampMixin
│   │   │   ├── fund.py                    # Fund, FundNav, FundEstimate
│   │   │   ├── sector.py                  # Sector, SectorSnapshot, SectorMoneyFlow, SectorRealtime
│   │   │   ├── news.py                    # NewsArticle, NewsSectorLink
│   │   │   ├── analysis.py                # AnalysisReport, FundAdvice, Recommendation
│   │   │   ├── sentiment.py               # MarketSentiment
│   │   │   ├── system.py                  # AIProvider, CollectorSetting, CollectLog, PromptSetting
│   │   │   └── watchlist.py               # WatchedFund, WatchedSector
│   │   │
│   │   ├── schemas/                       # Pydantic 请求/响应模型
│   │   │   ├── fund.py / sector.py / news.py / analysis.py
│   │   │   ├── system.py / ai.py / chat.py / watchlist.py
│   │   │   └── recommend.py
│   │   │
│   │   ├── repositories/                  # 数据库访问层（仅 CRUD）
│   │   │   ├── base.py                    # BaseRepository
│   │   │   ├── fund_repo.py / sector_repo.py / news_repo.py
│   │   │   ├── analysis_repo.py           # + RecommendationRepo
│   │   │   ├── sentiment_repo.py
│   │   │   ├── system_repo.py
│   │   │   └── watchlist_repo.py
│   │   │
│   │   ├── services/                      # 业务逻辑层
│   │   │   ├── fund_service.py            # 基金搜索/详情
│   │   │   ├── sector_service.py          # 板块排行/详情/实时行情
│   │   │   ├── collector_service.py       # 14 个采集方法
│   │   │   ├── analysis_service.py        # AI 分析引擎（报告/建议/情绪）
│   │   │   ├── chat_service.py            # AI 问询 SSE 流式
│   │   │   ├── recommendation_service.py  # 综合推荐 + 加仓推荐
│   │   │   └── sentiment_service.py       # 市场情绪复合评分计算
│   │   │
│   │   ├── integrations/                  # 第三方数据源
│   │   │   ├── base.py                    # with_retry 重试
│   │   │   └── akshare/
│   │   │       ├── __init__.py            # force_ipv4
│   │   │       ├── fund_datasource.py     # 基金数据
│   │   │       ├── sector_datasource.py   # 板块数据 + 资金流向
│   │   │       ├── news_datasource.py     # 多源新闻（东方财富/金十/财联社/华尔街见闻）
│   │   │       └── sentiment_datasource.py # 市场情绪（涨停/北向/两融等）
│   │   │
│   │   ├── ai/                            # AI Provider 适配器
│   │   │   ├── base.py                    # AIProvider 抽象基类
│   │   │   ├── openai_compat.py           # OpenAI 兼容适配器（DeepSeek/GLM/Qwen/OpenAI/Kimi/MiniMax）
│   │   │   └── prompts.py                 # 所有提示词模板
│   │   │
│   │   ├── api/v1/                        # API 路由（极薄）
│   │   │   ├── router.py                  # 路由聚合
│   │   │   ├── funds.py / sectors.py / news.py
│   │   │   ├── collect.py                 # 采集触发/配置/日志
│   │   │   ├── analysis.py                # AI 分析
│   │   │   ├── recommend.py               # 推荐系统
│   │   │   ├── watchlist.py               # 关注列表
│   │   │   ├── chat.py                    # AI 问询 SSE
│   │   │   ├── ai_providers.py            # AI Provider 管理 + 连通性测试
│   │   │   └── prompts.py                 # 提示词编辑
│   │   │   └── realtime.py                # 实时行情
│   │   │
│   │   ├── tasks/                         # APScheduler 定时任务
│   │   │   ├── scheduler.py               # 调度器 + 任务注册
│   │   │   ├── collect_tasks.py           # 14 个采集任务
│   │   │   └── analysis_tasks.py          # AI 分析任务
│   │   │
│   │   └── utils/
│   │       └── encryption.py              # EncryptedText 透明加解密
│   │
│   ├── tests/                             # pytest 测试
│   ├── scripts/                           # 工具脚本
│   ├── docs/                              # 文档
│   └── .env.example
│
├── frontend/                              # React + Vite + Ant Design
│   └── src/
│       ├── api/                           # API 客户端（ky）
│       ├── pages/
│       │   ├── Dashboard.tsx              # 投资看板
│       │   ├── funds/                     # 基金查询/详情
│       │   ├── sectors/                   # 板块排行/详情
│       │   ├── analysis/                  # 报告/建议/情绪/推荐
│       │   ├── collect/                   # 采集状态/日志/配置
│       │   ├── settings/                  # AI 配置
│       │   ├── watchlist/                 # 关注列表
│       │   └── news/                      # 新闻
│       └── components/                    # 通用组件
│
├── scripts/db/                            # 数据库初始化脚本
│   ├── schema.sql                         # 19 张表 DDL
│   ├── seed.sql                           # 14 个采集器初始数据
│   ├── create.sh                          # 建表脚本
│   └── seed.sh                            # 初始数据导入
│
├── scripts/                               # 运维脚本（start/stop/status）
├── docker-compose.yml
├── .gitignore
├── CLAUDE.md
└── README.md
```

---

## 二、技术栈

### 后端

| 包 | 用途 |
|----|------|
| Python 3.12.13 + FastAPI + Uvicorn | Web 框架 |
| SQLAlchemy 2.0 async + asyncpg | ORM + PostgreSQL 驱动 |
| APScheduler | 定时任务调度 |
| AkShare | 财经数据源 |
| httpx + aiohttp | HTTP 客户端 |
| openai | AI Provider 适配 |
| cryptography (Fernet) | API Key 加密存储 |

### 前端

| 包 | 用途 |
|----|------|
| React 19 + TypeScript 6 + Vite 8 | 框架 |
| Ant Design 6 | UI 组件库 |
| TanStack React Query 5 | 异步状态管理 |
| ECharts + echarts-for-react | 图表（仪表盘） |
| ky | HTTP 客户端 |
| react-router-dom 7 | 路由 |

---

## 三、数据库模型

### 19 张表总览

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| `funds` | 基金基本信息 | code, name, type, company, latest_price |
| `fund_navs` | 基金每日净值 | fund_id, date, nav, daily_change_pct |
| `fund_estimates` | 基金盘中估值 | fund_id, estimate_nav, estimate_change_pct |
| `sectors` | 板块信息 | name, code, category(industry/concept) |
| `sector_snapshots` | 板块收盘快照 | sector_id, timestamp, price, change_pct |
| `sector_money_flows` | 板块资金流向 | sector_id, date, main_force_net_inflow, retail_net_inflow |
| `sector_realtime` | 板块实时行情 | sector_id, price, change_pct, volume |
| `news_articles` | 新闻文章 | title, source, url, published_at, sentiment_score |
| `news_sector_links` | 新闻-板块关联 | news_id, sector_id |
| `analysis_reports` | AI 分析报告 | date, report_type, content(JSONB) |
| `fund_advices` | AI 基金建议 | fund_id, date, action, reason(JSONB) |
| `recommendations` | AI 推荐结果 | date, mode(top_picks/dip_buy), rec_type, action, reason_detail |
| `market_sentiments` | 市场情绪指标 | date, limit_up_count, north_bound_net_inflow, composite_sentiment_score |
| `watched_funds` | 关注基金 | fund_id, holding_amount |
| `watched_sectors` | 关注板块 | sector_id |
| `collector_settings` | 采集器配置 | collector_name, interval_seconds, schedule_config(JSONB), other_config |
| `collect_logs` | 采集执行日志 | collector_name, status, records_added, duration_ms |
| `ai_providers` | AI 模型配置 | name, provider_type, api_key(加密), api_base_url |
| `prompt_settings` | 自定义提示词 | prompt_key, prompt_text |

### 通用约定

- 所有表使用 `UUID` 主键 + `gen_random_uuid()` 默认值
- 所有表包含 `created_at` + `updated_at` 自动时间戳
- JSONB 字段存储结构化数据（分析结果、定时配置、额外参数）

---

## 四、分层架构

```
API (thin) ──→ Services (business) ──→ Repositories (CRUD) ──→ DB
                  │
                  ├──→ Integrations (第三方 API)
                  └──→ AI (Provider 适配器)
```

### 职责边界

- **API 路由** — 参数校验、调用 service、返回响应。不含任何业务逻辑
- **Service** — 业务编排、组合数据源、调用 AI。不含数据库访问细节
- **Repository** — 仅做 SQL CRUD/upsert/search。不含业务判断
- **Integration** — 第三方 API 调用、AkShare 封装、with_retry 重试
- **AI** — Provider 抽象、Prompt 模板、JSON 结构化输出

---

## 五、采集系统

### 14 个采集器

| 采集器 | 默认间隔 | 数据源 |
|--------|---------|--------|
| `fund_list` | 每月 1 日 00:00 | AkShare fund_open_fund_info_em |
| `fund_nav_history` | 每月 1 日 01:00 | AkShare fund_open_fund_info_em |
| `fund_nav_daily` | 每日 00:00 | AkShare fund_open_fund_info_em |
| `fund_estimate` | 交易时段每 5min | AkShare fund_estimate_em |
| `etf` | 交易时段每 5min | AkShare fund_etf_spot_em |
| `sector_list` | 每月 1 日 14:00 | AkShare stock_board_industry/concept_em |
| `sector_batch_history` | 每月 1 日 15:00 | EM push2his |
| `sector_batch_daily` | 工作日 15:30 | EM push2his + THS |
| `sector_realtime` | 交易时段每 5min | THS 排行 |
| `market_sentiment` | 工作日 14:00 | 9 个 AkShare 情绪 API |
| `news` | 每 60min | 东方财富/金十/财联社/华尔街见闻 |
| `news_sentiment` | 每 60min | DeepSeek AI 分析 |
| `recommend_top_picks` | 每 4h | AI + 市场排行/资金流/情绪 |
| `recommend_dip_buy` | 每 12h | AI + 净值回撤/板块/情绪 |

### 采集流程

```
APScheduler cron 触发 → collect_tasks.py → _should_run 校验
    → CollectorService.collect_xxx() → datasource.fetch()
    → 数据清洗/转换 → repository.batch_upsert()
    → _write_collect_log() → 记录日志
```

### 定时配置

支持两种模式：
- **interval**：按固定间隔执行（如每 60 分钟），可选激活时间窗口（如 09:30-15:00）
- **specific_time**：在指定时刻执行（如 00:00），可选 weekdays/month_days

配置存储在 `collector_settings.schedule_config`（JSONB），通过前端采集配置页编辑。

---

## 六、AI 推荐系统

### 综合推荐（Top Picks）

流程：板块排行 TOP + 资金流向 + 基金涨幅排行 + 新闻情绪 → DeepSeek 综合分析 → 结构化推荐列表

### 加仓推荐（Dip Buy）

流程：筛选阶段跌幅 > 阈值 + 连跌天数达标的基金 → 取净值走势 + 板块表现 + 新闻情绪 → AI 判断加仓/观望/止损

两种推荐结果均写入 `recommendations` 表，支持前端查看历史、按日期筛选、批量删除。

---

## 七、安全

- API Key 通过 `ENCRYPTION_KEY`（Fernet）加密后存储在 `ai_providers` 表
- `.env` 文件在 `.gitignore` 中排除，不提交到 Git
- 所有敏感配置通过环境变量注入，代码中无硬编码密钥
- API 层支持可选的 API Key 鉴权中间件

---

## 八、数据库初始化

不再在应用启动时自动建表，改为独立脚本：

```bash
./scripts/db/create.sh --drop   # 清空重建 19 张表
./scripts/db/seed.sh            # 导入 14 个采集器默认配置
```

详见 [scripts/db/schema.sql](scripts/db/schema.sql) 和 [scripts/db/seed.sql](scripts/db/seed.sql)。
