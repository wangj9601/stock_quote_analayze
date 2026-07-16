# CentOS 生产环境迁移手册

> 目标：从现有 **Windows** 生产迁到 **CentOS**（含 Rocky/Alma）。  
> Windows 侧 NSSM / `scripts/deploy/*.ps1` **仅作旧生产与开发机构建包**；新机主路径为本文 + `scripts/deploy/linux/`。

相关文件：

| 路径 | 用途 |
|------|------|
| [nginx.centos.conf](nginx.centos.conf) | 系统 Nginx 站点配置（建议放到 `/etc/nginx/conf.d/`） |
| [../scripts/deploy/linux/bootstrap_centos.sh](../../scripts/deploy/linux/bootstrap_centos.sh) | 目录 / 用户 / venv |
| [../scripts/deploy/linux/release.sh](../../scripts/deploy/linux/release.sh) | 解压发布、切 symlink、重启服务 |
| [../scripts/deploy/linux/backup_postgres.sh](../../scripts/deploy/linux/backup_postgres.sh) | `pg_dump -Fc` 备份 |
| [../scripts/deploy/linux/install_units.sh](../../scripts/deploy/linux/install_units.sh) | 安装 systemd 五服务 |
| [../scripts/deploy/linux/rehearsal_check.sh](../../scripts/deploy/linux/rehearsal_check.sh) | 灰测 / 发布后健康检查 |
| [../scripts/deploy/linux/.env.centos.example](../../scripts/deploy/linux/.env.centos.example) | 生产 `.env` 模板 |
| [../scripts/deploy/linux/systemd/](../../scripts/deploy/linux/systemd/) | 五个 unit 文件 |

## 1. 约定拓扑与目录

```
浏览器 → Nginx :80/:443
  /        → 127.0.0.1:8000  (frontend)
  /admin/  → 127.0.0.1:8001  (admin/dist)
  /api/    → 127.0.0.1:5000  (backend_api)
  backend_core / start_scheduler → PostgreSQL（无对外端口）
```

```
/opt/stock_quote/
  releases/          # 历史版本
  current -> ...     # 当前运行 symlink
  shared/.env
  shared/logs/
  shared/backups/
  shared/ssl/        # 证书（与 nginx.centos.conf 一致）
  shared/reports/
  .venv/
```

运行用户：`stockquote`（`nologin`）。

安全组 / firewalld：对外仅 **SSH、80、443**。勿对公网开放 5000 / 8000 / 8001 / 5432。

## 2. 阶段 0：旧 Windows 盘点

- [ ] 导出现网 `.env`、生效 Nginx conf、SSL 证书与私钥
- [ ] 记录 PG 版本与端口（笔记常见 8432）、库名 `stock_analysis`
- [ ] 记下最近 `stock_quote_release_*.zip` 或 `current` 版本名
- [ ] DNS TTL 提前降到 300s
- [ ] 约定停写窗口（建议交易日收盘后）

## 3. 阶段 1：CentOS 基础运行时

```bash
# CentOS 8+/Stream 示例；CentOS 7 用 yum，Python 3.10 需额外源/SCL/源码
sudo dnf -y update
sudo dnf -y install nginx firewalld unzip curl gcc openssl-devel libpq-devel

sudo firewall-cmd --permanent --add-service=http --add-service=https --add-service=ssh
sudo firewall-cmd --reload

# 将仓库 scripts/deploy/linux 或发布包拷到机器后：
sudo bash scripts/deploy/linux/bootstrap_centos.sh
```

`bootstrap_centos.sh` 会创建 `/opt/stock_quote` 目录树、用户 `stockquote`、共享 venv。

