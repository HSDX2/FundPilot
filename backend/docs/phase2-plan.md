# Phase 2 Implementation & Testing Plan

## Context

Phase 1 完成了项目骨架、12 张数据库表、9 个采集器、全部 CRUD API、定时任务系统、强制停止/进度追踪/事务拆分，138 个测试通过。

**Phase 2 目标**：填补 Phase 1 遗留的空白 — 新闻采集实现、板块资金流向采集、业务服务层补全、API 路由重构（遵循分层约定）。不涉及 AI 分析（Phase 3）。

### Phase 1 已知缺口

| 缺口 | 详情 |
|------|------|
| 新闻采集 | `NewsDataSource.fetch()` 直接返回 `[]`，`collect_news()` 直接返回 0 |
| 资金流向 | `sector_money_flows` 表已建、`SectorMoneyFlowRepo` 已实现，从未被采集 |
| 业务服务层 | `fund_service.py` / `sector_service.py` 不存在，API 路由直接调 repo（违反 CLAUDE.md 分层约定） |
| 成分股采集 | `SectorDataSource.fetch_board_cons()` 已实现但从未被调用 |

---

## 一、AkShare 接口确认

实现前需验证以下 AkShare 接口实际返回的列名和数据结构：

```python
# 新闻
import akshare as ak
ak.stock_news_em()          # 东方财富新闻列表 — 确认列名
ak.stock_news_content_em()  # 新闻正文 — 确认参数名

# 板块资金流向
ak.stock_sector_fund_flow_rank()        # 板块资金流向排名 — 确认列名
ak.stock_sector_fund_flow_individual()  # 个股资金流向 — 确认列名

# 板块成分股 (已有)
ak.stock_board_industry_cons_em()       # 已验证可用
```

**验证方式**：`python -c "import akshare as ak; df = ak.xxx(); print(df.columns.tolist()); print(df.head(2))"`

---

## 二、新闻采集实现

### 2.1 数据源 (`integrations/akshare/news_datasource.py`)

重写 `NewsDataSource`，从占位替换为实际实现：

```python
class NewsDataSource:
    async def fetch_news_list(page: int = 1) -> list[dict[str, Any]]
        # ak.stock_news_em() → list[dict], 列映射到 title/source/url/published_at

    async def fetch_news_content(url: str) -> str | None
        # ak.stock_news_content_em(url=url) → 正文文本
```

列映射（按 AkShare 实际返回调整）：

| AkShare 列名 | 内部字段 | 说明 |
|-------------|---------|------|
| 标题/title | `title` | 新闻标题 |
| 来源/source | `source` | 来源网站 |
| 链接/url | `url` | 唯一标识，去重键 |
| 发布时间 | `published_at` | ISO 格式 |
| 正文/content | `content` | 通过 content 接口二次抓取 |

### 2.2 Repository 扩展 (`repositories/news_repo.py`)

```python
class NewsArticleRepo:
    # 已有: find_by_url, search
    async def batch_upsert(records) -> tuple[int, int]
        # 按 url 去重，返回 (added, updated)
```

### 2.3 板块关键词匹配（关联 `news_sector_links`）

```python
# SectorRepo 新增
async def get_all_names() -> list[tuple[uuid.UUID, str]]
    # 返回所有板块 (id, name) 用于关键词匹配

# 简单匹配策略：标题/正文中出现板块名称 → 创建关联
# 存储到 news_sector_links 表
```

### 2.4 CollectorService 新增方法

```python
async def collect_news(self, limit: int = 50) -> CollectResult:
    # 1. 拉取最新 N 条新闻
    # 2. 按 URL 去重写入 news_articles
    # 3. 对新增的新闻，匹配板块名称 → 写入 news_sector_links
    # 4. 每处理一批 commit 一次
```

### 2.5 测试

```
tests/test_integrations/
├── test_news_datasource.py    # mock ak.stock_news_em 返回值

tests/test_services/
└── test_collector_service.py  # 新增 TestCollectNews 实际用例 (替换 test_placeholder)
```

---

## 三、板块资金流向采集

### 3.1 数据源扩展 (`integrations/akshare/sector_datasource.py`)

```python
class SectorDataSource:
    # 新增方法
    async def fetch_sector_fund_flow() -> list[dict[str, Any]]
        # ak.stock_sector_fund_flow_rank() → 板块资金流向排名
        # 列映射: 板块名称→sector_name, 主力净流入→main_force_net_inflow, etc.

    async def fetch_individual_fund_flow() -> list[dict[str, Any]]
        # ak.stock_sector_fund_flow_individual() → 个股资金流向
```

