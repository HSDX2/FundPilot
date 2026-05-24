# FundPilot 开发进度

> 最后更新: 2026-05-24

---

## Phase 1 — 项目骨架与数据采集层

**目标**: 搭建项目骨架、数据库模型、AkShare 数据采集、基础 API、定时任务。

| # | 任务 | 状态 | 备注 |
|---|------|------|------|
| 1.1 | 项目初始化 (pyproject.toml, Docker, .env, .python-version) | 完成 | Python 3.12.13, 清华源 |
| 1.2 | Core 层 (config, database, response, errors) | 完成 | pydantic-settings, asyncpg |
| 1.3 | Base model + TimestampMixin | 完成 | UUID 主键, created_at/updated_at |
| 1.4 | 12 张表 ORM 模型 | 完成 | funds, fund_navs, fund_estimates, sectors, sector_snapshots, sector_money_flows, news_articles, news_sector_links, analysis_reports, fund_advices, ai_providers, collector_settings |
| 1.5 | Schemas 层 (Pydantic 请求/响应模型) | 完成 | fund, sector, news, analysis, system |
| 1.6 | BaseRepository + 全部 Repo | 完成 | CRUD + batch_upsert + search |
| 1.7 | AkShare 基金数据源 | 完成 | 基金列表, 净值历史, 实时估值, ETF 行情 |
| 1.8 | AkShare 板块数据源 | 完成 | 行业/概念板块列表, 历史日线, 实时行情, 成分股 |
| 1.9 | CollectorService (8 个采集方法) | 完成 | 含类型过滤、名称匹配、数据转换 |
| 1.10 | 基金 API (`/funds`, `/funds/{code}`, `/funds/{code}/nav`, `/funds/{code}/estimate`, `/funds/estimates/batch`) | 完成 | 分页、筛选、搜索 |
| 1.11 | 板块 API (`/sectors`, `/sectors/{id}`, `/sectors/{id}/snapshots`, `/sectors/{id}/realtime`, `/sectors/rank/current`) | 完成 | 分页、排行 |
| 1.12 | 采集控制 API (`POST /collect/trigger`, `GET /collect/settings`, `PUT /collect/settings/{name}`) | 完成 | 9 个采集器手动触发 |
| 1.13 | 实时查询 API (`/realtime/funds/{code}`, `/realtime/sectors/boards`) | 完成 | 直调 AkShare |
| 1.14 | APScheduler 定时任务 (9 个) | 完成 | 交易日判断 + 配置驱动 |
| 1.15 | 强制停止 + 实时进度 + 事务拆分 | 完成 | `POST /collect/stop/{name}`, `GET /collect/status` |
| 1.16 | 重新采集支持 (batch_upsert + 去重) | 完成 | 按 code/(fund_id,date) 去重 |
| 1.17 | Dockerfile + docker-compose.yml | 完成 | postgres + backend |
| 1.18 | 测试 (254 个) | 完成 | core, models, schemas, integrations, services, api, tasks, ai |

---

## Phase 2 — 数据完善与服务层

**目标**: 新闻采集、资金流向采集、业务服务层补全、API 路由重构、采集可靠性增强。

| # | 任务 | 状态 | 备注 |
|---|------|------|------|
| 2.1 | AkShare 接口验证 (新闻、资金流向) | 完成 | `stock_news_em()` 列名确认, `stock_sector_fund_flow_rank()` 参数确认 |
| 2.2 | 新闻数据源重写 (`news_datasource.py`) | 完成 | 替换占位实现, `stock_news_em()` 列映射 |
| 2.3 | NewsArticleRepo.batch_upsert | 完成 | 按 URL 去重, 返回 (added, updated) |
| 2.4 | 新闻采集器 (`collect_news()` 实际逻辑 + 板块关键词匹配) | 完成 | 自动关联 news_sector_links, 标题+正文关键词匹配 |
| 2.5 | 资金流向数据源 (`fetch_sector_fund_flow`) | 完成 | 行业/概念资金流, 9 字段列映射 |
| 2.6 | SectorMoneyFlowRepo.batch_upsert | 完成 | 按 (sector_id, date) 去重 |
| 2.7 | 资金流向采集器 (`collect_sector_money_flow()`) | 完成 | 行业+概念双类型, 按名称匹配 sector_id |
| 2.8 | CollectLog 模型 + Repo (`collect_logs` 表) | 完成 | collector_name, status, duration_ms, records_added/updated |
| 2.9 | 采集日志集成 (每个 Collector 写入日志) | 完成 | 所有 10 个采集方法 finally 块写日志 |
| 2.10 | 重试机制 | 完成 | `with_retry()` 指数退避, 已应用到 3 个 datasource |
| 2.11 | FundService 创建 | 完成 | search_funds, get_fund_detail, get_fund_nav_history, get_fund_estimate, get_batch_estimates |
| 2.12 | SectorService 创建 | 完成 | search_sectors, get_sector_detail, get_sector_snapshots, get_sector_realtime, get_rank |
| 2.13 | API 路由重构 (调 service 而非 repo) | 完成 | funds.py, sectors.py 瘦身, DI 级联依赖 |
| 2.14 | 新闻 API (`GET /news`, `GET /news/{id}`) | 完成 | 分页、关键词/来源/日期筛选 |
| 2.15 | 资金流向 API (`GET /sectors/{id}/money-flow`) | 完成 | 日期范围筛选 |
| 2.16 | 采集日志 API (`GET /collect/logs`) | 完成 | 分页、按采集器筛选 |
| 2.17 | 新采集器注册 (constants + scheduler + tasks) | 完成 | news, sector_money_flow |
| 2.18 | 灵活定时配置 API (`PUT /settings/{name}/schedule`) | 完成 | interval/specific_time 双模式，激活窗口 + 星期/月日维度 |
| 2.19 | schedule_config 运行时评估 (`_evaluate_schedule`) | 完成 | scheduler 从 DB 读 cron，任务执行前二次校验 |
| 2.20 | 多源新闻采集 — 金十数据 Plan B | 完成 | 直爬 `flash-api.jin10.com/get_flash_list`，httpx 异步请求 |
| 2.21 | 多源新闻采集 — 财联社 + 华尔街见闻 | 完成 | `stock_info_global_cls()` + `macro_info_ws()` |
| 2.22 | 新闻源参数配置 | 完成 | `CollectorTriggerRequest.sources`，`collect_news(sources=)`，定时任务从 schedule_config 读取 |
| 2.23 | Bug 修复 — `ApiJSONResponse._serialize` | 完成 | 未知类型 raise TypeError 避免无限递归；新增 time 类型序列化 |

