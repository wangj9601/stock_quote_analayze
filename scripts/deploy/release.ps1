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
    # admin npm install/build 前要求的最小可用磁盘空间（GB）。
    [int]$MinFreeSpaceGBForAdminBuild = 4,
    # 低空间时自动清理 releases，仅保留最新 N 个目录。
    [int]$KeepLatestReleases = 3,
    [switch]$SkipAutoCleanupOldReleases,
    # 防呆：默认要求当前执行脚本路径与 DeployRoot\current\scripts\deploy\release.ps1 完全一致。
    # 若确需跨目录调用（例如临时调试），可显式加 -AllowScriptPathMismatch。
    [switch]$AllowScriptPathMismatch,
    # 若不停止服务，pip 升级 psycopg2 等 .pyd 时常因进程占用报 WinError 5「拒绝访问」
    [switch]$SkipStopServicesBeforePip,
    # 仅跳过「pip 之前」的同解释器 python 结束；覆盖 current（robocopy）前仍会结束同解释器进程以释放目录/句柄
    [switch]$SkipKillPythonBeforePip,
    # 手工进程部署：不依赖 NSSM；不发 Restart-Service；在 DeployRoot\current 后台启动 5 个进程（日志 shared\logs\manual-*.log）
    [switch]$ManualProcessDeploy,
    # 服务器上不执行 npm（zip 已在本地含 admin 构建产物时使用；与 -ManualProcessDeploy 一起用）
    [switch]$SkipAdminBuild,
    # 服务器上不执行 pip（磁盘极紧张且依赖已预装时使用）
    [switch]$SkipPip,
    # 手工进程模式下管理端静态站端口（python -m http.server，cwd=current\admin\dist）
    [int]$ManualAdminHttpPort = 8001,
    # 相对于 -NginxHome 的配置路径（用于 ManualProcessDeploy 时校验 upstream）
    [string]$NginxConfFile = 'conf\nginx.conf',
    [switch]$SkipNginxUpstreamCheck,
    # 与 nginx upstream、手工启动进程默认端口对齐（若改 .env 请同步改 nginx.conf）
    [int]$NginxExpectBackendPort = 5000,
    [int]$NginxExpectFrontendPort = 8000
)

$ErrorActionPreference = "Stop"

$skipAdminOnServer = $SkipAdminBuild -or $ManualProcessDeploy

. (Join-Path $PSScriptRoot "Assert-RequirementsProdMinimal.ps1")

function Assert-ReleaseScriptPathMatchesDeployRoot {
    param(
        [Parameter(Mandatory = $true)][string]$DeployRootPath,
        [switch]$AllowMismatch
    )
    $scriptActual = [string](Resolve-Path -LiteralPath $PSCommandPath).Path
    Write-Host ("[INFO] Running release script: {0}" -f $scriptActual) -ForegroundColor DarkGray

    $deployResolved = $null
    try {
        $deployResolved = [string](Resolve-Path -LiteralPath $DeployRootPath).Path
    }
    catch {
        # DeployRoot 可能尚未创建，交给后续流程处理；这里不拦截。
        return
    }

    $expected = [string](Join-Path $deployResolved "current\scripts\deploy\release.ps1")
    if (-not (Test-Path -LiteralPath $expected)) {
        # 目标路径不存在时不做严格阻断，避免首次部署被误拦截。
        Write-Host ("[WARN] Guard skip: expected script not found yet: {0}" -f $expected) -ForegroundColor Yellow
        return
    }

    $expectedResolved = [string](Resolve-Path -LiteralPath $expected).Path
    if ($scriptActual.Equals($expectedResolved, [StringComparison]::OrdinalIgnoreCase)) {
        return
    }

    $msg = @(
        'Refuse to run release.ps1 from mismatched path.',
        ('- Running : {0}' -f $scriptActual),
        ('- Expected: {0}' -f $expectedResolved),
        'Use the expected script path above, or explicitly pass -AllowScriptPathMismatch to bypass once.'
    ) -join [Environment]::NewLine

    if ($AllowMismatch) {
        Write-Host '[WARN] Script path mismatch bypassed by -AllowScriptPathMismatch.' -ForegroundColor Yellow
        Write-Host ("[WARN] Expected path: {0}" -f $expectedResolved) -ForegroundColor Yellow
        return
    }

    throw $msg
}

