#!/usr/bin/env bash
# CentOS 与 Ubuntu 共用：发布 zip 到 /opt/stock_quote，切换 current，重启服务，健康检查失败则回滚 symlink。
# 用法：
#   sudo bash release.sh /path/to/stock_quote_release_xxx.zip [DEPLOY_ROOT]
#   sudo bash release.sh                 # 自动取 /tmp 下最新 stock_quote_release_*.zip
#   sudo bash release.sh /tmp            # 在指定目录取最新同名包
# 首次发布、服务尚未启动时：sudo SKIP_HEALTH=1 bash release.sh
set -euo pipefail

PACKAGE_HINT="${1:-}"
DEPLOY_ROOT="${2:-/opt/stock_quote}"
APP_USER="${APP_USER:-stockquote}"
VENV_PIP="$DEPLOY_ROOT/.venv/bin/pip"
VENV_PY="$DEPLOY_ROOT/.venv/bin/python"
SERVICES=(stock-quote-api stock-quote-core stock-quote-notify stock-quote-frontend stock-quote-admin)
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1/health}"
API_PROBE_URL="${API_PROBE_URL:-http://127.0.0.1:5000/api/admin/auth/verify}"
PACKAGE_GLOB="${PACKAGE_GLOB:-stock_quote_release_*.zip}"

# 未传 zip、或传入目录时：按修改时间取最新匹配包（默认搜 /tmp）
resolve_package_path() {
  local hint="${1:-}"
  local dir=""
  if [[ -z "$hint" ]]; then
    dir="/tmp"
  elif [[ -f "$hint" ]]; then
    printf '%s\n' "$hint"
    return 0
  elif [[ -d "$hint" ]]; then
    dir="${hint%/}"
  else
    echo "找不到包或目录: $hint" >&2
    return 1
  fi

  shopt -s nullglob
  local files=("$dir"/$PACKAGE_GLOB)
  shopt -u nullglob
  if [[ ${#files[@]} -eq 0 ]]; then
    echo "在 $dir 未找到 $PACKAGE_GLOB" >&2
    return 1
  fi
  # ls -t：最新修改时间在前
  ls -1t "${files[@]}" | head -n1
}

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 运行：sudo bash $0 [package.zip|/tmp]" >&2
  exit 1
fi

PACKAGE_PATH="$(resolve_package_path "$PACKAGE_HINT")" || {
  echo "用法: sudo bash $0 [/path/to/stock_quote_release_xxx.zip|/tmp] [DEPLOY_ROOT]" >&2
  echo "      省略参数时自动使用 /tmp 下最新的 $PACKAGE_GLOB" >&2
  exit 1
}
PACKAGE_PATH="$(readlink -f "$PACKAGE_PATH" 2>/dev/null || realpath "$PACKAGE_PATH" 2>/dev/null || echo "$PACKAGE_PATH")"
if [[ ! -f "$PACKAGE_PATH" ]]; then
  echo "包文件不存在: $PACKAGE_PATH" >&2
  exit 1
fi
echo "[release] 使用包: $PACKAGE_PATH"

if [[ ! -x "$VENV_PY" ]]; then
  echo "缺少 venv：$VENV_PY ，请先运行 bootstrap_centos.sh 或 bootstrap_ubuntu.sh" >&2
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
# Windows Compress-Archive 打的 zip 常带反斜杠路径；Info-ZIP 会告警并以 exit 1 结束。
# set -e 下必须忽略「仅警告」的 1，否则解压成功也不会切 current。
set +e
unzip -q "$PACKAGE_PATH" -d "$RELEASE_DIR"
unzip_rc=$?
set -e
if [[ "$unzip_rc" -gt 1 ]]; then
  echo "[release] unzip 失败 exit=$unzip_rc" >&2
  exit "$unzip_rc"
fi
if [[ "$unzip_rc" -eq 1 ]]; then
  echo "[release] unzip 有警告（多为 Windows 反斜杠路径），已解压，继续"
fi

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
mkdir -p "$DEPLOY_ROOT/shared/logs" "$RELEASE_DIR/logs"
chown -R "$APP_USER:$APP_USER" "$DEPLOY_ROOT/shared/logs" "$RELEASE_DIR/logs"

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

ok=1
# API 冷启动（大量路由导入）常超过 3s；默认最多等 60s，可用 API_READY_TIMEOUT 覆盖
API_READY_TIMEOUT="${API_READY_TIMEOUT:-60}"
wait_api_port() {
  local i code
  for ((i = 1; i <= API_READY_TIMEOUT; i++)); do
    code="$(curl -sS --max-time 2 -o /dev/null -w "%{http_code}" "http://127.0.0.1:5000/" 2>/dev/null || true)"
    if [[ "$code" =~ ^[0-9]+$ ]]; then
      echo "[release] OK api port 5000 有响应 (http_code=$code, waited ${i}s)"
      return 0
    fi
    sleep 1
  done
  echo "[release] 警告：${API_READY_TIMEOUT}s 内 5000 无响应" >&2
  return 1
}

if [[ "${SKIP_HEALTH:-}" == "1" ]]; then
  echo "[release] SKIP_HEALTH=1，跳过健康检查"
elif command -v curl >/dev/null 2>&1; then
  sleep 3
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
  # API 端口探测（未必 200，能连上拿到状态码即可）
  if ! wait_api_port; then
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
