# FundPilot Architecture Document

## Phase 1: 项目骨架与数据采集层

---

## 一、项目目录结构

```
/Users/yew/Program/FundPilot/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                        # FastAPI 入口 + 生命周期
│   │   │
│   │   ├── core/                          # 全局基础设施
│   │   │   ├── __init__.py
│   │   │   ├── config.py                  # pydantic-settings 配置
│   │   │   ├── constants.py               # 常量
│   │   │   ├── database.py                # SQLAlchemy 引擎 + Session
│   │   │   ├── response.py                # 统一响应封装
│   │   │   └── errors.py                  # 异常定义 + 错误码
│   │   │
│   │   ├── models/                        # SQLAlchemy ORM 模型
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # 声明性基类 + Mixin (UUID, timestamps)
│   │   │   ├── fund.py                    # Fund, FundNav, FundEstimate
│   │   │   ├── sector.py                  # Sector, SectorSnapshot, SectorMoneyFlow
│   │   │   ├── news.py                    # NewsArticle, NewsSectorLink
│   │   │   ├── analysis.py                # AnalysisReport, FundAdvice
│   │   │   └── system.py                  # AIProvider, CollectorSettings
│   │   │
│   │   ├── schemas/                       # Pydantic 请求/响应模型
│   │   │   ├── __init__.py
│   │   │   ├── fund.py
│   │   │   ├── sector.py
│   │   │   ├── news.py
│   │   │   ├── analysis.py
│   │   │   └── system.py
│   │   │
│   │   ├── repositories/                  # 数据库访问层 (仅 CRUD)
│   │   │   ├── __init__.py
│   │   │   ├── fund_repo.py
│   │   │   ├── sector_repo.py
│   │   │   ├── news_repo.py
│   │   │   └── system_repo.py
│   │   │
│   │   ├── integrations/                  # 第三方 API 封装
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # 集成基类
│   │   │   ├── akshare/                   # AkShare 数据源
│   │   │   │   ├── __init__.py
│   │   │   │   ├── fund_datasource.py     # 基金数据
│   │   │   │   ├── sector_datasource.py   # 板块数据
│   │   │   │   └── news_datasource.py     # 新闻数据 (占位)
│   │   │   └── http_client.py             # 通用 HTTP 客户端
│   │   │
│   │   ├── services/                      # 业务逻辑层
│   │   │   ├── __init__.py
│   │   │   ├── fund_service.py
│   │   │   ├── sector_service.py
│   │   │   └── collector_service.py       # 统筹采集流程的服务
│   │   │
│   │   ├── ai/                            # AI 分析 (Phase 3)
│   │   │   └── __init__.py
│   │   │
│   │   ├── api/                           # 路由层 (极薄，仅入参校验+调用 service)
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py              # v1 路由聚合
│   │   │   │   ├── funds.py
│   │   │   │   ├── sectors.py
│   │   │   │   └── collect.py             # 手动触发采集接口
│   │   │   └── deps.py                    # 依赖项 (Session 注入等)
│   │   │
│   │   └── tasks/                         # APScheduler 定时任务
│   │       ├── __init__.py
│   │       ├── scheduler.py               # 调度器初始化 + 任务注册
│   │       └── collect_tasks.py           # 各采集任务定义
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_repositories/
│   │   ├── test_services/
│   │   └── test_integrations/
│   │
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/                              # Phase 5 才开始
│   └── ...
│
├── docker-compose.yml
├── pyproject.toml
├── .python-version                        # 3.12.13
├── .env
├── ARCH.md
└── CLAUDE.md
```

---

## 二、技术选型与依赖

### 后端核心

| 包 | 用途 | 理由 |
|----|------|------|
| `fastapi` | Web 框架 | 异步原生、自动生成 OpenAPI |
| `uvicorn[standard]` | ASGI 服务器 | FastAPI 默认搭档 |
| `sqlalchemy[asyncio]` | ORM (2.0 风格) | 异步、类型安全 |
| `asyncpg` | PostgreSQL 异步驱动 | 高性能异步 PG 驱动 |
| `pydantic-settings` | 配置管理 | 环境变量类型安全读写 |
| `akshare` | 财经数据 | 免费开源，覆盖全面 |
| `aiohttp` | HTTP 客户端 | 异步爬虫/调用 |
| `apscheduler` | 定时任务 | 轻量，无需额外服务 |
| `httpx` | HTTP 客户端 | 备用 (兼容 AkShare 同步调用) |

