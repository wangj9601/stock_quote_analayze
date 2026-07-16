# 腾讯云 Windows CVM 一键部署（多服务）

> **说明（2026-07）**：新生产目标机已定为 **CentOS**，请优先使用  
> [centos-migration-runbook.md](centos-migration-runbook.md) 与 `scripts/deploy/linux/`。  
> 本文档仅适用于 **仍在 Windows CVM / NSSM 上运行的旧生产** 与开发机构建包参考。

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

先确保 `NSSM` 已复制到 `C:\work\stock_quote_analayze\tools\nssm.exe`（或与 `install_services.ps1 -NssmExe` 一致的路径），再执行：

```powershell
cd C:\deploy\stock_quote\current
powershell -ExecutionPolicy Bypass -File .\scripts\deploy\install_services.ps1 -StartAfterInstall
```

会注册 3 个服务：

- `stock-quote-api`
- `stock-quote-core`
- `stock-quote-notify`

## 4. 开发机构建发布包（默认：仅打包，不上传）

默认逻辑：**开发机只生成 `dist\stock_quote_release_<时间戳>.zip`**，不连接 SSH。手工把 zip 拷到服务器后再执行 **`release.ps1`**（见下一节服务器侧）。

```powershell
cd E:\wangxw\股票分析软件\编码\stock_quote_analayze
powershell -ExecutionPolicy Bypass -File .\scripts\deploy\deploy.ps1
```

可选跳过 `package.py`：`.\scripts\deploy\deploy.ps1 -SkipPackagePy`

### 4.1 可选：开发机 SSH 一键上传（需服务器已开通 SSH 且安全组放行 22）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy\deploy.ps1 `
  -RemoteDeploy `
  -ServerHost "你的CVM公网IP" `
  -ServerUser "Administrator"
```

如需私钥：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy\deploy.ps1 `
  -RemoteDeploy `
  -ServerHost "你的CVM公网IP" `
  -ServerUser "Administrator" `
  -SshKeyPath "C:\Users\xxx\.ssh\id_rsa" `
  -ServerDeployRoot "C:\work\stock_quote_analayze" `
  -ServerReleaseScript "C:\work\stock_quote_analayze\current\scripts\deploy\release.ps1" `
  -RemoteTempDir "C:\work\stock_quote_analayze\tmp" `
  -ServerNginxHome "C:\work\stock_quote_analayze\tools\nginx-1.28.0"
```

## 5. 发布流程说明

`deploy.ps1`（本地）会：

1. 在本地对 **`admin`** 执行 **`npm install`** 与 **`npm run build`**（需本机已安装 Node/npm）
2. 在项目根执行 **`python package.py`**（默认 `--format zip --output dist`，可用 `-PackageProjectRoot` 指定其它工程根；`-SkipPackagePy` 可跳过）。说明：`package.py` 会在 `dist` 下额外生成 **`stock_quote_analyze_*.zip`**；与下面第 3 步的 **`stock_quote_release_*.zip`** 不是同一个文件。
3. 再打 **`stock_quote_release_*.zip`**（**不包含** 顶层 `.git`、`.cursor`、`dist`、`node_modules` 等；并用临时目录 + **`robocopy`** 排除各目录下 **`node_modules` / `__pycache__`** 后再压缩；远端 **`release.ps1`** 仍会 **`npm install`**）
4. **默认到此结束**，终端会打印 **手工上传** 与 **`release.ps1`** 示例命令。
5. **仅当指定 `-RemoteDeploy`** 时：再通过 **`scp` / `ssh`** 上传并远端执行 **`release.ps1`**。

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

## 9. 目录布局示例：源码 / 运行 / Nginx 分开放置

部分环境将仓库与运行、Nginx 分开，例如：

| 用途 | 示例路径 |
|------|----------|
| 源码（git 检出） | `C:\work\stock_quote_analayze\src` |
| 历史/手工运行目录 | `C:\work\stock_quote_analayze\run` |
| Nginx 安装目录 | `C:\work\stock_quote_analayze\tools\nginx-1.28.0` |

