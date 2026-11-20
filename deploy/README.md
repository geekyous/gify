# Gify 部署

Compose 五容器：gateway（入口 nginx，TLS 与域名分流）、frontend（nginx 静态托管）、app（API）、postgres（pgvector）、redis。前端与 API 跨域：前端构建时注入 API 地址（`VITE_API_BASE_URL`），后端用 `CORS_ORIGINS` 白名单放行前端来源。

两种部署形态都用 Actions 构建并存放在阿里云 ACR 的镜像，服务器上不做构建：

| | 测试环境（云服务器） | 生产（云服务器） |
|---|---|---|
| 发版 | push main 自动部署 | 手动执行 upgrade.sh |
| 版本 | 跟随 main | 指定 git sha，便于回滚 |
| 备份 | 不备份，数据可弃 | 升级前 pg_dump 备份 |

## 测试环境

### 流程

```
GitHub 仓库（push main）
        │
        ▼
Actions：lint 与测试 → 构建镜像 → 推送 ACR
        │  SSH：同步 docker-compose.yml 与 deploy.sh，执行 deploy.sh
          （nginx-gateway.conf 为环境相关配置，服务器自持，不随发版覆盖）
        ▼
云服务器 /opt/gify（无业务源码）
        拉取镜像 → 数据迁移 → 重启容器

访问入口（gateway 容器，宿主机 80 与 443，TLS 终结、按域名分流）：
  https://test.gify.<域名>     → frontend 容器（静态资源）
  https://test.api.<域名>     → app 容器（API）

第二份前端部署在 Cloudflare Pages（独立构建同一份代码），见“第二份前端”一节。
```

镜像以 git 短 sha 作版本号，同时更新 latest 标签；`gify-app` 与 `gify-frontend` 存放在同一命名空间下。

### 首次搭建

**阿里云 ACR**

1. 开通容器镜像服务（个人版），创建命名空间。
2. 在访问凭证页设置固定密码。
3. 仓库 gify-app、gify-frontend 无需手工创建，首次推送自动建立，默认私有。

**GitHub**

1. 创建仓库并推送代码。部署审批（Required reviewers）免费套餐仅公共仓库可用，私有仓库需要 Team 套餐。
2. Repository 级配置（Settings → Secrets and variables → Actions）：secrets 添加 `ACR_REGISTRY`、`ACR_NAMESPACE`、`ACR_USERNAME`、`ACR_PASSWORD`；Variables 添加 `API_BASE_URL`（测试 API 地址，如 `https://api.example.com`）与 `PROD_API_BASE_URL`（生产 API 地址，正式版镜像构建时注入）。
3. 部署环境（Settings → Environments）：新建 `test`，Required reviewers 勾审批人——部署任务在此暂停等批准；环境 secrets 添加 `TEST_SSH_HOST`、`TEST_SSH_USER`、`TEST_SSH_KEY`。

**部署密钥**

CI 登录服务器用专用密钥，与个人密钥分离、可单独吊销。私钥必须**无口令**（CI 非交互环境无法解密带口令的私钥，会报 `error in libcrypto`）：

```bash
# 生成专用密钥（-N "" 表示无口令）
ssh-keygen -t ed25519 -f ~/gify-ci-deploy -N "" -C "gify-ci-deploy"

# 公钥装到云服务器并收紧权限
cat ~/gify-ci-deploy.pub | ssh <用户>@<服务器IP> \
  "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"

# 本地验证免密登录，输出 ok 再继续
ssh -i ~/gify-ci-deploy <用户>@<服务器IP> echo ok

# 私钥全文粘贴进 test 环境的 TEST_SSH_KEY
cat ~/gify-ci-deploy
```

粘贴时从 `-----BEGIN OPENSSH PRIVATE KEY-----` 到 `-----END OPENSSH PRIVATE KEY-----` 一行不少；本地验证不通过时先查服务器 `authorized_keys` 权限，再配置 CI。

**域名与证书**

1. DNS 两条 A 记录指向云服务器 IP，代理关闭（直连）。
2. 大陆服务器的 80、443 绑定域名需要 ICP 备案，动手前先确认域名备案状态。
3. 服务器安装 certbot：`apt install certbot`。
4. gateway 首次启动只带 80——`nginx-gateway.conf` 的 443 块保持注释（证书未签发前 nginx 起不来）：

```bash
cd /opt/gify
mkdir -p certbot/www
docker compose up -d gateway
```

5. 签发证书（webroot 方式，验证文件写入挂载目录）：

```bash
sudo certbot certonly --webroot -w /opt/gify/certbot/www \
  -d test.gify.<域名> -d test.api.<域名>
```

6. 解开 `nginx-gateway.conf` 中两个 443 块的注释，续期挂 hook 并 reload：

```bash
sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-gateway.sh <<'EOF'
#!/bin/sh
docker compose -f /opt/gify/docker-compose.yml exec gateway nginx -s reload
EOF
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-gateway.sh
docker compose up -d --force-recreate gateway
```

续期钩子放在 `/etc/letsencrypt/renewal-hooks/deploy/` 目录（certbot 的 systemd timer 每天自动续期时会执行目录内脚本）；命令行传 `--deploy-hook` 只对当次生效，不持久。

**手改入口配置的注意**：该文件以单文件方式挂载进容器，`sed -i` 等原地替换会产生新 inode，容器仍看到旧内容且 `docker compose up -d` 不会重建——每次修改后必须 `docker compose up -d --force-recreate gateway`。

