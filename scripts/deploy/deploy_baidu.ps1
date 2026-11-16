# 百度云 Windows：本地打包 → scp → ssh 执行 current\scripts\deploy\prod_release.ps1
# → 在新的 current 目录执行 scripts\db_migrate.py upgrade --yes
# 远端发布参数与服务器上双击 prod_release.bat 一致（ManualProcessDeploy，不跑服务器 npm）。
# 用法（仓库根目录）:
#   powershell -ExecutionPolicy Bypass -File .\scripts\deploy\deploy_baidu.ps1
#   .\deploy_baidu.bat
#   .\deploy_baidu.bat -PackOnly
#   .\deploy_baidu.bat -SkipAdminBuild
#   .\deploy_baidu.bat -WhatIf
#   .\deploy_baidu.bat -SkipDbMigrate
#
# 环境变量覆盖:
#   BAIDU_SSH_KEY / BAIDU_HOST / BAIDU_USER

param(
    [string]$ServerHost = "",
    [string]$ServerUser = "",
    [string]$SshKeyPath = "",
    [string]$RemoteTempDir = "C:\work\stock_quote_analayze\tmp",
    [string]$DeployRoot = "C:\work\stock_quote_analayze",
    [string]$ReleaseScript = "C:\work\stock_quote_analayze\current\scripts\deploy\prod_release.ps1",
    [string]$PythonExe = "C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe",
    [string]$NginxHome = "C:\work\stock_quote_analayze\tools\nginx-1.28.0",
    [switch]$PackOnly,
    [switch]$SkipAdminBuild,
    [switch]$WhatIf,
    # 默认发布成功后执行 alembic upgrade；跳过则加 -SkipDbMigrate
    [switch]$SkipDbMigrate
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

function Convert-ToWinPath([string]$Path) {
    return (($Path -replace '/', '\').TrimEnd('\'))
}

function Convert-ToScpPath([string]$Path) {
    return (($Path -replace '\\', '/').TrimEnd('/'))
}

function Assert-NoSpacePath([string]$Label, [string]$Path) {
    if ($Path -match '\s') {
        throw ("{0} contains space and cannot be passed through Windows ssh/cmd safely: {1}" -f $Label, $Path)
    }
}

function Resolve-BaiduSshKey([string]$Hint) {
    if (-not [string]::IsNullOrWhiteSpace($Hint) -and (Test-Path -LiteralPath $Hint)) {
        return (Resolve-Path -LiteralPath $Hint).Path
    }
    $candidates = @(
        $env:BAIDU_SSH_KEY,
        (Join-Path $env:USERPROFILE ".ssh\id_ed25519"),
        (Join-Path $env:USERPROFILE ".ssh\id_rsa")
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) {
            return (Resolve-Path -LiteralPath $c).Path
        }
    }
    return $null
}

try {
    if ([string]::IsNullOrWhiteSpace($ServerHost)) {
        if (-not [string]::IsNullOrWhiteSpace($env:BAIDU_HOST)) {
            $ServerHost = $env:BAIDU_HOST.Trim()
        }
        else {
            $ServerHost = "106.12.156.20"
        }
    }
    if ([string]::IsNullOrWhiteSpace($ServerUser)) {
        if (-not [string]::IsNullOrWhiteSpace($env:BAIDU_USER)) {
            $ServerUser = $env:BAIDU_USER.Trim()
        }
        else {
            $ServerUser = "administrator"
        }
    }

    $RemoteTempDir = Convert-ToWinPath $RemoteTempDir
    $DeployRoot = Convert-ToWinPath $DeployRoot
    $ReleaseScript = Convert-ToWinPath $ReleaseScript
    $PythonExe = Convert-ToWinPath $PythonExe
    $NginxHome = Convert-ToWinPath $NginxHome

    $resolvedKey = Resolve-BaiduSshKey -Hint $SshKeyPath
    $packScript = Join-Path $PSScriptRoot "deploy.ps1"
    if (-not (Test-Path -LiteralPath $packScript)) {
        throw "deploy.ps1 not found: $packScript"
    }

    Write-Host "========================================"
    Write-Host " Baidu Windows public deploy"
    Write-Host " Host      : $ServerUser@$ServerHost"
    Write-Host " Key       : $(if ($resolvedKey) { $resolvedKey } else { '(none)' })"
    Write-Host " RemoteDir : $RemoteTempDir"
    Write-Host " Release   : $ReleaseScript"
    Write-Host " DeployRoot: $DeployRoot"
    Write-Host " PackOnly  : $PackOnly"
    Write-Host " DbMigrate : $(if ($SkipDbMigrate) { 'skip' } else { 'alembic upgrade (default)' })"
    Write-Host "========================================"
    Write-Host ""

    if (-not $PackOnly) {
        foreach ($tool in @("ssh", "scp")) {
            if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
                throw ("Required tool not found in PATH: {0} (install OpenSSH Client)" -f $tool)
            }
        }
        if (-not $resolvedKey -and -not $WhatIf) {
            throw "SSH key not found. Set BAIDU_SSH_KEY or place %USERPROFILE%\.ssh\id_ed25519"
        }
    }

    $sshTarget = "$ServerUser@$ServerHost"
    $sshBase = @("-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "-o", "StrictHostKeyChecking=accept-new")
    if ($resolvedKey) {
        $sshBase += "-i", $resolvedKey
    }

    if ($WhatIf) {
        Write-Host "[WhatIf] Would run: powershell -NoProfile -ExecutionPolicy Bypass -File $packScript$(if ($SkipAdminBuild) { ' -SkipAdminBuild' })" -ForegroundColor Yellow
        if (-not $PackOnly) {
            Write-Host "[WhatIf] Would scp latest zip to ${sshTarget}:$(Convert-ToScpPath $RemoteTempDir)/" -ForegroundColor Yellow
            Write-Host "[WhatIf] Would ssh run prod_release.ps1 -PackagePath <remote-zip> -DeployRoot $DeployRoot -ManualProcessDeploy" -ForegroundColor Yellow
            if (-not $SkipDbMigrate) {
                $currentRoot = Join-Path $DeployRoot "current"
                Write-Host "[WhatIf] Would ssh: cd /d $currentRoot && $PythonExe scripts\db_migrate.py upgrade --yes" -ForegroundColor Yellow
            }
        }
        exit 0
    }

    Write-Step "Local pack via deploy.ps1"
    $packArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $packScript)
    if ($SkipAdminBuild) {
        $packArgs += "-SkipAdminBuild"
    }
    $p = Start-Process -FilePath "powershell.exe" -ArgumentList $packArgs -Wait -PassThru -NoNewWindow
    if ($null -eq $p -or $p.ExitCode -ne 0) {
        $code = if ($null -eq $p) { -1 } else { $p.ExitCode }
        throw ("deploy.ps1 failed, exit code: {0}" -f $code)
    }

    $projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\")
    $localDist = Join-Path $projectRoot "dist"
    $latest = Get-ChildItem -LiteralPath $localDist -Filter "stock_quote_release_*.zip" -File -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if ($null -eq $latest) {
        throw "No zip found: $localDist\stock_quote_release_*.zip"
    }

    Write-Host ("Selected zip (by name date): {0}" -f $latest.FullName) -ForegroundColor Green
    Write-Host ("Modified                  : {0}" -f $latest.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))
    Write-Host ("Size                      : {0:N2} MB" -f ($latest.Length / 1MB))
    Write-Host ""

    if ($PackOnly) {
        Write-Host "=== PackOnly: skip upload/release ===" -ForegroundColor Green
        Write-Host ("Release zip: {0}" -f $latest.FullName)
        exit 0
    }

    $remoteZipWin = Join-Path $RemoteTempDir $latest.Name
    $remoteZipScp = (Convert-ToScpPath $RemoteTempDir) + "/" + $latest.Name
    foreach ($pair in @(
            @("RemoteTempDir", $RemoteTempDir),
            @("ReleaseScript", $ReleaseScript),
            @("DeployRoot", $DeployRoot),
            @("PythonExe", $PythonExe),
            @("NginxHome", $NginxHome),
            @("remote zip", $remoteZipWin)
        )) {
        Assert-NoSpacePath -Label $pair[0] -Path $pair[1]
    }

    Write-Step "Ensure remote temp dir"
    Invoke-DeployCommand -Program "ssh" -Arguments ($sshBase + $sshTarget + ("cmd /c if not exist {0} mkdir {0}" -f $RemoteTempDir))

    Write-Step "Upload zip via scp"
    Invoke-DeployCommand -Program "scp" -Arguments ($sshBase + $latest.FullName + ($sshTarget + ":" + $remoteZipScp))

    Write-Step "Remote prod_release.ps1"
    # 远端默认 shell 是 cmd.exe。路径无空格，整段作为一条远程命令，避免引号被吃掉。
    $remoteCmd = @(
        "powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ReleaseScript",
        "-PackagePath $remoteZipWin",
        "-DeployRoot $DeployRoot",
        "-PythonExe $PythonExe",
        "-NginxHome $NginxHome"
    ) -join " "
    Invoke-DeployCommand -Program "ssh" -Arguments ($sshBase + $sshTarget + $remoteCmd)

    if (-not $SkipDbMigrate) {
        Write-Step "Remote Alembic upgrade"
        # 必须在发布切换 current 之后执行，才能用到新包里的 revision。
        # alembic.ini 的 script_location 相对当前目录，所以先 cd 到 current。
        $currentRoot = Join-Path $DeployRoot "current"
        Assert-NoSpacePath -Label "current" -Path $currentRoot
        $migrateCmd = "cd /d $currentRoot && $PythonExe scripts\db_migrate.py upgrade --yes"
        Invoke-DeployCommand -Program "ssh" -Arguments ($sshBase + $sshTarget + $migrateCmd)
    }

    Write-Host ""
    Write-Host "=== Baidu deploy completed ===" -ForegroundColor Green
    Write-Host "URL: https://www.icemaplecity.com/  |  https://www.icemaplecity.com/admin/"
    exit 0
}
catch {
    Write-Host ""
    Write-Host ("[ERROR] {0}" -f $_.Exception.Message) -ForegroundColor Red
    exit 1
}