### 开发工具

| 包 | 用途 |
|----|------|
| `pytest` + `pytest-asyncio` | 测试 |
| `ruff` | 代码检查 + 格式化 |
| `mypy` | 类型检查 |

### Python 源配置

使用国内镜像源优先：

```toml
# pyproject.toml
[[tool.pip.index-urls]]
url = "https://pypi.tuna.tsinghua.edu.cn/simple"
# 备选: https://mirrors.aliyun.com/pypi/simple/
```

---

## 三、数据库模型设计（Phase 1 完整定义）

### 通用约定

- 所有表使用 **UUID** 主键
- 所有表包含 `created_at` + `updated_at` 时间戳
- 从 `TimestampMixin` 基类继承

### 3.1 基金信息表 (`funds`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `code` | VARCHAR(16) NOT NULL UNIQUE | 基金代码 (如 `000001`) |
| `name` | VARCHAR(255) NOT NULL | 基金名称 |
| `type` | VARCHAR(32) | 基金类型 (股票型/混合型/指数/债券/货币/ETF/QDII) |
| `company` | VARCHAR(128) | 基金公司 |
| `established_date` | DATE | 成立日期 |
| `scale` | DECIMAL(20,4) | 基金规模 (亿元) |
| `fund_manager` | VARCHAR(64) | 基金经理 |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

索引: `(code)` UNIQUE, `(type)`, `(company, type)`

### 3.2 基金历史净值表 (`fund_navs`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `fund_id` | UUID FK→funds | |
| `date` | DATE NOT NULL | 净值日期 |
| `nav` | DECIMAL(12,4) | 单位净值 |
| `accumulated_nav` | DECIMAL(12,4) | 累计净值 |
| `daily_change_pct` | DECIMAL(8,4) | 日涨跌幅 (%) |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

索引: `(fund_id, date)` UNIQUE

### 3.3 基金实时估值表 (`fund_estimates`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `fund_id` | UUID FK→funds | |
| `timestamp` | TIMESTAMP NOT NULL | 估值时间 (盘中) |
| `estimate_nav` | DECIMAL(12,4) | 估算净值 |
| `estimate_change_pct` | DECIMAL(8,4) | 估算涨跌幅 (%) |
| `estimate_change_amount` | DECIMAL(8,4) | 估算涨跌额 |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

索引: `(fund_id, timestamp)` UNIQUE

### 3.4 板块信息表 (`sectors`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `name` | VARCHAR(64) NOT NULL | 板块名称 (如 "半导体"、"新能源") |
| `code` | VARCHAR(32) UNIQUE | 板块代码 |
| `category` | VARCHAR(16) NOT NULL | 分类: `industry`(行业)/`concept`(概念) |
| `description` | TEXT | 描述 |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

索引: `(category, name)` 复合索引

### 3.5 板块快照表 (`sector_snapshots`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `sector_id` | UUID FK→sectors | |
| `timestamp` | TIMESTAMP NOT NULL | 快照时间 (盘中或收盘) |
| `price` | DECIMAL(14,4) | 当前价/收盘价 |
| `open` | DECIMAL(14,4) | 开盘价 |
| `high` | DECIMAL(14,4) | 最高价 |
| `low` | DECIMAL(14,4) | 最低价 |
| `change_pct` | DECIMAL(8,4) | 涨跌幅 (%) |
| `volume` | BIGINT | 成交量 |
| `turnover` | DECIMAL(20,4) | 成交额 (元) |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

索引: `(sector_id, timestamp)` UNIQUE