Cloudflare 代理（Origin Rules 端口改写）作为备选入口保留可行性：需要时放开 app、frontend 端口映射并配置 CF 即可，gateway 不冲突。

**云服务器**

1. 安装 Docker。
2. 创建目录 `/opt/gify`，手动放入仓库 `deploy/` 下的 `docker-compose.yml`、`deploy.sh`、`nginx-gateway.conf` 三个文件（后两个此后由 Actions 同步 / 服务器自持：compose 与 deploy.sh 每次发版覆盖，gateway 配置含本机域名与证书路径，只在初装与变更时手动更新）。写入 `.env`，以 `.env.example` 为底，修改以下各项：

```
SECRET_KEY=<openssl rand -hex 32 生成>
CORS_ORIGINS=https://test.gify.<域名>
INIT_ADMIN_PASSWORD=<初始管理员口令>
APP_PORT=<高位端口>
FRONTEND_PORT=<另一个高位端口>
POSTGRES_PASSWORD=<openssl rand -hex 16 生成>
REDIS_PASSWORD=<openssl rand -hex 16 生成>
ACR_REGISTRY=registry.cn-<地域>.aliyuncs.com
ACR_NAMESPACE=<命名空间>
ACR_USERNAME=<阿里云账号或 RAM 子账号>
ACR_PASSWORD=<固定密码>
```

前端与 API 同注册域，`COOKIE_SAMESITE` 保持默认 `lax` 即可；`ENV=prod` 使会话 cookie 带 Secure。`APP_PORT` 与 `FRONTEND_PORT` 仅绑定 127.0.0.1，供本地排障与 Cloudflare 备选入口使用。

3. 防火墙只放行 80 与 443。app、frontend、postgres、redis 均只绑定 127.0.0.1，不对外。

**验证**

1. 向 main 推送一次提交，观察 Actions 从检查到部署全部通过。
2. `curl https://test.api.<域名>/api/health` 应返回 `{"code":0,...}`。
3. 浏览器打开 `https://test.gify.<域名>`，用初始管理员登录并修改密码。

### 第二份前端（Cloudflare Pages）

前端另有一份部署在 Cloudflare Pages，连接 GitHub 仓库自动构建，与服务器上的 frontend 容器互为独立副本。首次配置（Dashboard → Workers & Pages → Create → Pages → Connect to Git，选中本仓库）：

| 配置项 | 值 |
|---|---|
| Production branch | `main` |
| Root directory | `frontend` |
| Build command | `npm run build` |
| Build output directory | `dist` |
| 环境变量 | `VITE_API_BASE_URL`（与 GitHub variable `API_BASE_URL` 同值）；`NODE_VERSION` = `22` |

构建配置与 CI 镜像构建相互独立：Pages 只负责这份静态副本，检查与测试仍由 Actions 负责。

绑定自定义域（必须）：Pages 项目 → Custom domains → 添加 `test.web.<域名>`，CNAME 记录由 Cloudflare 自动创建。**不要用 `*.pages.dev` 默认域**——它与 API 不在同一注册域，`lax` cookie 不会随请求携带，登录无法工作。

服务器 `.env` 的 `CORS_ORIGINS` 需追加该域名：

```
CORS_ORIGINS=https://test.gify.<域名>,https://test.web.<域名>
```

改后 `docker compose up -d app` 重建 app 容器生效。

### 发版与回滚

日常发版只需 push main，其余自动。回滚到历史版本：

```bash
ssh <服务器>
cd /opt/gify
TAG=<commit sha> sh deploy.sh
```

## 生产部署（云服务器）

生产与测试用同一套镜像与入口形态，差异只在发版方式：生产手动指定版本，升级前备份。云服务器可访问 ACR 拉取镜像；地域选大陆需域名 ICP 备案（见测试环境一节的教训），海外地域（如香港）无此要求。

### 初装

1. 安装 Docker，创建部署目录（如 `/opt/gify`），放入 `docker-compose.yml`、`deploy.sh`、`upgrade.sh` 三个文件。
2. 执行一次 `docker login <ACR 地址>`，凭据会写入 `~/.docker/config.json`。
3. 写 `.env`，项与测试环境相同，地址换生产实际值；前端与 API 若在同一注册域，`COOKIE_SAMESITE` 用 `lax` 即可。
4. `TAG=<版本号，如 v0.3.0> sh deploy.sh`。

完成后浏览器打开 `http://<主机>:${FRONTEND_PORT}`，用初始管理员账号登录，首次登录强制改密。

### 升级

```bash
TAG=<版本号，如 v0.3.1> sh upgrade.sh
```

upgrade.sh 先做备份确认（pg_dump），确认后执行与 deploy.sh 相同的拉取、迁移、重启。

`POSTGRES_PASSWORD` 只在数据卷首次初始化时生效。库已建立后修改口令，需要进容器执行 `ALTER USER`（容器内 socket 连接不需要密码）：

```bash
docker compose exec -T postgres psql -U gify \
  -c "ALTER USER gify WITH PASSWORD '新口令';"
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

本地起后端、前端开发服务时，postgres 与 redis 由 compose 启动并映射到 `127.0.0.1`（端口取 `.env` 的 `POSTGRES_PORT`、`REDIS_PORT`，默认 5432、6379）。后端配置从组件拼装连接串：本机默认连 `localhost`，app 容器内由 compose `environment` 覆盖主机名与端口指向服务地址。前端开发服务（5173）走 Vite 代理转发 `/api`，无需注入 `VITE_API_BASE_URL`。
