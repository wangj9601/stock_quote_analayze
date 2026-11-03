#!/usr/bin/env bash
# Ubuntu：为 www.xworld-wangxw.top、apex 与 admin 子域申请 Let's Encrypt 证书并启用自动续期。
# 用法：
#   sudo bash setup_letsencrypt_ubuntu.sh
#   sudo EMAIL=you@example.com bash setup_letsencrypt_ubuntu.sh
# 前提：DNS A/AAAA 已指向本机；安全组放行 80；Nginx 已加载本仓库的 80 端口
#       ACME location（webroot=/usr/share/nginx/html）。不要用 certbot --nginx 改写整站。
set -euo pipefail

EMAIL="${EMAIL:-}"
DOMAINS=(www.xworld-wangxw.top xworld-wangxw.top admin.xworld-wangxw.top)
CERT_NAME="www.xworld-wangxw.top"
WEBROOT="/usr/share/nginx/html"
HOOK="/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请使用 root：sudo bash $0" >&2
  exit 1
fi

if [[ -z "$EMAIL" ]]; then
  read -r -p "Let's Encrypt 通知邮箱: " EMAIL
fi
if [[ -z "$EMAIL" ]]; then
  echo "需要 EMAIL" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
if ! command -v certbot >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y certbot
fi

install -d -m 755 "$WEBROOT/.well-known/acme-challenge"
# 确保 HTTP-01 探测目录可写可读
chmod -R a+rX "$WEBROOT/.well-known" || true

echo "[le] 申请证书: ${DOMAINS[*]}"
DOMAIN_ARGS=()
for d in "${DOMAINS[@]}"; do
  DOMAIN_ARGS+=(-d "$d")
done

# --expand：证书已存在时把新增域名（如 admin）并进同一张证，不另起 cert-name
certbot certonly --webroot -w "$WEBROOT" \
  --cert-name "$CERT_NAME" \
  --expand \
  --agree-tos --non-interactive \
  -m "$EMAIL" \
  "${DOMAIN_ARGS[@]}"

install -d -m 755 /etc/letsencrypt/renewal-hooks/deploy
cat >"$HOOK" <<'EOF'
#!/bin/bash
set -euo pipefail
if command -v nginx >/dev/null 2>&1; then
  nginx -t
  systemctl reload nginx
fi
EOF
chmod 755 "$HOOK"

# Ubuntu 自带定时器（约每天两次检查，到期前自动续）
systemctl enable --now certbot.timer
systemctl status certbot.timer --no-pager || true

echo "[le] 干跑续期（验证 hook / 权限）..."
certbot renew --dry-run

echo
echo "[le] 完成。证书："
echo "  /etc/letsencrypt/live/${CERT_NAME}/fullchain.pem"
echo "  /etc/letsencrypt/live/${CERT_NAME}/privkey.pem"
echo "请确认 Nginx ssl_certificate* 指向上述路径后：nginx -t && systemctl reload nginx"
echo "查看续期定时：systemctl list-timers certbot.timer"