### 3.6 板块资金流向表 (`sector_money_flows`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `sector_id` | UUID FK→sectors | |
| `date` | DATE NOT NULL | |
| `main_force_net_inflow` | DECIMAL(20,4) | 主力净流入 (元) |
| `retail_net_inflow` | DECIMAL(20,4) | 散户净流入 (元) |
| `middle_net_inflow` | DECIMAL(20,4) | 中单净流入 |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

索引: `(sector_id, date)` UNIQUE

### 3.7 新闻表 (`news_articles`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `title` | TEXT NOT NULL | 标题 |
| `content` | TEXT | 正文/摘要 |
| `source` | VARCHAR(32) | 来源 (东方财富/财联社/新浪) |
| `url` | TEXT UNIQUE | 原文链接 |
| `published_at` | TIMESTAMP | 发布时间 |
| `sentiment_score` | DECIMAL(4,2) | 情感分数 (-1~1, NULL 未分析) |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### 3.8 新闻-板块关联表 (`news_sector_links`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `news_id` | UUID FK→news_articles | |
| `sector_id` | UUID FK→sectors | |
| `relevance_score` | DECIMAL(4,2) | 相关度 (0~1) |
| `PRIMARY KEY` | | (news_id, sector_id) |

### 3.9 AI 提供商配置表 (`ai_providers`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `name` | VARCHAR(64) NOT NULL | 显示名称 |
| `provider_type` | VARCHAR(32) NOT NULL | openai / claude / local / custom |
| `api_key` | TEXT | API Key (加密) |
| `api_base_url` | TEXT | 自定义 endpoint |
| `model_name` | VARCHAR(64) | 模型名 |
| `is_active` | BOOLEAN DEFAULT FALSE | 是否当前激活 |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### 3.10 分析报告表 (`analysis_reports`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `date` | DATE NOT NULL | 报告日期 |
| `report_type` | VARCHAR(16) NOT NULL | daily / weekly / monthly |
| `content` | JSONB NOT NULL | 结构化分析结果 |
| `ai_model` | VARCHAR(64) | 使用的 AI 模型 |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

**`content` JSONB 结构约定**:

```json
{
  "summary": "今日市场整体偏强，科技板块领涨...",
  "sectors": [
    {
      "sector_id": "uuid-xxx",
      "sector_name": "半导体",
      "score": 87,
      "trend": "bullish",
      "sentiment": 0.76,
      "risk": "medium",
      "confidence": 0.82,
      "reason": "国产替代政策利好+资金持续流入",
      "key_levels": {
        "support": 3200,
        "resistance": 3500
      }
    }
  ],
  "market_overview": {
    "overall_sentiment": 0.65,
    "hot_sector": "半导体",
    "risk_level": "medium"
  }
}
```

### 3.11 基金操作建议表 (`fund_advices`)

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `fund_id` | UUID FK→funds | |
| `date` | DATE NOT NULL | |
| `action` | VARCHAR(16) NOT NULL | buy / hold / reduce / redeem |
| `reason` | JSONB NOT NULL | 结构化理由 |
| `confidence` | DECIMAL(4,2) | 置信度 (0~1) |
| `ai_model` | VARCHAR(64) | |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

**`reason` JSONB 结构约定**:

```json
{
  "summary": "基金持仓板块近期资金流出明显...",
  "factors": [
    {"factor": "板块趋势", "impact": "negative", "weight": 0.4},
    {"factor": "资金流向", "impact": "negative", "weight": 0.3},
    {"factor": "政策面", "impact": "positive", "weight": 0.3}
  ],
  "sector_scores": {
    "新能源": 65,
    "半导体": 82
  },
  "suggested_action": "reduce",
  "alternatives": ["转投债券基金避险", "等待板块企稳"]
}
```

### 3.12 采集器配置表 (`collector_settings`)

用于支持各采集类型频率可配置 + 手动触发。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | |
| `collector_name` | VARCHAR(32) UNIQUE NOT NULL | 标识: `etf` / `sector` / `fund_estimate` / `news` |
| `display_name` | VARCHAR(64) | 显示名称 |
| `interval_seconds` | INTEGER NOT NULL | 采集间隔 (秒) |
| `is_active` | BOOLEAN DEFAULT TRUE | 是否启用自动采集 |
| `last_run_at` | TIMESTAMP | 上次执行时间 |
| `last_status` | VARCHAR(16) | success / failed / running |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

