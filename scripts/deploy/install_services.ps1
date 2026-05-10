# 注册 NSSM 服务。默认不执行 pip；首次缺依赖可加 -PreparePython（PIP_USER=0 装入 Lib\site-packages）。依赖也可由 release.ps1 预装。
param(
    [string]$DeployRoot = "C:\deploy\stock_quote",
    [string]$PythonExe = "python",
    [string]$NssmExe = "C:\work\stock_quote_analayze\tools\nssm.exe",
    # 首次部署或服务报 ModuleNotFoundError 时加上：用 PIP_USER=0 装入 Lib\site-packages（与 NSSM LocalSystem 一致）
    [switch]$PreparePython,
    [switch]$StartAfterInstall
)

$ErrorActionPreference = "Stop"

# PS5.1：原生程序写 stderr 会变成 ErrorRecord；在 Stop 策略下可能误判为失败并中断。
# NSSM 常把正常提示写到 stderr，故统一用此包装调用。
function Invoke-Nssm {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $old = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $null = & $NssmExe @Arguments 2>&1
        return $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $old
    }
}

# NSSM 以服务账户运行，通常拿不到交互式 PATH；必须用 python.exe 绝对路径。
function Resolve-PythonExeToFullPath([string]$Preferred) {
    $s = [string]$Preferred
    if ([string]::IsNullOrWhiteSpace($s)) {
        $s = "python"
    }
    else {
        $s = $s.Trim()
        if ([string]::IsNullOrWhiteSpace($s)) {
            $s = "python"
        }
    }
    if ([System.IO.Path]::IsPathRooted($s) -and (Test-Path -LiteralPath $s)) {
        return (Resolve-Path -LiteralPath $s).Path
    }
    $cmd = Get-Command -Name $s -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $cmd -and $cmd.Source) {
        $p = $cmd.Source.Trim()
        if (Test-Path -LiteralPath $p) {
            return (Resolve-Path -LiteralPath $p).Path
        }
    }
    if ($env:OS -eq 'Windows_NT') {
        $whereExe = Join-Path $env:SystemRoot "System32\where.exe"
        if (Test-Path -LiteralPath $whereExe) {
            $raw = @(& $whereExe $s 2>$null)
            foreach ($item in @($raw)) {
                $line = ([string]$item).Trim()
                if (-not [string]::IsNullOrWhiteSpace($line) -and (Test-Path -LiteralPath $line)) {
                    return (Resolve-Path -LiteralPath $line).Path
                }
            }
        }
    }
    throw "无法解析 python.exe。NSSM 服务环境无 PATH 时请传入完整路径，例如: -PythonExe 'C:\Python313\python.exe'"
}

function Ensure-Service([string]$ServiceName, [string]$ScriptPath, [string]$WorkDir, [string]$StdoutFile, [string]$StderrFile) {
    if (-not (Test-Path -LiteralPath $ScriptPath)) {
        throw "脚本不存在: $ScriptPath"
    }

    $exists = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($null -ne $exists) {
        $null = Invoke-Nssm @('remove', $ServiceName, 'confirm')
        $deadline = (Get-Date).AddSeconds(90)
        while ((Get-Date) -lt $deadline) {
            $gone = $null -eq (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)
            if ($gone) { break }
            Start-Sleep -Seconds 3
        }
        Start-Sleep -Seconds 2
    }

    $installed = $false
    for ($i = 1; $i -le 8; $i++) {
        $null = Invoke-Nssm @('install', $ServiceName, $PythonExe, $ScriptPath)
        Start-Sleep -Milliseconds 800
        if ($null -ne (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)) {
            $installed = $true
            break
        }
        Write-Host "[WARN] nssm install retry $i/8 ($ServiceName): service not visible yet (marked-for-delete cooldown?)" -ForegroundColor Yellow
        Start-Sleep -Seconds 6
    }
    if (-not $installed) {
        throw "NSSM install failed: $ServiceName (still missing after retries). Try: reboot, then run this script again; or sc.exe delete $ServiceName if stuck."
    }

    $null = Invoke-Nssm @('set', $ServiceName, 'AppDirectory', $WorkDir)
    $null = Invoke-Nssm @('set', $ServiceName, 'Start', 'SERVICE_AUTO_START')
    $null = Invoke-Nssm @('set', $ServiceName, 'AppStdout', $StdoutFile)
    $null = Invoke-Nssm @('set', $ServiceName, 'AppStderr', $StderrFile)
    $null = Invoke-Nssm @('set', $ServiceName, 'AppRotateFiles', '1')
    $null = Invoke-Nssm @('set', $ServiceName, 'AppRotateOnline', '1')
    $null = Invoke-Nssm @('set', $ServiceName, 'AppRotateSeconds', '86400')
    $null = Invoke-Nssm @('set', $ServiceName, 'AppExit', 'Default', 'Restart')
    # PYTHONNOUSERSITE=1：禁止读 Administrator 的 Roaming site-packages；依赖须装在 Lib\site-packages（与 release.ps1 PIP_USER=0 一致）
    $null = Invoke-Nssm @('set', $ServiceName, 'AppEnvironmentExtra', 'PYTHONUTF8=1 PYTHONNOUSERSITE=1')

    Write-Host "[OK] Service installed: $ServiceName"
}

if (-not (Test-Path -LiteralPath $NssmExe)) {
    throw "未找到 NSSM: $NssmExe"
}

