# Ubuntu 26.04 公网阿里云部署手册

> 目标机：阿里云 ECS，镜像 **Ubuntu 26.04 LTS**。  
> 不要执行 [centos-migration-runbook.md](centos-migration-runbook.md) 里的 `dnf`、`firewalld`、`libpq-devel`。那些是 CentOS 步骤。  
> 应用发布、回滚、备份与 CentOS 共用 `scripts/deploy/linux/release.sh`、`backup_postgres.sh`、`rehearsal_check.sh`。

相关文件（在仓库中；发布 zip **不含** `docs/`，Nginx 配置在脚本目录里，会打进 zip）：

| 路径 | 用途 |
|------|------|
| [../../scripts/deploy/linux/bootstrap_ubuntu.sh](../../scripts/deploy/linux/bootstrap_ubuntu.sh) | 装包、Python 3.12、用户、目录、venv |
| [../../scripts/deploy/linux/init_postgres_ubuntu.sh](../../scripts/deploy/linux/init_postgres_ubuntu.sh) | 本机库与密码 |
| [../../scripts/deploy/linux/install_units_ubuntu.sh](../../scripts/deploy/linux/install_units_ubuntu.sh) | systemd 五服务，API/用户站只听本机 |
| [../../scripts/deploy/linux/nginx.ubuntu.conf](../../scripts/deploy/linux/nginx.ubuntu.conf) | Nginx 站点 |
| [../../scripts/deploy/linux/.env.ubuntu.example](../../scripts/deploy/linux/.env.ubuntu.example) | `.env` 模板 |
| [../../scripts/deploy/linux/release.sh](../../scripts/deploy/linux/release.sh) | 解压发布、切 `current`、重启、失败回滚 |

## 1. 阿里云前置

1. 镜像选 **Ubuntu 26.04 64 位**。生产 venv 只用 **Python 3.12 或 3.13**。系统自带的 `python3`（3.14）不能用：`psycopg2-binary==2.9.10` 没有 3.14 wheel。机器上若已经有 `python3.12` / `python3.13` 和 Nginx，引导脚本会直接沿用，不重装、不重启 Nginx。只有解释器不是 3.12/3.13 时，才额外安装 Python 3.12，且不替换 `/usr/bin/python3`。
2. **中国大陆地域**对外网站要先完成域名 ICP 备案，再把域名解析到这台 ECS。未备案时 80/443 会被阿里云拦截。香港或海外地域不需要备案。
3. 安全组入方向只放行：

| 端口 | 来源 | 用途 |
|------|------|------|
| 22 | 运维出口 IP | SSH |
| 80 | 0.0.0.0/0 | HTTP 与证书校验 |
| 443 | 0.0.0.0/0 | HTTPS |

不要对公网开放 5000、8000、8002（本系统 admin）、5432。出方向保持默认，以便访问 PyPI 镜像、行情源、企业微信和 SMTP。同机 DeepTutor 若必须对公网提供 8001，由其自己的安全组/反代策略管理，与本系统隔离。

4. SSH 使用密钥登录。不要在安全组里对 `0.0.0.0/0` 开放 22。

## 2. 拓扑与目录

```
浏览器 → Nginx :80/:443
  /        → 127.0.0.1:8000  (frontend)
  /admin/  → 127.0.0.1:8002  (admin/dist；Ubuntu 默认，避开同机 DeepTutor 的 8001)
  /api/    → 127.0.0.1:5000  (backend_api)
  backend_core / start_scheduler → PostgreSQL（只听 localhost）
```

同机已部署 **DeepTutor**（`0.0.0.0:8001`）时：不要抢 8001。本系统管理端用 **`ADMIN_PORT=8002`**，与 `nginx.ubuntu.conf` 中 `admin_server` 一致。DeepTutor 继续原端口；本系统只经 Nginx 的 `/admin/` 对外。

```
/opt/stock_quote/
  releases/
  current -> ...
  shared/.env
  shared/logs/
  shared/backups/
  shared/reports/
  .venv/                 # Python 3.12
/etc/nginx/ssl/          # 证书。不要放在 /opt 下，避免 AppArmor 拒绝
```

运行用户：`stockquote`（`/usr/sbin/nologin`）。时区：`Asia/Shanghai`。

`start_backend_api.py` 与 `start_frontend.py` 读取 `BIND_HOST`。未设置时仍是 `0.0.0.0`（Windows / CentOS 不变）。Ubuntu 单元 drop-in 和 `.env.ubuntu.example` 设为 `127.0.0.1`。管理端单元本来就 `--bind 127.0.0.1`。

