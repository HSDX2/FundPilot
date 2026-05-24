# FundPilot

中国基金投研分析平台 — 数据采集、AI 分析、命令行工具。

---

## 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | **3.12.13** | 必须精确版本 |
| PostgreSQL | **16** | 数据库 |
| Docker (可选) | 24+ | 替代本地 PostgreSQL，一键启动 |
| pyenv (可选) | — | 管理 Python 版本 |

中国用户：`pip` 和 Docker 构建默认使用清华 PyPI 镜像，如需更改见配置说明。

---

## 从零开始运行项目

### 1. 克隆项目

```bash
git clone <repo-url>
cd FundPilot
```

### 2. 安装 Python 3.12.13

```bash
# 使用 pyenv
pyenv install 3.12.13
pyenv local 3.12.13

# 验证
python --version   # 必须输出 Python 3.12.13
```

### 3. 创建数据库

**方式 A: Docker（推荐）**
```bash
docker compose up -d postgres
# PostgreSQL 运行在 localhost:5432
```

**方式 B: 本地 PostgreSQL**
```bash
# macOS (Homebrew)
brew install postgresql@16
brew services start postgresql@16

# 创建用户和数据库
createuser -s fundpilot
createdb fundpilot -O fundpilot
```

验证数据库可连接：
```bash
psql -U fundpilot -h localhost -c "SELECT 1"
```

### 4. 创建配置文件

项目有 **3 个配置模版**，需要依次复制并填写：

```bash
# ① Docker Compose / 脚本引用（根目录）
cp .env.example .env

# ② 后端服务（backend/）
cp backend/.env.example backend/.env

# ③ CLI 工具（cli/，可选）
cp cli/.env.example cli/.env
```

**必须修改的配置项：**

| 文件 | 变量 | 说明 |
|------|------|------|
| `.env` 和 `backend/.env` | `DB_PASSWORD` | 修改默认值 `change-me` |
| `backend/.env` | `DB_HOST` | Docker 用 `localhost`，本地 PG 用 `localhost` |

> 如果你在中国境外，还需修改 `.env` 中的 `PIP_INDEX_URL`。

### 5. 安装依赖

```bash
# 后端
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .

# CLI（可选，终端操作后端用）
cd ../cli
pip install -e .
```

### 6. 启动服务

**Docker 方式（一键）：**
```bash
cd /path/to/FundPilot
docker compose up -d
./scripts/status.sh --docker
```

**本地方式：**
```bash
cd /path/to/FundPilot
./scripts/start.sh
```

启动后后端自动：
- 创建数据库表（`Base.metadata.create_all`）
- 初始化 11 个采集器的默认配置
- 注册并启动定时任务调度器

### 7. 验证

```bash
# 健康检查
curl http://localhost:8000/health
# → {"status":"ok"}

# 查看 API 文档
open http://localhost:8000/docs

# 测试采集器
fundpilot collect trigger sector_list
fundpilot collect status
```

---

## 项目架构

```
FundPilot/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/             # API 路由（thin layer，不含业务逻辑）
│   │   ├── core/               # 配置、数据库、错误处理
│   │   ├── models/             # SQLAlchemy ORM（12 张表）
│   │   ├── schemas/            # Pydantic 请求/响应模型
│   │   ├── repositories/       # 数据库访问（仅 CRUD）
│   │   ├── services/           # 业务逻辑
│   │   ├── integrations/       # AkShare、Jin10、CLS 等第三方 API
│   │   ├── ai/                 # AI Provider 适配器（6 家）
│   │   └── tasks/              # APScheduler 定时任务
│   ├── tests/                  # 254 个测试
│   ├── .env.example            # 后端配置模版
│   └── docs/                   # 架构/进度文档
├── cli/                        # 命令行工具（typer）
│   ├── fundpilot/
│   │   └── commands/           # fund / sector / analysis / news / collect
│   ├── tests/                  # 44 个测试
│   └── .env.example            # CLI 配置模版
├── scripts/                    # 运维脚本（start/stop/status/db）
├── skills/                     # Claude Code Skill 定义
├── docker-compose.yml          # Docker 编排
├── .env.example                # Docker/项目级环境变量模版
├── .gitignore
└── README.md
```

### 技术栈

