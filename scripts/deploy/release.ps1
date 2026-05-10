param(
    [Parameter(Mandatory = $true)]
    [string]$PackagePath,
    [string]$DeployRoot = "C:\deploy\stock_quote",
    [string]$PythonExe = "python",
    [string]$NpmExe = "npm",
    [string]$NginxHome = "",
    [int]$HealthRetry = 10,
    [int]$HealthTimeoutSec = 3,
    [int]$HealthIntervalSec = 2,
    [switch]$SkipHealthCheck,
    # 若不停止服务，pip 升级 psycopg2 等 .pyd 时常因进程占用报 WinError 5「拒绝访问」
    [switch]$SkipStopServicesBeforePip,
    # 若同为 Python313 下还有手工起的 python/pythonw（未注册为服务），仍会锁住 .pyd；默认结束这些进程
    [switch]$SkipKillPythonBeforePip
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Assert-RequirementsProdMinimal.ps1")

<#
  唯一维护副本：<repo>\scripts\deploy\release.ps1（请直接 -File 此路径）。
  若存在 src\scripts\deploy\release.ps1，仅为转发到本文件，勿另拷贝手写同步。
  生产机建议显式传入（避免 PS5.1 / PATH / 别名歧义）：
  -PythonExe 'C:\...\Python313\python.exe'
  可选：-NpmExe 'C:\Program Files\nodejs\npm.cmd'
#>

function Normalize-NonEmpty([string]$Value, [string]$Default) {
    $v = [string]$Value
    if ([string]::IsNullOrWhiteSpace($v)) {
        return $Default
    }
    $v = $v.Trim()
    if ([string]::IsNullOrWhiteSpace($v)) {
        return $Default
    }
    return $v
}

$NpmExe = Normalize-NonEmpty $NpmExe "npm"

# 统一解析 python.exe 绝对路径（仅此一处使用 Get-Command -Name，禁止对「完整路径」做位置调用）
function Resolve-ToPythonExePath {
    param([string]$Preferred)
    $s = Normalize-NonEmpty $Preferred "python"
    if ([System.IO.Path]::IsPathRooted($s) -and (Test-Path -LiteralPath $s)) {
        return (Resolve-Path -LiteralPath $s).Path
    }
    $cmd = Get-Command -Name $s -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $cmd) {
        foreach ($p in @([string]$cmd.Source, [string]$cmd.Path)) {
            if (-not [string]::IsNullOrWhiteSpace($p)) {
                $pt = $p.Trim()
                if (Test-Path -LiteralPath $pt) {
                    return (Resolve-Path -LiteralPath $pt).Path
                }
            }
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
    throw "Cannot resolve python.exe from '$Preferred'. Use full path: -PythonExe 'C:\...\python.exe'"
}

function Assert-LastExitCode([string]$StepName) {
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "$StepName failed (exit code $LASTEXITCODE)."
    }
}

# Windows PowerShell 下 `& python -m pip` 有时不刷新 $LASTEXITCODE；用 Start-Process 取可靠退出码。
# PIP_USER=0：包装进 Lib\site-packages，避免仅装进 Administrator 的 Roaming（NSSM LocalSystem 读不到）。
function Invoke-PythonPip {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$PipArguments
    )
    $allArgs = @('-m', 'pip') + $PipArguments
    $savedPipUser = $env:PIP_USER
    $env:PIP_USER = '0'
    try {
        $p = Start-Process -FilePath $PythonExe -ArgumentList $allArgs -WorkingDirectory (Get-Location).Path -Wait -PassThru -NoNewWindow
        $code = $p.ExitCode
        if ($null -eq $code -or $code -ne 0) {
            throw ("pip failed (exit {0}): python {1}" -f $code, ($allArgs -join ' '))
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
}

function Write-DeployStep([string]$Msg) {
    Write-Host "==> $Msg" -ForegroundColor Cyan
}

# PS5.1 且脚本 $ErrorActionPreference=Stop：*-Service 在无管理员权限时常抛*终止性*异常，
# 单靠 -ErrorAction SilentlyContinue 仍可能中断脚本；统一用 try/catch 吞掉后再轮询状态或走 sc.exe。
function Invoke-StopServiceBestEffort([string]$ServiceName) {
    try {
        Stop-Service -Name $ServiceName -Force -ErrorAction Stop
    }
    catch {
    }
}

function Invoke-StartServiceBestEffort([string]$ServiceName) {
    try {
        Start-Service -Name $ServiceName -ErrorAction Stop
    }
    catch {
    }
}

function Restart-IfExists([string]$Name) {
    $svc = $null
    try {
        $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
    }
    catch {
        Write-Host ("[WARN] Cannot query service {0}: {1}" -f $Name, $_.Exception.Message) -ForegroundColor Yellow
        return
    }
    if ($null -eq $svc) {
        Write-Host "[SKIP] Service not installed: $Name"
        return
    }
    try {
        if ($svc.Status -eq 'Paused') {
            Write-Host ("[WARN] Service {0} is Paused; trying Stop then Start." -f $Name) -ForegroundColor Yellow
            Stop-Service -Name $Name -Force -ErrorAction Stop
            Start-Sleep -Seconds 2
            Start-Service -Name $Name -ErrorAction Stop
        }
        else {
            Restart-Service -Name $Name -Force -ErrorAction Stop
        }
        Write-Host "[RESTART] $Name"
    }
    catch {
        Write-Host ("[WARN] Restart failed for {0}: {1}" -f $Name, $_.Exception.Message) -ForegroundColor Yellow
        Invoke-StopServiceBestEffort $Name
        Start-Sleep -Seconds 2
        $scExe = Join-Path $env:SystemRoot "System32\sc.exe"
        if (Test-Path -LiteralPath $scExe) {
            $null = & $scExe stop $Name 2>&1
            Start-Sleep -Seconds 1
        }
        Invoke-StartServiceBestEffort $Name
        if (Test-Path -LiteralPath $scExe) {
            $null = & $scExe start $Name 2>&1
            Start-Sleep -Seconds 2
        }
        $chk = Get-Service -Name $Name -ErrorAction SilentlyContinue
        if ($null -ne $chk -and $chk.Status -eq 'Running') {
            Write-Host ("[RESTART] {0} (stop/start fallback)" -f $Name)
        }
        else {
            Write-Host ("[WARN] Could not start {0}. Run install_services.ps1 or reboot if service is stuck." -f $Name) -ForegroundColor Yellow
        }
    }
}

function Stop-StockQuoteServicesIfRunning {
    # 非管理员或 SCM 异常时 Stop-Service 会抛「无法打开…服务」；禁止因此中断整次 release。
    $scExe = Join-Path $env:SystemRoot "System32\sc.exe"
    foreach ($svcName in @('stock-quote-api', 'stock-quote-core', 'stock-quote-notify')) {
        $svc = Get-Service -Name $svcName -ErrorAction SilentlyContinue
        if ($null -eq $svc) { continue }
        if ($svc.Status -ne 'Running' -and $svc.Status -ne 'Paused') { continue }

        Invoke-StopServiceBestEffort $svcName
        $ok = $false
        for ($w = 0; $w -lt 10; $w++) {
            Start-Sleep -Milliseconds 500
            $chk = Get-Service -Name $svcName -ErrorAction SilentlyContinue
            if ($null -eq $chk -or $chk.Status -eq 'Stopped') {
                $ok = $true
                break
            }
        }
        if (-not $ok -and (Test-Path -LiteralPath $scExe)) {
            $null = & $scExe stop $svcName 2>&1
            for ($w = 0; $w -lt 10; $w++) {
                Start-Sleep -Milliseconds 500
                $chk = Get-Service -Name $svcName -ErrorAction SilentlyContinue
                if ($null -eq $chk -or $chk.Status -eq 'Stopped') {
                    $ok = $true
                    break
                }
            }
        }
        if ($ok) {
            Write-Host "[STOP] $svcName (release pip unlock site-packages)" -ForegroundColor DarkYellow
        }
        else {
            $last = Get-Service -Name $svcName -ErrorAction SilentlyContinue
            $st = if ($null -ne $last) { [string]$last.Status } else { 'unknown' }
            Write-Host ("[WARN] Cannot stop service '{0}' (still {1}). Pip may hit WinError 5 on locked .pyd. Run PowerShell as Administrator, stop the service manually, or pass -SkipStopServicesBeforePip." -f $svcName, $st) -ForegroundColor Yellow
        }
    }
}

function Get-NginxExe {
    if ($NginxHome -ne "") {
        $exe = Join-Path $NginxHome "nginx.exe"
        if (Test-Path -LiteralPath $exe) {
            return $exe
        }
        Write-Host "[WARN] nginx.exe not found at $exe, using nginx from PATH" -ForegroundColor Yellow
    }
    return "nginx"
}

function Expand-ZipToDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ZipPath,
        [Parameter(Mandatory = $true)]
        [string]$DestinationDirectory
    )
    $zipResolved = (Resolve-Path -LiteralPath $ZipPath).Path
    if (Get-Command -Name 'Expand-Archive' -ErrorAction SilentlyContinue) {
        Expand-Archive -LiteralPath $zipResolved -DestinationPath $DestinationDirectory -Force
        return
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction Stop
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zipResolved, $DestinationDirectory)
}