systemd 里 `EnvironmentFile`（即 `shared/.env`）会盖过单元里的 `Environment=`。`.env` 里的 `BIND_HOST` 必须是 `127.0.0.1`，不能改成 `0.0.0.0`。

## 3. 把脚本弄到机器上

开发机打包（zip 含 `admin/dist`，服务器不需要 Node）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy\deploy.ps1
```

把 `dist\stock_quote_release_*.zip` 上传到 ECS，例如 `/tmp/`。zip 不含 `docs/`，首次只需 unzip 里的脚本。

Python 和 Nginx 已经装好时，先核对版本再引导。3.12 或 3.13 会直接用；只有 `Python 3.14.x` 时脚本才会再装 3.12：

```bash
python3 --version
command -v python3.12 >/dev/null && python3.12 --version
command -v python3.13 >/dev/null && python3.13 --version
nginx -v
```

```bash
sudo apt-get update
sudo apt-get install -y unzip
sudo unzip -q /tmp/stock_quote_release_xxx.zip -d /tmp/stock_quote_boot
sudo bash /tmp/stock_quote_boot/scripts/deploy/linux/bootstrap_ubuntu.sh
```

`bootstrap_ubuntu.sh` 会：

- 已有 Nginx 则跳过安装，不删除站点、不重启。只在本次新装 Nginx 时去掉默认站；已有实例要改配置可再加 `CONFIGURE_NGINX=1`
- 已有 Python 3.12/3.13 则用它建 venv；缺少 `venv` 模块时只补对应的 `python3.12-venv`（或 3.13）
- 没有 3.12/3.13 时才添加 deadsnakes 安装 Python 3.12
- 没有 `psql` 时才安装 PostgreSQL；编译头文件、`unzip`、`curl` 仍会装
- 时区设为 `Asia/Shanghai`（`sudo TIMEZONE= bash ...` 可跳过）
- 创建 `/opt/stock_quote` 与用户 `stockquote`
- 创建 `/etc/nginx/ssl`
- 为 `stockquote` 写入阿里云 PyPI 镜像（`sudo PIP_INDEX_URL= bash ...` 可跳过）
- **不**打开 firewalld，也 **不**默认启用 ufw

国内 ECS 访问 `ppa.launchpadcontent.net` 可能超时。失败时先确认出网，或在能打开 Launchpad 的机器上下载 Ubuntu 26.04（resolute）的 `python3.12`、`python3.12-venv`、`python3.12-dev` 及其依赖 deb，拷到 ECS 后 `sudo dpkg -i`。不要改用系统 `python3`。

本机还要 ufw 时（会放行 OpenSSH、80、443，有把当前 SSH 锁在外面的风险，先确认安全组来源 IP）：

```bash
sudo ENABLE_UFW=1 bash /tmp/stock_quote_boot/scripts/deploy/linux/bootstrap_ubuntu.sh
```

## 4. PostgreSQL

Ubuntu 26.04 的 `postgresql` 包是 18。旧库的 `pg_dump -Fc` 可以恢复进 18。配置在 `/etc/postgresql/18/main/`，服务名是 `postgresql`，不是 `postgresql-16`。

```bash
sudo DB_PASSWORD='换成强密码' bash /tmp/stock_quote_boot/scripts/deploy/linux/init_postgres_ubuntu.sh
```

脚本会：给 `postgres` 设密码、创建 `stock_analysis`（已存在则跳过）、确认 `pg_hba.conf` 允许 `127.0.0.1/32` 密码登录、检查 `listen_addresses` 仍是 localhost。

### 4.1 推荐：轻量迁库（新机可重采行情）

本地/旧库往往大部分体积在日 K、资金流、指标与策略轨迹上。**新机可以重新采集行情时，不要做全量 dump。**  
`--exclude-table-data` 仍会创建这些表的结构，只是不带行数据；用户、策略、观察、权限、自选等业务表照常迁出。

**保留（会进 dump）：** `users` / `admins`、角色权限、策略配置、交易观察与正式交易、自选股、股票/板块基本信息与成分、推送与邮件配置、交易日历等。

**排除数据（新机重采或重算）：** 个股/指数/板块/基金历史行情与实时快照、个股与板块资金流、复权因子、财务与技术指标、策略 `*_signal_trace` / RS / 复盘简报、公告新闻、系统监控类大表等。

**Windows 本机（开发库常见端口 5446）**可直接跑仓库根目录脚本（密码用环境变量，勿写入 bat）：

```bat
set PGPASSWORD=你的密码
pg_dump_light.bat
rem 或: scripts\deploy\pg_dump_light.bat -Port 5446 -OutDir dist\db_dumps
```

产物默认：`dist\db_dumps\stock_analysis_light_YYYYMMDD_HHMMSS.dump`。

**Linux / 旧机 bash**（按实际改主机与端口；先 `export PGPASSWORD=...`）：

```bash
# 仅排除「表已存在」的 --exclude-table-data，避免旧库缺表时报错
EXCLUDE_TABLES=(
  # 行情 / 实时
  historical_quotes historical_quotes_hk
  index_historical_quotes industry_board_historical_quotes concept_board_historical_quotes
  hk_index_historical_quotes fund_historical_quotes quote_data
  stock_realtime_quote stock_realtime_quote_hk
  index_realtime_quotes industry_board_realtime_quotes hk_index_realtime_quotes fund_realtime_quote
  # 资金流 / 两融
  stock_fund_flow_daily stock_fund_flow_daily_hk stock_fund_flow_em_daily
  board_fund_flow_daily stock_margin_daily
  # 复权 / 财务 / 指标
  stock_adj_factor stock_fina_indicator
  macd_indicators kdj_indicators rsi_indicators ma_indicators boll_indicators
  mavol_indicators icost_indicators mean_frequency_resonance_indicators
  industry_board_daily_metrics concept_board_daily_metrics
  # 预计算 / 轨迹 / 复盘
  rs_ratings rs_ratings_hk
  gms_signal_trace urt_signal_trace csb_signal_trace sbbr_signal_trace rpe_signal_trace
  stock_zt_pool_daily market_daily_review market_daily_mainline_hits stock_recommend_brief
  one_yang_three_lines_signals volume_shrink_breakout_signals
  # 公告新闻 / 监控（可重建）
  stock_notice_report stock_news stock_research_reports
  system_monitor_metrics system_alerts system_performance_reports push_records email_send_logs
)