| 层 | 技术 |
|----|------|
| 框架 | FastAPI + Uvicorn |
| 数据库 | PostgreSQL 16 + SQLAlchemy 2.0 async |
| 调度 | APScheduler（交易日感知） |
| 数据源 | AkShare、Jin10、财联社、华尔街见闻 |
| AI | DeepSeek / GLM / QWEN / OpenAI / Kimi / MiniMax |
| CLI | Typer + HTTPX |
| 部署 | Docker Compose |

### 分层约定

```
API Routes ──→ Services ──→ Repositories ──→ Database
  (thin)       (business)     (CRUD only)

Integrations ──→ 第三方 API   │   AI Module ──→ Provider 适配器
```

---

## 全部配置文件说明

### `backend/.env` — 后端服务配置

参照 [backend/.env.example](backend/.env.example)：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_HOST` | `0.0.0.0` | 监听地址 |
| `APP_PORT` | `8000` | 监听端口 |
| `DEBUG` | `false` | 调试模式（开发时可开） |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `CORS_ORIGINS` | `*` | CORS 允许域名，逗号分隔 |
| `DB_HOST` | `localhost` | 数据库地址 |
| `DB_PORT` | `5432` | 数据库端口 |
| `DB_USER` | `fundpilot` | 数据库用户 |
| `DB_PASSWORD` | — | 数据库密码（必改） |
| `DB_NAME` | `fundpilot` | 数据库名 |
| `DB_POOL_SIZE` | `10` | 连接池大小 |
| `DB_MAX_OVERFLOW` | `20` | 最大溢出连接 |
| `OPENAI_API_KEY` | — | AI API Key（可选） |

### `.env` — Docker 编排配置

参照 [.env.example](.env.example)，变量同上表。`docker-compose.yml` 通过 `${VAR:-default}` 语法读取。

### `cli/.env` — CLI 工具配置

参照 [cli/.env.example](cli/.env.example)：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FUNDPILOT_URL` | `http://localhost:8000` | 后端地址 |

### `.gitignore` — 版本控制排除

已配置排除：`.env`、`.venv/`、`.claude/`、`__pycache__/`、IDE 目录等。

---

## CLI 命令参考

```bash
# 基金
fundpilot fund search --name 新能源 --type stock --table
fundpilot fund detail 000001
fundpilot fund nav 000001 --start 2026-01-01
fundpilot fund estimate 000001
fundpilot fund batch-estimate 000001,000011

# 板块
fundpilot sector search --category concept --table
fundpilot sector rank --category industry --limit 10
fundpilot sector money-flow <uuid> --start 2026-05-01

# AI 分析
fundpilot analysis report-latest --type daily
fundpilot analysis advice-list --action buy
fundpilot analysis sentiment-latest

# 新闻
fundpilot news search --keyword 新能源 --table

# 采集
fundpilot collect trigger news
fundpilot collect status
fundpilot collect logs --collector news
fundpilot collect settings fund_list --interval 86400
```

详细用法见 [skills/fundpilot.md](skills/fundpilot.md)。

---

## 运维脚本

| 脚本 | 说明 |
|------|------|
| `./scripts/start.sh [--docker]` | 启动所有服务 |
| `./scripts/stop.sh [--docker]` | 停止所有服务 |
| `./scripts/status.sh [--docker]` | 查看服务运行状态和端点 |
| `./scripts/db/start.sh` | 仅启动 PostgreSQL |
| `./scripts/db/stop.sh` | 仅停止 PostgreSQL |

---

## 测试

```bash
# 后端
cd backend
pytest tests/ -v                # 254 个测试
pytest --cov=app --cov-report=term-missing

# CLI
cd cli
pytest tests/ -v                # 44 个测试
```

---

## 开发进度

| Phase | 内容 | 状态 |
|-------|------|------|
| 1 | 项目骨架、数据采集层 | 100% |
| 2 | 新闻/资金流向、服务层 | 100% |
| 3 | AI 分析引擎、情绪指标 | 100% |
| 4 | CLI 工具、Skill 文件 | 100% |
| 5 | 前端页面 | 待开发 |

**总计 63/72 (88%)** — [PROGRESS.md](backend/docs/PROGRESS.md)

---

## 相关文档

- [ARCH.md](backend/docs/ARCH.md) — 架构设计文档
- [CLAUDE.md](CLAUDE.md) — 编码规范
- [skills/fundpilot.md](skills/fundpilot.md) — CLI Skill 使用指南
