#!/usr/bin/env bash
# Ubuntu：为本机应用准备 PostgreSQL。只通过 127.0.0.1 密码登录，不改成对外监听。
# 用法：sudo DB_PASSWORD='强密码' bash init_postgres_ubuntu.sh
# 可选：DB_NAME（默认 stock_analysis）、DB_USER（默认 postgres）
set -euo pipefail

DB_NAME="${DB_NAME:-stock_analysis}"
DB_USER="${DB_USER:-postgres}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 运行：sudo DB_PASSWORD='...' bash $0" >&2
  exit 1
fi

if [[ -z "${DB_PASSWORD:-}" ]]; then
  echo "请设置 DB_PASSWORD，例如：sudo DB_PASSWORD='强密码' bash $0" >&2
  exit 1
fi

if [[ "$DB_PASSWORD" == *$'\n'* ]]; then
  echo "DB_PASSWORD 不能包含换行" >&2
  exit 1
fi

if [[ ! "$DB_NAME" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo "DB_NAME 只能包含字母、数字、下划线" >&2
  exit 1
fi

if [[ ! "$DB_USER" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo "DB_USER 只能包含字母、数字、下划线" >&2
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "未找到 psql。请先运行 bootstrap_ubuntu.sh" >&2
  exit 1
fi

systemctl enable --now postgresql

sudo -u postgres psql -v ON_ERROR_STOP=1 \
  -v dbuser="$DB_USER" \
  -v dbpass="$DB_PASSWORD" <<'SQL'
ALTER USER :"dbuser" WITH PASSWORD :'dbpass';
SQL
echo "[postgres] 已设置用户 ${DB_USER} 的密码"

exists="$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | tr -d '[:space:]')"
if [[ "$exists" != "1" ]]; then
  sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
  echo "[postgres] 已创建数据库 $DB_NAME"
else
  echo "[postgres] 数据库 $DB_NAME 已存在"
fi

HBA="$(sudo -u postgres psql -tAc 'SHOW hba_file' | tr -d '[:space:]')"
if [[ ! -f "$HBA" ]]; then
  echo "找不到 pg_hba.conf: ${HBA:-<空>}" >&2
  exit 1
fi

if grep -Eq '^[[:space:]]*host[[:space:]]+all[[:space:]]+all[[:space:]]+127\.0\.0\.1/32[[:space:]]+(scram-sha-256|md5)([[:space:]]|$)' "$HBA"; then
  echo "[postgres] pg_hba 已允许 127.0.0.1 密码登录 ($HBA)"
else
  printf '\n# stock_quote: 仅本机 TCP 密码登录\nhost all all 127.0.0.1/32 scram-sha-256\n' >> "$HBA"
  systemctl reload postgresql
  echo "[postgres] 已向 $HBA 追加 127.0.0.1/32 scram-sha-256"
fi

LISTEN="$(sudo -u postgres psql -tAc 'SHOW listen_addresses' | tr -d '[:space:]')"
case "$LISTEN" in
  localhost|127.0.0.1|localhost,127.0.0.1)
    echo "[postgres] listen_addresses=$LISTEN"
    ;;
  *)
    echo "[postgres] 警告: listen_addresses=$LISTEN 。公网机器应保持 localhost，不要对 0.0.0.0 开放 5432。" >&2
    ;;
esac

echo "[postgres] 完成。请把同一密码写入 /opt/stock_quote/shared/.env 的 DATABASE_URL。"