### 3.2 Repository 扩展 (`repositories/sector_repo.py`)

```python
class SectorMoneyFlowRepo:
    # 已有: get_by_sector_and_date
    async def batch_upsert(records) -> tuple[int, int]
        # 按 (sector_id, date) 去重
```

### 3.3 CollectorService 新增方法

```python
async def collect_sector_money_flow(self) -> CollectResult:
    # 1. 拉取板块资金流向数据
    # 2. 按名称匹配 sector_id
    # 3. batch_upsert 写入 sector_money_flows
```

### 3.4 新采集器注册

在 `constants.py` 中新增 `CollectorName.SECTOR_MONEY_FLOW = "sector_money_flow"`，注册到 `collector_map`、`TASK_MAP`、`DEFAULT_COLLECTOR_INTERVALS`，每日盘后执行。

### 3.5 测试

```
tests/test_integrations/
└── test_sector_datasource.py  # 补充 test_fetch_sector_fund_flow

tests/test_services/
└── test_collector_service.py  # 新增 TestCollectSectorMoneyFlow
```

---

## 四、业务服务层补全

### 4.1 背景

当前 `app/services/` 下只有 `collector_service.py`。API 路由直接调 repo，违反 CLAUDE.md 中 "Business logic must NOT exist inside API routes" 和 "API routes — thin, no business logic" 的约定。

### 4.2 FundService (`services/fund_service.py`)

```python
class FundService:
    def __init__(self, fund_repo, fund_nav_repo, fund_estimate_repo)

    async def search_funds(name, type_, company, page, page_size)
        # 当前在 funds.py:63-75 中直接调 repo.search + 类型编码转换
        # 迁移：类型编码转换逻辑 + repo.search

    async def get_fund_detail(code)
        # 基金详情 + 最新净值 + 最新估值聚合

    async def get_fund_nav_history(code, start_date, end_date)
        # 当前在 funds.py:101-129

    async def get_fund_estimate(code)
        # 当前在 funds.py:137-151

    async def get_batch_estimates(codes)
        # 当前在 funds.py:159-178
```

### 4.3 SectorService (`services/sector_service.py`)

```python
class SectorService:
    def __init__(self, sector_repo, sector_snapshot_repo, sector_money_flow_repo)

    async def search_sectors(name, category, page, page_size)
        # 当前在 sectors.py:36-63

    async def get_sector_detail(sector_id)
        # 板块详情 + 最新快照 + 资金流向聚合

    async def get_sector_snapshots(sector_id, start_time, end_time)
        # 当前在 sectors.py:90-130

    async def get_sector_realtime(sector_id)
        # 当前在 sectors.py:133-158

    async def get_rank(category, limit)
        # 当前在 sectors.py:162-207 (含复杂 SQL 查询)
```

### 4.4 API 路由重构

API 路由瘦身：从直接调 repo → 调 service。

```python
# Before (funds.py):
@router.get("")
async def list_funds(repo: FundRepo = Depends(get_fund_repo)):
    items, total = await repo.search(...)
    ...

# After:
@router.get("")
async def list_funds(service: FundService = Depends(get_fund_service)):
    items, total = await service.search_funds(...)
    ...
```

### 4.5 DI 更新 (`api/deps.py`)

```python
async def get_fund_service(session = Depends(get_db)) -> FundService:
    yield FundService(
        fund_repo=FundRepo(session),
        fund_nav_repo=FundNavRepo(session),
        fund_estimate_repo=FundEstimateRepo(session),
    )

async def get_sector_service(session = Depends(get_db)) -> SectorService:
    yield SectorService(
        sector_repo=SectorRepo(session),
        sector_snapshot_repo=SectorSnapshotRepo(session),
        sector_money_flow_repo=SectorMoneyFlowRepo(session),
    )
```

### 4.6 测试

```
tests/test_services/
├── test_fund_service.py    # mock repo, 测业务编排
├── test_sector_service.py  # mock repo, 测业务编排
└── test_collector_service.py  # 更新

tests/test_api/
├── test_funds.py     # 更新 mock 目标: repo → service
├── test_sectors.py   # 更新 mock 目标: repo → service
└── test_collect.py   # 更新
```

---

## 五、新增/修改 API 端点