function Test-Health([string]$Name, [string]$url, [int]$retry, [int]$timeoutSec, [int]$intervalSec) {
    Write-Host ("[HEALTH] checking {0}: {1} (retry={2}, timeout={3}s, interval={4}s)" -f $Name, $url, $retry, $timeoutSec, $intervalSec) -ForegroundColor DarkGray
    for ($i = 1; $i -le $retry; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeoutSec
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                Write-Host ("[HEALTH][OK] {0} attempt {1}/{2}: HTTP {3}" -f $Name, $i, $retry, $resp.StatusCode) -ForegroundColor Green
                return $true
            }
            Write-Host ("[HEALTH][WAIT] {0} attempt {1}/{2}: HTTP {3}" -f $Name, $i, $retry, $resp.StatusCode) -ForegroundColor DarkYellow
        }
        catch {
            Write-Host ("[HEALTH][WAIT] {0} attempt {1}/{2}: {3}" -f $Name, $i, $retry, $_.Exception.Message) -ForegroundColor DarkYellow
        }
        if ($i -lt $retry) {
            Start-Sleep -Seconds $intervalSec
        }
    }
    Write-Host ("[HEALTH][FAIL] {0} not ready after {1} attempts." -f $Name, $retry) -ForegroundColor Yellow
    return $false
}

