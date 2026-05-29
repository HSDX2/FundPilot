# FundPilot

中国基金投研分析平台 — 数据采集、AI 分析、可视化看板。

## 项目简介

FundPilot 是一个面向中国 A 股市场的基金研究与数据分析平台，提供以下核心功能：

- **数据采集** — 从东方财富、金十数据、财联社、华尔街见闻等中国金融数据源定时采集基金净值、板块行情、新闻、资金流向等数据
- **AI 分析引擎** — 接入 DeepSeek / GLM / Qwen / OpenAI 等大模型，自动生成板块分析报告、基金操作建议、新闻情绪评分
- **可视化看板** — 前端基于 React + Ant Design，提供板块排行、基金查询、分析报告、情绪指标等交互页面
- **任务调度** — 基于 APScheduler 的定时采集系统，支持交易日感知、交易时段限定、多级并发控制
- **CLI 工具** — 可选命令行工具，终端直接查询和管理

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | Python 3.12 + FastAPI + Uvicorn |
| 数据库 | PostgreSQL 16 + SQLAlchemy 2.0 async (asyncpg) |
| 前端 | React 19 + TypeScript 6 + Vite 8 + Ant Design 6 |
| 状态管理 | TanStack React Query 5 |
| 任务调度 | APScheduler（交易日感知，活跃时段限定） |
| 数据源 | AkShare / 东方财富 / 金十数据 / 财联社 / 华尔街见闻 |
| AI 适配 | OpenAI 兼容接口（DeepSeek / GLM / Qwen / OpenAI / Kimi / MiniMax） |
| CLI | Python Typer（可选组件） |

## 项目架构

```
FundPilot/
├── backend/                          # FastAPI 后端服务
│   ├── app/
│   │   ├── api/v1/                   # API 路由层（无业务逻辑）
│   │   │   ├── analysis.py           #   分析报告 / 操作建议 / 情绪分析
│   │   │   ├── ai_providers.py       #   AI Provider CRUD + 连通性测试
│   │   │   ├── chat.py               #   AI 对话接口
│   │   │   ├── collect.py            #   采集器触发 / 配置 / 日志
│   │   │   ├── funds.py              #   基金查询 / 详情 / 净值
│   │   │   ├── news.py               #   新闻列表 / 详情
│   │   │   ├── sectors.py            #   板块排行 / 详情 / 快照 / 资金流向
│   │   │   └── watchlist.py          #   自选关注（基金 / 板块）
│   │   ├── core/                     # 配置、常量、数据库引擎、错误处理
│   │   │   ├── config.py             #   环境变量 → Pydantic Settings
│   │   │   ├── constants.py          #   枚举、采集器元信息
│   │   │   ├── database.py           #   异步引擎与会话工厂
│   │   │   ├── errors.py             #   统一错误码与异常类
│   │   │   ├── response.py           #   统一响应格式
│   │   │   └── task_lock.py          #   任务去重锁
│   │   ├── models/                   # SQLAlchemy ORM 模型
│   │   │   ├── fund.py               #   基金 / 净值 / 估值
│   │   │   ├── sector.py             #   板块 / 快照 / 资金流向
│   │   │   ├── news.py               #   新闻 / 板块关联
│   │   │   ├── analysis.py           #   分析报告 / 操作建议
│   │   │   ├── sentiment.py          #   市场情绪指标
│   │   │   ├── system.py             #   Provider / 采集器配置 / 日志
│   │   │   └── watchlist.py          #   自选关注
│   │   ├── schemas/                  # Pydantic 请求/响应
│   │   ├── repositories/            # 数据库访问层（仅 CRUD）
│   │   ├── services/                 # 业务逻辑层
│   │   │   ├── fund_service.py       #   基金搜索 / 净值采集
│   │   │   ├── sector_service.py     #   板块排行 / 实时行情
│   │   │   ├── analysis_service.py   #   AI 分析引擎
│   │   │   └── collector_service.py  #   采集任务调度与服务
│   │   ├── integrations/             # 第三方数据源适配器
│   │   │   └── akshare/              #   AkShare 封装 + HTTP 源
│   │   ├── ai/                       # AI 模型适配器
│   │   │   ├── base.py               #   抽象 Provider 接口
│   │   │   ├── openai_compat.py      #   OpenAI 兼容适配器
│   │   │   └── prompts.py            #   系统提示词模板
│   │   └── tasks/                    # APScheduler 定时任务
│   │       ├── scheduler.py          #   调度器注册
│   │       ├── collect_tasks.py      #   各采集任务实现
│   │       └── analysis_tasks.py     #   AI 分析任务
│   ├── tests/                        # pytest 测试
│   ├── docs/                         # 架构 / 进度文档
│   └── .env.example                  # 环境变量模版
├── frontend/                         # React 前端
│   └── src/
│       ├── api/                      # API 客户端（ky）
│       ├── pages/                    # 页面组件
│       │   ├── dashboard/            #   数据看板
│       │   ├── sectors/              #   板块排行 / 详情
│       │   ├── funds/                #   基金查询 / 详情
│       │   ├── analysis/             #   分析报告 / 操作建议 / 情绪
│       │   ├── collect/              #   采集设置 / 日志
│       │   ├── settings/             #   AI 配置 / 提示词编辑
│       │   └── watchlist/            #   自选管理
│       └── components/               # 通用组件
├── scripts/                          # 启动/停止/状态 运维脚本
├── docker-compose.yml                # Docker 编排
└── .env.example                      # 项目级环境变量
```

