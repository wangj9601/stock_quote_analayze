#!/usr/bin/env bash
# Ubuntu：安装 systemd 五服务，并把 API / 用户站限制在 127.0.0.1。
# 用法：sudo bash install_units_ubuntu.sh [DEPLOY_ROOT]
set -euo pipefail

DEPLOY_ROOT="${1:-/opt/stock_quote}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DROPIN_SRC="$SCRIPT_DIR/systemd/ubuntu/bind-localhost.conf"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 运行：sudo bash $0" >&2
  exit 1
fi

if [[ ! -f "$DROPIN_SRC" ]]; then
  echo "缺少 $DROPIN_SRC" >&2
  exit 1
fi

bash "$SCRIPT_DIR/install_units.sh" "$DEPLOY_ROOT"

for unit in stock-quote-api stock-quote-frontend; do
  dest_dir="/etc/systemd/system/${unit}.service.d"
  install -d -m 755 "$dest_dir"
  install -m 644 "$DROPIN_SRC" "$dest_dir/bind-localhost.conf"
  echo "[install_units_ubuntu] ${unit} 仅监听 BIND_HOST=127.0.0.1"
done

systemctl daemon-reload
echo "[install_units_ubuntu] 完成。管理端单元本身已 --bind 127.0.0.1。"
echo "  sudo systemctl enable --now stock-quote-api stock-quote-core stock-quote-notify stock-quote-frontend stock-quote-admin"
echo "DeployRoot 约定: $DEPLOY_ROOT （unit 内路径已写死为 /opt/stock_quote，如更改请同步改 unit）"
