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

不要对公网开放 5000、8000、8001、5432。出方向保持默认，以便访问 PyPI 镜像、行情源、企业微信和 SMTP。

4. SSH 使用密钥登录。不要在安全组里对 `0.0.0.0/0` 开放 22。

## 2. 拓扑与目录

```
浏览器 → Nginx :80/:443
  /        → 127.0.0.1:8000  (frontend)
  /admin/  → 127.0.0.1:8001  (admin/dist)
  /api/    → 127.0.0.1:5000  (backend_api)
  backend_core / start_scheduler → PostgreSQL（只听 localhost）
```

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

从旧机迁库时，在停写后：

```bash
pg_dump -h <旧机> -p <端口> -U postgres -Fc -f stock_analysis_YYYYMMDD.dump stock_analysis
```

上传到 `/opt/stock_quote/shared/backups/` 后：

```bash
sudo -u postgres pg_restore -d stock_analysis --no-owner --role=postgres \
  /opt/stock_quote/shared/backups/stock_analysis_YYYYMMDD.dump
sudo -u postgres psql -d stock_analysis -c "SELECT COUNT(*) FROM users;"
```

全量 dump 已含最终 schema 时，不要把 `migrations/*.py` 全部重跑。

## 5. 填写 `.env`

引导脚本已从 `.env.ubuntu.example` 复制到 `/opt/stock_quote/shared/.env`（文件已存在则不会覆盖）。

至少改这几项：

- `DATABASE_URL` 里的密码与 `init_postgres_ubuntu.sh` 的 `DB_PASSWORD` 一致
- `JWT_SECRET_KEY`
- `BIND_HOST=127.0.0.1`
- `TUSHARE_TOKEN`、邮件、企业微信（键名是 `WECHAT_CORP_ID` / `WECHAT_CORP_SECRET` / `WECHAT_AGENT_ID`）

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

## 7. systemd

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
| `stock-quote-admin` | 127.0.0.1:8001，`admin/dist` |

确认没有对公网监听：

```bash
sudo ss -lptn | grep -E ':5000|:8000|:8001|:5432'
```

这四个端口的地址应是 `127.0.0.1`，不能是 `0.0.0.0`。

## 8. 证书与 Nginx

按实际域名修改 `nginx.ubuntu.conf` 里的 `server_name` 和证书文件名。下面沿用当前生产域名。

```bash
sudo install -d -m 755 /etc/nginx/ssl
sudo install -m 644 /path/to/www.icemaplecity.com-chain.pem /etc/nginx/ssl/www.icemaplecity.com-chain.pem
sudo install -m 600 /path/to/www.icemaplecity.com-key.pem /etc/nginx/ssl/www.icemaplecity.com-key.pem

sudo cp /opt/stock_quote/current/scripts/deploy/linux/nginx.ubuntu.conf \
  /etc/nginx/conf.d/stock_quote.conf
sudo nginx -t && sudo systemctl reload nginx
```

证书放在 `/etc/nginx/ssl/`。Ubuntu 的 Nginx AppArmor 配置允许读 `/etc/nginx/**`。放到 `/opt/stock_quote/shared/ssl/` 时，`nginx -t` 可能通过，握手阶段在 `/var/log/nginx/error.log` 里出现 Permission denied。

若 `error.log` 仍有 AppArmor 拒绝：

```bash
sudo journalctl -k | grep -i apparmor | tail
```

阿里云证书服务下载的 pem 按上面的文件名安装即可。使用 certbot 时用 webroot `/usr/share/nginx/html`，不要让它重写整站反代。

## 9. 灰测

DNS 切到新 IP 之前，在运维电脑的 hosts 里把域名指到 ECS 公网 IP：

```
<公网IP>  www.icemaplecity.com icemaplecity.com
```

在 ECS 上：

```bash
sudo bash /opt/stock_quote/current/scripts/deploy/linux/rehearsal_check.sh
```

再人工确认：用户站登录、选股长请求无 502/504、管理端登录、`journalctl -u stock-quote-core` 与 `stock-quote-notify` 没有持续报错。

## 10. 从旧生产切换

| 步骤 | 动作 |
|------|------|
| T-1 | 第 9 节灰测通过 |
| T0 | 旧机停写 → 最终 `pg_dump -Fc` → 新机 `pg_restore` → 核对行数 |
| T1 | 五个服务与 nginx 已启动，再跑 `rehearsal_check.sh` |
| T2 | DNS A/AAAA 指到新公网 IP |
| T3 | 观察 30–60 分钟：`journalctl`、`/var/log/nginx/error.log`、下一采集窗口 |
| T4 | 旧机只读观察 24–48 小时后下线。切换窗口内不要两台同时写库 |

回滚：DNS 指回旧机；应用把 `current` 指回上一 `releases/*` 后 `systemctl restart` 五个服务。库回滚必须用切日前的 dump。

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
