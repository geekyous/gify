# Gify

`Python 3.12+` · `FastAPI` · `Vue 3` · `PostgreSQL 16 (pgvector)` · `Redis 7` · `Docker Compose`

内网部署的轻量 AI Agent 平台，面向 20–50 人团队：管理员注册模型服务，Agent 负责人配置 Agent（提示词、模型、工具、知识库），普通用户在网页上直接使用，用量与成本可查。

## 功能特性

- **三角色账号体系** — 管理员（admin）/ Agent 负责人（builder）/ 普通用户（user），管理员统一开号，禁用即时生效
- **模型接入** — 仅 OpenAI 兼容协议，一条代码路径覆盖 vLLM、Ollama、DeepSeek、Qwen 及中转网关；连接测试、模型导入、单价配置
- **Agent 配置** — 提示词、模型（按能力过滤）、工具勾选、知识库挂载、记忆轮数，保存即生效
- **知识库 + RAG** — 固定摄取管道（上传 → 抽取 → 分块 → 嵌入 → 检索），可调 chunk size 与 top-k，附检索测试页
- **MCP 工具调用** — 平台作为 MCP 客户端，注册即用；内置 web_search / fetch_url / http_request 三个工具
- **智能分流** — 规则（正则）+ LLM 兜底的两级路由，一个对话入口对接多个专家 Agent
- **对话与分享** — 平台内多会话管理，另可生成免登录的内网分享页
- **审计与用量** — 变更操作全量审计，对话轨迹查询，token 与成本聚合统计

## 里程碑状态

| 里程碑 | 功能 | 状态 |
|---|---|---|
| M1 系统框架 | FR-01 用户与权限 | ✅ 完成 |
| | FR-02 部署与升级 | 🚧 主体完成，剩初装与升级演练 |
| | FR-03 操作审计 | ⬜ 下一步 |
| M2 业务基础 | FR-04 模型供应商管理 | ⬜ 规划中 |
| | FR-05 对话引擎 | ⬜ 规划中 |
| | FR-06 知识库 + RAG | ⬜ 规划中 |
| | FR-07 MCP 工具接入 | ⬜ 规划中 |
| M3 业务核心 | FR-08 Agent 创建与配置 | ⬜ 规划中 |
| | FR-09 与 Agent 对话 | ⬜ 规划中 |
| | FR-10 智能分流 | ⬜ 规划中 |
| | FR-11 对话日志与用量成本 | ⬜ 规划中 |
| | FR-12 分享页使用 | ⬜ 规划中 |

## 架构

四容器部署，前端与 API 跨域（CORS 白名单放行，会话凭证随跨域请求携带）：

```
 浏览器
   │  静态页面 / API（跨域）
   ▼
┌──────────┐      ┌──────────┐
│  nginx   │      │   app    │
│ 前端静态  │      │ FastAPI  │
└──────────┘      └──────────┘
                    │        │
              ┌─────┘        └─────┐
              ▼                    ▼
        ┌──────────┐        ┌──────────┐
        │ postgres │        │  redis   │
        │ pgvector │        │ 会话/队列 │
        └──────────┘        └──────────┘
```

## 快速开始

前置要求：Docker（含 Compose v2）。

```bash
cd deploy
cp .env.example .env
# 编辑 .env：SECRET_KEY、初始管理员密码、VITE_API_BASE_URL、CORS_ORIGINS
docker compose up -d --build
sh migrate.sh
```

浏览器打开 `http://<主机>:${FRONTEND_PORT}`（默认 8080），用初始管理员账号登录，首次登录强制改密。

升级、备份、日志查看见 [deploy/README.md](deploy/README.md)。

## 本地开发

前置要求：Python 3.12+、uv、Node 20+、Docker。

```bash
# 1. 起基础设施（postgres/redis 映射 127.0.0.1:5432、6379）
cd deploy && docker compose up -d postgres redis

# 2. 后端（配置读 deploy/.env）
cd backend
uv sync
uv run uvicorn app.main:app --port 8000

# 3. 前端（/api 由 Vite 代理转发到 127.0.0.1:8000）
cd frontend
npm install
npm run dev
```

检查命令：

```bash
cd backend && uv run ruff check . && uv run pytest   # lint + 测试（独立库 gify_test）
cd frontend && npm run lint && npm run build         # lint + 构建（含类型检查）
```

## 项目结构

```
backend/     FastAPI 模块化单体：app/ 按业务域分模块（identity、providers、engine、
             kb、tools、agents、chat、usage），core 为公共层
frontend/    Vue 3：src/{api,stores,router,layouts,views,components,utils}
deploy/      Compose 四容器：Dockerfile（app）、frontend.Dockerfile、nginx.conf、
             docker-compose.yml、migrate.sh、upgrade.sh、.env.example
docs/        需求文档与开发规范
```

## 文档

- [需求文档](docs/gify-product-doc.md) — 功能规格 FR-01~12、里程碑、技术选型（功能需求唯一来源）
- [开发规范](docs/gify-dev-conventions.md) — 分层结构、API 协议、数据库、安全、测试、Git 约定
- [部署说明](deploy/README.md) — 初装、升级、备份与恢复、日志

## 范围边界

v1 做到"单 Agent + 智能分流"为止，画布 DAG 编排、插件市场、多租户、计费等明确不做；编排演进到 v2 的串行链为止，更复杂场景应改用 Dify 等平台。完整边界见需求文档第 4 章。

---

内部项目，不对外发布。
