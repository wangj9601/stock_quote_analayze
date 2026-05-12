<#
.SYNOPSIS
    单独结束「本 stock_quote 部署」相关的 python.exe / pythonw.exe（与 release.ps1 手工进程识别规则一致）。

.DESCRIPTION
    匹配条件（满足其一即视为本项目相关）：
    1) 命令行包含 DeployRoot\current 下入口路径：start_backend_core.py / start_backend_api.py /
       start_scheduler.py / start_frontend.py，或 current\admin\dist（与手工启动一致）；
    2) 若指定 -PythonExe：与 release.ps1 一致，同时结束「同解释器」进程（ExecutablePath 位于该 python 目录下，或命令行含该 python 全路径）。
       未指定 -PythonExe 时，仅按上述 current 路径标记匹配（更安全）。

    需要 Windows；建议以管理员运行以便结束其它会话启动的进程。

.EXAMPLE
    .\Kill-StockQuotePython.ps1
    # 使用默认 DeployRoot C:\deploy\stock_quote

.EXAMPLE
    .\Kill-StockQuotePython.ps1 -DeployRoot 'D:\work\stock_quote_deploy' -WhatIf
    # 仅列出将结束的 PID，不实际结束

.EXAMPLE
    .\Kill-StockQuotePython.ps1 -DeployRoot 'C:\deploy\stock_quote' -PythonExe 'C:\Python311\python.exe'
    # 同时按同解释器路径辅助匹配（与 release -PythonExe 一致）
#>

param(
    [string]$DeployRoot = 'C:\deploy\stock_quote',
    [string]$PythonExe = '',
    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'

if ($env:OS -ne 'Windows_NT') {
    Write-Host '仅支持 Windows。' -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path -LiteralPath $DeployRoot)) {
    Write-Host ("[ERR] DeployRoot 不存在: {0}" -f $DeployRoot) -ForegroundColor Red
    exit 1
}

$deployFull = (Resolve-Path -LiteralPath $DeployRoot).Path
$currentJoin = Join-Path $deployFull 'current'
$currentFull = if (Test-Path -LiteralPath $currentJoin) {
    (Resolve-Path -LiteralPath $currentJoin).Path
}
else {
    $currentJoin
}

$markers = [System.Collections.ArrayList]@()
foreach ($rel in @('start_backend_core.py', 'start_backend_api.py', 'start_scheduler.py', 'start_frontend.py')) {
    [void]$markers.Add((Join-Path $currentFull $rel))
}
[void]$markers.Add((Join-Path $currentFull 'admin\dist'))
# 命令行里可能出现正斜杠
foreach ($m in @($markers.ToArray())) {
    $u = $m -replace '\\', '/'
    if ($u -ne $m -and -not $markers.Contains($u)) {
        [void]$markers.Add($u)
    }
}

