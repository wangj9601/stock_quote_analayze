#!/usr/bin/env bash
# CentOS：安装/更新 systemd 五服务单元。
# 用法：sudo bash install_units.sh [DEPLOY_ROOT]
set -euo pipefail

DEPLOY_ROOT="${1:-/opt/stock_quote}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_SRC="$SCRIPT_DIR/systemd"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 运行：sudo bash $0" >&2
  exit 1
fi

if [[ ! -d "$UNIT_SRC" ]]; then
  echo "找不到单元目录: $UNIT_SRC" >&2
  exit 1
fi

for f in stock-quote-api stock-quote-core stock-quote-notify stock-quote-frontend stock-quote-admin; do
  src="$UNIT_SRC/${f}.service"
  if [[ ! -f "$src" ]]; then
    echo "缺少 $src" >&2
    exit 1
  fi
  install -m 644 "$src" "/etc/systemd/system/${f}.service"
  echo "[install_units] 已安装 ${f}.service"
done

systemctl daemon-reload
echo "[install_units] daemon-reload 完成。启用示例："
echo "  sudo systemctl enable --now stock-quote-api stock-quote-core stock-quote-notify stock-quote-frontend stock-quote-admin"
echo "DeployRoot 约定: $DEPLOY_ROOT （unit 内路径已写死为 /opt/stock_quote，如更改请同步改 unit）"
