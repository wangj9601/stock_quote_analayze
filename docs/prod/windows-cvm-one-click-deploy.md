# 腾讯云 Windows CVM 一键部署（多服务）

本文档对应以下服务拓扑：

- `https://www.icemaplecity.com/` -> `frontend`
- `https://www.icemaplecity.com/admin` -> `admin`
- `/api/*` -> `backend_api`
- 后台常驻任务：`backend_core`、`start_scheduler.py`

> 说明：Nginx 已预配置，本文不会生成新的 Nginx 配置，只在发布时执行校验和 reload。

## 1. 目录与脚本

- 初始化脚本：`scripts/deploy/bootstrap_windows.ps1`
- 服务注册脚本：`scripts/deploy/install_services.ps1`
- 远端发布脚本：`scripts/deploy/release.ps1`
- 本地一键触发脚本：`scripts/deploy/deploy.ps1`

服务器目录规范：

- `C:\deploy\stock_quote\releases`：历史版本
- `C:\deploy\stock_quote\current`：当前运行版本
- `C:\deploy\stock_quote\shared`：共享配置与日志（不随版本覆盖）

## 2. 首次初始化（服务器执行）

在 Windows CVM（管理员 PowerShell）执行：

```powershell
Set-ExecutionPolicy RemoteSigned -Scope LocalMachine
cd C:\deploy\stock_quote\current
powershell -ExecutionPolicy Bypass -File .\scripts\deploy\bootstrap_windows.ps1
```

然后编辑：

- `C:\deploy\stock_quote\shared\.env`

确保至少包含：

- `ENVIRONMENT=production`
- `BACKEND_PORT=5000`
- `DATABASE_URL=...`

## 3. 安装 Windows 服务（服务器执行）

先确保 `NSSM` 已安装到 `C:\tools\nssm\nssm.exe`，再执行：

```powershell
cd C:\deploy\stock_quote\current
powershell -ExecutionPolicy Bypass -File .\scripts\deploy\install_services.ps1 -StartAfterInstall
```

会注册 3 个服务：

- `stock-quote-api`
- `stock-quote-core`
- `stock-quote-notify`

## 4. 本地一键发布（你的开发机执行）

```powershell
cd E:\wangxw\work\stock_quote_analayze
powershell -ExecutionPolicy Bypass -File .\scripts\deploy\deploy.ps1 `
  -ServerHost "你的CVM公网IP" `
  -ServerUser "Administrator"
```

如需私钥：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy\deploy.ps1 `
  -ServerHost "你的CVM公网IP" `
  -ServerUser "Administrator" `
  -SshKeyPath "C:\Users\xxx\.ssh\id_rsa"
```

## 5. 发布流程说明

`deploy.ps1` 会：

1. 打包当前项目为 zip
2. 通过 `scp` 上传到服务器临时目录
3. 通过 `ssh` 调用远端 `release.ps1`

`release.ps1` 会：

1. 解压到 `releases\<timestamp>`
2. 复制 `shared\.env`
3. 安装 Python 依赖、构建 `admin`
4. 执行可选迁移（`migrate_db.py` 存在时）
5. 原子切换 `current`
6. 重启三项服务
7. 执行 `nginx -t` 和 `nginx -s reload`
8. 执行健康检查，失败自动回滚

## 6. 日志与排障

- 服务日志目录：`C:\deploy\stock_quote\shared\logs`
- 查看服务状态：

```powershell
Get-Service stock-quote-*
```

- 重启单个服务：

```powershell
Restart-Service stock-quote-api
```

- Nginx 校验：

```powershell
nginx -t
```

## 7. 环境变量与敏感信息规范

- 仅在服务器 `shared\.env` 保存真实密钥
- 仓库中不提交生产 `.env`
- 建议本地只保留脱敏模板（如 `.env.example`）

## 8. 验收清单

- `https://www.icemaplecity.com/` 可打开
- `https://www.icemaplecity.com/admin` 可打开
- `https://www.icemaplecity.com/api/...` 接口正常
- `Get-Service stock-quote-*` 均为 Running
- 人工停止任一服务后，系统可自动恢复