$PythonExe = Resolve-PythonExeToFullPath $PythonExe
Write-Host "[INFO] NSSM will use Python: $PythonExe"

$current = Join-Path $DeployRoot "current"
$sharedLogs = Join-Path $DeployRoot "shared\logs"

if (-not (Test-Path -LiteralPath $current)) {
    throw "未找到 current 目录，请先执行一次 release.ps1: $current"
}

New-Item -ItemType Directory -Path $sharedLogs -Force | Out-Null

if ($PreparePython) {
    $prodReq = Join-Path $current "requirements-prod.txt"
    if (-not (Test-Path -LiteralPath $prodReq)) {
        throw "未找到 $prodReq ，请先 release.ps1 部署 current"
    }
    Write-Host "[INFO] pip install -r requirements-prod.txt (PIP_USER=0 -> Lib\site-packages) ..."
    $savedPipUser = $env:PIP_USER
    $env:PIP_USER = '0'
    try {
        $p = Start-Process -FilePath $PythonExe -ArgumentList @('-m', 'pip', 'install', '-r', $prodReq) -WorkingDirectory $current -Wait -PassThru -NoNewWindow
        if ($null -eq $p.ExitCode -or $p.ExitCode -ne 0) {
            throw ("pip install failed (exit {0})" -f $p.ExitCode)
        }
    }
    finally {
        if ($null -eq $savedPipUser) {
            Remove-Item Env:\PIP_USER -ErrorAction SilentlyContinue
        }
        else {
            $env:PIP_USER = $savedPipUser
        }
    }
    Write-Host "[OK] Python deps refreshed for system site-packages."
}

Ensure-Service `
    -ServiceName "stock-quote-api" `
    -ScriptPath (Join-Path $current "start_backend_api.py") `
    -WorkDir $current `
    -StdoutFile (Join-Path $sharedLogs "stock-quote-api.out.log") `
    -StderrFile (Join-Path $sharedLogs "stock-quote-api.err.log")

Ensure-Service `
    -ServiceName "stock-quote-core" `
    -ScriptPath (Join-Path $current "start_backend_core.py") `
    -WorkDir $current `
    -StdoutFile (Join-Path $sharedLogs "stock-quote-core.out.log") `
    -StderrFile (Join-Path $sharedLogs "stock-quote-core.err.log")

Ensure-Service `
    -ServiceName "stock-quote-notify" `
    -ScriptPath (Join-Path $current "start_scheduler.py") `
    -WorkDir $current `
    -StdoutFile (Join-Path $sharedLogs "stock-quote-notify.out.log") `
    -StderrFile (Join-Path $sharedLogs "stock-quote-notify.err.log")

if ($StartAfterInstall) {
    $startPairs = @(
        @{ Name = "stock-quote-api"; Err = (Join-Path $sharedLogs "stock-quote-api.err.log") },
        @{ Name = "stock-quote-core"; Err = (Join-Path $sharedLogs "stock-quote-core.err.log") },
        @{ Name = "stock-quote-notify"; Err = (Join-Path $sharedLogs "stock-quote-notify.err.log") }
    )
    $anyFail = $false
    foreach ($sp in $startPairs) {
        $nm = $sp.Name
        try {
            $svc0 = Get-Service -Name $nm -ErrorAction SilentlyContinue
            if ($null -ne $svc0 -and $svc0.Status -eq 'Running') {
                Write-Host ("[OK] Already running: {0}" -f $nm)
                continue
            }
            Start-Service -Name $nm -ErrorAction Stop
        }
        catch {
            # Start-Service 在部分环境下会抛错，但子进程已拉起（尤其是 api 多 worker）；以下用状态为准
        }
        Start-Sleep -Seconds 3
        $svc = Get-Service -Name $nm -ErrorAction SilentlyContinue
        if ($null -ne $svc -and $svc.Status -eq 'Running') {
            Write-Host ("[OK] Started: {0}" -f $nm)
            continue
        }
        $anyFail = $true
        Write-Host ("[ERROR] Not running: {0} (status={1})" -f $nm, $(if ($null -ne $svc) { $svc.Status } else { 'missing' })) -ForegroundColor Red
        if (Test-Path -LiteralPath $sp.Err) {
            Write-Host ("[INFO] Last lines of stderr ({0}):" -f $sp.Err) -ForegroundColor Yellow
            Get-Content -LiteralPath $sp.Err -Tail 40 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host $_ }
        }
        else {
            Write-Host "[INFO] No stderr log yet." -ForegroundColor Yellow
        }
    }
    if ($anyFail) {
        $pipHint = Join-Path $current "requirements-prod.txt"
        Write-Host "[HINT] Run install_services.ps1 with -PreparePython (installs requirements-prod into Lib\site-packages), or manually:" -ForegroundColor Cyan
        Write-Host ('  $env:PIP_USER=''0''; & "{0}" -m pip install -r "{1}"' -f $PythonExe, $pipHint) -ForegroundColor Cyan
        Write-Host "[HINT] Redeploy current via release.ps1 if start_backend_core.py still shows emoji in stderr." -ForegroundColor Cyan
        throw "One or more services failed to start. Fix Python path or check logs under shared\logs."
    }
    Write-Host "[OK] All services running."
}

Write-Host "Done. Get-Service stock-quote-*"