DUMP_ARGS=(-h 127.0.0.1 -p 5432 -U postgres -Fc -f stock_analysis_light_YYYYMMDD.dump)
for t in "${EXCLUDE_TABLES[@]}"; do
  if psql -h 127.0.0.1 -p 5432 -U postgres -d stock_analysis -Atc \
    "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='${t}'" | grep -q 1; then
    DUMP_ARGS+=(--exclude-table-data="$t")
  fi
done
pg_dump "${DUMP_ARGS[@]}" stock_analysis
```

上传到 ECS 的 `/opt/stock_quote/shared/backups/` 后。`sudo -u postgres` 必须以 **postgres 可读** 的路径打开文件；`shared/backups` 默认属主是 `stockquote`，root 上传的文件常导致 `Permission denied`。恢复前先改权限（或拷到 `/tmp`）：

```bash
# 须先有空库（未跑过 init 时先执行本节开头的 init_postgres_ubuntu.sh，或：）
sudo -u postgres psql -c "SELECT 1 FROM pg_database WHERE datname='stock_analysis';" | grep -q 1 \
  || sudo -u postgres createdb -O postgres stock_analysis

DUMP=/opt/stock_quote/shared/backups/stock_analysis_light_YYYYMMDD.dump
sudo chmod a+rX /opt/stock_quote/shared /opt/stock_quote/shared/backups
sudo chmod a+r "$DUMP"
# 若仍被拒：sudo cp "$DUMP" /tmp/ && DUMP=/tmp/$(basename "$DUMP") && sudo chmod a+r "$DUMP"

