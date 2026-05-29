# FundPilot CLI 技能

使用 `fundpilot` CLI 查询基金数据、板块排名、AI 分析报告以及管理数据采集。

## 前置条件

- FundPilot 后端必须处于运行状态（默认地址：`http://localhost:8000`）
- 如果后端使用其他地址，请设置 `FUNDPILOT_URL` 环境变量

## 快速参考

所有命令默认输出 JSON。对于支持的命令，添加 `--table` 参数可以输出表格格式。

### 基金查询

```
# 按名称搜索基金
fundpilot fund search --name 新能源 --page 1 --page-size 10

# 按类型搜索（stock/mixed/index/etf/bond/monetary/qdii）
fundpilot fund search --type stock --page 1 --page-size 10 --table

# 按代码获取基金详情
fundpilot fund detail 000001

# 获取基金净值历史
fundpilot fund nav 000001 --start 2026-01-01 --end 2026-05-24 --table

# 获取最新盘中估值
fundpilot fund estimate 000001

# 批量估值
fundpilot fund batch-estimate 000001,000011,110011
```

### 板块查询

```
# 按名称搜索板块
fundpilot sector search --name 新能源 --category concept --table

# 获取板块排名（默认表格输出，前 20 条）
fundpilot sector rank --category industry --limit 10
fundpilot sector rank --category concept --limit 20 --table

# 获取板块资金流向
fundpilot sector money-flow <sector_uuid> --start 2026-05-01 --end 2026-05-24 --table
```

### AI 分析

```
# 查看分析报告列表
fundpilot analysis report-list --type daily --page 1

# 获取最新报告
fundpilot analysis report-latest --type daily

# 查看基金建议列表
fundpilot analysis advice-list --action buy --page 1

# 获取最新市场情绪
fundpilot analysis sentiment-latest
```

### 采集管理

```
# 触发采集器
fundpilot collect trigger sector_daily
fundpilot collect trigger news --sources eastmoney,jin10

# 查看状态（全部或指定）
fundpilot collect status
fundpilot collect status fund_list

# 停止正在运行的采集器
fundpilot collect stop fund_nav

# 查看采集日志
fundpilot collect logs --collector news --page 1 --table

# 查看/更新采集器设置
fundpilot collect settings
fundpilot collect settings fund_list --interval 86400 --active
```

### 可用采集器（14 个）

| 名称 | 描述 | 默认间隔 |
|------|------|---------|
| `fund_list` | 基金列表 | 24h |
| `etf` | ETF 实时行情 | 30s |
| `sector_list` | 板块列表 | 24h |
| `fund_nav_history` | 基金净值历史 | 24h |
| `fund_nav_daily` | 基金净值每日 | 24h |
| `news` | 新闻采集 | 10min |
| `market_sentiment` | 市场情绪 | 24h |
| `sector_batch_history` | 板块历史数据 | 24h |
| `sector_batch_daily` | 板块每日数据 | 24h |
| `fund_estimate` | 基金估值 | 5min |
| `sector_realtime` | 板块实时行情 | 5min |
| `news_sentiment` | 新闻情绪分析 | 1h |
| `recommend_top_picks` | 综合推荐 | 4h |
| `recommend_dip_buy` | 加仓推荐 | 12h |

### 基金类型

| 代码 | 含义 |
|------|------|
| `stock` | 股票型 |
| `mixed` | 混合型 |
| `index` | 指数型 |
| `etf` | ETF |
| `bond` | 债券型 |
| `monetary` | 货币型 |
| `qdii` | QDII |

### 新闻来源（用于 `collect trigger news --sources`）

| 键 | 来源 |
|-----|------|
| `eastmoney` | 东方财富 |
| `jin10` | 金十数据 |
| `cls` | 财联社 |
| `wallstreetcn` | 华尔街见闻 |

## AI 使用模式

### 模式 1：用户询问市场情况

同时运行情绪查询和排名查询，提供完整视图：

```
fundpilot analysis sentiment-latest
fundpilot sector rank --category concept --limit 10
```

### 模式 2：用户询问某只基金

获取基金详情 + 估值 + 最新建议：

```
fundpilot fund detail <code>
fundpilot fund estimate <code>
```

### 模式 3：用户要求采集数据

触发相应的采集器：

```
fundpilot collect trigger <collector_name>
fundpilot collect status <collector_name>
```

### 模式 4：用户询问板块

搜索获取板块 UUID，然后获取详细信息：

```
fundpilot sector search --name <keyword>
fundpilot sector rank --category concept --limit 10
```

## 重要说明

- CLI 依赖 FundPilot REST API——后端必须保持运行
- `--table` 参数适用于人类可读的输出；机器解析时请省略
- 板块操作（资金流向、详情）需要 UUID 而非名称——先使用 `sector search` 查找 ID
- 采集触发后立即返回——使用 `collect status` 检查进度
- 所有命令返回 JSON，结构为 `{"success": true, "data": ...}`