### 分层约定

```
API Routes (thin) ──→ Services (business) ──→ Repositories (CRUD) ──→ Database

第三方数据源 → Integrations (AkShare/HTTP)    AI 模型 → AI (Provider 适配器)
```

- API 路由层不含业务逻辑
- Service 层不含数据库访问细节
- Repository 层仅做 CRUD，不含业务判断
- 所有 AI 调用经过 `AIProvider` 抽象接口

## 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | **3.12.13** | 必须精确版本，详见 `.python-version` |
| PostgreSQL | **16** | 主数据库 |
| Node.js | **18+** | 前端构建（Vite 8 需要） |
| pnpm 或 npm | — | 前端包管理（用项目锁文件） |
| Docker (可选) | 24+ | 替代本地 PostgreSQL，一键启动 |

## 从零开始运行

### 1. 克隆项目

```bash
git clone <repo-url>
cd FundPilot
```

### 2. 安装 Python 3.12.13

**方式 A: pyenv（推荐）**

```bash
# 安装 pyenv
curl https://pyenv.run | bash

# 安装 Python 3.12.13
pyenv install 3.12.13
pyenv local 3.12.13

# 验证
python --version   # 必须输出 Python 3.12.13
```

**方式 B: 直接从 Python 官网下载**

```bash
# macOS
brew install python@3.12
# Linux（apt）
sudo apt install python3.12 python3.12-venv
```

### 3. 启动 PostgreSQL 16

**方式 A: Docker（推荐，无需本地安装）**

```bash
# 启动 PostgreSQL
docker compose up -d postgres

# 验证连接
psql -U fundpilot -h localhost -c "SELECT 1"
# 密码: change-me（如未修改）
```

**方式 B: 本地安装**

```bash
# macOS
brew install postgresql@16
brew services start postgresql@16

# 创建用户和数据库
createuser -s fundpilot
createdb fundpilot -O fundpilot
```

验证：
```bash
psql -U fundpilot -d fundpilot -c "SELECT version();"
```

### 4. 创建环境变量配置文件

项目使用 `.env` 文件管理配置。需要复制模版并根据环境填写。

```bash
# 复制模版
cp .env.example .env                  # Docker Compose 用
cp backend/.env.example backend/.env  # 后端服务用
```

#### 后端配置（backend/.env）

| 变量 | 默认值 | 必须修改 | 说明 |
|------|--------|---------|------|
| `DB_HOST` | `localhost` | 否 | 数据库地址，Docker 用 `postgres` |
| `DB_PORT` | `5432` | 否 | 数据库端口 |
| `DB_USER` | `fundpilot` | 否 | 数据库用户 |
| `DB_PASSWORD` | `change-me` | **是** | 数据库密码 |
| `DB_NAME` | `fundpilot` | 否 | 数据库名 |
| `ENCRYPTION_KEY` | 空 | 建议 | AI API Key 加密密钥，**不设置则 API Key 明文存储**。生成命令: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `API_KEYS` | 空 | 否 | 前端接口鉴权，逗号分隔，留空=不开启鉴权 |
| `CORS_ORIGINS` | `*` | 否 | 允许跨域来源，生产环境改为具体域名 |
| `LOG_LEVEL` | `INFO` | 否 | 日志级别 |
| `NO_PROXY` | 国内源域名列表 | 否 | 绕过系统代理的域名，国内金融数据源需要直连 |
| `PIP_INDEX_URL` | `https://pypi.tuna.tsinghua.edu.cn/simple` | 建议 | PyPI 镜像，**境外用户请置空** |

#### 项目配置（.env）

用于 Docker Compose 和服务脚本：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DB_PASSWORD` | `change-me` | 与 `backend/.env` 保持一致 |
| `ENCRYPTION_KEY` | 空 | 与 `backend/.env` 保持一致 |

#### 配置 AI Provider（运行后通过页面操作）

AI 模型配置（API Key、模型名、接口地址）**不需要写在 `.env` 中**，启动后在页面 `设置 → AI Provider 配置` 中通过表单添加和激活。API Key 会使用 `ENCRYPTION_KEY` 加密后存入数据库。

支持的 AI 提供商：DeepSeek / GLM / Qwen / OpenAI / Kimi / MiniMax。

#### 快速启动的最小配置

```bash
# backend/.env
DB_PASSWORD=your-password           # 改密码
ENCRYPTION_KEY=your-fernet-key      # 生成一个

# .env
DB_PASSWORD=your-password           # 保持一致
ENCRYPTION_KEY=your-fernet-key      # 保持一致
```

### 5. 初始化 Python 虚拟环境并安装后端依赖

```bash
# 创建虚拟环境（在项目根目录）
python3.12 -m venv .venv

