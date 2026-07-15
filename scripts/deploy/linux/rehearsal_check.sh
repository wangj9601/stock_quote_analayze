#!/usr/bin/env bash
# CentOS：发布后 / 切 DNS 前灰测检查（本机探测）。
# 用法：bash rehearsal_check.sh
# 可先把 hosts 指到新机后再用浏览器验登录；本脚本只做端口与 HTTP 探测。
set -euo pipefail

PASS=0
FAIL=0

check() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "[OK]   $name"
    PASS=$((PASS + 1))
  else
    echo "[FAIL] $name"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== stock_quote CentOS rehearsal ==="
echo "时间: $(date -Is 2>/dev/null || date)"

check "systemd stock-quote-api active" systemctl is-active --quiet stock-quote-api
check "systemd stock-quote-core active" systemctl is-active --quiet stock-quote-core
check "systemd stock-quote-notify active" systemctl is-active --quiet stock-quote-notify
check "systemd stock-quote-frontend active" systemctl is-active --quiet stock-quote-frontend
check "systemd stock-quote-admin active" systemctl is-active --quiet stock-quote-admin
check "systemd nginx active" systemctl is-active --quiet nginx

check "TCP 5000 (api)" bash -c 'echo >/dev/tcp/127.0.0.1/5000'
check "TCP 8000 (frontend)" bash -c 'echo >/dev/tcp/127.0.0.1/8000'
check "TCP 8001 (admin)" bash -c 'echo >/dev/tcp/127.0.0.1/8001'
check "TCP 5432 (postgres，若本机库)" bash -c 'echo >/dev/tcp/127.0.0.1/5432' || true

if command -v curl >/dev/null 2>&1; then
  check "HTTP /health via nginx :80" curl -fsS --max-time 5 http://127.0.0.1/health
  check "HTTP frontend :8000/" curl -fsS --max-time 5 -o /dev/null http://127.0.0.1:8000/
  check "HTTP admin :8001/" curl -fsS --max-time 5 -o /dev/null http://127.0.0.1:8001/
fi

if [[ -f /opt/stock_quote/shared/.env ]]; then
  echo "[INFO] shared/.env 存在"
  if grep -q 'CHANGE_ME' /opt/stock_quote/shared/.env 2>/dev/null; then
    echo "[WARN] shared/.env 仍含 CHANGE_ME 占位符"
    FAIL=$((FAIL + 1))
  else
    PASS=$((PASS + 1))
    echo "[OK]   shared/.env 无 CHANGE_ME 占位"
  fi
else
  echo "[FAIL] 缺少 /opt/stock_quote/shared/.env"
  FAIL=$((FAIL + 1))
fi

if [[ -L /opt/stock_quote/current || -d /opt/stock_quote/current ]]; then
  echo "[OK]   current → $(readlink -f /opt/stock_quote/current 2>/dev/null || echo /opt/stock_quote/current)"
  PASS=$((PASS + 1))
else
  echo "[FAIL] 缺少 /opt/stock_quote/current"
  FAIL=$((FAIL + 1))
fi

echo
echo "=== 人工灰测清单（hosts 指新机后）==="
echo " [ ] https://www.icemaplecity.com/ 登录"
echo " [ ] 选股 / GMS 长请求无 502"
echo " [ ] https://www.icemaplecity.com/admin/ 登录"
echo " [ ] journalctl -u stock-quote-core -n 50"
echo " [ ] 最终 pg_restore 后关键表行数核对"
echo
echo "结果: PASS=$PASS FAIL=$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
exit 0
