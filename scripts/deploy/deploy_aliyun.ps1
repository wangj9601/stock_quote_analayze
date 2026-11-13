# 阿里云 Ubuntu 公网：本地打包 → scp → ssh 执行 linux/release.sh → Alembic upgrade
# 用法（仓库根目录）:
#   powershell -ExecutionPolicy Bypass -File .\scripts\deploy\deploy_aliyun.ps1
#   .\deploy_aliyun.bat
#   .\deploy_aliyun.bat -PackOnly
#   .\deploy_aliyun.bat -SkipAdminBuild
#   .\deploy_aliyun.bat -WhatIf
#   .\deploy_aliyun.bat -SkipDbMigrate
#   .\deploy_aliyun.bat -RunRecentMigrations            # 额外跑 migrations/*.py（mtime，默认 3 天）
#   .\deploy_aliyun.bat -RunRecentMigrations -MigrationDays 5
#
# 环境变量覆盖:
#   ALIYUN_SSH_KEY / ALIYUN_HOST / ALIYUN_USER

param(
    [string]$ServerHost = "",
    [string]$ServerUser = "",
    [string]$SshKeyPath = "",
    [string]$RemoteTempDir = "/tmp",
    [string]$DeployRoot = "/opt/stock_quote",
    [string]$ReleaseScript = "",
    [string]$RunProdScript = "",
    [switch]$PackOnly,
    [switch]$SkipAdminBuild,
    [switch]$WhatIf,
    [switch]$SkipHealth,
    # 默认发布后执行 alembic upgrade；跳过则加 -SkipDbMigrate
    [switch]$SkipDbMigrate,
    # 可选：再按 mtime 跑 migrations/*.py（已弃用路径，仅应急）
    [switch]$RunRecentMigrations,
    [int]$MigrationDays = 3
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Msg) {
    Write-Host "==> $Msg" -ForegroundColor Cyan
}

function Invoke-DeployCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Program,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw ("Command failed: {0} {1}" -f $Program, ($Arguments -join ' '))
    }
}

function Restrict-SshPrivateKeyAcl([string]$KeyPath) {
    # OpenSSH on Windows rejects keys with "too open" ACLs (common under Downloads).
    if ([string]::IsNullOrWhiteSpace($KeyPath) -or -not (Test-Path -LiteralPath $KeyPath)) {
        return
    }
    $user = if (-not [string]::IsNullOrWhiteSpace($env:USERNAME)) { $env:USERNAME } else { [Environment]::UserName }
    Write-Host ("Locking SSH key ACL for current user only: {0}" -f $KeyPath) -ForegroundColor Yellow
    & icacls.exe $KeyPath /inheritance:r | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw ("icacls /inheritance:r failed for key: {0}" -f $KeyPath)
    }
    & icacls.exe $KeyPath /grant:r "${user}:(R)" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw ("icacls /grant failed for key: {0}" -f $KeyPath)
    }
}

function Resolve-AliyunSshKey([string]$Hint) {
    if (-not [string]::IsNullOrWhiteSpace($Hint) -and (Test-Path -LiteralPath $Hint)) {
        $resolved = (Resolve-Path -LiteralPath $Hint).Path
        Restrict-SshPrivateKeyAcl -KeyPath $resolved
        return $resolved
    }
    $sshDir = Join-Path $env:USERPROFILE ".ssh"
    $securePemName = "qidianspacetime-2023-12-30.pem"
    $securePem = Join-Path $sshDir $securePemName
    $downloadsPem = Join-Path $env:USERPROFILE "Downloads\$securePemName"

    # Prefer ~/.ssh copy; if only Downloads has it, copy then lock ACL (Downloads is often too open).
    if (-not (Test-Path -LiteralPath $securePem) -and (Test-Path -LiteralPath $downloadsPem)) {
        if (-not (Test-Path -LiteralPath $sshDir)) {
            New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
        }
        Copy-Item -LiteralPath $downloadsPem -Destination $securePem -Force
        Write-Host ("Copied SSH key to safer path: {0}" -f $securePem) -ForegroundColor Yellow
    }

    $candidates = @(
        $env:ALIYUN_SSH_KEY,
        $securePem,
        $downloadsPem,
        (Join-Path $env:USERPROFILE ".ssh\id_ed25519"),
        (Join-Path $env:USERPROFILE ".ssh\id_rsa")
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) {
            $resolved = (Resolve-Path -LiteralPath $c).Path
            Restrict-SshPrivateKeyAcl -KeyPath $resolved
            return $resolved
        }
    }
    return $null
}

