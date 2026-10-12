# Gify 开发规范

| 项 | 内容 |
|---|---|
| 版本 | v1.4（2026-10） |
| 适用范围 | backend、frontend、deploy |

## 1. 总则

1. 需求文档（gify-product-doc.md）定义做什么，本文档定义怎么做。实现与规范冲突时，先改文档再改代码。
2. 条文用语：**必须**（强制）、**禁止**（强制反向）、**默认**（无特别理由时遵循）、**允许**（明确放开）。
3. 条文分两层：
   - **协议与工程规范**（第 2、4–6、8–10 章）：语言无关。字段命名、信封结构、错误码、数据格式、建表与查询规则、安全要求、流程约定，描述的是接口契约与工程纪律，更换实现技术时不变。
   - **实现规范**（第 3、7 章）：绑定当前技术栈（Python / FastAPI、Vue 3 / TypeScript）。更换技术栈时仅重写这两章。
4. 协议章节中括注"当前选型"的工具名只是落点提示，不构成约束；本文未覆盖的场景遵循社区惯例。

## 2. API 规范

### 2.1 路径与方法

1. 路径以 `/api` 开头。
2. URL 命名：资源名复数、全小写、连字符分词，如 `/api/users`、`/api/model-providers`、`/api/conversations`。
3. 方法语义固定：GET 查询、POST 创建、PUT 全量更新、PATCH 局部更新、DELETE 删除。
4. 子资源层级不超过两层：`/api/agents/{id}/tools` 允许，更深层级改用查询参数。
5. SSE 接口路径以 `/stream` 结尾，如 `/api/conversations/{id}/stream`。
6. 不做 API 版本号（内网单实例部署，前端与后端同仓同步发布）。

### 2.2 请求参数

1. JSON 字段统一 camelCase，如 `createdAt`、`pageSize`。
2. 查询参数：分页 `page`（从 1 起）、`pageSize`（默认 20，最大 100）；排序 `orderBy`（字段名，camelCase）、`order`（`asc` / `desc`）。
3. 可排序、可过滤的字段为白名单，未在白名单内的 `orderBy` 返回 400。
4. 请求体字段与资源 JSON 字段同名（camelCase）。
5. 请求体必须声明校验规则：必填 / 可选、长度上限、枚举取值；校验规则与前端表单规则一致。

### 2.3 响应格式

所有接口返回统一信封，三个字段固定返回：

```json
// 成功
{ "code": 0, "message": "ok", "data": { "…资源字段": "…" } }

// 错误
{ "code": 2001, "message": "用户名或密码错误", "data": null }
```