sudo -u postgres pg_restore -d stock_analysis --no-owner --role=postgres "$DUMP"
sudo -u postgres psql -d stock_analysis -c "SELECT COUNT(*) FROM users;"
sudo -u postgres psql -d stock_analysis -c "SELECT COUNT(*) FROM historical_quotes;"   # 期望 0
```

轻量 dump 已含最终 schema 时，不要把 `migrations/*.py` 全部重跑。恢复后填好 `.env`（尤其 `TUSHARE_TOKEN`），启动五个服务，由 `backend_core` 按调度或管理端手工回补行情；**不必等全市场全历史齐了再做 DNS 切换**，先确认登录、策略配置、观察股与当日采集正常即可。

备选：空库 + 管理端「环境数据同步」只 Push **策略 + 观察 + 权限**（可选基本信息/板块），**不要**勾行情/资金流/预计算。目标端须先有对应用户（同步会跳过目标不存在的用户）。

### 4.2 备选：全量 dump（必须带齐历史、新机不重采）

旧机停写后：

```bash
pg_dump -h <旧机> -p <端口> -U postgres -Fc -f stock_analysis_YYYYMMDD.dump stock_analysis
```

上传到 `/opt/stock_quote/shared/backups/` 后（同样先保证 postgres 可读，见 §4.1）：

```bash
DUMP=/opt/stock_quote/shared/backups/stock_analysis_YYYYMMDD.dump
sudo chmod a+rX /opt/stock_quote/shared /opt/stock_quote/shared/backups
sudo chmod a+r "$DUMP"
sudo -u postgres pg_restore -d stock_analysis --no-owner --role=postgres "$DUMP"
sudo -u postgres psql -d stock_analysis -c "SELECT COUNT(*) FROM users;"
```

全量 dump 已含最终 schema 时，同样不要把 `migrations/*.py` 全部重跑。库很大时优先用并行目录格式（`-Fd -j N`）或 SSH 管道直灌，见运维讨论；日常手册默认仍用 `-Fc` 单文件。

## 5. 填写 `.env`

引导脚本已从 `.env.ubuntu.example` 复制到 `/opt/stock_quote/shared/.env`（文件已存在则不会覆盖）。

至少改这几项：

- `DATABASE_URL` 里的密码与 `init_postgres_ubuntu.sh` 的 `DB_PASSWORD` 一致；主机端口用 **`127.0.0.1:5432`**（不要用开发机 `5446`）
- `JWT_SECRET_KEY`
- `BIND_HOST=127.0.0.1`
- `ADMIN_PORT=8002`（同机 DeepTutor 占 8001 时）
- `TUSHARE_TOKEN`、邮件、企业微信（键名是 `WECHAT_CORP_ID` / `WECHAT_CORP_SECRET` / `WECHAT_AGENT_ID`）

生产只认 **`/opt/stock_quote/shared/.env`**。若 `current/.env` 仍存在（旧包误打进开发机配置），会干扰排障；应删除：

```bash
sudo rm -f /opt/stock_quote/current/.env
# 并确认无 5446：
grep -R 5446 /opt/stock_quote/shared/.env /opt/stock_quote/current/.env 2>/dev/null || true
```

```bash
sudo chown stockquote:stockquote /opt/stock_quote/shared/.env
sudo chmod 640 /opt/stock_quote/shared/.env
```

`GMS_SCREENING_TIMEOUT=600` 须与 Nginx `proxy_read_timeout 600s` 一致。

## 6. 首次发布

服务还没装时，健康检查会失败。首次用 `SKIP_HEALTH=1`，只解压、装依赖、切 `current`：

```bash
sudo SKIP_HEALTH=1 bash /tmp/stock_quote_boot/scripts/deploy/linux/release.sh \
  /tmp/stock_quote_release_xxx.zip
```

之后每次发布（此时用已经切到 `current` 里的脚本）：

```bash
sudo bash /opt/stock_quote/current/scripts/deploy/linux/release.sh \
  /tmp/stock_quote_release_yyy.zip
```

健康检查失败时，`release.sh` 会把 `current` 指回上一版并重启。`SKIP_HEALTH=1` 不做这项检查，只用于第一次。

若解压出现 `appears to use backslashes as path separators` 后脚本直接退出、且没有 `current`：旧版 `release.sh` 把 unzip 的警告码 1 当成失败。用仓库新版 `release.sh`，或对已解压目录手工切链：

```bash
RELEASE=$(ls -1dt /opt/stock_quote/releases/*/ | head -1)
ls "$RELEASE/start_backend_api.py" "$RELEASE/requirements-prod.txt"
sudo ln -sfn "$RELEASE" /opt/stock_quote/current
sudo chown -h stockquote:stockquote /opt/stock_quote/current
sudo -u stockquote /opt/stock_quote/.venv/bin/pip install -r /opt/stock_quote/current/requirements-prod.txt
```

## 7. systemd

须先完成 §6 首次发布，使 `/opt/stock_quote/current` 指向含 `scripts/deploy/linux/` 的 release。若提示 `No such file`：

```bash
ls -la /opt/stock_quote/current
ls /opt/stock_quote/current/scripts/deploy/linux/install_units_ubuntu.sh
```

- `current` 不存在或目录里没有该脚本：先按 §6 用 `/tmp/stock_quote_boot/.../release.sh` + 发布 zip 装一版；或直接用引导包里的脚本安装单元（单元仍指向 `/opt/stock_quote/current`）：

```bash
sudo bash /tmp/stock_quote_boot/scripts/deploy/linux/install_units_ubuntu.sh
```

`current` 已就绪时：

```bash
sudo bash /opt/stock_quote/current/scripts/deploy/linux/install_units_ubuntu.sh
sudo systemctl enable --now \
  stock-quote-api stock-quote-core stock-quote-notify \
  stock-quote-frontend stock-quote-admin