与本文 **DeployRoot** 约定（`releases` / `current` / `shared`）的对应关系：

- 建议将 **DeployRoot** 设为项目根，例如 `C:\work\stock_quote_analayze`，则发布后的**当前运行代码根**为 `C:\work\stock_quote_analayze\current`（NSSM 工作目录即此目录）。原 `run` 若曾用于放置运行文件，可逐步迁到 `current` 与 `shared`，或仅保留为备份，以 `current` 为准。

### `run` 与 `current` 怎么对应

两者表示的是**同一类目录**：「当前对外提供服务的代码与资源根」，只是命名来自不同时期。

| 概念 | 路径（示例） | 说明 |
|------|----------------|------|
| 手工/习惯上的运行目录 | `...\run` | 以前可能把构建产物、静态站、或整份运行树放在这里 |
| 一键部署约定的运行目录 | `...\current` | `release.ps1` 每次发布会把新版本解压/轮换到这里；**NSSM 的 AppDirectory 应指向这里**（见 `install_services.ps1`） |

**推荐约定（单一真相源）：**

1. **以后只认 `current`**：发布、重启服务、排障都以 `DeployRoot\current` 为准。
2. **原 `run` 的处理**：  
   - 若里面仅有可被新版本覆盖的内容：可改名为 `run_backup_YYYYMMDD` 备查，避免与新建的 `current` 混淆。  
   - 若 Nginx 仍配置 `root .../run/...`，应改为指向 `.../current/...`（或见下「目录联接」过渡方案）。
3. **可选过渡——目录联接（仅当 Windows 上短期无法改 Nginx）**：让 **`run` 作为指向 `current` 的联接**，则旧配置里的 `/run/` 路径仍指向当前版本（物理上与 `current` 同一块目录）。**管理员 CMD** 示例（**必须先**不存在名为 `run` 的文件夹；若已有则先 `ren run run_backup`）：

```bat
cd /d C:\work\stock_quote_analayze
mklink /J run current
```

（执行前请确认目录 **`current` 已存在**，例如已完成至少一次 `release.ps1` 发布；且 **`run` 不能已是同名文件夹**，需先改名或删除。）

注意：`mklink /J run current` 表示「名为 `run` 的联接 → 指向目录 `current`」。若你希望反过来保持文件夹名叫 `run` 而脚本仍写 `current`，更稳妥的做法仍是：**统一把 Nginx/NSSM 配置改为使用 `current`**，联接仅作临时兼容。

**不要**长期同时维护两套互相拷贝的 `run` 与 `current`，否则会出现「发布更新了 `current` 但 Nginx 仍读 `run`」的不一致。
- **`src` 仅作 Git 工作副本**时，本地 `deploy.ps1` 里 **首次** 远端的 `release.ps1` 需指向服务器上**已存在**的脚本，例如：`-ServerReleaseScript "C:\work\stock_quote_analayze\src\scripts\deploy\release.ps1"`；待完成一次发布生成 `current` 后，可改为 `...\current\scripts\deploy\release.ps1`。
- Nginx 未加入系统 **PATH** 时，在发布参数中增加 **Nginx 根目录**（与 `release.ps1` 的 `-NginxHome` 一致）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy\deploy.ps1 `
  -ServerHost "你的CVM公网IP" `
  -ServerUser "Administrator" `
  -ServerDeployRoot "C:\work\stock_quote_analayze" `
  -ServerReleaseScript "C:\work\stock_quote_analayze\src\scripts\deploy\release.ps1" `
  -RemoteTempDir "C:\work\stock_quote_analayze\tmp" `
  -ServerNginxHome "C:\work\stock_quote_analayze\tools\nginx-1.28.0"
```

服务器侧手工校验 Nginx 时，也应使用该目录下的 `nginx.exe`：

```powershell
& "C:\work\stock_quote_analayze\tools\nginx-1.28.0\nginx.exe" -t
```
