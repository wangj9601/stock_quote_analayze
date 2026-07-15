# Linux / CentOS 部署脚本

生产目标机请使用本目录，完整步骤见：

**[docs/prod/centos-migration-runbook.md](../../../docs/prod/centos-migration-runbook.md)**

| 脚本 | 说明 |
|------|------|
| `bootstrap_centos.sh` | 用户、目录、venv |
| `install_units.sh` | 安装 systemd 五服务 |
| `release.sh` | 发布 zip、切 symlink、重启、失败回滚 |
| `backup_postgres.sh` | `pg_dump -Fc` + 按天清理 |
| `rehearsal_check.sh` | 灰测 / 健康检查 |
| `.env.centos.example` | 生产环境变量模板 |
| `systemd/*.service` | api / core / notify / frontend / admin |

开发机构建发布包仍可用 Windows 下的 `scripts/deploy/deploy.ps1`，把 zip 传到 CentOS 后执行 `release.sh`。