# admin/node_modules 常有 junction，Remove-Item 可能报「未能找到路径的一部分」；用 cmd rd / robocopy 兜底，失败仅告警不阻断发布。
function Remove-DirectoryRobust([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    $full = (Resolve-Path -LiteralPath $Path).Path
    try {
        Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction Stop
        return
    }
    catch {
        Write-Host ("[WARN] Remove-Item failed, trying fallback: {0}" -f $_.Exception.Message) -ForegroundColor DarkYellow
    }
    if ($env:OS -eq 'Windows_NT') {
        $cmdExe = Join-Path $env:SystemRoot "System32\cmd.exe"
        $null = Start-Process -FilePath $cmdExe -ArgumentList @('/d', '/c', "rd /s /q `"$full`"") -Wait -PassThru -NoNewWindow
        if (-not (Test-Path -LiteralPath $Path)) {
            return
        }
        $rob = Join-Path $env:SystemRoot "System32\robocopy.exe"
        if (Test-Path -LiteralPath $rob) {
            $empty = Join-Path $env:TEMP ("deploy_rm_empty_" + [Guid]::NewGuid().ToString('N'))
            try {
                New-Item -ItemType Directory -Path $empty -Force | Out-Null
                & $rob $empty $full /MIR /R:0 /W:0 /NJH /NJS /NP | Out-Null
            }
            finally {
                if (Test-Path -LiteralPath $empty) {
                    Remove-Item -LiteralPath $empty -Recurse -Force -ErrorAction SilentlyContinue
                }
            }
            if (Test-Path -LiteralPath $full) {
                Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
        if (Test-Path -LiteralPath $Path) {
            Write-Host ("[WARN] Could not fully delete (may remain junction debris): {0}" -f $full) -ForegroundColor Yellow
        }
        return
    }
    Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction SilentlyContinue
}

# robocopy 退出码：0–7 视为成功（含“无文件可复制”等）；≥8 为失败。
function Test-RobocopyExitOk {
    param([int]$ExitCode)
    return ($ExitCode -ge 0 -and $ExitCode -lt 8)
}

# 不重命名 current 目录（Move-Item 在 Windows 上易被句柄锁死）；用镜像同步目录内容。
function Invoke-RobocopyMirror {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,
        [Parameter(Mandatory = $true)]
        [string]$Destination
    )
    $rob = Join-Path $env:SystemRoot "System32\robocopy.exe"
    if (-not (Test-Path -LiteralPath $rob)) {
        throw "未找到 robocopy.exe，无法部署。"
    }
    $src = [string]$Source.TrimEnd('\')
    $dst = [string]$Destination.TrimEnd('\')
    # 完整镜像（含 admin 等）；勿 /XD node_modules，否则前端依赖目录不会被同步。
    & $rob $src $dst /MIR /R:8 /W:5 /NP /MT:8
    $code = $LASTEXITCODE
    if (-not (Test-RobocopyExitOk $code)) {
        throw ("robocopy 失败 (exit {0}): `"{1}`" -> `"{2}`"" -f $code, $src, $dst)
    }
}

# 需在脚本中已解析 $PythonExe 之后调用；用于释放 _psycopg*.pyd / current 目录占用。
# PS5.1：`Get-Process -Name python` 在部分环境下触发 ParameterBindingException；改为枚举全部进程再按 Name 过滤。
function Invoke-KillPythonSameInterpreter {
    if ($env:OS -ne 'Windows_NT') {
        return
    }
    try {
        $pyExeForKill = $PythonExe
        if (-not (Test-Path -LiteralPath $pyExeForKill)) {
            throw "Python executable not found: $pyExeForKill"
        }
        $fullPyKill = (Resolve-Path -LiteralPath $pyExeForKill).Path
        $pyRootKill = Split-Path -LiteralPath $fullPyKill -Parent
        $allProc = @(Get-Process -ErrorAction SilentlyContinue)
        foreach ($procKill in $allProc) {
            $nm = $null
            try {
                $nm = $procKill.Name
            }
            catch {
                continue
            }
            if ($nm -ne 'python' -and $nm -ne 'pythonw') {
                continue
            }
            $exePathKill = $null
            try {
                $exePathKill = $procKill.Path
            }
            catch {
                continue
            }
            if ([string]::IsNullOrWhiteSpace($exePathKill)) {
                continue
            }
            if (-not ($exePathKill.StartsWith($pyRootKill, [StringComparison]::OrdinalIgnoreCase))) {
                continue
            }
            $procIdKill = $procKill.Id
            try {
                Stop-Process -Id $procIdKill -Force -ErrorAction Stop
                Write-Host ("[KILL] {0} PID {1} under {2}" -f ($nm + '.exe'), $procIdKill, $pyRootKill) -ForegroundColor DarkYellow
            }
            catch {
                Write-Host ("[WARN] Cannot stop PID {0}: {1}" -f $procIdKill, $_.Exception.Message) -ForegroundColor Yellow
            }
        }
    }
    catch {
        Write-Host ("[WARN] Kill python helper failed: {0}" -f $_.Exception.Message) -ForegroundColor Yellow
    }
}

$PythonExe = Normalize-NonEmpty $PythonExe "python"
$PythonExe = Resolve-ToPythonExePath $PythonExe
# 强制为单个字符串，避免少数环境下解析为数组导致后续绑定歧义
$PythonExe = [string](@($PythonExe)[0])

if (-not (Test-Path -LiteralPath $PackagePath)) {
    throw "Package zip not found: $PackagePath"
}

$releasesDir = Join-Path $DeployRoot "releases"
$sharedDir = Join-Path $DeployRoot "shared"
$currentDir = Join-Path $DeployRoot "current"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$newRelease = Join-Path $releasesDir $timestamp
$backupCurrent = "${currentDir}_backup_${timestamp}"

Write-DeployStep "Create release folder"
New-Item -ItemType Directory -Path $newRelease -Force | Out-Null

Write-DeployStep "Expand zip"
Expand-ZipToDirectory -ZipPath $PackagePath -DestinationDirectory $newRelease

Write-DeployStep "Copy shared .env"
$sharedEnv = Join-Path $sharedDir ".env"
if (Test-Path -LiteralPath $sharedEnv) {
    Copy-Item -Path $sharedEnv -Destination (Join-Path $newRelease ".env") -Force
}
else {
    Write-Host "[WARN] shared\.env not found; backend may fail to start"
}

Write-DeployStep 'pip install (requirements-prod.txt -> backend_api/requirements-minimal.txt + backend_core/requirements-minimal.txt)'
Push-Location $newRelease
$locationPushed = $true
if (-not $SkipStopServicesBeforePip) {
    Write-DeployStep "Stop Windows services before pip (unlock psycopg2/pydantic .pyd; avoids WinError 5)"
    Stop-StockQuoteServicesIfRunning
    Start-Sleep -Seconds 5
}
if ($env:OS -eq 'Windows_NT' -and -not $SkipKillPythonBeforePip) {
    Write-DeployStep "Stop python.exe/pythonw still using same interpreter (unlock _psycopg*.pyd)"
    Invoke-KillPythonSameInterpreter
    Start-Sleep -Seconds 3
}
Invoke-PythonPip @('install', '--upgrade', 'pip')
$prodReq = Join-Path $newRelease "requirements-prod.txt"
if (-not (Test-Path -LiteralPath $prodReq)) {
    throw 'requirements-prod.txt not found in release package (expected to aggregate backend_api/requirements-minimal.txt and backend_core/requirements-minimal.txt).'
}
Assert-RequirementsProdMinimalDeps -RequirementsProdPath $prodReq
Write-Host '[pip] requirements-prod only (backend_api + backend_core minimal); pydantic-core forced binary wheel.' -ForegroundColor DarkGray
# --only-binary pydantic-core：禁止源码编译（无需 Rust/link.exe）；若无匹配 wheel 会立刻失败而非卡住。
Invoke-PythonPip @(
    'install',
    '--prefer-binary',
    '--only-binary', 'pydantic-core',
    '--only-binary', 'pydantic',
    '-r', 'requirements-prod.txt'
)

Write-DeployStep "Build admin"
$adminDirForNpm = Join-Path $newRelease "admin"
if (Test-Path -LiteralPath (Join-Path $adminDirForNpm "package.json")) {
    # 完全不使用 Get-Command（部分环境会对 -Name 做空校验异常）；仅用 Test-Path + Start-Process
    $npmCmdPath = $null
    if (-not [string]::IsNullOrWhiteSpace([string]$NpmExe)) {
        $np = $NpmExe.Trim()
        if ([System.IO.Path]::IsPathRooted($np) -and (Test-Path -LiteralPath $np)) {
            $npmCmdPath = $np
        }
    }
    if ($null -eq $npmCmdPath -and $env:OS -eq 'Windows_NT') {
        foreach ($pfRoot in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
            if ([string]::IsNullOrWhiteSpace([string]$pfRoot)) {
                continue
            }
            $tryNpm = Join-Path $pfRoot "nodejs\npm.cmd"
            if (Test-Path -LiteralPath $tryNpm) {
                $npmCmdPath = $tryNpm
                break
            }
        }
    }
    $cmdExePath = $env:ComSpec
    if ([string]::IsNullOrWhiteSpace($cmdExePath) -or -not (Test-Path -LiteralPath $cmdExePath)) {
        $cmdExePath = Join-Path $env:SystemRoot "System32\cmd.exe"
    }
    if ($null -ne $npmCmdPath) {
        $pInstall = Start-Process -FilePath $npmCmdPath -ArgumentList @('install') -WorkingDirectory $adminDirForNpm -Wait -PassThru -NoNewWindow
        if ($null -eq $pInstall.ExitCode -or $pInstall.ExitCode -ne 0) {
            throw ("npm install failed (exit {0})." -f $pInstall.ExitCode)
        }
        $pBuild = Start-Process -FilePath $npmCmdPath -ArgumentList @('run', 'build') -WorkingDirectory $adminDirForNpm -Wait -PassThru -NoNewWindow
        if ($null -eq $pBuild.ExitCode -or $pBuild.ExitCode -ne 0) {
            throw ("npm run build failed (exit {0})." -f $pBuild.ExitCode)
        }
    }
    else {
        $pInstall = Start-Process -FilePath $cmdExePath -ArgumentList @('/d', '/c', 'npm.cmd install') -WorkingDirectory $adminDirForNpm -Wait -PassThru -NoNewWindow
        if ($null -eq $pInstall.ExitCode -or $pInstall.ExitCode -ne 0) {
            throw ("npm install via cmd failed (exit {0}). Install Node.js or pass -NpmExe full path to npm.cmd." -f $pInstall.ExitCode)
        }
        $pBuild = Start-Process -FilePath $cmdExePath -ArgumentList @('/d', '/c', 'npm.cmd run build') -WorkingDirectory $adminDirForNpm -Wait -PassThru -NoNewWindow
        if ($null -eq $pBuild.ExitCode -or $pBuild.ExitCode -ne 0) {
            throw ("npm run build via cmd failed (exit {0})." -f $pBuild.ExitCode)
        }
    }
}
else {
    Write-Host "[WARN] admin/package.json not found, skip admin build"
}

Write-DeployStep "Optional migrate_db.py"
if (Test-Path -LiteralPath (Join-Path $newRelease "migrate_db.py")) {
    & $PythonExe migrate_db.py
}

# 先离开 $newRelease，再移动该目录；否则会触发“目录正在使用中”。
if ($locationPushed) {
    Pop-Location
    $locationPushed = $false
}

Write-DeployStep "Prepare to switch current (cwd + stop services + unlock)"
try {
    $deployResolved = (Resolve-Path -LiteralPath $DeployRoot).Path
    Set-Location -LiteralPath $deployResolved
}
catch {
    Write-Host ("[WARN] Set-Location DeployRoot failed (another process may lock current): {0}" -f $_.Exception.Message) -ForegroundColor Yellow
}

# 与 -SkipStopServicesBeforePip 无关：切换 current 目录内容前必须停服务，否则 NSSM 子进程占用文件。
Write-DeployStep "Stop Windows services before switching current"
Stop-StockQuoteServicesIfRunning
Start-Sleep -Seconds 8

if ($env:OS -eq 'Windows_NT' -and -not $SkipKillPythonBeforePip) {
    Write-DeployStep "Kill python.exe/pythonw again (unlock current directory)"
    Invoke-KillPythonSameInterpreter
    Start-Sleep -Seconds 3
}

Write-DeployStep "Switch current (robocopy in-place; avoids Move-Item directory lock)"
if ($env:OS -ne 'Windows_NT') {
    throw "当前 release.ps1 的目录切换依赖 robocopy，请在 Windows 上执行。"
}
if (Test-Path -LiteralPath $currentDir) {
    Write-Host "[DEPLOY] Backup current -> $(Split-Path -Leaf $backupCurrent)" -ForegroundColor DarkGray
    Invoke-RobocopyMirror -Source $currentDir -Destination $backupCurrent
}
else {
    New-Item -ItemType Directory -Path $currentDir -Force | Out-Null
}
Write-Host "[DEPLOY] Mirror new release -> current" -ForegroundColor DarkGray
Invoke-RobocopyMirror -Source $newRelease -Destination $currentDir
Remove-DirectoryRobust $newRelease

try {
    Write-DeployStep 'Restart Windows services (if exist)'
    Restart-IfExists "stock-quote-api"
    Restart-IfExists "stock-quote-core"
    Restart-IfExists "stock-quote-notify"

    Write-DeployStep "nginx -t and reload"
    $nginxExe = Get-NginxExe
    $nginxWorkDir = $null
    if (-not [string]::IsNullOrWhiteSpace([string]$NginxHome) -and (Test-Path -LiteralPath $NginxHome)) {
        $nginxWorkDir = (Resolve-Path -LiteralPath $NginxHome).Path
    }
    if ($null -ne $nginxWorkDir) {
        Push-Location $nginxWorkDir
    }
    try {
        & $nginxExe -t
        if ($LASTEXITCODE -eq 0) {
            & $nginxExe -s reload
        }
        else {
            Write-Host "[WARN] nginx -t failed, skip reload" -ForegroundColor Yellow
        }
    }
    finally {
        if ($null -ne $nginxWorkDir) {
            Pop-Location
        }
    }

    if ($SkipHealthCheck) {
        Write-Host "[WARN] Health check skipped by -SkipHealthCheck." -ForegroundColor Yellow
    }
    else {
        Write-DeployStep "Health check"
        $okApi = Test-Health -Name "api" -url "http://127.0.0.1:5000/" -retry $HealthRetry -timeoutSec $HealthTimeoutSec -intervalSec $HealthIntervalSec
        $okWeb = Test-Health -Name "web" -url "https://www.icemaplecity.com/" -retry $HealthRetry -timeoutSec $HealthTimeoutSec -intervalSec $HealthIntervalSec
        $okAdmin = Test-Health -Name "admin" -url "https://www.icemaplecity.com/admin/" -retry $HealthRetry -timeoutSec $HealthTimeoutSec -intervalSec $HealthIntervalSec

        if (-not ($okApi -and $okWeb -and $okAdmin)) {
            throw "Health check failed: api=$okApi web=$okWeb admin=$okAdmin"
        }
    }

    Remove-DirectoryRobust $backupCurrent
    Write-Host "[SUCCESS] Released: $timestamp"
}
catch {
    Write-Host ("ERROR: Release failed, rollback: " + $_.Exception.Message) -ForegroundColor Red
    if ($env:OS -eq 'Windows_NT' -and (Test-Path -LiteralPath $backupCurrent)) {
        try {
            if (-not (Test-Path -LiteralPath $currentDir)) {
                New-Item -ItemType Directory -Path $currentDir -Force | Out-Null
            }
            Write-Host "[ROLLBACK] robocopy mirror backup -> current" -ForegroundColor Yellow
            Invoke-RobocopyMirror -Source $backupCurrent -Destination $currentDir
        }
        catch {
            Write-Host ("[WARN] Rollback restore via robocopy failed: {0}" -f $_.Exception.Message) -ForegroundColor Yellow
        }
    }
    Restart-IfExists "stock-quote-api"
    Restart-IfExists "stock-quote-core"
    Restart-IfExists "stock-quote-notify"
    throw
}
finally {
    if ($locationPushed) {
        Pop-Location
    }
}