1. `code`：0 表示成功，非 0 为业务错误码（号段见 2.5）。
2. `message`：成功固定 `ok`；错误为可直接展示给用户的中文，排查信息写日志不进响应。
3. `data`：成功时为资源 JSON；错误时为 `null`，仅 422 校验失败时为字段级错误对象 `{字段名: 错误信息}`。
4. 分页响应的 `data` 固定结构：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "pageSize": 20
}
```

5. 资源中的可空字段显式返回 `null`，不省略键。

### 2.4 状态码

| 状态码 | 使用场景 |
|---|---|
| 200 | 查询、更新、删除成功（统一返回信封，不使用 204） |
| 201 | 创建成功 |
| 400 | 请求语义错误（白名单外的排序字段等） |
| 401 | 未登录、会话失效 |
| 403 | 已登录但无权限 |
| 404 | 资源不存在，或存在但当前用户不可见（不泄露存在性） |
| 409 | 业务冲突（用户名重复、名称重复、状态冲突） |
| 422 | 请求体校验失败，`code` 为 1001，`data` 为字段级错误 |
| 500 | 服务端错误，`code` 为 1000 |

HTTP 状态码与信封 `code` 必须成对声明、由同一处定义产生，禁止两处分别设置，避免不一致。

### 2.5 业务错误码

数字码，按域分配号段：

| 域 | 号段 |
|---|---|
| COMMON | 1000–1999 |
| AUTH | 2000–2999 |
| USER | 3000–3999 |
| PROVIDER | 4000–4999 |
| AGENT | 5000–5999 |
| KB | 6000–6999 |
| CHAT | 7000–7999 |
| SHARE | 8000–8999 |

1. 错误码集中登记、统一引用：登记名语义化 UPPER_SNAKE（如 `AUTH_INVALID_CREDENTIALS`），值为号段内数字；业务代码禁止使用裸数字。登记位置与实现见 3.4。
2. 内置保留：1000 服务端错误（`COMMON_INTERNAL`）、1001 请求校验失败（`COMMON_VALIDATION`）。
3. 示例：`AUTH_INVALID_CREDENTIALS = 2001`、`AUTH_USER_DISABLED = 2002`、`USER_USERNAME_TAKEN = 3001`、`PROVIDER_CONNECT_FAILED = 4001`。

### 2.6 数据格式

1. 时间：ISO 8601 UTC 字符串，`2026-10-09T08:30:00Z`；存储使用带时区的时间类型；前端展示转本地时区。
2. ID：UUID，传输为字符串。
3. 枚举：字符串传输（`"admin"` / `"builder"` / `"user"`），不使用数字枚举。
4. 布尔：true / false，禁止用 0 / 1 代替。
5. 金额与单价：字符串形式的十进制数传输（避免浮点精度丢失），存储使用定点十进制类型。

### 2.7 SSE 事件（M2 落地，先定骨架）

1. 事件名小写连字符：`message-delta`（增量文本）、`message-done`（本轮完成，含用量）、`error`。
2. `data` 为 JSON 对象，字段 camelCase，不使用 2.3 的信封结构——事件类型路由由 SSE 的 `event` 字段承担。
3. `error` 事件的 `data` 为 `{"code": …, "message": "…"}`，code 使用 2.5 的错误码号段，与普通接口的错误处理保持同一套。
4. 连接建立后先推一次会话元数据事件，断线重连按会话 ID 拉全量。

## 3. 后端实现规范（当前栈：Python / FastAPI）

> 本章绑定当前后端技术栈；更换语言时重写本章，第 2 章协议不变。

### 3.1 工程结构与分层

```
backend/app/
├── main.py        # 应用入口：路由注册、中间件、异常处理器、生命周期
├── db.py          # engine 与 session 工厂
├── core/          # config、security、audit、errors、logging、通用 deps
├── api/           # 路由层，按资源一个文件：auth.py、users.py …
├── schemas/       # Pydantic 模型，文件与资源同名：users.py …
├── models/        # SQLAlchemy ORM 模型，文件与表所在域同名
└── services/      # 业务逻辑层，模块名 资源_service.py：user_service.py …
```

1. 路由层只做：参数校验、权限检查、调用 service、组装响应。禁止在路由层写业务逻辑、直接操作数据库。
2. service 层承载业务逻辑与数据访问，函数式模块（模块内普通函数，不用类）。
3. service 层的创建 / 更新 / 删除操作必须调用统一审计入口（`core/audit`）。
4. ORM 模型只描述数据结构，不含业务方法。
5. 依赖注入统一 FastAPI `Depends`：session、当前用户、角色检查均以依赖提供。

### 3.2 命名规范

| 对象 | 规则 | 示例 |
|---|---|---|
| 模块 / 文件 | snake_case | `user_service.py` |
| 变量 / 函数 | snake_case | `create_user` |
| 类 / Pydantic 模型 | PascalCase | `User`、`UserCreate` |
| 常量 | UPPER_SNAKE | `SESSION_COOKIE` |

### 3.3 编码规则

1. Python 3.12+，函数与属性全量类型标注。
2. ruff 负责 lint 与格式化，配置写入 pyproject.toml，规则取默认；提交前检查执行 `ruff check` 与 `ruff format --check`。
3. I/O 全部 async：路由、数据库（SQLAlchemy 2.0 async + psycopg async）、Redis、HTTP。同步库只允许出现在独立进程（arq worker）。
4. SQLAlchemy 一律 2.0 风格（`Mapped` / `mapped_column`），禁止遗留 Query API。
5. 路由函数返回 Pydantic 模型（`response_model`），禁止返回裸 dict。
6. JSON 字段 camelCase（2.2）由 Pydantic alias 统一转换，业务代码内部使用 snake_case。
7. 请求体校验（2.2.5）由 `schemas/` 下的 Pydantic 模型声明。
8. 关联数据预载（4.4.2）使用 `selectinload` / `joinedload`。
9. 日志（第 6 章）用标准库 logging + JSON formatter，封装为 logger 工厂（`core/logging`），业务代码只取 logger，不自行配置 handler。

### 3.4 异常处理

1. 业务异常统一 `AppError(code, message, http_status)`，集中定义在 `core/errors.py`；错误码常量（语义化 UPPER_SNAKE，值取 2.5 号段）与 HTTP 状态码在此成对声明。
2. 业务代码 `raise AppError(...)`，禁止直接 raise `HTTPException`。
3. 全局异常处理器输出 2.3 的信封结构，并负责将请求体校验错误转换为 1001 + 字段级 `data`；未捕获异常记 ERROR 日志（含 request_id）并返回 500 / 1000。

### 3.5 配置

1. 配置统一由 `core/config.py`（pydantic-settings）提供，业务代码禁止 `os.getenv`。
2. 环境变量命名 UPPER_SNAKE（`DATABASE_URL`、`SECRET_KEY`）。
3. 新增配置项必须同步 `deploy/.env.example`。

## 4. 数据库与 SQL 规范（PostgreSQL）

> 本章基于 PostgreSQL，与后端语言无关；涉及工具处以"当前选型"标注。

### 4.1 建表规范

1. 表名复数 snake_case（`users`、`kb_documents`）；列名 snake_case（`created_at`）。
2. 每张业务表必须包含：`id UUID PRIMARY KEY DEFAULT gen_random_uuid()`、`created_at timestamptz NOT NULL DEFAULT now()`；有更新语义的表加 `updated_at`。
3. 表与列必须写 `COMMENT`，说明业务含义（建库自描述）。
4. 默认硬删除（内部平台，追溯靠审计日志）；用户类数据用状态位（`enabled`）代替删除。
5. 标识符全小写；不使用数据库保留字。

### 4.2 字段类型

| 场景 | 类型 |
|---|---|
| 时间 | timestamptz（禁止 timestamp without tz） |
| 文本 | 默认 text；有长度上限要求时 varchar(n) 且应用层同步校验 |
| 状态 / 枚举 | varchar + CHECK 约束 |
| 金额 / 单价 | numeric（禁止 float / double 存钱） |
| 布尔 | boolean |
| JSON 配置 | jsonb，读写必须经过对应模型校验 |
| 外键 | uuid，引用父表 id |

### 4.3 约束与索引命名

| 对象 | 规则 | 示例 |
|---|---|---|
| 索引 | `idx_表_列` | `idx_users_role` |
| 唯一约束 | `uk_表_列` | `uk_users_username` |
| 外键约束 | `fk_表_列` | `fk_messages_conversation_id` |

1. 外键必须显式声明 `ON DELETE` 策略：默认 `RESTRICT`，明确的从属数据（如分块随文档）用 `CASCADE`。
2. 外键列、频繁过滤列、排序列必须建索引；唯一性用唯一约束表达，不靠应用层判重。
3. 复合索引列顺序：过滤列在前、排序列在后。

### 4.4 查询规范

1. 手写 SQL 禁止 `SELECT *`，显式列出字段；ORM 整实体查询允许，但列表接口不加载大字段（正文、JSONB 大对象）。
2. 禁止 N+1：关联数据在查询时显式预载，禁止循环内逐条查询。
3. 事务边界在 service 层：一个 service 函数一个事务，禁止跨请求持有事务。
4. 行锁仅在并发写同一行的场景使用，并在代码注释说明理由。
5. 涉及用户隔离的数据（会话、日志），查询必须带归属条件，禁止先查后过滤。

### 4.5 迁移规范

1. 表结构变更一律通过迁移工具完成（当前选型 Alembic），自动生成的内容必须人工检查后提交。
2. 迁移文件提交后禁止修改；返工通过新迁移完成。
3. 迁移 message 语义化：`create users table`、`add role to users`。
4. 破坏性变更（删列、改类型、删表）在 message 前加 `[destructive]`，并在升级说明中记录处理方式。
5. 迁移链必须可从空库完整重放（CI 或本地验证）。

## 5. 安全规范

### 5.1 认证与会话

1. 会话 cookie：`HttpOnly`；`SameSite=Lax`；生产环境 `Secure`；`Path=/`。
2. session 存 Redis，键含用户与状态；每次请求校验用户 `enabled`，禁用即时失效。
3. 会话空闲过期 7 天（滑动续期）。
4. 登录接口防爆破：同一用户名连续失败 5 次锁定 10 分钟（Redis 计数）。

### 5.2 密码

1. 哈希算法 argon2id，使用标准参数集。
2. 最小长度 8 位；初始管理员账号与重置后的密码在首次登录强制修改。
3. 明文密码禁止出现在日志、审计 detail、异常栈、响应中。

### 5.3 敏感数据

1. `api_key`、MCP 鉴权信息用 Fernet 方案加密落库（密钥由 `SECRET_KEY` 派生）；界面只显示尾 4 位。
2. 日志脱敏字段清单：`password`、`api_key`、`authorization`、`session_id`、`token`；结构化日志在输出层统一过滤。
3. `.env` 永不提交（.gitignore 覆盖）；密钥变更走部署文档流程。

### 5.4 输入与注入

1. SQL 一律参数化执行（ORM 或绑定参数），禁止字符串拼接。
2. 动态排序字段、表名字段必须走白名单。
3. 路径参数校验类型（UUID 按 UUID 解析），不信任外部输入做文件路径拼接。

### 5.5 接口防护

1. CORS 默认关闭（前端由 app 容器同源托管）；确需放开时按部署文档配置白名单。
2. 上传（M2）：单文件 ≤ 20MB，扩展名白名单（txt / md / pdf / docx），文件名不信任。
3. 分享页 token 用密码学安全随机数生成（URL-safe 编码，≥ 32 字节熵），关闭分享立即失效。

## 6. 日志规范

1. 日志以 JSON 结构输出 stdout，一行一条。
2. 级别定义：ERROR 需要人工介入；WARNING 异常但已自愈；INFO 关键路径事件（登录、配置变更、任务启动）；DEBUG 仅开发期。
3. 每个请求由中间件分配 `requestId`，日志与响应头（`X-Request-Id`）均携带。
4. 结构化字段统一 camelCase：`ts`、`level`、`logger`、`requestId`、`userId`、`event`、`msg`。

## 7. 前端实现规范（当前栈：Vue 3 / TypeScript）

> 本章绑定当前前端技术栈；更换框架时重写本章，第 2 章协议不变。

### 7.1 工程结构

```
frontend/src/
├── api/         # 接口调用，按模块一个文件 + request.ts 单例
├── stores/      # Pinia 状态，按域一个 store
├── router/      # 路由与守卫（登录态 + 角色）
├── views/       # 页面组件
├── components/  # 跨页面复用组件
└── utils/       # 纯函数工具
```

1. 目录名全小写；页面组件放 views，跨页面复用组件放 components。

### 7.2 命名规范

| 对象 | 规则 | 示例 |
|---|---|---|
| Vue 组件文件 | PascalCase | `UserList.vue` |
| 非组件 ts 文件 | camelCase | `request.ts` |
| 组合式函数 | use 前缀 + PascalCase | `useChat.ts` |
| TS 类型 / 接口 | PascalCase，不加 I 前缀 | `User`（不是 `IUser`） |
| CSS class | kebab-case，scoped | `.chat-panel` |
| 常量 | UPPER_SNAKE | `MAX_FILE_SIZE` |

### 7.3 组件与状态

1. 统一 `<script setup lang="ts">`，禁止 Options API。
2. 组件超过 250 行或含 3 个以上独立区块时拆分。
3. 状态：服务端数据缓存与用户信息进 Pinia；组件内临时状态用 ref / reactive，不进 store。
4. 路由守卫集中处理登录态与角色，页面组件内禁止权限判断。

### 7.4 接口调用

1. HTTP 客户端单例在 `src/api/request.ts`：`baseURL '/api'`、`withCredentials`。
2. 响应拦截器统一解包：HTTP 401 跳登录页；`code !== 0` 时以 `message` 弹出（ElMessage）并 reject；`code === 0` 时直接向调用方返回 `data`；网络错误统一提示。
3. 每个接口函数标注返回类型，类型定义与后端模型字段一一对应（camelCase）。
4. 组件禁止直接使用 HTTP 客户端。

### 7.5 表单校验

1. 前端校验规则与后端校验约束一致（必填、长度、格式）。
2. 422 返回的字段级错误（`data`）映射回对应表单项展示。

## 8. Git 规范

### 8.1 分支模型

1. 分支名 `feature/` 前缀 + kebab-case，如 `feature/user-auth`。
2. main 单分支开发，保持可发布状态。
3. 跨多日的功能开 `feature/xxx` 分支；完成后 rebase 到 main，`--ff-only` 合并，保持线性历史。
4. 单人项目不设 review 流程；修复类允许直接提交 main。

### 8.2 提交信息

1. 格式 `类型(范围): 中文描述`，描述不超过 50 字，必要时加 body 说明动机。

| 类型 | 用途 |
|---|---|
| feat | 新功能 |
| fix | 缺陷修复 |
| refactor | 重构（不改行为） |
| docs | 文档 |
| test | 测试 |
| chore | 构建、依赖、脚手架 |

2. 正例：`feat(auth): 实现登录与会话管理`、`fix(provider): 修复测试连接超时未捕获`、`docs(conventions): 细化 SQL 规范`。
3. 反例（禁止）：`修改bug`、`更新`、`fix: 修复了一些问题`。
4. 一次提交一个关注点；格式化与重构独立提交，不与功能混在一起。

### 8.3 合并与标签

1. 里程碑完成打 tag：`m1`、`m2`、`m3`。
2. 对外发布版本从 `v1.0.0` 起按语义化版本递增。

### 8.4 提交前检查

1. 提交前必须通过：后端 lint 与全部测试；前端 lint 与构建（含类型检查）。
2. 当前栈命令：后端 `uv run ruff check . && uv run pytest`；前端 `npm run lint && npm run build`。
3. 禁止提交：`.env`、`node_modules/`、`.venv/`、`dist/`、数据库文件。

## 9. 测试与完成定义

1. 测试框架随技术栈（当前选型 pytest）；必须有测试的范围：权限判断、审计入口、分流路由、成本聚合、工具调用循环；纯 CRUD 不强制。不设覆盖率指标。
2. 测试使用独立数据库，通过迁移建表；测试数据在 fixture 中构造，不依赖手工造数。
3. 功能（FR-xx）的完成定义：
   1. 需求文档"功能要求"逐条实现；
   2. "验收标准"逐条通过：可自动化的写成测试，其余手动验证后在提交信息中记录；
   3. 空库可完整重放迁移；
   4. lint 无报错；
   5. 涉及需求变更的，先更新需求文档再合入代码。

## 10. 文档维护

1. 功能需求唯一来源为 `docs/gify-product-doc.md`；开发中发现需求问题，先改文档再改代码。
2. 本文档随提交演进，重大调整在提交信息中说明。
