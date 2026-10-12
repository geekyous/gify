#!/usr/bin/env sh
# 升级流程（FR-02 功能要求 3）：备份提示 → 构建镜像 → 数据迁移 → 重启
set -eu
cd "$(dirname "$0")"

echo "==> 升级前请先备份数据库与 volumes："
echo "    docker compose exec postgres pg_dump -U \${POSTGRES_USER:-gify} \${POSTGRES_DB:-gify} > backup-\$(date +%F).sql"
echo "    volumes: pg_data / redis_data（参见 README 备份一节）"
printf "已备份，继续升级？[y/N] "
read answer
[ "$answer" = "y" ] || [ "$answer" = "Y" ] || exit 1

docker compose build
sh migrate.sh
docker compose up -d
echo "==> 升级完成：docker compose ps 确认各容器状态"
