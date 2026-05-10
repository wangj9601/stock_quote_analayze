# UTF-8 BOM (first char): PS 5.1 正确解析中文；勿删文件首字节 BOM。
# 注册 NSSM 服务。默认：用即将写入 NSSM 的同一 python.exe 探测生产依赖，缺失则自动 pip（PIP_USER=0 -> Lib\site-packages，与 AppEnvironmentExtra=PYTHONNOUSERSITE=1 一致）。
# -PreparePython：无论是否已齐全都强制 pip。-SkipAutoPreparePython：关闭自动 pip（离线/自控）。依赖也可由 release.ps1 预装。
param(
    [string]$DeployRoot = "C:\deploy\stock_quote",
    [string]$PythonExe = "python",
    [string]$NssmExe = "C:\work\stock_quote_analayze\tools\nssm.exe",
    # 强制 pip install -r current\requirements-prod.txt（升级/修环境）
    [switch]$PreparePython,
    # 探测失败时不自动 pip（仍可与 -PreparePython 联用）
    [switch]$SkipAutoPreparePython,
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
    throw "Cannot resolve python.exe. Pass full path: -PythonExe 'C:\Python313\python.exe'"
}

function Test-LegacyEmojiStartBackendCore([string]$ScriptPath) {
    if (-not (Test-Path -LiteralPath $ScriptPath)) {
        return $false
    }
    try {
        $bytes = [System.IO.File]::ReadAllBytes($ScriptPath)
        $sig = [byte[]](0xF0, 0x9F, 0x93, 0x8A)
        for ($i = 0; $i -le $bytes.Length - $sig.Length; $i++) {
            $ok = $true
            for ($j = 0; $j -lt $sig.Length; $j++) {
                if ($bytes[$i + $j] -ne $sig[$j]) {
                    $ok = $false
                    break
                }
            }
            if ($ok) {
                return $true
            }
        }
    }
    catch {
    }
    try {
        $raw = Get-Content -LiteralPath $ScriptPath -Raw -Encoding UTF8 -ErrorAction Stop
        if ($null -ne $raw -and $raw.Contains('\U0001f4ca')) {
            return $true
        }
        if ($null -ne $raw -and $raw.IndexOf([char]0x1F4CA) -ge 0) {
            return $true
        }
    }
    catch {
    }
    return $false
}

function Sync-StartBackendCoreFromRepoRoot([string]$DeployRootParam) {
    try {
        $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
        $src = Join-Path $repoRoot 'start_backend_core.py'
        $dst = Join-Path $DeployRootParam 'current\start_backend_core.py'
        if (-not (Test-Path -LiteralPath $src)) {
            return
        }
        $need = $false
        if (-not (Test-Path -LiteralPath $dst)) {
            $need = $true
        }
        elseif (Test-LegacyEmojiStartBackendCore $dst) {
            $need = $true
        }
        else {
            try {
                $tx = Get-Content -LiteralPath $dst -Raw -Encoding UTF8 -ErrorAction Stop
                if ($tx -notmatch '\[START\] backend_core') {
                    $need = $true
                }
            }
            catch {
                $need = $true
            }
            if (-not $need) {
                $need = ((Get-Item -LiteralPath $src).LastWriteTimeUtc -gt (Get-Item -LiteralPath $dst).LastWriteTimeUtc)
            }
        }
        if ($need) {
            Copy-Item -LiteralPath $src -Destination $dst -Force
            Write-Host '[INFO] Synced start_backend_core.py from repo root into DeployRoot\current\.' -ForegroundColor Cyan
        }
    }
    catch {
        Write-Host ('[WARN] Sync start_backend_core skipped: ' + $_.Exception.Message) -ForegroundColor Yellow
    }
}

# 与 start_backend_core.py 依赖检查一致；仅用 NSSM 将绑定的解释器探测。
function Test-NssmPythonHasProdDeps([string]$PyExe) {
    $snippet = 'import requests,apscheduler,akshare,tushare,pandas'
    $p = Start-Process -FilePath $PyExe -ArgumentList @('-c', $snippet) -Wait -PassThru -NoNewWindow
    if ($null -eq $p.ExitCode) {
        return $false
    }
    return ($p.ExitCode -eq 0)
}