---

## Phase 3 — AI 分析引擎

**目标**: 多 AI Provider 适配、分析报告生成、基金操作建议。

| # | 任务 | 状态 | 备注 |
|---|------|------|------|
| 3.1 | AI Provider 抽象基类 (`ai/base.py`) | **完成** | `chat()` + `analyze()` 接口 |
| 3.2 | OpenAI 兼容适配器 (`ai/openai_compat.py`) | **完成** | 一个适配器覆盖 6 家：DeepSeek/GLM/QWEN/OpenAI/Kimi/MiniMax |
| 3.3 | `AIProviderType` 枚举扩展 | **完成** | deepseek, glm, qwen, openai, kimi, minimax, custom |
| 3.4 | `ai_providers` 模型扩展 — `extra_config` JSON | **完成** | 预留 max_tokens, temperature, top_p 默认值 |
| 3.5 | `AIProviderRepo` 完善 | **完成** | get_active, set_active(activate + 自动停用其他), list_by_types |
| 3.6 | AI Provider 管理 API | **完成** | `GET/POST/PUT/DELETE /admin/ai-providers`, `POST /{id}/activate` |
| 3.7 | Provider 预设注册表 | **完成** | 6 家厂商 base_url + 默认 model 预设 |
| 3.8 | 板块分析报告生成 (日/周/月) | **完成** | `generate_sector_report()`，结构化 prompt → JSONB 存储 |
| 3.9 | 基金操作建议生成 (buy/hold/reduce/redeem) | **完成** | `generate_fund_advice()`，多因子评分，action fallback |
| 3.10 | 分析报告 API | **完成** | `GET /analysis/reports`, `POST /generate`, `/latest` |
| 3.11 | 基金建议 API | **完成** | `GET /analysis/advice`, `POST /generate`, `/generate-batch` |
| 3.12 | 新闻情感分析 | **完成** | `batch_analyze_sentiment()`，并发控制，sentiment_score 填充 |
| 3.13 | 情绪数据采集器 (涨停/跌停/北向/融资融券/龙虎榜/主力流向) | **完成** | 9 个数据源, `SentimentDataSource`, `collect_market_sentiment()` |
| 3.14 | 情绪复合指标计算 | **完成** | 10 因子加权评分, 0-100, `SentimentService` |
| 3.15 | AI 分析定时任务 | **完成** | 每日 15:30 板块分析 + 16:00 情感分析，仅交易日 |

---

## Phase 4 — CLI & Skill

**目标**: 命令行工具 + Claude Code Skill，支持终端操作和 AI 助手调用。

| # | 任务 | 状态 | 备注 |
|---|------|------|------|
| 4.1 | CLI 骨架 (typer) + HTTP 客户端 | **完成** | `fundpilot` 命令，5 个子命令组 |
| 4.2 | 基金查询命令 (search/detail/nav/estimate/batch-estimate) | **完成** | 搜索、详情、净值、估值、批量 |
| 4.3 | 板块查询命令 (search/rank/money-flow) | **完成** | 搜索、排行、资金流向 |
| 4.4 | 分析报告命令 (report-list/report-latest/advice-list/sentiment-latest) | **完成** | 报告、建议、情绪 |
| 4.5 | 采集管理命令 (trigger/status/stop/logs/settings) | **完成** | 触发、状态、停止、日志、配置 |
| 4.6 | Skill 文件 | **完成** | `.claude/skills/fundpilot.md`，封装常用 CLI 模式 |
| 4.7 | CLI 测试 (44 个) | **完成** | client, commands, output |

---

## Phase 5 — 前端页面

**目标**: Web 可视化界面，展示数据和分析结果。

| # | 任务 | 状态 | 备注 |
|---|------|------|------|
| 5.1 | 前端框架搭建 | 待开发 | 技术栈待定 |
| 5.2 | 基金筛选/搜索页面 | 待开发 | 列表 + 详情 + 净值图表 |
| 5.3 | 板块热度排行榜 | 待开发 | 实时涨幅 + 资金流向 |
| 5.4 | 分析报告展示页 | 待开发 | 板块评分、趋势、风险 |
| 5.5 | 基金操作建议页 | 待开发 | 建议列表 + 理由展示 |
| 5.6 | 采集控制台 | 待开发 | 手动触发、状态监控、日志查看 |
| 5.7 | 系统配置页 | 待开发 | AI Provider、采集器频率配置 |

---

## 进度总览

```
Phase 1  ████████████████████ 100%  已完成 (18/18)
Phase 2  ████████████████████ 100%  已完成 (23/23)
Phase 3  ████████████████████ 100%  已完成 (15/15)
Phase 4  ████████████████████ 100%  已完成 (7/7)
Phase 5  ░░░░░░░░░░░░░░░░░░░░   0%  待开发 (0/7)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
总体     ██████████████████░░  88%  (63/72)
```