安装 PostgreSQL 12+（建议 [PGDG](https://www.postgresql.org/download/linux/redhat/) 与旧机大版本一致），创建库：

```sql
CREATE DATABASE stock_analysis OWNER postgres;
```

配置 `pg_hba.conf` 仅允许本机应用连接，然后：

```bash
sudo systemctl enable --now postgresql   # 实际单元名随安装源可能是 postgresql-15 等
```

## 4. 阶段 2：数据库迁移

### 4.1 旧机停写

顺序：`stock-quote-core` → `stock-quote-notify` → `stock-quote-api` → frontend/admin。

### 4.2 导出

```bash
export PGPASSWORD='...'
pg_dump -h <旧机> -p <端口> -U postgres -Fc -f stock_analysis_YYYYMMDD.dump stock_analysis
scp stock_analysis_YYYYMMDD.dump user@centos:/opt/stock_quote/shared/backups/
```

### 4.3 导入与校验

```bash
sudo -u postgres pg_restore -d stock_analysis --no-owner --role=postgres \
  /opt/stock_quote/shared/backups/stock_analysis_YYYYMMDD.dump

# 抽样
sudo -u postgres psql -d stock_analysis -c "\dt"
sudo -u postgres psql -d stock_analysis -c "SELECT COUNT(*) FROM users;"
```

**注意**：全量 dump 已含最终 schema 时，不要盲目跑全部 `migrations/*.py`。仅缺表/缺列时执行对应单个脚本或项目根 `init_db.py`。  
仓库中不存在 `migrate_db.py` / `init_postgresql_db.py` / `start_system.py`，勿照抄过期 Windows 文档。

日常备份（新机就绪后）：

```bash
sudo -u stockquote bash /opt/stock_quote/current/scripts/deploy/linux/backup_postgres.sh
# 或 crontab: 每天 02:30
```

## 5. 阶段 3：`.env` 与首次代码发布

```bash
sudo cp /opt/stock_quote/current/scripts/deploy/linux/.env.centos.example \
       /opt/stock_quote/shared/.env
sudo -u stockquote -e /opt/stock_quote/shared/.env   # 或 vi
# 至少填：ENVIRONMENT=production、DATABASE_URL、JWT_SECRET_KEY、FRONTEND_PORT=8000
sudo chown stockquote:stockquote /opt/stock_quote/shared/.env
sudo chmod 640 /opt/stock_quote/shared/.env
```

微信推送键名与代码一致（默认档）：

- `WECHAT_CORP_ID` / `WECHAT_CORP_SECRET` / `WECHAT_AGENT_ID`
- 命名 profile：`WECHAT_<PROFILE>_CORP_ID` 等  
勿依赖未在推送代码中读取的别名键。

### 开发机构建包（可在 Windows）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy\deploy.ps1
# 将 dist\stock_quote_release_*.zip scp 到 CentOS
```

### CentOS 首次解压（若尚无 current）

```bash
sudo mkdir -p /opt/stock_quote/releases
sudo unzip -q /path/to/stock_quote_release_xxx.zip -d /opt/stock_quote/releases/stock_quote_release_xxx
# 若 zip 内自带一层目录，按实际结构调整
sudo ln -sfn /opt/stock_quote/releases/stock_quote_release_xxx /opt/stock_quote/current
sudo chown -R stockquote:stockquote /opt/stock_quote/releases /opt/stock_quote/current
sudo -u stockquote /opt/stock_quote/.venv/bin/pip install -U pip
sudo -u stockquote /opt/stock_quote/.venv/bin/pip install -r /opt/stock_quote/current/requirements-prod.txt
```

后续发布一律：

```bash
sudo bash /opt/stock_quote/current/scripts/deploy/linux/release.sh \
  /path/to/stock_quote_release_YYY.zip
```

## 6. 阶段 4：Nginx 与证书

```bash
sudo mkdir -p /opt/stock_quote/shared/ssl
# 从旧机拷贝 chain + key，文件名与 nginx.centos.conf 一致：
#   www.icemaplecity.com-chain.pem
#   www.icemaplecity.com-key.pem

sudo cp /opt/stock_quote/current/docs/prod/nginx.centos.conf \
       /etc/nginx/conf.d/stock_quote.conf
# 如默认 default.conf 抢 80/443，请 disable 或改 server_name
sudo nginx -t && sudo systemctl enable --now nginx && sudo systemctl reload nginx
```

`/api/` 已设 `proxy_read_timeout 600s`，须与 `.env` 中 `GMS_SCREENING_TIMEOUT=600` 对齐。

## 7. 阶段 5：systemd 五服务

```bash
sudo bash /opt/stock_quote/current/scripts/deploy/linux/install_units.sh
sudo systemctl enable --now \
  stock-quote-api stock-quote-core stock-quote-notify \
  stock-quote-frontend stock-quote-admin
sudo systemctl status stock-quote-api --no-pager
journalctl -u stock-quote-api -f
```

| 单元 | 端口 / 职责 |
|------|-------------|
| `stock-quote-api` | 5000，FastAPI |
| `stock-quote-core` | 采集常驻 |
| `stock-quote-notify` | 推送调度 |
| `stock-quote-frontend` | 8000 |
| `stock-quote-admin` | 8001，`admin/dist` |

## 8. 灰测演练（切 DNS 前必做）

在运维机或浏览器本机 `hosts` 将域名指到 **新 CentOS 公网 IP**：

```
<新IP>  www.icemaplecity.com icemaplecity.com
```

在新机执行：

```bash
sudo bash /opt/stock_quote/current/scripts/deploy/linux/rehearsal_check.sh
```

人工再验：

- [ ] 用户站登录
- [ ] 选股（含 GMS 长请求，不出现 502/504）
- [ ] 管理端登录、行情、GMS 管理页
- [ ] `journalctl -u stock-quote-core` / `stock-quote-notify` 无持续报错
- [ ] DB 抽样日期与行数符合预期

完整 **pg_restore 演练**：用一份非切换日 dump 在测试库或先导入再启动服务，确认应用能读库后再做切换日最终 dump。

## 9. 切换日 Runbook

| 步骤 | 动作 |
|------|------|
| T-1 | 灰测通过（§8） |
| T0 | 旧机停写 → 最终 `pg_dump -Fc` → 新机 `pg_restore` → 行数校验 |
| T1 | `systemctl start` 五服务 + nginx；`rehearsal_check.sh` |
| T2 | DNS A/AAAA → 新公网 IP |
| T3 | 监控 30–60 分钟：`journalctl`、`/var/log/nginx/error.log`、下一采集窗口 |
| T4 | 旧 Windows 只读观察 24–48h 后下线 |

## 10. 回滚

1. DNS 指回旧 Windows。
2. 旧机按原 NSSM 启服务（迁机窗口禁止双写）。
3. 应用：将 `current` symlink 指回上一 `releases/*`，然后：

```bash
sudo systemctl restart stock-quote-api stock-quote-core stock-quote-notify \
  stock-quote-frontend stock-quote-admin
```

4. 库回滚必须使用切日前 `pg_dump`，不能只靠应用回滚。

`release.sh` 在健康检查失败时会自动尝试把 `current` 指回切换前目标并 restart。

## 11. 常用命令速查

```bash
# 服务
sudo systemctl restart stock-quote-api
journalctl -u stock-quote-api -n 100 --no-pager

# 发布
sudo bash /opt/stock_quote/current/scripts/deploy/linux/release.sh /path/to/pkg.zip

# 备份
sudo -u stockquote bash /opt/stock_quote/current/scripts/deploy/linux/backup_postgres.sh

# Nginx
sudo nginx -t && sudo systemctl reload nginx
```
