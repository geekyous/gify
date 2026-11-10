# Gify

内网部署的轻量 AI Agent 平台。单人开发，20–50 人使用。三角色：管理员（admin）/ Agent 负责人（builder）/ 普通用户（user）。

## 必读文档

- `docs/gify-product-doc.md` — 需求文档：功能 FR-01~12、里程碑 M1–M3、技术选型
- `docs/gify-dev-conventions.md` — 开发规范：结构、分层、API、数据库、安全、测试、提交

写代码前先读这两份并严格遵守；实现与文档冲突时，先改文档再改代码。

## 目录结构

```
backend/     FastAPI 模块化单体：app/core 公共层 + 按域模块（identity、providers、
             engine、kb、tools、agents、chat、usage）、alembic/、tests/
frontend/    Vue 3：src/{api,stores,router,layouts,views,components,utils}
deploy/      Compose 四容器：Dockerfile（app）、frontend.Dockerfile、nginx.conf、
             docker-compose.yml、deploy.sh、upgrade.sh、.env.example、README.md
docs/        需求文档与开发规范（功能需求唯一来源）
```

## 常用命令

```bash
# 后端
cd backend
uv run uvicorn app.main:app --port 8000                # 开发服务
uv run ruff check . && uv run ruff format --check .    # lint
uv run pytest                                          # 测试（独立库 gify_test，fixture 自动重建）

# 前端
cd frontend
npm run dev                    # 开发服务，/api 由 Vite 代理转发到 127.0.0.1:8000
npm run lint && npm run build  # 提交前检查（build 含类型检查）

# 部署栈（本地验证 / 目标机部署）
cd deploy
docker compose up -d --build   # 本地四容器验证；postgres、redis 仅绑定 127.0.0.1
sh upgrade.sh                  # 备份确认 → 拉取镜像 → 迁移 → 重启（生产）
```

- 测试环境与生产都用 Actions 构建并存放于 ACR 的镜像（`TAG=<sha> sh deploy.sh` 拉取部署），服务器不做构建；流程见 `deploy/README.md`
- 后端配置统一读 `deploy/.env`（样例 `deploy/.env.example`，永不提交；真实凭据不进仓库）；新增配置项必须同步样例
- 本地开发用 compose 起 postgres/redis，后端直连 `127.0.0.1`（端口可在 `.env` 改）；app 容器内由 compose `environment` 覆盖主机名与端口
- 测试使用独立库 `gify_test` 与 Redis db 1，不触碰开发数据

## 技术栈

- 后端：Python 3.12 + FastAPI + SQLAlchemy 2.0（async）+ Alembic，uv 管理依赖
- 前端：Vue 3 + TypeScript + Vite + Element Plus + Pinia
- 数据：PostgreSQL 16（pgvector 镜像）+ Redis 7；部署 Compose 四容器：app（API）、nginx（前端静态）、postgres、redis（`deploy/`）
- 前端与 API 跨域：生产构建注入 `VITE_API_BASE_URL`，后端 CORS 白名单 `CORS_ORIGINS` 放行；认证为服务端 session（Redis 存储 + HttpOnly cookie）

## 关键约定

- 开发顺序即功能编号；当前阶段 M1：FR-01、FR-02 已完成（FR-02 剩全新机器初装与升级演练两项验收），下一步 FR-03 审计
- 模型接入仅 OpenAI 兼容协议；工具接入走 MCP（平台为客户端）
- 跨多日功能开 `feature/` 分支，完成后 rebase 到 main 以 `--ff-only` 合并；里程碑完成打 tag（`m1`/`m2`/`m3`）
- 编码分工：Claude 提供完整参考源码（含单元测试、集成测试代码），由用户本人写入仓库并运行检查；Claude 负责文档、方案、评审与排障
- 功能开发流程：每个功能按 后端代码（含单元测试）→ 前端代码 → 集成测试 顺序推进，前一阶段完成后再进入下一阶段
- 提交信息：`类型(范围): 中文描述`，如 `feat(auth): 实现登录与会话管理`；一次提交一个关注点
- 提交前必须通过：后端 lint 与全部测试、前端 lint 与构建
- 文档与提交说明用常规开发文风，不用比喻和口号
- 功能完成的判定以需求文档"验收标准"为准；可自动化的写成测试，手动验证的在提交信息中记录

## 高频规范（完整以开发规范为准）

- 后端为领域模块化单体：模块间只 import 对方 service 公开函数，禁止摸对方 api/schemas/models 内部；core 是唯一公共层，不依赖任何模块
- 路由层只做参数校验、权限检查、调用 service、组装响应；业务逻辑与数据访问在 service 层
- 接口统一信封 `{code, message, data}`；错误码集中登记在 `backend/app/core/errors.py`，禁止裸数字、裸 dict 返回、直接 raise `HTTPException`
- JSON 字段 camelCase（Pydantic alias 转换），业务代码内部 snake_case
- 敏感字段（`password`、`api_key`、`authorization`、`session_id`、`token`）不进日志、审计 detail 与响应
- 表结构变更一律走 Alembic 迁移；迁移文件提交后不再修改
- 前端组件不直接使用 HTTP 客户端，统一走 `src/api/request.ts`
- 注释与文档字符串：中文用中文标点、英文用英文标点，类名引用保持原大小写；不用“ / ”作连词，写自然完整中文（规范 3.6）