$fullPyKill = $null
$pyRootKill = $null
$pyRootNorm = $null
if (-not [string]::IsNullOrWhiteSpace($PythonExe)) {
    if (-not (Test-Path -LiteralPath $PythonExe)) {
        Write-Host ("[ERR] -PythonExe 路径不存在: {0}" -f $PythonExe) -ForegroundColor Red
        exit 1
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
}

function Get-Win32PythonProcesses {
    $procFilter = "Name='python.exe' OR Name='pythonw.exe'"
    $list = @()
    try {
        if (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {
            $list = @(Get-CimInstance -ClassName Win32_Process -Filter $procFilter -ErrorAction Stop)
        }
    }
    catch {
        $list = @()
    }
    if ($list.Count -eq 0) {
        try {
            $list = @(Get-WmiObject -Class Win32_Process -Filter $procFilter -ErrorAction Stop)
        }
        catch {
            $list = @()
        }
    }
    return $list
}

function Test-MatchDeployMarkers {
    param([string]$CmdLine)
    if ([string]::IsNullOrWhiteSpace($CmdLine)) {
        return $false
    }
    foreach ($mk in $markers) {
        if ($CmdLine.IndexOf($mk, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            return $true
        }
    }
    return $false
}

function Test-MatchSameInterpreter {
    param([string]$ExePath, [string]$CmdLine)
    if ($null -eq $fullPyKill) {
        return $false
    }
    if (-not [string]::IsNullOrWhiteSpace($ExePath)) {
        try {
            $exeNorm = [System.IO.Path]::GetFullPath($ExePath)
            if ($exeNorm.StartsWith($pyRootNorm, [StringComparison]::OrdinalIgnoreCase)) {
                return $true
            }
        }
        catch {
            if ($ExePath.StartsWith($pyRootKill, [StringComparison]::OrdinalIgnoreCase)) {
                return $true
            }
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($CmdLine)) {
        if ($CmdLine.IndexOf($fullPyKill, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            return $true
        }
    }
    return $false
}

Write-Host ("[INFO] DeployRoot={0}" -f $deployFull) -ForegroundColor Cyan
Write-Host ("[INFO] current={0}" -f $currentFull) -ForegroundColor Cyan
if ($null -ne $fullPyKill) {
    Write-Host ("[INFO] PythonExe={0}" -f $fullPyKill) -ForegroundColor Cyan
}
if ($WhatIf) {
    Write-Host '[INFO] -WhatIf：仅列出将结束的进程，不执行 Stop-Process/taskkill。' -ForegroundColor Yellow
}

$cimList = Get-Win32PythonProcesses
if ($cimList.Count -eq 0) {
    Write-Host '[INFO] 未发现 python.exe / pythonw.exe 进程。' -ForegroundColor Green
    exit 0
}

$taskkillExe = Join-Path $env:SystemRoot 'System32\taskkill.exe'
$killed = 0

foreach ($wp in $cimList) {
    $exePathKill = [string]$wp.ExecutablePath
    $cmdLineKill = [string]$wp.CommandLine
    $matchDeploy = Test-MatchDeployMarkers -CmdLine $cmdLineKill
    $matchInterp = Test-MatchSameInterpreter -ExePath $exePathKill -CmdLine $cmdLineKill
    # 与 release.ps1 Invoke-KillPythonSameInterpreter：命中 current 标记或同解释器即结束
    $shouldKill = $matchDeploy -or $matchInterp

    if (-not $shouldKill) {
        continue
    }

    $procIdKill = [int]$wp.ProcessId
    if ($procIdKill -le 0) {
        continue
    }

    $reason = if ($matchDeploy -and $matchInterp) { 'markers+interpreter' }
    elseif ($matchDeploy) { 'deploy-markers' }
    else { 'same-interpreter' }

    if ($WhatIf) {
        Write-Host ("[WHATIF] PID={0} reason={1} exe={2}" -f $procIdKill, $reason, $(if ([string]::IsNullOrWhiteSpace($exePathKill)) { '(empty)' } else { $exePathKill })) -ForegroundColor Magenta
        if (-not [string]::IsNullOrWhiteSpace($cmdLineKill)) {
            $snippet = $cmdLineKill
            if ($snippet.Length -gt 200) {
                $snippet = $snippet.Substring(0, 200) + '...'
            }
            Write-Host ("         cmd: {0}" -f $snippet) -ForegroundColor DarkGray
        }
        $killed++
        continue
    }

    try {
        Stop-Process -Id $procIdKill -Force -ErrorAction Stop
        Write-Host ("[KILL] PID={0} ({1})" -f $procIdKill, $reason) -ForegroundColor DarkYellow
        $killed++
    }
    catch {
        Write-Host ("[WARN] Stop-Process PID {0}: {1}" -f $procIdKill, $_.Exception.Message) -ForegroundColor Yellow
        if (Test-Path -LiteralPath $taskkillExe) {
            $null = & $taskkillExe /F /PID $procIdKill 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host ("[KILL] taskkill /F /PID {0} ({1})" -f $procIdKill, $reason) -ForegroundColor DarkYellow
                $killed++
            }
            else {
                Write-Host ("[WARN] taskkill 退出码 {0} PID={1}" -f $LASTEXITCODE, $procIdKill) -ForegroundColor Yellow
            }
        }
    }
}

Write-Host ("[DONE] 处理结束，共匹配并尝试结束 {0} 个进程。" -f $killed) -ForegroundColor Green