# 激活
source .venv/bin/activate      # Linux/macOS
# 或: .venv\Scripts\activate   # Windows

# 验证 Python 版本
python --version               # 必须 3.12.13

# 安装后端依赖
cd backend
pip install -e .
cd ..
```

> **国内用户**: pip 默认使用清华 PyPI 镜像。
> **境外用户**: 在 `.env` 中设置 `PIP_INDEX_URL=""` 使用官方源。

### 6. 创建数据库表并导入初始数据

数据库表结构和初始数据通过独立脚本管理，不再在应用启动时自动建表。

```bash
# 建表（18 张表：基金、板块、新闻、AI 分析、市场情绪、采集器等）
./scripts/db/create.sh

# 导入采集器默认配置（12 个采集器，ON CONFLICT DO NOTHING）
./scripts/db/seed.sh
```

如需要重建表（清空数据后重新创建）：

```bash
./scripts/db/create.sh --drop   # 删除所有表后重新创建
./scripts/db/seed.sh            # 重新导入初始数据
```

建表和导数脚本说明：

| 文件 | 内容 |
|------|------|
| `scripts/db/schema.sql` | 18 张表的 `CREATE TABLE`（含主键、唯一约束、外键、索引、`gen_random_uuid()` 默认值）|
| `scripts/db/seed.sql` | `collector_settings` — 12 个采集器的默认配置 |
| `scripts/db/create.sh` | 调用 `schema.sql` 建表，支持 `--drop` 参数先删后建 |
| `scripts/db/seed.sh` | 调用 `seed.sql` 导入初始配置 |

### 7. 安装前端依赖并启动（可选，如需使用 Web 界面）

```bash
cd frontend

# 使用 npm
npm install
npm run dev

# 或使用 pnpm
pnpm install
pnpm dev
```

前端默认运行在 `http://localhost:3000`。

### 8. 验证所有服务

```bash
# 后端健康检查
curl http://localhost:8000/health
# → {"status": "ok"}

# API 文档（浏览器打开）
open http://localhost:8000/docs

# 测试采集器
curl -X POST http://localhost:8000/api/v1/collect/trigger \
  -H "Content-Type: application/json" \
  -d '{"collector": "sector_list"}'

# 查看采集状态
curl http://localhost:8000/api/v1/collect/status
```

## 启动脚本

项目提供 `scripts/` 下的运维脚本，简化日常操作：

```bash
# 本地模式（需要自行启动 PostgreSQL）
./scripts/start.sh          # 启动后端 + 前端
./scripts/stop.sh           # 停止
./scripts/status.sh         # 查看状态

# Docker 模式（一键启动全部）
./scripts/start.sh --docker
./scripts/stop.sh --docker

# 数据库管理
./scripts/db/start.sh       # 仅启动 PostgreSQL
./scripts/db/stop.sh        # 仅停止 PostgreSQL
```

## API 概览

| 端点 | 说明 |
|------|------|
| `GET /health` | 健康检查 |
| `GET /api/v1/funds` | 基金分页查询（支持名称/类型/公司/关注筛选） |
| `GET /api/v1/funds/{code}/nav` | 基金净值 |
| `GET /api/v1/sectors` | 板块列表 |
| `GET /api/v1/sectors/rank` | 板块排行 |
| `GET /api/v1/sectors/{id}` | 板块详情（含快照和实时估算） |
| `GET /api/v1/news` | 新闻列表 |
| `POST /api/v1/collect/trigger` | 触发采集任务 |
| `GET /api/v1/collect/settings` | 采集器配置 |
| `POST /api/v1/analysis/news/sentiment` | 批量新闻情绪分析 |
| `GET /api/v1/analysis/reports` | 分析报告列表 |
| `GET /api/v1/analysis/advice` | 操作建议列表 |
| `POST /api/v1/admin/ai-providers/{id}/test` | AI 连通性测试 |

## 测试

```bash
# 后端测试
cd backend
source ../.venv/bin/activate
pytest tests/ -v

# 带覆盖率
pytest --cov=app --cov-report=term-missing
```

## 安全注意事项

- `.env` 文件包含数据库密码和 API Key，已配置 `.gitignore` 排除
- AI Provider 的 API Key 通过 `ENCRYPTION_KEY` 加密后存储在数据库中
- 运行时日志文件（`*.log`）已在 `.gitignore` 中排除
- 所有敏感配置通过环境变量注入，不硬编码在代码中

## 开发进度

| Phase | 内容 | 状态 |
|-------|------|------|
| 1 | 项目骨架、数据采集层 | 100% |
| 2 | 新闻/资金流向、服务层 | 100% |
| 3 | AI 分析引擎、情绪指标 | 100% |
| 4 | CLI 工具、Skill 文件 | 100% |
| 5 | 前端页面 | 100% |

详细进度见 [backend/docs/PROGRESS.md](backend/docs/PROGRESS.md)。
