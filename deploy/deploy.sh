#!/usr/bin/env sh
# 测试环境部署：拉取镜像 → 迁移 → 重启。无备份确认（测试数据可弃），
# 生产（内网）升级用 upgrade.sh。TAG 由 CI 传入（git sha），缺省 latest。

set -eu
cd "$(dirname "$0")"

set -a
. ./.env
set +a

export TAG="${TAG:-latest}"
echo "$ACR_PASSWORD" | docker login "$ACR_REGISTRY" -u "$ACR_USERNAME" --password-stdin

docker compose pull app frontend
docker compose run --rm app uv run alembic upgrade head
docker compose up -d --no-build
