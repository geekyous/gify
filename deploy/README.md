# Gify 部署

四容器：app（API）、frontend（nginx 静态托管）、postgres（pgvector）、redis。

前端与 API 跨域：前端构建时注入 `VITE_API_BASE_URL`（浏览器可达的 API 入口），后端 `CORS_ORIGINS` 白名单放行前端来源，会话 cookie 随跨域请求携带。

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
