# Gify

内网部署的轻量 AI Agent 平台。单人开发，20–50 人使用。三角色：管理员（admin）/ Agent 负责人（builder）/ 普通用户（user）。

## 必读文档

- `docs/gify-product-doc.md` — 需求文档：功能 FR-01~12、里程碑 M1–M3、技术选型
- `docs/gify-dev-conventions.md` — 开发规范：结构、分层、API、数据库、测试、提交

写代码前先读这两份并严格遵守；实现与文档冲突时，先改文档再改代码。

## 技术栈

- 后端：Python 3.12 + FastAPI + SQLAlchemy 2.0（async）+ Alembic，uv 管理依赖
- 前端：Vue 3 + TypeScript + Vite + Element Plus + Pinia
- 数据：PostgreSQL 16（pgvector 镜像）+ Redis 7；部署 Compose 四容器：app（API）、nginx（前端静态）、postgres、redis（`deploy/`）
- 前端与 API 跨域：生产构建注入 `VITE_API_BASE_URL`，后端 CORS 白名单 `CORS_ORIGINS` 放行

## 关键约定

- 开发顺序即功能编号：当前阶段 M1（FR-01 用户与权限 → FR-02 部署 → FR-03 审计）
- 模型接入仅 OpenAI 兼容协议；工具接入走 MCP（平台为客户端）
- 提交信息：`类型(范围): 中文描述`，如 `feat(auth): 实现登录与会话管理`
- 文档与提交说明用常规开发文风，不用比喻和口号
- 功能完成的判定以需求文档"验收标准"为准