### 5.1 新闻接口

```
GET /api/v1/news
  → 新闻列表，?keyword=&source=&start=&end=&page=&page_size=
  → Response: { items: NewsArticle[], total, page, page_size }

GET /api/v1/news/{news_id}
  → 新闻详情 + 关联板块

GET /api/v1/news/sectors/{sector_id}
  → 某板块相关的新闻列表
```

### 5.2 板块资金流向接口

```
GET /api/v1/sectors/{id}/money-flow
  → 板块资金流向历史，?start_date=&end_date=
  → Response: { items: SectorMoneyFlow[] }
```

### 5.3 采集控制接口 (新增)

```
GET /api/v1/collect/status           # 已实现
GET /api/v1/collect/status/{name}    # 已实现
POST /api/v1/collect/stop/{name}     # 已实现
GET /api/v1/collect/logs             # 新增：采集日志
  → ?collector=&page=&page_size=
  → Response: { items: CollectLog[], total }
```

### 5.4 新增错误码

| 错误码 | HTTP | 场景 |
|--------|------|------|
| `NEWS_NOT_FOUND` | 404 | 新闻不存在 |

### 5.5 新增 Schema

```
app/schemas/news.py — 已有 NewsArticleResponse, 补充:
  - NewsArticleDetailResponse (含关联板块列表)
  - NewsArticleListData

app/schemas/sector.py — 已有 SectorResponse/SectorSnapshotResponse, 补充:
  - SectorMoneyFlowResponse
  - SectorMoneyFlowListData
  - SectorDetailResponse (聚合：板块信息 + 最新快照 + 最新资金流向)

app/schemas/system.py — 已有 CollectorSettingResponse/CollectorTriggerRequest, 补充:
  - CollectLogResponse
  - CollectLogListData
```

---

## 六、采集日志表 (`collect_logs`)

### 6.1 模型 (`models/system.py`)

```python
class CollectLog(TimestampMixin, Base):
    __tablename__ = "collect_logs"

    collector_name: str (32)    # 采集器名称
    status: str (16)            # success / failed / stopped
    records_added: int
    records_updated: int
    error_message: str | None   # Text
    duration_ms: int | None     # 执行耗时
    started_at: datetime        # 开始时间
    finished_at: datetime | None # 结束时间
```

### 6.2 Repository

```python
class CollectLogRepo(BaseRepository[CollectLog]):
    async def list_by_collector(name, page, page_size) -> tuple[list[CollectLog], int]
    async def get_recent_logs(name, limit=10) -> list[CollectLog]
```

### 6.3 集成到 CollectorService

每个采集方法的 `finally` 块中写入 `collect_logs` 记录。

---

## 七、采集可靠性增强

### 7.1 重试机制 (`integrations/base.py` 或 datasource 基类)

```python
async def _with_retry(coro, max_retries=3, base_delay=1.0):
    """指数退避重试：1s → 2s → 4s"""
    for attempt in range(max_retries):
        try:
            return await coro()
        except Exception as exc:
            if attempt == max_retries - 1:
                raise DataSourceException(str(exc))
            await asyncio.sleep(base_delay * (2 ** attempt))
```

在 `FundDataSource`、`SectorDataSource`、`NewsDataSource` 中应用。

### 7.2 速率限制

在 `BaseDataSource` 中添加 `_rate_limit(min_interval=0.5)` — 两次请求间最小间隔，通过 `asyncio.sleep` 实现。

---

## 八、实作顺序

