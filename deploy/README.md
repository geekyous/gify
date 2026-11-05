# Gify 部署

四容器：app（API）、frontend（nginx 静态托管）、postgres（pgvector）、redis。

前端与 API 跨域：前端构建时注入 `VITE_API_BASE_URL`（浏览器可达的 API 入口），后端 `CORS_ORIGINS` 白名单放行前端来源，会话 cookie 随跨域请求携带。

## 测试环境（云服务器，自动部署）

代码托管在 GitHub（私有仓），push main 触发 CI（lint、测试、构建），通过后由 Actions SSH 到云服务器执行 `deploy.sh`（构建、迁移、重启，无备份确认——测试数据可弃）。生产（内网）仍走本文档后半部分的 `upgrade.sh` 手动流程。

测试环境前端有两份，API 统一经 Cloudflare 代理提供 HTTPS：

- `app.example.com` → Cloudflare → 云服务器 frontend 容器（源站端口 `FRONTEND_PORT`）
- `web.example.com` → Cloudflare Pages（仓库关联自动构建，另一份前端）
- `api.example.com` → Cloudflare → 云服务器 app 容器（源站端口 `APP_PORT`）

Cloudflare 侧配置：三个 DNS 记录开橙云代理；用 Origin Rules 把 `app` / `api` 两个主机名分别改写源站端口；Pages 站点绑定 `web` 子域，构建配置 root 目录 `frontend`、命令 `npm run build`、输出 `dist`、环境变量 `VITE_API_BASE_URL=https://api.example.com`。

服务器 `.env` 关键项：

```
APP_PORT=8080
FRONTEND_PORT=8081
VITE_API_BASE_URL=https://api.example.com
CORS_ORIGINS=https://app.example.com,https://web.example.com
COOKIE_SAMESITE=none
```

`COOKIE_SAMESITE=none` 的原因：Pages 域与 API 不同注册域，Lax 不随跨站请求携带 cookie；`none` 在配置中联动强制 `Secure`，依赖 Cloudflare 的 HTTPS。

GitHub 仓库 secrets：`TEST_SSH_HOST`、`TEST_SSH_USER`、`TEST_SSH_KEY`（能登录云服务器并进入仓库目录的用户）。


## 初装

```bash
cd deploy
cp .env.example .env
# 编辑 .env：SECRET_KEY（openssl rand -hex 32）、INIT_ADMIN_PASSWORD、
# VITE_API_BASE_URL（API 对外地址）、CORS_ORIGINS（前端对外地址）、端口
docker compose up -d --build
sh migrate.sh        # 建表（首次启动执行一次）
```

完成后浏览器打开 `http://<主机>:${FRONTEND_PORT}`，用初始管理员账号登录，首次登录强制改密。

## 升级

```bash
cd deploy
sh upgrade.sh        # 备份提示 → 构建镜像 → 迁移 → 重启
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

本地起后端 / 前端开发服务时，postgres 与 redis 已映射到 `127.0.0.1:5432` / `127.0.0.1:6379`；`.env` 中 `DATABASE_URL` / `REDIS_URL` 的 localhost 值即为此用途，app 容器内由 compose `environment` 覆盖为服务名地址。前端开发服务（5173）走 Vite 代理转发 `/api`，无需注入 `VITE_API_BASE_URL`。