默认值:

| collector_name | interval_seconds |
|---|---|
| `etf` | 30 |
| `sector` | 60 |
| `fund_estimate` | 300 |
| `news` | 600 |

---

## 四、配置设计 (`core/config.py`)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "FundPilot"
    DEBUG: bool = False

    # 数据库
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "fundpilot"
    DB_PASSWORD: str = ""
    DB_NAME: str = "fundpilot"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # AI API (Phase 3)
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = ""
    CLAUDE_API_KEY: str = ""

    # 日志
    LOG_LEVEL: str = "INFO"
```

---

## 五、采集流程设计

### 5.1 分层职责

```
┌──────────┐    ┌──────────────┐    ┌──────────────┐
│  tasks/   │───▶│ services/    │───▶│ repositories/│
│ (调度触发) │    │ (业务编排)    │    │ (DB 持久化)   │
└──────────┘    └──────┬───────┘    └──────────────┘
                       │
              ┌────────▼────────┐
              │ integrations/   │
              │ (第三方 API 调用) │
              └─────────────────┘
```

### 5.2 集成基类 (`integrations/base.py`)

```python
class BaseDataSource(ABC):
    """第三方数据源抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """数据源标识"""
        ...

    @abstractmethod
    async def fetch(self, **kwargs) -> list[dict]:
        """拉取原始数据，返回 list[dict]"""
        ...
```

### 5.3 AkShare 基金数据源 (`integrations/akshare/fund_datasource.py`)

| 方法 | 对应 AkShare 接口 | 说明 |
|------|-------------------|------|
| `fetch_fund_list()` | `fund_open_fund_info_em` | 全市场基金列表 |
| `fetch_fund_nav(code)` | `fund_open_fund_info_em` → 解析净值 | 单只基金历史净值 |
| `fetch_estimate_all()` | `fund_estimate_em` | 所有基金实时估值 |
| `fetch_etf_spot()` | `fund_etf_spot_em` | ETF 实时行情 |

采集策略:
- 首次运行：全量拉取基金列表 + 近 1 年净值
- 每日增量：当日净值
- 盘中：5min 估值轮询、30s ETF 轮询
- 过滤规则：仅保留股票型/混合型/指数/ETF

### 5.4 AkShare 板块数据源 (`integrations/akshare/sector_datasource.py`)

| 方法 | 对应 AkShare 接口 | 说明 |
|------|-------------------|------|
| `fetch_board_list(category)` | `stock_board_industry_em` + `stock_board_concept_em` | 申万一级行业 + 概念板块 |
| `fetch_board_history(code)` | `stock_board_industry_hist_em` | 板块历史日线 |
| `fetch_board_realtime()` | `stock_board_industry_em` | 板块实时行情 |
| `fetch_board_cons(code)` | `stock_board_industry_cons_em` | 板块成分股 |

采集策略:
- 每日收盘 15:30：全量板块快照 + 资金流向
- 盘中：1min 轮询实时行情
- 每周：更新板块成分股

### 5.5 AkShare 新闻数据源 (`integrations/akshare/news_datasource.py`)

Phase 1 仅注册框架，Phase 2 实现。

### 5.6 CollectorService 编排 (`services/collector_service.py`)

```python
class CollectorService:
    """
    统筹采集流程:
    1. 从 datasource 拉取原始数据
    2. 清洗/转换 (过滤基金类型、格式化)
    3. 通过 repository 写入数据库
    """

    def __init__(self):
        self.fund_ds = FundDataSource()
        self.sector_ds = SectorDataSource()
        self.fund_repo = FundRepo()
        self.sector_repo = SectorRepo()

    async def collect_etf_spot(self) -> CollectResult:
        raw = await self.fund_ds.fetch_etf_spot()
        # 过滤 + 转换
        records = [ETFRecord.from_akshare(r) for r in raw]
        return await self.fund_repo.batch_upsert_estimates(records)

    async def collect_sector_realtime(self) -> CollectResult:
        raw = await self.sector_ds.fetch_board_realtime()
        records = [SectorSnapshot.from_akshare(r) for r in raw]
        return await self.sector_repo.batch_upsert_snapshots(records)

    # ...
```

---

## 六、API 接口设计（Phase 1 实现）

### 6.1 基金接口

```
GET /api/v1/funds
  → 基金列表，分页 + 筛选(type/company) + 搜索(name/code)
  → Response: { "success": true, "data": { items: Fund[], total: int, page: int, page_size: int }, "message": "" }

GET /api/v1/funds/{code}
  → 基金详情 + 最新净值
  → Response: FundDetail

GET /api/v1/funds/{code}/nav
  → 历史净值，?start_date=&end_date=
  → Response: { items: NavRecord[] }

GET /api/v1/funds/{code}/estimate
  → 最新实时估值
  → Response: EstimateRecord | null

GET /api/v1/funds/estimates
  → 批量估值 ?codes=000001,000011
  → Response: { items: EstimateRecord[] }
```

### 6.2 板块接口

```
GET /api/v1/sectors
  → 板块列表，?category=industry|concept
  → Response: { items: Sector[] }

GET /api/v1/sectors/{id}
  → 板块详情

GET /api/v1/sectors/{id}/snapshots
  → 板块快照历史，?start_time=&end_time=
  → Response: { items: SectorSnapshot[] }

GET /api/v1/sectors/{id}/realtime
  → 板块最新快照
  → Response: SectorSnapshot | null

GET /api/v1/sectors/rank
  → 板块今日涨跌幅排名，?category=&limit=
  → Response: { items: SectorRank[] }
```

### 6.3 采集控制接口

```
POST /api/v1/collect/trigger
  → 手动触发指定采集器
  → Body: { "collector": "etf" | "sector" | "fund_estimate" | "news" }
  → Response: CollectResult

GET /api/v1/collect/settings
  → 查看所有采集器配置及状态
  → Response: { items: CollectorSetting[] }

PUT /api/v1/collect/settings/{collector_name}
  → 修改采集器配置 (调整频率、启停)
  → Body: { "interval_seconds": 60, "is_active": true }
```

### 6.4 接口约定

- 统一前缀: `/api/v1`
- 分页: `page` (默认1), `page_size` (默认20, 最大100)
- 日期格式: `YYYY-MM-DD`
- 响应格式统一:

```json
// 成功
{
  "success": true,
  "data": { ... },
  "message": ""
}

// 失败
{
  "success": false,
  "error": {
    "code": "FUND_NOT_FOUND",
    "message": "基金代码 000000 不存在"
  }
}
```

错误码范围:

| 错误码 | HTTP 状态码 | 场景 |
|--------|------------|------|
| `INTERNAL_ERROR` | 500 | 服务器内部错误 |
| `INVALID_ARGUMENT` | 400 | 参数校验失败 |
| `FUND_NOT_FOUND` | 404 | 基金不存在 |
| `SECTOR_NOT_FOUND` | 404 | 板块不存在 |
| `COLLECTOR_NOT_FOUND` | 404 | 采集器不存在 |
| `COLLECTOR_BUSY` | 409 | 采集器正在运行中 |

---

## 七、定时任务（Phase 1）

```python
# tasks/collect_tasks.py

# ── 交易日盘中判断 ──
def is_in_trading_session() -> bool:
    """判断当前是否在 A 股交易时段 (9:30-11:30, 13:00-15:00)"""
    ...

# ── 高频: ETF 实时行情 (30s) ──
@scheduler.scheduled_job("interval", seconds=30)
async def collect_etf_job():
    if not is_in_trading_session():
        return
    service = CollectorService()
    await service.collect_etf_spot()

# ── 中频: 板块实时快照 (1min) ──
@scheduler.scheduled_job("interval", seconds=60)
async def collect_sector_realtime_job():
    if not is_in_trading_session():
        return
    service = CollectorService()
    await service.collect_sector_realtime()

# ── 中频: 基金实时估值 (5min) ──
@scheduler.scheduled_job("interval", seconds=300)
async def collect_estimate_job():
    if not is_in_trading_session():
        return
    service = CollectorService()
    await service.collect_estimates()

# ── 低频: 新闻采集 (10min) ──
@scheduler.scheduled_job("interval", seconds=600)
async def collect_news_job():
    """Phase 2 实现"""
    pass

# ── 盘后 (15:30) ──
@scheduler.scheduled_job("cron", hour=15, minute=30)
async def collect_close_data_job():
    service = CollectorService()
    await service.collect_sector_close()    # 收盘快照 + 资金流向
    await service.collect_fund_nav_today()  # 当日净值
```

> 任务体内从 `collector_settings` 表读取实际配置，决定是否执行。定时器作为"最大频率"保底。

---

## 八、Phase 1 功能清单

### 核心功能

- [x] **FastAPI 应用骨架** — main.py、生命周期管理、CORS 中间件
- [x] **配置系统** — `core/config.py`，pydantic-settings，`.env` 覆盖
- [x] **PostgreSQL 数据库初始化** — 异步引擎(asyncpg)、Session 工厂、DDL 自动创建
- [x] **所有 12 张表的 ORM 模型** — UUID 主键、统一 TimestampMixin
- [x] **Pydantic Schema 层** — 请求/响应模型
- [x] **全局响应封装** — `{success, data, message}` / `{success, error}` 统一格式
- [x] **错误码定义** — 6 种标准错误码 + HTTP 状态码映射
- [x] **Repository 层** — FundRepo, SectorRepo, SystemRepo (纯 CRUD)
- [x] **AkShare 基金数据源** — 基金列表、净值、实时估值、ETF 行情 (仅股票/混合/指数/ETF)
- [x] **AkShare 板块数据源** — 板块列表(申万一级行业+概念)、历史日线、实时行情、成分股
- [x] **CollectorService 编排** — 统筹数据源 + 清洗 + 持久化
- [x] **全部 REST API 接口** — 基金、板块、采集控制
- [x] **采集控制接口** — 手动触发、查看/修改频率配置
- [x] **定时任务系统** — APScheduler + 交易日判断 + 配置表驱动
- [x] **单元测试** — conftest + repositories + services + integrations
- [x] **Dockerfile + docker-compose.yml** — postgres + backend 一键启动
- [x] **.env.example + .python-version** — 环境模板 + Python 版本锁定
- [x] **国内镜像源配置** — pyproject.toml 中 pip 清华源优先
- [x] **项目文档** — ARCH.md + CLAUDE.md + README 更新

### Phase 1 不包含

| 功能 | 计划阶段 | 原因 |
|------|---------|------|
| 新闻采集实现 | Phase 2 | 需处理反爬、去重 |
| AI 分析引擎 | Phase 3 | 需数据积累 |
| AI Provider 管理 | Phase 3 | |
| 基金操作建议 | Phase 3 | |
| MCP Server | Phase 4 | 后端 API 先行 |
| CLI 工具 | Phase 4 | |
| 前端页面 | Phase 5 | 先保证数据层稳定 |

---

## 九、决策记录

| 决策项 | 结论 |
|--------|------|
| 数据库 | PostgreSQL + asyncpg |
| 基金范围 | 股票型/混合型/指数/ETF，预留 type 字段可扩展 |
| 板块体系 | 申万一级行业 + 概念板块，category 字段区分 |
| 采集频率 | `collector_settings` 表运行时配置；默认 ETF 30s / 板块 1min / 基金估值 5min / 新闻 10min；支持手动触发 |
| 启动方式 | Docker Compose (postgres + backend) + 本地 uvicorn 均可 |
| AI 分析结果 | JSONB 结构化存储，不做自然语言，为排序/回测/准确性分析铺垫 |
| 主键方案 | UUID |
| 分层架构 | api → services → repositories + integrations，职责严格分离 |
| 响应格式 | `{success, data, message}` / `{success, error}` |
| Python 源 | 清华 tuna 优先，备选阿里云 |
| Python 版本 | 3.12.13，`.python-version` + Docker `python:3.12.13-slim` |
