#!/usr/bin/env bash
# CentOS：初始化 /opt/stock_quote 目录、用户 stockquote、共享 venv。
# 用法：sudo bash bootstrap_centos.sh [DEPLOY_ROOT]
set -euo pipefail

DEPLOY_ROOT="${1:-/opt/stock_quote}"
APP_USER="${APP_USER:-stockquote}"
PYTHON_BIN="${PYTHON_BIN:-}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 运行：sudo bash $0" >&2
  exit 1
fi

detect_python() {
  if [[ -n "$PYTHON_BIN" && -x "$PYTHON_BIN" ]]; then
    echo "$PYTHON_BIN"
    return
  fi
  for c in python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1; then
      local ver
      ver="$("$c" -c 'import sys; print("%d.%d"%sys.version_info[:2])')"
      # 至少 3.8
      if "$c" -c 'import sys; raise SystemExit(0 if sys.version_info>=(3,8) else 1)'; then
        echo "$c"
        return
      fi
    fi
  done
  echo "" 
}

PY="$(detect_python)"
if [[ -z "$PY" ]]; then
  echo "未找到 Python>=3.8。请安装 Python 3.10+ 后重试（可设 PYTHON_BIN=/path/to/python）。" >&2
  exit 1
fi
echo "[bootstrap] 使用 Python: $PY ($("$PY" --version 2>&1))"

if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd -r -m -d "$DEPLOY_ROOT" -s /sbin/nologin "$APP_USER" || \
    useradd -r -m -d "$DEPLOY_ROOT" -s /usr/sbin/nologin "$APP_USER"
  echo "[bootstrap] 已创建用户 $APP_USER"
else
  echo "[bootstrap] 用户 $APP_USER 已存在"
fi

mkdir -p \
  "$DEPLOY_ROOT/releases" \
  "$DEPLOY_ROOT/shared/logs" \
  "$DEPLOY_ROOT/shared/backups" \
  "$DEPLOY_ROOT/shared/ssl" \
  "$DEPLOY_ROOT/shared/reports"

if [[ ! -f "$DEPLOY_ROOT/shared/.env" ]]; then
  EXAMPLE=""
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [[ -f "$SCRIPT_DIR/.env.centos.example" ]]; then
    EXAMPLE="$SCRIPT_DIR/.env.centos.example"
  elif [[ -f "$DEPLOY_ROOT/current/scripts/deploy/linux/.env.centos.example" ]]; then
    EXAMPLE="$DEPLOY_ROOT/current/scripts/deploy/linux/.env.centos.example"
  fi
  if [[ -n "$EXAMPLE" ]]; then
    cp "$EXAMPLE" "$DEPLOY_ROOT/shared/.env"
    echo "[bootstrap] 已写入 $DEPLOY_ROOT/shared/.env（请立即填写密钥）"
  else
    touch "$DEPLOY_ROOT/shared/.env"
    echo "[bootstrap] 已创建空 $DEPLOY_ROOT/shared/.env"
  fi
  chmod 640 "$DEPLOY_ROOT/shared/.env"
fi

if [[ ! -d "$DEPLOY_ROOT/.venv" ]]; then
  echo "[bootstrap] 创建 venv: $DEPLOY_ROOT/.venv"
  "$PY" -m venv "$DEPLOY_ROOT/.venv"
fi

chown -R "$APP_USER:$APP_USER" "$DEPLOY_ROOT"
# venv 内 pip 需要可写
sudo -u "$APP_USER" "$DEPLOY_ROOT/.venv/bin/pip" install -U pip setuptools wheel

echo "[bootstrap] 完成。"
echo "  下一步："
echo "  1) 编辑 $DEPLOY_ROOT/shared/.env"
echo "  2) 解压首个发布包到 $DEPLOY_ROOT/releases/ 并 ln -sfn 为 current"
echo "  3) sudo -u $APP_USER $DEPLOY_ROOT/.venv/bin/pip install -r $DEPLOY_ROOT/current/requirements-prod.txt"
echo "  4) sudo bash $(dirname "$0")/install_units.sh"
echo "  5) 安装 Nginx 站点：docs/prod/nginx.centos.conf → /etc/nginx/conf.d/stock_quote.conf"
