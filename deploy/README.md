# Gify 部署

Compose 四容器：app（API）、frontend（nginx 静态托管）、postgres（pgvector）、redis。前端与 API 跨域：前端构建时注入 API 地址（`VITE_API_BASE_URL`），后端用 `CORS_ORIGINS` 白名单放行前端来源。

两种部署形态：

| | 测试环境（云服务器） | 生产（内网） |
|---|---|---|
| 构建方式 | Actions 构建镜像，推送阿里云 ACR | 服务器上从源码构建 |
| 发版方式 | push main 自动部署 | 手动执行 upgrade.sh |
| 备份 | 不备份，数据可弃 | 升级前 pg_dump 备份 |

## 测试环境

### 流程

```
GitHub 私有仓（push main）
        │
        ▼
Actions：lint 与测试 → 构建镜像 → 推送 ACR
        │  SSH：同步 compose 与 deploy.sh，执行 deploy.sh
        ▼
云服务器 /opt/gify（无业务源码）
        拉取镜像 → 数据迁移 → 重启容器

访问入口（Cloudflare 提供 HTTPS）：
  app.<域名>  → frontend 容器（源站 :8081）
  api.<域名>  → app 容器（源站 :8080）
  web.<域名>  → Cloudflare Pages 自动构建的另一份前端
```

镜像以 git 短 sha 作版本号，同时更新 latest 标签；`gify-app` 与 `gify-frontend` 存放在同一命名空间下。

### 首次搭建

**阿里云 ACR**

1. 开通容器镜像服务（个人版），创建命名空间。
2. 在访问凭证页设置固定密码。
3. 仓库 gify-app、gify-frontend 无需手工创建，首次推送自动建立，默认私有。

**GitHub**

1. 创建私有仓库并推送代码。
2. Settings → Secrets and variables → Actions，添加 secrets：`TEST_SSH_HOST`、`TEST_SSH_USER`、`TEST_SSH_KEY`、`ACR_REGISTRY`、`ACR_NAMESPACE`、`ACR_USERNAME`、`ACR_PASSWORD`。
3. 同页 Variables 添加 `API_BASE_URL`，值为 API 对外地址，如 `https://api.example.com`。

**Cloudflare**

1. DNS 添加两条 A 记录：`app` 与 `api` 指向云服务器 IP，开启代理（橙云）。
2. Origin Rules 添加两条端口改写：`app` 主机名改写到 8081，`api` 改写到 8080。
3. Pages 创建项目并连接 GitHub 仓库：根目录 `frontend`，构建命令 `npm run build`，输出目录 `dist`，环境变量 `VITE_API_BASE_URL` 与 `API_BASE_URL` 同值；绑定自定义域 `web`。

**云服务器**

1. 安装 Docker。
2. 创建目录 `/opt/gify`，写入 `.env`（`docker-compose.yml` 与 `deploy.sh` 首次部署时由 Actions 复制过来）。以 `.env.example` 为底，修改以下各项：

```
SECRET_KEY=<openssl rand -hex 32 生成>
INIT_ADMIN_PASSWORD=<初始管理员口令>
POSTGRES_PASSWORD=<改掉默认值>
APP_PORT=8080
FRONTEND_PORT=8081
ACR_REGISTRY=registry.cn-<地域>.aliyuncs.com
ACR_NAMESPACE=<命名空间>
ACR_USERNAME=<阿里云账号或 RAM 子账号>
ACR_PASSWORD=<固定密码>
VITE_API_BASE_URL=https://api.<域名>
CORS_ORIGINS=https://app.<域名>,https://web.<域名>
COOKIE_SAMESITE=none
```

3. 防火墙放行 8080 与 8081。postgres 与 redis 只绑定 127.0.0.1，不对外。

`COOKIE_SAMESITE` 取 `none` 的原因：Pages 的域名与 API 不在同一注册域，`lax` 不会随跨站请求携带 cookie；`none` 要求 cookie 同时带 Secure 标记，由 Cloudflare 的 HTTPS 满足。

**验证**

1. 向 main 推送一次提交，观察 Actions 从检查到部署全部通过。
2. `curl https://api.<域名>/api/health` 应返回 `{"code":0,...}`。
3. 浏览器分别打开 `https://app.<域名>` 与 `https://web.<域名>`，用初始管理员登录并修改密码。

### 发版与回滚

日常发版只需 push main，其余自动。回滚到历史版本：

```bash
ssh <服务器>
cd /opt/gify
TAG=<commit sha> sh deploy.sh
```

## 生产部署（内网）

### 初装

```bash
cd deploy
cp .env.example .env
# 编辑 .env：SECRET_KEY、INIT_ADMIN_PASSWORD、POSTGRES_PASSWORD，
# 以及 VITE_API_BASE_URL 与 CORS_ORIGINS（实际的前端与 API 地址）
docker compose up -d --build
sh migrate.sh
```

完成后浏览器打开 `http://<主机>:${FRONTEND_PORT}`，用初始管理员账号登录，首次登录强制改密。

### 升级

```bash
cd deploy
sh upgrade.sh
```

## 备份与恢复

```bash
# 备份（升级前必做）
docker compose exec postgres pg_dump -U gify gify > backup-$(date +%F).sql
docker compose exec postgres pg_dump -Fc -U gify gify > backup-$(date +%F).dump

# 恢复（会覆盖现有数据，先停 app）
docker compose stop app
cat backup-YYYY-MM-DD.sql | docker compose exec -T postgres psql -U gify gify
docker compose start app
```

pgvector 数据在 `pg_data` volume 内，`pg_dump` 一并覆盖，无需单独备份向量文件。

## 日志

结构化 JSON 输出到 stdout，按服务查看：

```bash
docker compose logs -f app
docker compose logs -f --tail 100 app frontend
```

每条访问日志携带 `requestId`，与响应头 `X-Request-Id` 对应，用于排障串联。

## 本地开发

本地起后端、前端开发服务时，postgres 与 redis 已映射到 `127.0.0.1:5432`、`127.0.0.1:6379`；`.env` 中 `DATABASE_URL`、`REDIS_URL` 的 localhost 值即为此用途，app 容器内由 compose `environment` 覆盖为服务名地址。前端开发服务（5173）走 Vite 代理转发 `/api`，无需注入 `VITE_API_BASE_URL`。
