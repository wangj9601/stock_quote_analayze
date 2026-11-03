# Linux 部署脚本

按目标系统选手册。开发机构建发布包仍用 Windows 下的 `scripts/deploy/deploy.ps1`，把 zip 传到服务器后执行 `release.sh`。发布包不含 `docs/`，Nginx 站点文件放在本目录，会随 zip 带上服务器。

## Ubuntu 26.04 / 阿里云公网

**[docs/prod/ubuntu-aliyun-runbook.md](../../../docs/prod/ubuntu-aliyun-runbook.md)**

| 脚本 | 说明 |
|------|------|
| `bootstrap_ubuntu.sh` | apt 包、Python 3.12、用户、目录、venv、阿里云 pip 镜像 |
| `init_postgres_ubuntu.sh` | 本机库、密码、`pg_hba` 只允许 127.0.0.1 |
| `install_units_ubuntu.sh` | 五个 systemd 服务，API / 用户站只听 127.0.0.1 |
| `nginx.ubuntu.conf` | 站点配置；用户站 `www` / apex，管理端 `admin.xworld-wangxw.top` 反代到本机 8002。证书路径 `/etc/letsencrypt/live/www.xworld-wangxw.top/` |
| `setup_letsencrypt_ubuntu.sh` | certbot webroot 申请 + `certbot.timer` 自动续期 + reload hook |
| `.env.ubuntu.example` | 生产环境变量模板 |

`release.sh`、`backup_postgres.sh`、`rehearsal_check.sh` 与 CentOS 共用。

## CentOS / Rocky / Alma

**[docs/prod/centos-migration-runbook.md](../../../docs/prod/centos-migration-runbook.md)**

| 脚本 | 说明 |
|------|------|
| `bootstrap_centos.sh` | 用户、目录、venv |
| `install_units.sh` | 安装 systemd 五服务 |
| `.env.centos.example` | 生产环境变量模板 |
| `systemd/*.service` | api / core / notify / frontend / admin |

不要在 Ubuntu 上执行 `bootstrap_centos.sh` 对应手册里的 `dnf` / `firewalld` 步骤。