```

| 单元 | 职责 |
|------|------|
| `stock-quote-api` | 127.0.0.1:5000 |
| `stock-quote-core` | 采集常驻 |
| `stock-quote-notify` | 推送调度 |
| `stock-quote-frontend` | 127.0.0.1:8000 |
| `stock-quote-admin` | 127.0.0.1:**8002**（`ADMIN_PORT`），`admin/dist` |

确认本系统端口只听本机（DeepTutor 的 `0.0.0.0:8001` 可单独存在）：

```bash
sudo ss -lptn | grep -E ':5000|:8000|:8002|:5432'
```

`5000` / `8000` / `8002` / `5432` 应为 `127.0.0.1`，不能是 `0.0.0.0`。

## 8. 证书与 Nginx（Let's Encrypt + 自动续期）

当前 Ubuntu 生产域名：**`www.xworld-wangxw.top`** / **`xworld-wangxw.top`**。  
推荐 **certbot webroot**（不改写整站反代）。证书路径（与 `nginx.ubuntu.conf` 一致）：

- `/etc/letsencrypt/live/www.xworld-wangxw.top/fullchain.pem`
- `/etc/letsencrypt/live/www.xworld-wangxw.top/privkey.pem`

### 8.1 前置

1. DNS：`www.xworld-wangxw.top` 与 `xworld-wangxw.top` 的 A 记录指向本机公网 IP（或先用 hosts 灰测，但 **签发时 Let's Encrypt 必须能从公网访问你的 80**）。
2. 安全组放行 **入站 80**（HTTP-01）；443 也一并放行。
3. 大陆地域需已完成该域名 **ICP 备案**，否则 80/443 可能被拦，申请失败。
4. **不要**用 `certbot --nginx` 自动改配置（会弄乱与 DeepTutor 共存的站点）。用 `--webroot`。

### 8.2 先只开 80（证书尚未存在时）

完整 conf 含 443 且证书文件不存在时，`nginx -t` 会失败。先装「仅 HTTP + ACME」或临时注释 443 段：

```bash
# 写入最小 80 站点（与正式 conf 的 ACME 路径一致）
sudo tee /etc/nginx/conf.d/stock_quote.conf >/dev/null <<'EOF'
server {
    listen 80;
    server_name www.xworld-wangxw.top xworld-wangxw.top;
    location /.well-known/acme-challenge/ {
        root /usr/share/nginx/html;
        try_files $uri =404;
    }
    location / { return 200 'stock_quote acme ok\n'; add_header Content-Type text/plain; }
}
EOF
sudo mkdir -p /usr/share/nginx/html/.well-known/acme-challenge
sudo nginx -t && sudo systemctl reload nginx

# 本机自测（应 200）：
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1/ -H 'Host: www.xworld-wangxw.top'
```

### 8.3 申请证书

一键脚本（在仓库 / 已发布到 `current` 或 boot 包内）：

```bash
sudo EMAIL='你的邮箱@example.com' bash /opt/stock_quote/current/scripts/deploy/linux/setup_letsencrypt_ubuntu.sh
# 若 current 尚无该脚本：
# sudo EMAIL='你的邮箱@example.com' bash /tmp/stock_quote_boot/scripts/deploy/linux/setup_letsencrypt_ubuntu.sh
```

或手工等价命令：

```bash
sudo apt-get update -y && sudo apt-get install -y certbot
sudo certbot certonly --webroot -w /usr/share/nginx/html \
  --cert-name www.xworld-wangxw.top \
  --agree-tos -m 你的邮箱@example.com --non-interactive \
  -d www.xworld-wangxw.top -d xworld-wangxw.top
