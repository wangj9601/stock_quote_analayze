#!/usr/bin/env bash
# CentOS：发布 zip 到 /opt/stock_quote，切换 current，重启服务，健康检查失败则回滚 symlink。
# 用法：sudo bash release.sh /path/to/stock_quote_release_xxx.zip [DEPLOY_ROOT]
set -euo pipefail

PACKAGE_PATH="${1:-}"
DEPLOY_ROOT="${2:-/opt/stock_quote}"
APP_USER="${APP_USER:-stockquote}"
VENV_PIP="$DEPLOY_ROOT/.venv/bin/pip"
VENV_PY="$DEPLOY_ROOT/.venv/bin/python"
SERVICES=(stock-quote-api stock-quote-core stock-quote-notify stock-quote-frontend stock-quote-admin)
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1/health}"
API_PROBE_URL="${API_PROBE_URL:-http://127.0.0.1:5000/api/admin/auth/verify}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 运行：sudo bash $0 <package.zip>" >&2
  exit 1
fi

if [[ -z "$PACKAGE_PATH" || ! -f "$PACKAGE_PATH" ]]; then
  echo "用法: sudo bash $0 /path/to/stock_quote_release_xxx.zip [DEPLOY_ROOT]" >&2
  exit 1
fi

if [[ ! -x "$VENV_PY" ]]; then
  echo "缺少 venv：$VENV_PY ，请先运行 bootstrap_centos.sh" >&2
  exit 1
fi

TS="$(date +%Y%m%d_%H%M%S)"
BASE_NAME="$(basename "$PACKAGE_PATH")"
BASE_NAME="${BASE_NAME%.zip}"
RELEASE_DIR="$DEPLOY_ROOT/releases/${BASE_NAME}_${TS}"
PREV_TARGET=""
if [[ -L "$DEPLOY_ROOT/current" ]]; then
  PREV_TARGET="$(readlink -f "$DEPLOY_ROOT/current" || true)"
elif [[ -d "$DEPLOY_ROOT/current" ]]; then
  PREV_TARGET="$DEPLOY_ROOT/current"
fi

echo "[release] 解压 → $RELEASE_DIR"
mkdir -p "$RELEASE_DIR"
unzip -q "$PACKAGE_PATH" -d "$RELEASE_DIR"

# 若 zip 顶层只有一个目录，则使用该目录作为真正 release root
shopt -s nullglob
TOP_ENTRIES=("$RELEASE_DIR"/*)
if [[ ${#TOP_ENTRIES[@]} -eq 1 && -d "${TOP_ENTRIES[0]}" ]]; then
  INNER="${TOP_ENTRIES[0]}"
  # 若内层像是完整项目（含 start_backend_api.py），把 current 指到内层
  if [[ -f "$INNER/start_backend_api.py" || -f "$INNER/requirements-prod.txt" ]]; then
    RELEASE_DIR="$INNER"
  fi
fi

if [[ ! -f "$RELEASE_DIR/start_backend_api.py" && ! -f "$RELEASE_DIR/requirements-prod.txt" ]]; then
  echo "[release] 警告：未在 $RELEASE_DIR 找到 start_backend_api.py / requirements-prod.txt，请检查 zip 结构" >&2
fi

chown -R "$APP_USER:$APP_USER" "$(dirname "$RELEASE_DIR")" "$RELEASE_DIR" 2>/dev/null || \
  chown -R "$APP_USER:$APP_USER" "$DEPLOY_ROOT/releases"

REQ="$RELEASE_DIR/requirements-prod.txt"
if [[ -f "$REQ" ]]; then
  echo "[release] pip install -r requirements-prod.txt"
  sudo -u "$APP_USER" "$VENV_PIP" install -r "$REQ"
fi

echo "[release] 切换 current → $RELEASE_DIR"
ln -sfn "$RELEASE_DIR" "$DEPLOY_ROOT/current"
chown -h "$APP_USER:$APP_USER" "$DEPLOY_ROOT/current" || true

restart_all() {
  for s in "${SERVICES[@]}"; do
    if systemctl list-unit-files "${s}.service" >/dev/null 2>&1; then
      systemctl restart "$s" || true
    fi
  done
}

echo "[release] 重启服务"
restart_all

if command -v nginx >/dev/null 2>&1; then
  if nginx -t 2>/dev/null; then
    systemctl reload nginx || true
  else
    echo "[release] nginx -t 失败，跳过 reload" >&2
  fi
fi

sleep 3
ok=1
if command -v curl >/dev/null 2>&1; then
  if curl -fsS --max-time 10 "$HEALTH_URL" >/dev/null 2>&1; then
    echo "[release] OK health: $HEALTH_URL"
  else
    # 无 nginx 时直接探 upstream
    if curl -fsS --max-time 5 "http://127.0.0.1:8000/" >/dev/null 2>&1; then
      echo "[release] OK frontend :8000（无 /health，请稍后配 Nginx）"
    else
      echo "[release] 健康检查失败: $HEALTH_URL" >&2
      ok=0
    fi
  fi
  # API 端口探测（未必 200，连接成功即可）
  if curl -sS --max-time 5 -o /dev/null -w "%{http_code}" "http://127.0.0.1:5000/" | grep -qE '^[0-9]+$'; then
    echo "[release] OK api port 5000 有响应"
  else
    echo "[release] 警告：5000 无响应" >&2
    ok=0
  fi
fi

if [[ "$ok" -ne 1 ]]; then
  if [[ -n "$PREV_TARGET" && -d "$PREV_TARGET" ]]; then
    echo "[release] 回滚 current → $PREV_TARGET" >&2
    ln -sfn "$PREV_TARGET" "$DEPLOY_ROOT/current"
    chown -h "$APP_USER:$APP_USER" "$DEPLOY_ROOT/current" || true
    restart_all
  fi
  exit 1
fi

echo "[release] 完成: $DEPLOY_ROOT/current -> $(readlink -f "$DEPLOY_ROOT/current")"