<#
  唯一维护副本：<repo>\scripts\deploy\release.ps1（请直接 -File 此路径）。
  若存在 src\scripts\deploy\release.ps1，仅为转发到本文件，勿另拷贝手写同步。
  生产机建议显式传入（避免 PS5.1 / PATH / 别名歧义）：
  -PythonExe 'C:\...\Python313\python.exe'
  可选：-NpmExe 'C:\Program Files\nodejs\npm.cmd'

  低磁盘 / 不用 NSSM：本地用 scripts\deploy\deploy.ps1 打好含 admin 产物的 zip，上传后在服务器：
  -ManualProcessDeploy [-SkipAdminBuild] [-SkipPip] [-SkipHealthCheck] [-ManualAdminHttpPort 8001]
  将解压、possibly pip、镜像 current，并后台启动 5 个进程（与手工一致，日志 shared\logs\manual-*.log）：
  (1) python -m http.server 于 admin\dist  (2) start_backend_core (3) start_backend_api (4) start_scheduler (5) start_frontend
  nginx：仓库根目录 nginx.conf（与 docs/prod/nginx.conf 同步）应与上述端口一致；-ManualProcessDeploy 且指定 -NginxHome 时会在 nginx -t 前校验 conf 内 upstream。
#>

function Get-NonEmptyString([string]$Value, [string]$Default) {
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

$NpmExe = Get-NonEmptyString $NpmExe "npm"

# 统一解析 python.exe 绝对路径（仅此一处使用 Get-Command -Name，禁止对「完整路径」做位置调用）
function Resolve-ToPythonExePath {
    param([string]$Preferred)
    $s = Get-NonEmptyString $Preferred "python"
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

function Get-DriveFreeSpaceGB([string]$Path) {
    try {
        $resolved = (Resolve-Path -LiteralPath $Path).Path
        $root = [System.IO.Path]::GetPathRoot($resolved)
        if ([string]::IsNullOrWhiteSpace($root)) {
            return -1
        }
        $driveName = $root.TrimEnd('\').TrimEnd(':')
        $drv = Get-PSDrive -Name $driveName -ErrorAction SilentlyContinue
        if ($null -eq $drv -or $null -eq $drv.Free) {
            return -1
        }
        return [int][Math]::Floor([double]$drv.Free / 1GB)
    }
    catch {
        return -1
    }
}

function Remove-OldReleaseFolders {
    param(
        [Parameter(Mandatory = $true)][string]$ReleasesDirectory,
        [int]$KeepCount = 3
    )
    if ($KeepCount -lt 1) {
        $KeepCount = 1
    }
    if (-not (Test-Path -LiteralPath $ReleasesDirectory)) {
        return
    }
    $dirs = @(Get-ChildItem -LiteralPath $ReleasesDirectory -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending)
    if ($dirs.Count -le $KeepCount) {
        return
    }
    $toDelete = @($dirs | Select-Object -Skip $KeepCount)
    foreach ($d in $toDelete) {
        try {
            Remove-DirectoryRobust $d.FullName
            Write-Host ('[CLEAN] removed old release: {0}' -f $d.FullName) -ForegroundColor DarkGray
        }
        catch {
            Write-Host ('[WARN] failed to remove old release {0}: {1}' -f $d.FullName, $_.Exception.Message) -ForegroundColor Yellow
        }
    }
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

# admin/node_modules 常有 junction / 失效 symlink，Remove-Item -Recurse 易报「未能找到路径的一部分」。
# Windows 下优先 rd /s /q，再 Remove-Item，再 robocopy 清空兜底。
function Remove-DirectoryRobust([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    $full = (Resolve-Path -LiteralPath $Path).Path
    if ($env:OS -eq 'Windows_NT') {
        $cmdExe = Join-Path $env:SystemRoot "System32\cmd.exe"
        $null = Start-Process -FilePath $cmdExe -ArgumentList @('/d', '/c', "rd /s /q `"$full`"") -Wait -PassThru -NoNewWindow
        if (-not (Test-Path -LiteralPath $Path)) {
            return
        }
    }
    try {
        Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction Stop
        return
    }
    catch {
        Write-Host ("[INFO] Remove-Item recurse fallback (junction/long path): {0}" -f $_.Exception.Message) -ForegroundColor DarkGray
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

# robocopy exit code 0-7 means success; >=8 means failure.
function Test-RobocopyExitOk {
    param([int]$ExitCode)
    return ($ExitCode -ge 0 -and $ExitCode -lt 8)
}

# robocopy 返回码为位掩码：常见 8=部分复制失败，16=严重错误；9=1+8 多为磁盘满或路径问题。
function Format-RobocopyFailureMessage {
    param(
        [int]$ExitCode,
        [string]$Src,
        [string]$Dst
    )
    $bits = @()
    if (($ExitCode -band 1) -ne 0) { $bits += 'extra_files' }
    if (($ExitCode -band 2) -ne 0) { $bits += 'extra_dirs' }
    if (($ExitCode -band 4) -ne 0) { $bits += 'mismatch' }
    if (($ExitCode -band 8) -ne 0) { $bits += 'copy_errors' }
    if (($ExitCode -band 16) -ne 0) { $bits += 'fatal' }
    $hint = $bits -join ','
    $diskHint = ''
    try {
        $root = [System.IO.Path]::GetPathRoot((Resolve-Path -LiteralPath $Dst).Path)
        if (-not [string]::IsNullOrWhiteSpace($root)) {
            $dn = $root.TrimEnd('\').TrimEnd(':')
            $drv = Get-PSDrive -Name $dn -ErrorAction SilentlyContinue
            if ($null -ne $drv -and $null -ne $drv.Free) {
                $gb = [Math]::Round([double]$drv.Free / 1GB, 2)
                $diskHint = (' destination_drive_free={0}GB' -f $gb)
            }
        }
    }
    catch {
    }
    $extra = ''
    if (($ExitCode -band 8) -ne 0 -or ($ExitCode -band 16) -ne 0) {
        $extra = ' Often: disk full (ENOSPC), path too long, or access denied. Free space on destination drive and retry.'
    }
    return ('robocopy failed (exit {0}, bits: {1}){2}: {3} -> {4}.{5}' -f $ExitCode, $hint, $diskHint, $Src, $Dst, $extra)
}

function Get-NginxUpstreamPortFromText {
    param(
        [Parameter(Mandatory = $true)][string]$Content,
        [Parameter(Mandatory = $true)][string]$UpstreamName
    )
    $pattern = '(?s)upstream\s+' + [regex]::Escape($UpstreamName) + '\s*\{[^}]*?server\s+[^\s:]+:(\d+)\s*;'
    $m = [regex]::Match($Content, $pattern)
    if ($m.Success) {
        return [int]$m.Groups[1].Value
    }
    return $null
}

# current + ManualProcessDeploy：nginx 反代本机端口，须与 release 启动的进程及 .env 一致（与运行目录是否为 current 无关，但必须检查转发端口）
function Assert-NginxConfMatchesManualDeploy {
    param(
        [Parameter(Mandatory = $true)][string]$NginxHomePath,
        [Parameter(Mandatory = $true)][string]$ConfRelativePath,
        [int]$ExpectBackendPort,
        [int]$ExpectFrontendPort,
        [int]$ExpectAdminPort,
        [switch]$SkipCheck
    )
    if ($SkipCheck) {
        return
    }
    if ([string]::IsNullOrWhiteSpace($NginxHomePath)) {
        Write-Host '[WARN] ManualProcessDeploy: -NginxHome empty; skip nginx upstream check.' -ForegroundColor Yellow
        return
    }
    if (-not (Test-Path -LiteralPath $NginxHomePath)) {
        Write-Host ('[WARN] NginxHome not found; skip upstream check: {0}' -f $NginxHomePath) -ForegroundColor Yellow
        return
    }
    $confFull = Join-Path $NginxHomePath $ConfRelativePath
    if (-not (Test-Path -LiteralPath $confFull)) {
        Write-Host ('[WARN] nginx conf not found; skip upstream check: {0}' -f $confFull) -ForegroundColor Yellow
        return
    }
    $raw = Get-Content -LiteralPath $confFull -Raw -Encoding UTF8
    $pApi = Get-NginxUpstreamPortFromText -Content $raw -UpstreamName 'backend_api'
    $pFe = Get-NginxUpstreamPortFromText -Content $raw -UpstreamName 'frontend_server'
    $pAd = Get-NginxUpstreamPortFromText -Content $raw -UpstreamName 'admin_server'
    Write-Host '[CHECK] nginx upstream (must match manual Python listeners):' -ForegroundColor Cyan
    Write-Host ('        backend_api      conf={0} expect={1}' -f $pApi, $ExpectBackendPort) -ForegroundColor DarkGray
    Write-Host ('        frontend_server  conf={0} expect={1}' -f $pFe, $ExpectFrontendPort) -ForegroundColor DarkGray
    Write-Host ('        admin_server     conf={0} expect={1}' -f $pAd, $ExpectAdminPort) -ForegroundColor DarkGray
    $bad = $false
    if ($null -eq $pApi -or $pApi -ne $ExpectBackendPort) {
        $bad = $true
    }
    if ($null -eq $pFe -or $pFe -ne $ExpectFrontendPort) {
        $bad = $true
    }
    if ($null -eq $pAd -or $pAd -ne $ExpectAdminPort) {
        $bad = $true
    }
    if ($bad) {
        throw ('nginx upstream ports do not match manual deploy (expect backend={0} frontend={1} admin={2}). Edit {3}' -f $ExpectBackendPort, $ExpectFrontendPort, $ExpectAdminPort, $confFull)
    }
    foreach ($rx in @('^\s*ssl_certificate\s+([^;\r\n]+);', '^\s*ssl_certificate_key\s+([^;\r\n]+);')) {
        foreach ($line in ($raw -split "`r?`n")) {
            $mm = [regex]::Match($line, $rx)
            if (-not $mm.Success) {
                continue
            }
            $pp = $mm.Groups[1].Value.Trim().Trim("'").Trim('"')
            $ppNorm = $pp -replace '/', '\'
            if (-not (Test-Path -LiteralPath $ppNorm)) {
                Write-Host ('[WARN] TLS file missing on disk: {0}' -f $ppNorm) -ForegroundColor Yellow
            }
        }
    }
    Write-Host '[OK] nginx upstream ports aligned with manual deploy; TLS paths checked if present.' -ForegroundColor Green
}

# Do not rename current dir on Windows; mirror content in place.
function Invoke-RobocopyMirror {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,
        [Parameter(Mandatory = $true)]
        [string]$Destination
    )
    $rob = Join-Path $env:SystemRoot "System32\robocopy.exe"
    if (-not (Test-Path -LiteralPath $rob)) {
        throw "robocopy.exe not found."
    }
    $src = [string]$Source
    $dst = [string]$Destination
    if ($src.EndsWith('\')) { $src = $src.Substring(0, $src.Length - 1) }
    if ($dst.EndsWith('\')) { $dst = $dst.Substring(0, $dst.Length - 1) }
    # Quiet mode: no per-file/per-dir spam in console (especially admin/node_modules).
    $null = & $rob $src $dst /MIR /R:8 /W:5 /MT:8 /NP /NFL /NDL /NJH /NJS
    $code = $LASTEXITCODE
    if (-not (Test-RobocopyExitOk $code)) {
        throw (Format-RobocopyFailureMessage -ExitCode $code -Src $src -Dst $dst)
    }
}

# 需在脚本中已解析 $PythonExe 之后调用；用于释放 _psycopg*.pyd / current 目录占用。
# 枚举进程：优先 Win32_Process（可看 CommandLine）；避免 Get-Variable（部分宿主报「无法使用指定的命名参数解析参数集」）；
# 避免 Get-Process -Name 多名称；CIM/WMI 的 Filter 不用 OR，分两次查询更稳。
# 说明：Win32_Process.ExecutablePath 在不少主机上为空（权限/会话差异），若仅按路径前缀匹配会杀不掉旧进程；
# 因此补充 CommandLine 匹配（同解释器路径、或 DeployRoot\current 下手工启动入口脚本路径）。
function Invoke-KillPythonSameInterpreter {
    if ($env:OS -ne 'Windows_NT') {
        return
    }
    try {
        if (-not (Test-Path -LiteralPath $PythonExe)) {
            Write-Host "[WARN] Kill python: PythonExe path not found." -ForegroundColor Yellow
            return
        }
        $fullPyKill = (Resolve-Path -LiteralPath $PythonExe).Path
        $pyRootKill = Split-Path -LiteralPath $fullPyKill -Parent
        $pyRootNorm = $pyRootKill
        try {
            $pyRootNorm = [System.IO.Path]::GetFullPath($pyRootKill)
        }
        catch {
            $pyRootNorm = $pyRootKill
        }

        # 与 Start-ManualStockQuoteProcesses 对齐：用于 ExecutablePath 为空时按命令行识别本部署 worker
        # 勿用 Get-Variable：在部分 PS5.1 宿主会与 $ErrorActionPreference=Stop 组合触发 ParameterBindingException，导致整段 kill 被跳过。
        $currentScriptMarkers = @()
        $cdRaw = $null
        if (Test-Path -LiteralPath 'variable:currentDir') {
            try {
                $cdRaw = [string](Get-Item -LiteralPath 'variable:currentDir').Value
            }
            catch {
                $cdRaw = $null
            }
        }
        if (-not [string]::IsNullOrWhiteSpace($cdRaw)) {
            $cd = $cdRaw.Trim()
            if (Test-Path -LiteralPath $cd) {
                try {
                    $curFull = (Resolve-Path -LiteralPath $cd).Path
                    foreach ($rel in @('start_backend_core.py', 'start_backend_api.py', 'start_scheduler.py', 'start_frontend.py')) {
                        $currentScriptMarkers += (Join-Path $curFull $rel)
                    }
                    $currentScriptMarkers += (Join-Path $curFull 'admin\dist')
                }
                catch {
                    $currentScriptMarkers = @()
                }
            }
        }

        $cimList = [System.Collections.Generic.List[object]]::new()
        foreach ($procBaseName in @('python.exe', 'pythonw.exe')) {
            $oneFilter = "Name='$procBaseName'"
            try {
                if (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {
                    foreach ($row in @(Get-CimInstance -ClassName Win32_Process -Filter $oneFilter -ErrorAction SilentlyContinue)) {
                        if ($null -ne $row) {
                            $cimList.Add($row)
                        }
                    }
                }
            }
            catch {
            }
        }
        if ($cimList.Count -eq 0) {
            foreach ($procBaseName in @('python.exe', 'pythonw.exe')) {
                $oneFilter = "Name='$procBaseName'"
                try {
                    foreach ($row in @(Get-WmiObject -Class Win32_Process -Filter $oneFilter -ErrorAction SilentlyContinue)) {
                        if ($null -ne $row) {
                            $cimList.Add($row)
                        }
                    }
                }
                catch {
                }
            }
        }
        # CIM/WMI 全失败时：用 .NET 按 MainModule 路径匹配同解释器（无 CommandLine，仅路径规则）
        if ($cimList.Count -eq 0) {
            foreach ($procBase in @('python', 'pythonw')) {
                try {
                    foreach ($dp in @([System.Diagnostics.Process]::GetProcessesByName($procBase))) {
                        if ($null -eq $dp) {
                            continue
                        }
                        $exeP = $null
                        try {
                            $exeP = [string]$dp.MainModule.FileName
                        }
                        catch {
                            continue
                        }
                        if ([string]::IsNullOrWhiteSpace($exeP)) {
                            continue
                        }
                        $matchRoot = $false
                        try {
                            $exeNormP = [System.IO.Path]::GetFullPath($exeP)
                            if ($exeNormP.StartsWith($pyRootNorm, [StringComparison]::OrdinalIgnoreCase)) {
                                $matchRoot = $true
                            }
                        }
                        catch {
                            if ($exeP.StartsWith($pyRootKill, [StringComparison]::OrdinalIgnoreCase)) {
                                $matchRoot = $true
                            }
                        }
                        if (-not $matchRoot) {
                            continue
                        }
                        $cimList.Add([PSCustomObject]@{ ProcessId = $dp.Id; ExecutablePath = $exeP; CommandLine = [string]::Empty })
                    }
                }
                catch {
                }
            }
        }

        $taskkillExe = Join-Path $env:SystemRoot "System32\taskkill.exe"

        foreach ($wp in $cimList) {
            $exePathKill = [string]$wp.ExecutablePath
            $cmdLineKill = [string]$wp.CommandLine

            $matchSameInterpreter = $false
            if (-not [string]::IsNullOrWhiteSpace($exePathKill)) {
                try {
                    $exeNorm = [System.IO.Path]::GetFullPath($exePathKill)
                    if ($exeNorm.StartsWith($pyRootNorm, [StringComparison]::OrdinalIgnoreCase)) {
                        $matchSameInterpreter = $true
                    }
                }
                catch {
                    if ($exePathKill.StartsWith($pyRootKill, [StringComparison]::OrdinalIgnoreCase)) {
                        $matchSameInterpreter = $true
                    }
                }
            }

            if (-not $matchSameInterpreter -and -not [string]::IsNullOrWhiteSpace($cmdLineKill)) {
                if ($cmdLineKill.IndexOf($fullPyKill, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
                    $matchSameInterpreter = $true
                }
            }

            $matchDeployWorker = $false
            if (-not $matchSameInterpreter -and $currentScriptMarkers.Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($cmdLineKill)) {
                foreach ($marker in $currentScriptMarkers) {
                    if ($cmdLineKill.IndexOf($marker, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
                        $matchDeployWorker = $true
                        break
                    }
                }
            }

            if (-not $matchSameInterpreter -and -not $matchDeployWorker) {
                continue
            }

            $procIdKill = [int]$wp.ProcessId
            if ($procIdKill -le 0) {
                continue
            }

            $reason = if ($matchDeployWorker) { 'deploy-current cmdline' } else { 'same-interpreter' }
            try {
                Stop-Process -Id $procIdKill -Force -ErrorAction Stop
                Write-Host ("[KILL] PID {0} ({1}) exe={2}" -f $procIdKill, $reason, $(if ([string]::IsNullOrWhiteSpace($exePathKill)) { '(empty)' } else { $exePathKill })) -ForegroundColor DarkYellow
            }
            catch {
                Write-Host ("[WARN] Stop-Process PID {0}: {1}" -f $procIdKill, $_.Exception.Message) -ForegroundColor Yellow
                if (Test-Path -LiteralPath $taskkillExe) {
                    try {
                        $null = & $taskkillExe /F /PID $procIdKill 2>&1
                        if ($LASTEXITCODE -eq 0) {
                            Write-Host ("[KILL] taskkill /F /PID {0} ({1})" -f $procIdKill, $reason) -ForegroundColor DarkYellow
                        }
                        else {
                            Write-Host ("[WARN] taskkill exit {0} for PID {1}" -f $LASTEXITCODE, $procIdKill) -ForegroundColor Yellow
                        }
                    }
                    catch {
                        Write-Host ("[WARN] taskkill failed for PID {0}: {1}" -f $procIdKill, $_.Exception.Message) -ForegroundColor Yellow
                    }
                }
            }
        }
    }
    catch {
        Write-Host ("[WARN] Kill python helper failed: {0}" -f $_.Exception.Message) -ForegroundColor Yellow
    }
}

# 无 NSSM：后台启动与手工一致的 5 个入口（顺序固定）；日志 shared\logs\manual-*.log
# 1) admin 静态：python -m http.server 8001（cwd=admin\dist）
# 2) start_backend_core.py  3) start_backend_api.py  4) start_scheduler.py  5) start_frontend.py
function Start-ManualStockQuoteProcesses {
    param(
        [Parameter(Mandatory = $true)][string]$PythonExePath,
        [Parameter(Mandatory = $true)][string]$WorkDir,
        [Parameter(Mandatory = $true)][string]$LogDir,
        [int]$AdminHttpPort = 8001
    )
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    $tasks = @(
        @{ Mode = 'httpServer'; Name = 'manual-admin-http'; CwdRel = 'admin\dist'; Display = ('python -m http.server {0} (cwd admin\dist)' -f $AdminHttpPort) },
        @{ Mode = 'script'; Name = 'manual-core'; Script = 'start_backend_core.py'; Display = 'python start_backend_core.py' },
        @{ Mode = 'script'; Name = 'manual-api'; Script = 'start_backend_api.py'; Display = 'python start_backend_api.py' },
        @{ Mode = 'script'; Name = 'manual-notify'; Script = 'start_scheduler.py'; Display = 'python start_scheduler.py' },
        @{ Mode = 'script'; Name = 'manual-frontend'; Script = 'start_frontend.py'; Display = 'python start_frontend.py' }
    )
    foreach ($t in $tasks) {
        $outLog = Join-Path $LogDir ($t.Name + '.out.log')
        $errLog = Join-Path $LogDir ($t.Name + '.err.log')
        $workForTask = $WorkDir
        $argList = $null
        if ($t.Mode -eq 'httpServer') {
            $workForTask = Join-Path $WorkDir $t.CwdRel
            if (-not (Test-Path -LiteralPath $workForTask)) {
                Write-Host ('[WARN] admin\dist missing, skip admin static server: {0}' -f $workForTask) -ForegroundColor Yellow
                continue
            }
            $argList = @('-m', 'http.server', ([string]$AdminHttpPort))
        }
        else {
            $scriptFull = Join-Path $WorkDir $t.Script
            if (-not (Test-Path -LiteralPath $scriptFull)) {
                Write-Host ('[WARN] Missing script, skip: {0}' -f $scriptFull) -ForegroundColor Yellow
                continue
            }
            $argList = @($scriptFull)
        }
        try {
            $p = Start-Process -FilePath $PythonExePath `
                -ArgumentList $argList `
                -WorkingDirectory $workForTask `
                -WindowStyle Hidden `
                -RedirectStandardOutput $outLog `
                -RedirectStandardError $errLog `
                -PassThru `
                -ErrorAction Stop
            Write-Host ('[START] {0} PID={1}' -f $t.Display, $p.Id) -ForegroundColor Green
            Write-Host ('        cwd={0}' -f $workForTask) -ForegroundColor DarkGray
            Write-Host ('        stdout={0}' -f $outLog) -ForegroundColor DarkGray
            Write-Host ('        stderr={0}' -f $errLog) -ForegroundColor DarkGray
        }
        catch {
            Write-Host ('[WARN] Failed to start ({0}): {1}' -f $t.Display, $_.Exception.Message) -ForegroundColor Yellow
        }
    }
}

$PythonExe = Get-NonEmptyString $PythonExe "python"
$PythonExe = Resolve-ToPythonExePath $PythonExe
# 强制为单个字符串，避免少数环境下解析为数组导致后续绑定歧义
$PythonExe = [string](@($PythonExe)[0])

Assert-ReleaseScriptPathMatchesDeployRoot -DeployRootPath $DeployRoot -AllowMismatch:$AllowScriptPathMismatch

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

Push-Location $newRelease
$locationPushed = $true

if (-not $SkipPip) {
    Write-DeployStep 'pip install (requirements-prod.txt -> backend_api/requirements-minimal.txt + backend_core/requirements-minimal.txt)'
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
    Invoke-PythonPip @(
        'install',
        '--prefer-binary',
        '--only-binary', 'pydantic-core',
        '--only-binary', 'pydantic',
        '-r', 'requirements-prod.txt'
    )
}
else {
    Write-Host '[INFO] SkipPip: no pip on server (pre-install deps into this Python or use current\requirements-prod.txt manually).' -ForegroundColor Yellow
}

if (-not $skipAdminOnServer) {
    Write-DeployStep "Build admin"
}
$adminDirForNpm = Join-Path $newRelease "admin"
if (-not $skipAdminOnServer -and (Test-Path -LiteralPath (Join-Path $adminDirForNpm "package.json"))) {
    $freeGbBeforeAdmin = Get-DriveFreeSpaceGB $adminDirForNpm
    if ($freeGbBeforeAdmin -ge 0) {
        Write-Host ('[INFO] Free disk before admin build: {0} GB (min required {1} GB)' -f $freeGbBeforeAdmin, $MinFreeSpaceGBForAdminBuild) -ForegroundColor DarkGray
    }
    if ($freeGbBeforeAdmin -ge 0 -and $freeGbBeforeAdmin -lt $MinFreeSpaceGBForAdminBuild) {
        if (-not $SkipAutoCleanupOldReleases) {
            Write-Host ('[WARN] Low disk space ({0} GB). Auto cleanup releases, keep latest {1}...' -f $freeGbBeforeAdmin, $KeepLatestReleases) -ForegroundColor Yellow
            Remove-OldReleaseFolders -ReleasesDirectory $releasesDir -KeepCount $KeepLatestReleases
            $freeGbBeforeAdmin = Get-DriveFreeSpaceGB $adminDirForNpm
            if ($freeGbBeforeAdmin -ge 0) {
                Write-Host ('[INFO] Free disk after cleanup: {0} GB' -f $freeGbBeforeAdmin) -ForegroundColor DarkGray
            }
        }
    }
    if ($freeGbBeforeAdmin -ge 0 -and $freeGbBeforeAdmin -lt $MinFreeSpaceGBForAdminBuild) {
        throw ('Insufficient disk space for admin npm build: {0} GB < {1} GB. Clean DeployRoot\releases and temp files, then retry. Use -SkipAutoCleanupOldReleases to disable auto cleanup.' -f $freeGbBeforeAdmin, $MinFreeSpaceGBForAdminBuild)
    }

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
            $freeGbOnFail = Get-DriveFreeSpaceGB $adminDirForNpm
            if ($freeGbOnFail -ge 0) {
                throw ("npm install failed (exit {0}). Free disk: {1} GB. If you see ENOSPC, clean DeployRoot\\releases and npm cache, then retry." -f $pInstall.ExitCode, $freeGbOnFail)
            }
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
            $freeGbOnFail = Get-DriveFreeSpaceGB $adminDirForNpm
            if ($freeGbOnFail -ge 0) {
                throw ("npm install via cmd failed (exit {0}). Free disk: {1} GB. If you see ENOSPC, clean DeployRoot\\releases and npm cache, or pass -NpmExe full path to npm.cmd." -f $pInstall.ExitCode, $freeGbOnFail)
            }
            throw ("npm install via cmd failed (exit {0}). Install Node.js or pass -NpmExe full path to npm.cmd." -f $pInstall.ExitCode)
        }
        $pBuild = Start-Process -FilePath $cmdExePath -ArgumentList @('/d', '/c', 'npm.cmd run build') -WorkingDirectory $adminDirForNpm -Wait -PassThru -NoNewWindow
        if ($null -eq $pBuild.ExitCode -or $pBuild.ExitCode -ne 0) {
            throw ("npm run build via cmd failed (exit {0})." -f $pBuild.ExitCode)
        }
    }
}
elseif (-not $skipAdminOnServer) {
    Write-Host '[WARN] admin/package.json not found, skip admin build'
}
elseif ($skipAdminOnServer) {
    Write-Host '[INFO] Skip admin npm on server (pre-built zip). Ensure admin\dist exists in the package.' -ForegroundColor DarkGray
    $distCheck = Join-Path $adminDirForNpm 'dist'
    if (-not (Test-Path -LiteralPath $distCheck)) {
        Write-Host '[WARN] admin\dist not found under expanded release; UI may be broken until you pack with deploy.ps1 build.' -ForegroundColor Yellow
    }
}

Write-DeployStep 'Optional migrate_db.py'
if (Test-Path -LiteralPath (Join-Path $newRelease 'migrate_db.py')) {
    & $PythonExe migrate_db.py
}

# Leave $newRelease first, then switch content under current.
if ($locationPushed) {
    Pop-Location
    $locationPushed = $false
}

Write-DeployStep 'Prepare to switch current (cwd + stop services + unlock)'
try {
    $deployResolved = (Resolve-Path -LiteralPath $DeployRoot).Path
    Set-Location -LiteralPath $deployResolved
}
catch {
    Write-Host ('[WARN] Set-Location DeployRoot failed (another process may lock current): {0}' -f $_.Exception.Message) -ForegroundColor Yellow
}

Write-DeployStep 'Stop Windows services before switching current'
Stop-StockQuoteServicesIfRunning
Start-Sleep -Seconds 8

# 镜像 current 前必须结束同解释器下的旧 Python（手工/NSSM 均适用），否则句柄占用导致 robocopy 失败。
# 与 -SkipKillPythonBeforePip 无关：该开关只跳过 pip 阶段的 kill，不跳过此处。
if ($env:OS -eq 'Windows_NT') {
    $killStepMsg = if ($ManualProcessDeploy) {
        'Kill old python.exe/pythonw (same interpreter as -PythonExe) before overwriting current (manual deploy)'
    }
    else {
        'Kill python.exe/pythonw (same interpreter as -PythonExe) before overwriting current (unlock directory)'
    }
    Write-DeployStep $killStepMsg
    Invoke-KillPythonSameInterpreter
    Start-Sleep -Seconds 3
}

Write-DeployStep 'Switch current (robocopy in-place; avoids Move-Item lock)'
if ($env:OS -ne 'Windows_NT') {
    throw 'release.ps1 current switching requires robocopy on Windows.'
}
if (Test-Path -LiteralPath $currentDir) {
    Write-Host ('[DEPLOY] Backup current -> {0}' -f (Split-Path -Leaf $backupCurrent)) -ForegroundColor DarkGray
    Invoke-RobocopyMirror -Source $currentDir -Destination $backupCurrent
}
else {
    New-Item -ItemType Directory -Path $currentDir -Force | Out-Null
}
Write-Host '[DEPLOY] Mirror new release -> current' -ForegroundColor DarkGray
Invoke-RobocopyMirror -Source $newRelease -Destination $currentDir
Remove-DirectoryRobust $newRelease

try {
    if ($ManualProcessDeploy) {
        Write-DeployStep 'Start Python workers (manual processes; NSSM not used)'
        if ($env:OS -eq 'Windows_NT') {
            Invoke-KillPythonSameInterpreter
            Start-Sleep -Seconds 2
        }
        $manualLogDir = Join-Path $sharedDir 'logs'
        Start-ManualStockQuoteProcesses -PythonExePath $PythonExe -WorkDir $currentDir -LogDir $manualLogDir -AdminHttpPort $ManualAdminHttpPort
    }
    else {
        Write-DeployStep 'Restart Windows services (if exist)'
        Restart-IfExists 'stock-quote-api'
        Restart-IfExists 'stock-quote-core'
        Restart-IfExists 'stock-quote-notify'
    }

    if ($ManualProcessDeploy) {
        Assert-NginxConfMatchesManualDeploy `
            -NginxHomePath $NginxHome `
            -ConfRelativePath $NginxConfFile `
            -ExpectBackendPort $NginxExpectBackendPort `
            -ExpectFrontendPort $NginxExpectFrontendPort `
            -ExpectAdminPort $ManualAdminHttpPort `
            -SkipCheck:$SkipNginxUpstreamCheck
    }

    Write-DeployStep 'nginx -t and reload'
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
            Write-Host '[WARN] nginx -t failed, skip reload' -ForegroundColor Yellow
        }
    }
    finally {
        if ($null -ne $nginxWorkDir) {
            Pop-Location
        }
    }

    if ($SkipHealthCheck) {
        Write-Host '[WARN] Health check skipped by -SkipHealthCheck.' -ForegroundColor Yellow
    }
    else {
        Write-DeployStep 'Health check'
        $okApi = Test-Health -Name 'api' -url 'http://127.0.0.1:5000/' -retry $HealthRetry -timeoutSec $HealthTimeoutSec -intervalSec $HealthIntervalSec
        $okWeb = Test-Health -Name 'web' -url 'https://www.icemaplecity.com/' -retry $HealthRetry -timeoutSec $HealthTimeoutSec -intervalSec $HealthIntervalSec
        $okAdmin = Test-Health -Name 'admin' -url 'https://www.icemaplecity.com/admin/' -retry $HealthRetry -timeoutSec $HealthTimeoutSec -intervalSec $HealthIntervalSec

        if (-not ($okApi -and $okWeb -and $okAdmin)) {
            throw ('Health check failed: api={0} web={1} admin={2}' -f $okApi, $okWeb, $okAdmin)
        }
    }

    Remove-DirectoryRobust $backupCurrent
    Write-Host ('[SUCCESS] Released: {0}' -f $timestamp)
}
catch {
    Write-Host ('ERROR: Release failed, rollback: ' + $_.Exception.Message) -ForegroundColor Red
    if ($env:OS -eq 'Windows_NT' -and (Test-Path -LiteralPath $backupCurrent)) {
        try {
            if (-not (Test-Path -LiteralPath $currentDir)) {
                New-Item -ItemType Directory -Path $currentDir -Force | Out-Null
            }
            Write-Host '[ROLLBACK] robocopy mirror backup -> current' -ForegroundColor Yellow
            Invoke-RobocopyMirror -Source $backupCurrent -Destination $currentDir
        }
        catch {
            Write-Host ('[WARN] Rollback restore via robocopy failed: {0}' -f $_.Exception.Message) -ForegroundColor Yellow
        }
    }
    if (-not $ManualProcessDeploy) {
        Restart-IfExists 'stock-quote-api'
        Restart-IfExists 'stock-quote-core'
        Restart-IfExists 'stock-quote-notify'
    }
    throw
}
finally {
    if ($locationPushed) {
        Pop-Location
    }
}