```

成功后应有：

```bash
sudo ls -l /etc/letsencrypt/live/www.xworld-wangxw.top/
```

### 8.4 启用完整 HTTPS 站点

```bash
sudo cp /opt/stock_quote/current/scripts/deploy/linux/nginx.ubuntu.conf \
  /etc/nginx/conf.d/stock_quote.conf
# 若 current 仍是旧域名/旧证书路径，把本机已改好的 nginx.ubuntu.conf 上传后再 cp
sudo nginx -t && sudo systemctl reload nginx
curl -sSI https://www.xworld-wangxw.top/ | head
```

### 8.5 自动续期

`setup_letsencrypt_ubuntu.sh` 会：

- 启用 **`certbot.timer`**（systemd 定时检查，到期前自动 `renew`）
- 安装 deploy hook：`/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh`（续期成功后 `nginx -t && reload`）

手工确认：

```bash
systemctl status certbot.timer --no-pager
systemctl list-timers certbot.timer --no-pager
sudo certbot renew --dry-run
```

`--dry-run` 通过即表示续期链路正常。无需 cron 再写一份（避免与 timer 重复）。

### 8.6 备选：阿里云下载的 pem

若不用 Let's Encrypt，可把全链/私钥装到 `/etc/nginx/ssl/`，并改 conf 里 `ssl_certificate*` 指向该路径。不要把私钥放在 `/opt/stock_quote/shared/ssl/`（AppArmor 可能拒绝 Nginx 读取）。

## 9. 灰测

DNS 切到新 IP 之前，在运维电脑的 hosts 里把域名指到 ECS 公网 IP：

```
<公网IP>  www.xworld-wangxw.top xworld-wangxw.top
```

在 ECS 上：

```bash
sudo bash /opt/stock_quote/current/scripts/deploy/linux/rehearsal_check.sh
```

再人工确认：用户站登录、选股长请求无 502/504、管理端登录、`journalctl -u stock-quote-core` 与 `stock-quote-notify` 没有持续报错。

## 10. 从旧生产切换

默认按 **§4.1 轻量迁库**（新机重采行情）。仅当必须带全历史时改用 §4.2。

| 步骤 | 动作 |
|------|------|
| T-1 | 第 9 节灰测通过；确认新机采集链路（Token、出网、core 日志）可用 |
| T0 | 旧机停写 → 按 §4.1 打轻量 dump（或 §4.2 全量）→ 新机 `pg_restore` → 核对 `users` 等业务表行数；轻量模式下行情表可为 0 |
| T1 | 五个服务与 nginx 已启动，再跑 `rehearsal_check.sh`；触发或等待一轮行情回补 |
| T2 | DNS A/AAAA 指到新公网 IP |
| T3 | 观察 30–60 分钟：`journalctl`、`/var/log/nginx/error.log`、下一采集窗口 |
| T4 | 旧机只读观察 24–48 小时后下线。切换窗口内不要两台同时写库 |

回滚：DNS 指回旧机；应用把 `current` 指回上一 `releases/*` 后 `systemctl restart` 五个服务。库回滚必须用切日前的 dump（轻量或全量与切换时一致）。

## 11. 日常

```bash
# 发布
sudo bash /opt/stock_quote/current/scripts/deploy/linux/release.sh /path/to/pkg.zip

# 备份（可放进 cron，每天 02:30）
sudo -u stockquote bash /opt/stock_quote/current/scripts/deploy/linux/backup_postgres.sh

# 日志
journalctl -u stock-quote-api -n 100 --no-pager

# Nginx
sudo nginx -t && sudo systemctl reload nginx
```

备份脚本读 `shared/.env` 的 `DATABASE_URL`，保留 14 天，可用 `RETAIN_DAYS=14` 覆盖。

## 12. 排障：`set: pipefail: invalid option name`

脚本若从 Windows 拷到 Linux 且带 CRLF，bash 会报类似：

```text
set: pipefail
: invalid option name
```

在服务器上先去掉 `\r` 再执行（或改用仓库里已统一为 LF 的脚本重新上传）：

```bash
sed -i 's/\r$//' /tmp/stock_quote_boot/scripts/deploy/linux/*.sh
sed -i 's/\r$//' /tmp/stock_quote_boot/scripts/deploy/linux/systemd/*.service
sed -i 's/\r$//' /tmp/stock_quote_boot/scripts/deploy/linux/systemd/ubuntu/*.conf
sed -i 's/\r$//' /tmp/stock_quote_boot/scripts/deploy/linux/*.conf /tmp/stock_quote_boot/scripts/deploy/linux/.env*.example
```