try {
    if ([string]::IsNullOrWhiteSpace($ServerHost)) {
        if (-not [string]::IsNullOrWhiteSpace($env:ALIYUN_HOST)) {
            $ServerHost = $env:ALIYUN_HOST.Trim()
        }
        else {
            $ServerHost = "47.99.185.87"
        }
    }
    if ([string]::IsNullOrWhiteSpace($ServerUser)) {
        if (-not [string]::IsNullOrWhiteSpace($env:ALIYUN_USER)) {
            $ServerUser = $env:ALIYUN_USER.Trim()
        }
        else {
            $ServerUser = "root"
        }
    }
    if ([string]::IsNullOrWhiteSpace($ReleaseScript)) {
        $ReleaseScript = "$DeployRoot/current/scripts/deploy/linux/release.sh"
    }
    if ([string]::IsNullOrWhiteSpace($RunProdScript)) {
        $RunProdScript = "$DeployRoot/run_prod.sh"
    }
    if ($MigrationDays -lt 1) {
        $MigrationDays = 3
    }

    $resolvedKey = Resolve-AliyunSshKey -Hint $SshKeyPath
    $packScript = Join-Path $PSScriptRoot "deploy.ps1"
    if (-not (Test-Path -LiteralPath $packScript)) {
        throw "deploy.ps1 not found: $packScript"
    }

    Write-Host "========================================"
    Write-Host " Aliyun Ubuntu public deploy"
    Write-Host " Host      : $ServerUser@$ServerHost"
    Write-Host " Key       : $(if ($resolvedKey) { $resolvedKey } else { '(none / agent or password)' })"
    Write-Host " RemoteDir : $RemoteTempDir"
    Write-Host " Release   : $ReleaseScript"
    Write-Host " PackOnly  : $PackOnly"
    Write-Host " DbMigrate : $(if ($SkipDbMigrate) { 'skip' } else { 'alembic upgrade (default)' })"
    Write-Host " MtimeMig  : $(if ($RunRecentMigrations) { "migrations/*.py last $MigrationDays day(s)" } else { 'skip (optional)' })"
    Write-Host "========================================"
    Write-Host ""

    if (-not $PackOnly) {
        foreach ($tool in @("ssh", "scp")) {
            if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
                throw ("Required tool not found in PATH: {0} (install OpenSSH Client)" -f $tool)
            }
        }
        if (-not $resolvedKey) {
            Write-Host "[WARN] SSH key not found. Will try default ssh agent / interactive auth." -ForegroundColor Yellow
            Write-Host "       Set ALIYUN_SSH_KEY or place pem at %USERPROFILE%\Downloads\qidianspacetime-2023-12-30.pem" -ForegroundColor Yellow
        }
    }

    Write-Step "Local pack via deploy.ps1"
    $packArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $packScript)
    if ($SkipAdminBuild) {
        $packArgs += "-SkipAdminBuild"
    }

    if ($WhatIf) {
        Write-Host "[WhatIf] Would run: powershell $($packArgs -join ' ')" -ForegroundColor Yellow
        if (-not $PackOnly) {
            Write-Host "[WhatIf] Would scp latest zip to ${ServerUser}@${ServerHost}:${RemoteTempDir}/" -ForegroundColor Yellow
            Write-Host "[WhatIf] Would ssh run: bash $ReleaseScript <remote-zip> $DeployRoot" -ForegroundColor Yellow
            if (-not $SkipDbMigrate -or $RunRecentMigrations) {
                Write-Host "[WhatIf] Would scp migrate.sh then: bash /tmp/stock_quote_aliyun_migrate.sh" -ForegroundColor Yellow
                if (-not $SkipDbMigrate) {
                    Write-Host "[WhatIf]   -> run_prod.sh scripts/db_migrate.py upgrade --yes" -ForegroundColor Yellow
                }
                if ($RunRecentMigrations) {
                    Write-Host "[WhatIf]   -> run_prod.sh scripts/run_recent_migrations.py --days $MigrationDays --yes --i-know-deprecated" -ForegroundColor Yellow
                }
            }
        }
        exit 0
    }

    $p = Start-Process -FilePath "powershell.exe" -ArgumentList $packArgs -Wait -PassThru -NoNewWindow
    if ($null -eq $p -or $p.ExitCode -ne 0) {
        $code = if ($null -eq $p) { -1 } else { $p.ExitCode }
        throw ("deploy.ps1 failed, exit code: {0}" -f $code)
    }

    $projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\")
    $localDist = Join-Path $projectRoot "dist"
    $latest = Get-ChildItem -LiteralPath $localDist -Filter "stock_quote_release_*.zip" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $latest) {
        throw "No zip found: $localDist\stock_quote_release_*.zip"
    }

    Write-Host ("Selected zip: {0}" -f $latest.FullName) -ForegroundColor Green
    Write-Host ("Modified   : {0}" -f $latest.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))
    Write-Host ("Size       : {0:N2} MB" -f ($latest.Length / 1MB))
    Write-Host ""

    if ($PackOnly) {
        Write-Host "=== PackOnly: skip upload/release ===" -ForegroundColor Green
        Write-Host ("Release zip: {0}" -f $latest.FullName)
        exit 0
    }

    $sshTarget = "$ServerUser@$ServerHost"
    $sshArgs = @("-o", "StrictHostKeyChecking=accept-new")
    $scpArgs = @("-o", "StrictHostKeyChecking=accept-new")
    if ($resolvedKey) {
        $sshArgs += "-i", $resolvedKey
        $scpArgs += "-i", $resolvedKey
    }

    $remoteZipPath = ($RemoteTempDir.TrimEnd("/") + "/" + $latest.Name)

    Write-Step "Upload zip via scp"
    Invoke-DeployCommand -Program "scp" -Arguments ($scpArgs + $latest.FullName + ($sshTarget + ":" + $remoteZipPath))

    Write-Step "Remote linux/release.sh"
    # Prefer current release.sh; fall back to unzipping scripts from the new zip if current is missing.
    # Use single-quoted fragments so PowerShell does not expand bash $vars.
    $healthPrefix = if ($SkipHealth) { 'SKIP_HEALTH=1 ' } else { '' }
    $remoteCmd = (
        'set -euo pipefail; ' +
        "REMOTE_ZIP='$remoteZipPath'; " +
        "DEPLOY_ROOT='$DeployRoot'; " +
        "REL='$ReleaseScript'; " +
        'if [ ! -f "$REL" ]; then ' +
        '  echo "[deploy_aliyun] current release.sh missing; bootstrap from uploaded zip"; ' +
        '  BOOT=/tmp/stock_quote_boot_deploy; ' +
        '  rm -rf "$BOOT"; mkdir -p "$BOOT"; ' +
        '  unzip -q "$REMOTE_ZIP" -d "$BOOT" || true; ' +
        '  if [ -f "$BOOT/scripts/deploy/linux/release.sh" ]; then REL="$BOOT/scripts/deploy/linux/release.sh"; ' +
        '  else INNER=$(find "$BOOT" -maxdepth 3 -type f -path "*/scripts/deploy/linux/release.sh" | head -n1); ' +
        '       REL="$INNER"; fi; ' +
        '  test -f "$REL" || { echo "release.sh not found in zip" >&2; exit 1; }; ' +
        'fi; ' +
        $healthPrefix +
        'bash "$REL" "$REMOTE_ZIP" "$DEPLOY_ROOT"'
    )

    Invoke-DeployCommand -Program "ssh" -Arguments ($sshArgs + $sshTarget + $remoteCmd)

    # 发布成功后：优先 Alembic；mtime 脚本仅 -RunRecentMigrations 时追加。
    # 不用 ssh 内联复杂引号（Windows OpenSSH 易触发 unexpected EOF matching '"'）；
    # 改为 scp 一段 LF 脚本再 bash 执行。
    if (-not $SkipDbMigrate -or $RunRecentMigrations) {
        Write-Step "Remote DB migrate"
        $migrateLines = New-Object System.Collections.Generic.List[string]
        [void]$migrateLines.Add('#!/usr/bin/env bash')
        [void]$migrateLines.Add('set -euo pipefail')
        [void]$migrateLines.Add(('DEPLOY_ROOT={0}' -f $DeployRoot))
        [void]$migrateLines.Add(('RUN_PROD={0}' -f $RunProdScript))
        [void]$migrateLines.Add('run_app() {')
        [void]$migrateLines.Add('  if [ -x "$RUN_PROD" ]; then')
        [void]$migrateLines.Add('    bash "$RUN_PROD" "$@"')
        [void]$migrateLines.Add('  else')
        [void]$migrateLines.Add('    echo "[deploy_aliyun] run_prod.sh missing, fallback dotenv+venv" >&2')
        [void]$migrateLines.Add('    cd "$DEPLOY_ROOT/current"')
        [void]$migrateLines.Add('    sudo -u stockquote "$DEPLOY_ROOT/.venv/bin/python" -m dotenv -f "$DEPLOY_ROOT/shared/.env" run -- \')
        [void]$migrateLines.Add('      "$DEPLOY_ROOT/.venv/bin/python" "$@"')
        [void]$migrateLines.Add('  fi')
        [void]$migrateLines.Add('}')
        if (-not $SkipDbMigrate) {
            [void]$migrateLines.Add('echo "[deploy_aliyun] alembic: scripts/db_migrate.py upgrade --yes"')
            [void]$migrateLines.Add('run_app scripts/db_migrate.py upgrade --yes')
        }
        if ($RunRecentMigrations) {
            [void]$migrateLines.Add(('echo "[deploy_aliyun] optional mtime migrations: last {0} day(s)"' -f $MigrationDays))
            [void]$migrateLines.Add(('run_app scripts/run_recent_migrations.py --days {0} --yes --i-know-deprecated' -f $MigrationDays))
        }
        $migrateBody = ($migrateLines -join "`n") + "`n"
        $localMigrate = Join-Path ([System.IO.Path]::GetTempPath()) ("stock_quote_aliyun_migrate_{0}.sh" -f [guid]::NewGuid().ToString("N"))
        $remoteMigrate = ($RemoteTempDir.TrimEnd("/") + "/stock_quote_aliyun_migrate.sh")
        try {
            $utf8NoBom = New-Object System.Text.UTF8Encoding $false
            [System.IO.File]::WriteAllText($localMigrate, $migrateBody, $utf8NoBom)
            Invoke-DeployCommand -Program "scp" -Arguments ($scpArgs + $localMigrate + ($sshTarget + ":" + $remoteMigrate))
            Invoke-DeployCommand -Program "ssh" -Arguments ($sshArgs + $sshTarget + ("bash '{0}'" -f $remoteMigrate))
        }
        finally {
            if (Test-Path -LiteralPath $localMigrate) {
                Remove-Item -LiteralPath $localMigrate -Force -ErrorAction SilentlyContinue
            }
        }
    }

    Write-Host ""
    Write-Host "=== Aliyun deploy completed ===" -ForegroundColor Green
    Write-Host "URL: https://www.xworld-wangxw.top/  |  https://admin.xworld-wangxw.top/"
    exit 0
}
catch {
    Write-Host ""
    Write-Host ("[ERROR] {0}" -f $_.Exception.Message) -ForegroundColor Red
    exit 1
}