# 必须用此函数安装：PIP_USER=0，否则 PYTHONNOUSERSITE=1 下服务仍 ModuleNotFoundError。
function Install-RequirementsProdForNssmPython {
    param(
        [Parameter(Mandatory = $true)][string]$PythonExeFullPath,
        [Parameter(Mandatory = $true)][string]$RequirementsFile,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )
    Write-Host '[INFO] pip install -r requirements-prod.txt (PIP_USER=0 -> Lib\site-packages, same exe as NSSM) ...'
    $savedPipUser = $env:PIP_USER
    $env:PIP_USER = '0'
    try {
        $proc = Start-Process -FilePath $PythonExeFullPath -ArgumentList @('-m', 'pip', 'install', '-r', $RequirementsFile) -WorkingDirectory $WorkingDirectory -Wait -PassThru -NoNewWindow
        if ($null -eq $proc.ExitCode -or $proc.ExitCode -ne 0) {
            throw ("pip install failed (exit {0})" -f $proc.ExitCode)
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
    Write-Host '[OK] Python deps refreshed for system site-packages (matches NSSM interpreter).'
}

function Write-WarnBadPythonUtf8EnvironmentVariable {
    foreach ($scope in @('Machine', 'User')) {
        $pv = [Environment]::GetEnvironmentVariable('PYTHONUTF8', $scope)
        if ([string]::IsNullOrWhiteSpace($pv)) {
            continue
        }
        $t = $pv.Trim()
        if ($t.Length -gt 12 -or $t -match '\s') {
            Write-Host ('[WARN] PYTHONUTF8="{0}" ({1}) bad value; fix or remove in System Properties env.' -f $t, $scope) -ForegroundColor Yellow
        }
    }
}

function Ensure-Service([string]$ServiceName, [string]$ScriptPath, [string]$WorkDir, [string]$StdoutFile, [string]$StderrFile) {
    if (-not (Test-Path -LiteralPath $ScriptPath)) {
        throw ('Missing script: ' + $ScriptPath)
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
        Write-Host ('[WARN] nssm install retry {0}/8 ({1}): service not visible yet' -f $i, $ServiceName) -ForegroundColor Yellow
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
    # 仅一行：多行 AppEnvironmentExtra 在部分 NSSM/编码下仍会弄坏 PYTHONUTF8。PYTHONUTF8 请在系统环境变量中删除非法值。
    $null = Invoke-Nssm @('set', $ServiceName, 'AppEnvironmentExtra', 'PYTHONNOUSERSITE=1')

    Write-Host ('[OK] Service installed: ' + $ServiceName)
}

if (-not (Test-Path -LiteralPath $NssmExe)) {
    throw ('NSSM not found: ' + $NssmExe)
}

$PythonExe = Resolve-PythonExeToFullPath $PythonExe
Write-Host ('[INFO] NSSM will use Python: ' + $PythonExe)

$current = Join-Path $DeployRoot "current"
$sharedLogs = Join-Path $DeployRoot "shared\logs"

if (-not (Test-Path -LiteralPath $current)) {
    throw ('Missing current directory (run release.ps1 first): ' + $current)
}

Sync-StartBackendCoreFromRepoRoot $DeployRoot

$coreStart = Join-Path $current "start_backend_core.py"
$coreResolved = (Resolve-Path -LiteralPath $coreStart).Path
Write-Host '[INFO] Script path NSSM uses (must be DeployRoot\current\, not repo root):' -ForegroundColor DarkGray
Write-Host ('       ' + $coreResolved) -ForegroundColor DarkGray
try {
    $rawCorePeek = Get-Content -LiteralPath $coreResolved -Raw -Encoding UTF8 -ErrorAction Stop
    if ($rawCorePeek -notmatch '\[START\] backend_core') {
        Write-Host '[WARN] No literal [START] backend_core in file above. Often: only repo root was updated, not current\.' -ForegroundColor Yellow
    }
}
catch {
}
if (Test-LegacyEmojiStartBackendCore $coreStart) {
    throw ('Deploy blocked: legacy emoji in current\start_backend_core.py. Path checked: ' + $coreResolved)
}

Write-WarnBadPythonUtf8EnvironmentVariable

New-Item -ItemType Directory -Path $sharedLogs -Force | Out-Null

$prodReq = Join-Path $current "requirements-prod.txt"
$depsOk = Test-NssmPythonHasProdDeps $PythonExe
$didPip = $false

if ($PreparePython) {
    if (-not (Test-Path -LiteralPath $prodReq)) {
        throw ('Missing requirements file: ' + $prodReq)
    }
    Write-Host '[INFO] -PreparePython: forcing pip install against NSSM Python.' -ForegroundColor Cyan
    Install-RequirementsProdForNssmPython -PythonExeFullPath $PythonExe -RequirementsFile $prodReq -WorkingDirectory $current
    $didPip = $true
}
elseif (-not $SkipAutoPreparePython) {
    if (-not $depsOk) {
        if (-not (Test-Path -LiteralPath $prodReq)) {
            throw ('Python missing prod deps and requirements-prod.txt not found under current\: ' + $prodReq + ' (re-run release.ps1 or copy requirements-prod.txt).')
        }
        Write-Host '[INFO] NSSM Python lacks prod deps; auto pip with SAME exe (PIP_USER=0). No manual copy-paste needed.' -ForegroundColor Cyan
        Install-RequirementsProdForNssmPython -PythonExeFullPath $PythonExe -RequirementsFile $prodReq -WorkingDirectory $current
        $didPip = $true
    }
    else {
        Write-Host '[OK] Production imports OK on NSSM Python (requests/apscheduler/akshare/tushare/pandas).' -ForegroundColor DarkGray
    }
}
elseif (-not $depsOk) {
    Write-Host '[WARN] NSSM Python missing prod deps; -SkipAutoPreparePython set — NOT running pip. Add -PreparePython or fix env.' -ForegroundColor Yellow
}

if ($didPip) {
    $depsOkAfter = Test-NssmPythonHasProdDeps $PythonExe
    if (-not $depsOkAfter) {
        throw 'pip finished but prod imports still fail. Check stderr above, VPN/wheel, or Python version.'
    }
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
                Write-Host ('[OK] Already running: ' + $nm)
                continue
            }
            Start-Service -Name $nm -ErrorAction Stop
        }
        catch {
            # Start-Service may throw while workers already up; verify by status
        }
        Start-Sleep -Seconds 3
        $svc = Get-Service -Name $nm -ErrorAction SilentlyContinue
        if ($null -ne $svc -and $svc.Status -eq 'Running') {
            Write-Host ('[OK] Started: ' + $nm)
            continue
        }
        if ($null -ne $svc -and $svc.Status -eq 'Paused') {
            try {
                Resume-Service -Name $nm -ErrorAction Stop
                Start-Sleep -Seconds 3
                $svc = Get-Service -Name $nm -ErrorAction SilentlyContinue
                if ($null -ne $svc -and $svc.Status -eq 'Running') {
                    Write-Host ('[OK] Resumed: ' + $nm)
                    continue
                }
            }
            catch {
            }
        }
        $anyFail = $true
        Write-Host ('[ERROR] Not running: ' + $nm + ' (status=' + $(if ($null -ne $svc) { $svc.Status } else { 'missing' }) + ')') -ForegroundColor Red
        if (Test-Path -LiteralPath $sp.Err) {
            Write-Host ('[INFO] Last lines of stderr (' + $sp.Err + '):') -ForegroundColor Yellow
            Get-Content -LiteralPath $sp.Err -Tail 40 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host $_ }
        }
        else {
            Write-Host '[INFO] No stderr log yet.' -ForegroundColor Yellow
        }
    }
    if ($anyFail) {
        $pipHint = Join-Path $current "requirements-prod.txt"
        Write-Host '[HINT] Re-run install_services.ps1 with same -PythonExe (auto pip when deps missing), or -PreparePython, or manual:' -ForegroundColor Cyan
        $pipOneLine = '$env:PIP_USER=''0''; & "' + $PythonExe + '" -m pip install -r "' + $pipHint + '"'
        Write-Host $pipOneLine -ForegroundColor Cyan
        Write-Host '[HINT] Offline: use -SkipAutoPreparePython and pre-install wheels. Emoji/PYTHONUTF8: fix current\ and system env.' -ForegroundColor Cyan
        throw "One or more services failed to start. Fix Python path or check logs under shared\logs."
    }
    Write-Host '[OK] All services running.'
}

Write-Host 'Done. Get-Service stock-quote-*'
