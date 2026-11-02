#!/usr/bin/env bash
# Ubuntu 26.04（阿里云 ECS）：目录、用户、venv。已安装的 Python 3.12/3.13 与 Nginx 直接沿用。
# 不启用 firewalld，也不默认打开 ufw。公网端口由阿里云安全组控制。
# 用法：sudo bash bootstrap_ubuntu.sh [DEPLOY_ROOT]
#
# 可选环境变量：
#   PYTHON_BIN=/usr/bin/python3.12
#   ALLOW_UNTESTED_PYTHON=1     允许 PYTHON_BIN 不是 3.12/3.13（自行承担依赖装不上的风险）
#   TIMEZONE=Asia/Shanghai      设为空字符串则不改时区
#   PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/   设为空字符串则不写 pip 镜像
#   ENABLE_UFW=1                额外启用本机 ufw，只放行 OpenSSH、80、443
#   CONFIGURE_NGINX=1           已有 Nginx 时也删除默认站并重启（默认只在本次新装 Nginx 时做）
set -euo pipefail

DEPLOY_ROOT="${1:-/opt/stock_quote}"
APP_USER="${APP_USER:-stockquote}"
PYTHON_BIN="${PYTHON_BIN:-}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root 运行：sudo bash $0" >&2
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then
  echo "无法读取 /etc/os-release" >&2
  exit 1
fi

OS_ID="$(. /etc/os-release && printf '%s' "${ID:-}")"
OS_VER="$(. /etc/os-release && printf '%s' "${VERSION_ID:-}")"
echo "[bootstrap] 系统: ${OS_ID} ${OS_VER}"
if [[ "$OS_ID" != "ubuntu" ]]; then
  echo "[bootstrap] 这不是 Ubuntu。CentOS 请用 bootstrap_centos.sh。" >&2
  exit 1
fi
if [[ "$OS_VER" != "26.04" ]]; then
  echo "[bootstrap] 警告：本脚本按 Ubuntu 26.04 编写，当前是 ${OS_VER}。" >&2
fi

export DEBIAN_FRONTEND=noninteractive

if command -v python3 >/dev/null 2>&1; then
  python3_ver="$(python3 --version 2>&1)"
  echo "[bootstrap] 已有 python3: $(command -v python3) ($python3_ver)"
fi
if command -v python3.12 >/dev/null 2>&1; then
  echo "[bootstrap] 已有 python3.12: $(command -v python3.12) ($(python3.12 --version 2>&1))"
fi
if command -v python3.13 >/dev/null 2>&1; then
  echo "[bootstrap] 已有 python3.13: $(command -v python3.13) ($(python3.13 --version 2>&1))"
fi

NGINX_INSTALLED=0
if command -v nginx >/dev/null 2>&1; then
  NGINX_INSTALLED=1
  echo "[bootstrap] 已有 Nginx: $(command -v nginx) ($(nginx -v 2>&1))，跳过安装，不重启"
fi

apt-get update
BASE_PACKAGES=(
  ca-certificates
  curl
  unzip
  gnupg
  build-essential
  libpq-dev
  libssl-dev
)
if ! command -v psql >/dev/null 2>&1; then
  BASE_PACKAGES+=(postgresql postgresql-contrib)
else
  echo "[bootstrap] 已有 PostgreSQL 客户端: $(psql --version)"
fi
if [[ "$NGINX_INSTALLED" -eq 0 ]]; then
  BASE_PACKAGES+=(nginx)
fi
apt-get install -y "${BASE_PACKAGES[@]}"

python_series_ok() {
  "$1" -c 'import sys; raise SystemExit(0 if (3, 12) <= sys.version_info[:2] <= (3, 13) else 1)'
}

venv_ready() {
  "$1" -c 'import venv, ensurepip' >/dev/null 2>&1
}

if [[ -n "$PYTHON_BIN" ]]; then
  PY="$PYTHON_BIN"
elif command -v python3.12 >/dev/null 2>&1 && python_series_ok python3.12; then
  PY="$(command -v python3.12)"
elif command -v python3.13 >/dev/null 2>&1 && python_series_ok python3.13; then
  PY="$(command -v python3.13)"
elif command -v python3 >/dev/null 2>&1 && python_series_ok python3; then
  PY="$(command -v python3)"
else
  PY=""
fi

if [[ -z "$PY" ]]; then
  echo "[bootstrap] 未找到可用的 Python 3.12/3.13。系统 python3 在 Ubuntu 26.04 上通常是 3.14，不能用来装 psycopg2-binary==2.9.10。"
  echo "[bootstrap] 额外安装 Python 3.12（deadsnakes），不替换 /usr/bin/python3。"
  apt-get install -y software-properties-common
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get update
  apt-get install -y python3.12 python3.12-venv python3.12-dev
  PY="$(command -v python3.12)"
fi

if ! python_series_ok "$PY"; then
  if [[ "${ALLOW_UNTESTED_PYTHON:-}" == "1" ]]; then
    echo "[bootstrap] 警告：ALLOW_UNTESTED_PYTHON=1，使用 $PY（$("$PY" --version 2>&1)）" >&2
  else
    echo "[bootstrap] 拒绝 $PY（$("$PY" --version 2>&1)）。只接受 3.12 或 3.13。不要用系统 python3。" >&2
    exit 1
  fi
fi
echo "[bootstrap] 使用已有或选定的 Python: $PY ($("$PY" --version 2>&1))"
if ! venv_ready "$PY"; then
  py_mm="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  echo "[bootstrap] $PY 缺少 venv，补装 python${py_mm}-venv / python${py_mm}-dev"
  apt-get install -y "python${py_mm}-venv" "python${py_mm}-dev"