| 步骤 | 内容 | 测试 | 验收条件 |
|------|------|------|---------|
| 1 | **AkShare 接口验证** — 确认新闻、资金流向接口的实际列名 | — | 脚本输出列名和数据样例 |
| 2 | **新闻数据源** — 重写 `news_datasource.py` | `test_news_datasource.py` | mock 测试通过 |
| 3 | **新闻采集器** — `collect_news()` 实际逻辑 + 板块匹配 | 更新 `test_collector_service.py` | 测试通过 |
| 4 | **资金流向数据源** — 补充 `sector_datasource.py` | 更新 `test_sector_datasource.py` | mock 测试通过 |
| 5 | **资金流向采集器** — `collect_sector_money_flow()` | 更新 `test_collector_service.py` | 测试通过 |
| 6 | **CollectLog 模型 + Repo** — 建表 + CRUD | `test_collect_logs.py` | 模型测试通过 |
| 7 | **采集日志集成** — 每个 Collector 写入日志 | — | 手动触发验证 |
| 8 | **重试机制** — datasource 基类 + 应用到 3 个 datasource | — | mock 异常测试 |
| 9 | **FundService** — 创建 + API 路由重构 | `test_fund_service.py` + 更新 `test_funds.py` | 全部测试通过 |
| 10 | **SectorService** — 创建 + API 路由重构 | `test_sector_service.py` + 更新 `test_sectors.py` | 全部测试通过 |
| 11 | **新闻 API** — `/news` 端点 | `test_news.py` | 端点测试矩阵通过 |
| 12 | **资金流向 API** — `/sectors/{id}/money-flow` | 更新 `test_sectors.py` | 端点测试通过 |
| 13 | **采集日志 API** — `/collect/logs` | 更新 `test_collect.py` | 端点测试通过 |
| 14 | **新采集器注册** — constants + scheduler + tasks | — | 调度器正常启动 |

---

## 九、关键文件修改清单

### 新建文件

```
app/services/fund_service.py
app/services/sector_service.py
tests/test_services/test_fund_service.py
tests/test_services/test_sector_service.py
tests/test_integrations/test_news_datasource.py
tests/test_api/test_news.py
```

### 重写文件

```
app/integrations/akshare/news_datasource.py    # 占位 → 实际实现
```

### 修改文件

```
app/integrations/akshare/sector_datasource.py  # + fetch_sector_fund_flow
app/integrations/akshare/__init__.py           # + NewsDataSource 导出
app/integrations/base.py                       # + 重试/限速
app/repositories/sector_repo.py                # + SectorMoneyFlowRepo.batch_upsert
app/repositories/news_repo.py                  # + NewsArticleRepo.batch_upsert
app/repositories/system_repo.py                # + CollectLogRepo
app/models/system.py                           # + CollectLog 模型
app/schemas/news.py                            # + NewsArticleDetailResponse
app/schemas/sector.py                          # + SectorMoneyFlowResponse, SectorDetailResponse
app/schemas/system.py                          # + CollectLogResponse
app/core/constants.py                          # + SECTOR_MONEY_FLOW, NEWS 等新枚举值
app/core/errors.py                             # + NewsNotFoundError
app/api/v1/funds.py                            # 重构：调 service 而非 repo
app/api/v1/sectors.py                          # 重构：调 service 而非 repo
app/api/v1/collect.py                          # + /collect/logs 端点
app/api/v1/news.py                             # 新增路由（在 router.py 注册）
app/api/deps.py                                # + get_fund_service, get_sector_service
app/api/v1/router.py                           # + news_router
app/services/collector_service.py              # + collect_news 实际逻辑, + collect_sector_money_flow, + 日志写入
app/tasks/collect_tasks.py                     # + collect_news_task, + collect_sector_money_flow_task
app/tasks/scheduler.py                         # + 新任务注册
tests/test_services/test_collector_service.py  # 更新 TestCollectNews
tests/test_api/test_collect.py                 # + test_get_collect_logs
tests/test_api/test_funds.py                   # mock 目标更新
tests/test_api/test_sectors.py                 # mock 目标更新 + money-flow 测试
tests/test_schemas/test_system.py              # + CollectLogResponse 测试
tests/conftest.py                              # factories 可能需要更新
```

---

## 十、验证方式

```bash
# 1. AkShare 接口验证 (步骤 1)
python -c "
import akshare as ak
df = ak.stock_news_em()
print('stock_news_em columns:', df.columns.tolist())
print(df.head(2))
"

# 2. 静态检查
cd backend && ruff check . && mypy .

# 3. 全部测试
cd backend && pytest tests/ -v

# 4. 覆盖率
cd backend && pytest --cov=app --cov-report=term-missing

# 5. 集成验证
# 启动服务后:
curl -X POST http://localhost:8000/api/v1/collect/trigger -d '{"collector":"news"}'
curl http://localhost:8000/api/v1/news?page=1
curl http://localhost:8000/api/v1/sectors/{id}/money-flow
curl http://localhost:8000/api/v1/collect/logs
```

### 覆盖率目标 (同 Phase 1)

| 层级 | 目标 |
|------|------|
| Core | 90%+ |
| Models | 100% |
| Repositories | 90%+ |
| Services | 90%+ |
| API | 90%+ |
| Integrations | 85%+ |
| Tasks | 80%+ |
