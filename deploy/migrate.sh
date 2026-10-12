#!/usr/bin/env sh
# 数据迁移：在 app 镜像内执行 Alembic 升级到最新版本（FR-02 功能要求 3）
set -eu
cd "$(dirname "$0")"
docker compose run --rm app uv run alembic upgrade head