fi

if [[ -z "${TIMEZONE+x}" ]]; then
  TIMEZONE="Asia/Shanghai"
fi
if [[ -n "$TIMEZONE" ]]; then
  timedatectl set-timezone "$TIMEZONE"
  echo "[bootstrap] 时区: $(timedatectl show -p Timezone --value)"
fi

if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd -r -m -d "$DEPLOY_ROOT" -s /usr/sbin/nologin "$APP_USER"
  echo "[bootstrap] 已创建用户 $APP_USER"
else
  echo "[bootstrap] 用户 $APP_USER 已存在"
fi

mkdir -p \
  "$DEPLOY_ROOT/releases" \
  "$DEPLOY_ROOT/shared/logs" \
  "$DEPLOY_ROOT/shared/backups" \
  "$DEPLOY_ROOT/shared/reports" \
  /etc/nginx/ssl
chmod 755 /etc/nginx/ssl

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f "$DEPLOY_ROOT/shared/.env" ]]; then
  EXAMPLE=""
  if [[ -f "$SCRIPT_DIR/.env.ubuntu.example" ]]; then
    EXAMPLE="$SCRIPT_DIR/.env.ubuntu.example"
  elif [[ -f "$DEPLOY_ROOT/current/scripts/deploy/linux/.env.ubuntu.example" ]]; then
    EXAMPLE="$DEPLOY_ROOT/current/scripts/deploy/linux/.env.ubuntu.example"
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

# 机器上已经在跑 Nginx 时，不删默认站、不重启。站点放到第 5 步复制 nginx.ubuntu.conf 之后再 reload。
if [[ "$NGINX_INSTALLED" -eq 0 || "${CONFIGURE_NGINX:-}" == "1" ]]; then
  if [[ -e /etc/nginx/sites-enabled/default ]]; then
    rm -f /etc/nginx/sites-enabled/default
    echo "[bootstrap] 已移除 /etc/nginx/sites-enabled/default，避免默认站抢占 80"
  fi
  systemctl enable nginx
  if nginx -t; then
    systemctl restart nginx
  else
    echo "[bootstrap] nginx -t 失败，请先处理配置后再启动" >&2
    exit 1
  fi
else
  echo "[bootstrap] 保留现有 Nginx 配置。确认默认站不占用 80 后，再安装 nginx.ubuntu.conf 并 nginx -t && systemctl reload nginx"
fi

if [[ -z "${PIP_INDEX_URL+x}" ]]; then
  PIP_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/"
fi
if [[ -n "$PIP_INDEX_URL" ]]; then
  pip_host="${PIP_INDEX_URL#*://}"
  pip_host="${pip_host%%/*}"
  install -d -m 755 "$DEPLOY_ROOT/.config/pip"
  cat > "$DEPLOY_ROOT/.config/pip/pip.conf" <<EOF
[global]
index-url = ${PIP_INDEX_URL}
trusted-host = ${pip_host}
EOF
  echo "[bootstrap] pip 镜像: $PIP_INDEX_URL"
fi

if [[ -x "$DEPLOY_ROOT/.venv/bin/python" ]] && ! python_series_ok "$DEPLOY_ROOT/.venv/bin/python"; then
  if [[ "${ALLOW_UNTESTED_PYTHON:-}" != "1" ]]; then
    echo "[bootstrap] 现有 venv 是 $("$DEPLOY_ROOT/.venv/bin/python" --version 2>&1)，不是 3.12/3.13。删除 $DEPLOY_ROOT/.venv 后重跑。" >&2
    exit 1
  fi
fi

if [[ ! -d "$DEPLOY_ROOT/.venv" ]]; then
  echo "[bootstrap] 创建 venv: $DEPLOY_ROOT/.venv"
  "$PY" -m venv "$DEPLOY_ROOT/.venv"
fi

chown -R "$APP_USER:$APP_USER" "$DEPLOY_ROOT"
sudo -u "$APP_USER" "$DEPLOY_ROOT/.venv/bin/pip" install -U pip setuptools wheel

if [[ "${ENABLE_UFW:-}" == "1" ]]; then
  apt-get install -y ufw
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable
  echo "[bootstrap] ufw 已启用：OpenSSH、80、443。请确认当前 SSH 会话仍可用。"
else
  echo "[bootstrap] 未改主机防火墙。公网只靠阿里云安全组（入方向仅 22/80/443）。"
  echo "  若还要本机防火墙：sudo ENABLE_UFW=1 bash $0"
fi

echo "[bootstrap] 完成。"
echo "  下一步："
echo "  1) sudo DB_PASSWORD='强密码' bash ${SCRIPT_DIR}/init_postgres_ubuntu.sh"
echo "  2) 编辑 $DEPLOY_ROOT/shared/.env （DATABASE_URL 与上面的密码一致，BIND_HOST=127.0.0.1）"
echo "  3) 首次发布：sudo SKIP_HEALTH=1 bash ${SCRIPT_DIR}/release.sh /path/to/stock_quote_release_xxx.zip"
echo "  4) sudo bash ${SCRIPT_DIR}/install_units_ubuntu.sh"
echo "  5) 证书放到 /etc/nginx/ssl/ ，站点配置：${SCRIPT_DIR}/nginx.ubuntu.conf → /etc/nginx/conf.d/stock_quote.conf"
echo "  手册：docs/prod/ubuntu-aliyun-runbook.md"
