#!/usr/bin/env sh
# 生产升级：备份确认后执行 deploy.sh（拉取镜像、迁移、重启）。
# TAG 指定版本（git sha），缺省 latest。
set -eu
cd "$(dirname "$0")"

echo "升级前请先备份数据库（见 README 备份与恢复一节）。"
printf "已备份，继续升级？[y/N] "
read answer
[ "$answer" = "y" ] || [ "$answer" = "Y" ] || exit 1

sh deploy.sh