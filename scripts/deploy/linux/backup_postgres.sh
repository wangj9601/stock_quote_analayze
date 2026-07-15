#!/usr/bin/env bash
# CentOS：PostgreSQL 自定义格式全库备份到 shared/backups，并按天数清理。
# 用法：
#   bash backup_postgres.sh
#   RETAIN_DAYS=14 bash backup_postgres.sh
#   DEPLOY_ROOT=/opt/stock_quote bash backup_postgres.sh
#
# 连接优先级：DATABASE_URL（.env）> PG* 环境变量 > 默认本机 stock_analysis
set -euo pipefail

DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/stock_quote}"
ENV_FILE="${ENV_FILE:-$DEPLOY_ROOT/shared/.env}"
BACKUP_DIR="${BACKUP_DIR:-$DEPLOY_ROOT/shared/backups}"
RETAIN_DAYS="${RETAIN_DAYS:-14}"
DB_NAME_DEFAULT="stock_analysis"

mkdir -p "$BACKUP_DIR"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  # 只导入 KEY=VALUE 行，忽略注释
  # shellcheck disable=SC1091
  source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENV_FILE" | sed 's/\r$//') || true
  set +a
fi

parse_database_url() {
  # postgresql+psycopg2://user:pass@host:port/db 或 postgresql://...
  local url="${DATABASE_URL:-}"
  [[ -z "$url" ]] && return 1
  url="${url#postgresql+psycopg2://}"
  url="${url#postgresql://}"
  # user:pass@host:port/db
  local cred hostpart
  cred="${url%%@*}"
  hostpart="${url#*@}"
  export PGUSER="${cred%%:*}"
  export PGPASSWORD="${cred#*:}"
  local hostport db
  hostport="${hostpart%%/*}"
  db="${hostpart#*/}"
  db="${db%%\?*}"
  export PGHOST="${hostport%%:*}"
  if [[ "$hostport" == *:* ]]; then
    export PGPORT="${hostport##*:}"
  else
    export PGPORT=5432
  fi
  export PGDATABASE="$db"
}

if [[ -n "${DATABASE_URL:-}" ]]; then
  parse_database_url || true
fi

export PGHOST="${PGHOST:-${DB_HOST:-127.0.0.1}}"
export PGPORT="${PGPORT:-${DB_PORT:-5432}}"
export PGUSER="${PGUSER:-${DB_USER:-postgres}}"
export PGDATABASE="${PGDATABASE:-${DB_NAME:-$DB_NAME_DEFAULT}}"
if [[ -n "${DB_PASSWORD:-}" && -z "${PGPASSWORD:-}" ]]; then
  export PGPASSWORD="$DB_PASSWORD"
fi

TS="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/${PGDATABASE}_${TS}.dump"

echo "[backup] $PGUSER@$PGHOST:$PGPORT/$PGDATABASE → $OUT"
if ! command -v pg_dump >/dev/null 2>&1; then
  echo "未找到 pg_dump，请安装 PostgreSQL 客户端工具" >&2
  exit 1
fi

pg_dump -Fc -f "$OUT" "$PGDATABASE"
echo "[backup] 完成 $(du -h "$OUT" | awk '{print $1}')"

# 清理
find "$BACKUP_DIR" -type f -name '*.dump' -mtime +"$RETAIN_DAYS" -print -delete || true
echo "[backup] 已清理 ${RETAIN_DAYS} 天前的 .dump"
