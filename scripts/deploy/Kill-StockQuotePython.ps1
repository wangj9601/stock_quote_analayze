<#
.SYNOPSIS
    Stop python.exe / pythonw.exe tied to this stock_quote deploy (same rules as release.ps1 manual workers).

.DESCRIPTION
    Match if CommandLine contains paths under DeployRoot\current for:
    start_backend_core.py, start_backend_api.py, start_scheduler.py, start_frontend.py, or current\admin\dist.

    -WhatIf typically lists ~4 roots (the four entry scripts). Production start_backend_api.py runs uvicorn with
    --workers N; worker python.exe processes usually do NOT contain start_backend_api.py in CommandLine, so they
    are not listed separately. Actual termination uses taskkill /T to stop each matched root AND its descendant
    processes (uvicorn workers, --reload child, etc.). When many PIDs match (e.g. -PythonExe), only roots
    (parent PID not in the matched set) receive taskkill /T to avoid Windows errors on child-only kills.

    Optional -PythonExe adds same-interpreter matching (ExecutablePath under that python folder, or CommandLine
    contains full python path). WARNING: -PythonExe alone matches every python.exe using that install tree — use
    only when you understand the blast radius.

.EXAMPLE
    .\Kill-StockQuotePython.ps1 -WhatIf

.EXAMPLE
    .\Kill-StockQuotePython.ps1 -DeployRoot 'D:\deploy\stock_quote' -PythonExe 'C:\Python311\python.exe'
#>

param(
    [string]$DeployRoot = 'C:\deploy\stock_quote',
    [string]$PythonExe = '',
    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'

if ($env:OS -ne 'Windows_NT') {
    Write-Host "This script supports Windows only." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path -LiteralPath $DeployRoot)) {
    Write-Host "ERR: DeployRoot not found: $DeployRoot" -ForegroundColor Red
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
        Write-Host "ERR: -PythonExe path not found: $PythonExe" -ForegroundColor Red
        exit 1
    }
    $fullPyKill = (Resolve-Path -LiteralPath $PythonExe).Path
    # Windows PowerShell 5.1：Split-Path -LiteralPath -Parent 会触发「无法使用指定的命名参数解析参数集」
    $pyRootKill = [System.IO.Path]::GetDirectoryName($fullPyKill)
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

Write-Host "INFO: DeployRoot=$deployFull" -ForegroundColor Cyan
Write-Host "INFO: current=$currentFull" -ForegroundColor Cyan
if ($null -ne $fullPyKill) {
    Write-Host "INFO: PythonExe=$fullPyKill" -ForegroundColor Cyan
}
if ($WhatIf) {
    Write-Host "INFO: -WhatIf lists matched ROOT processes only (no kill). Uvicorn/Celery workers under the same tree are not shown but are removed when you run without -WhatIf (taskkill /T)." -ForegroundColor Yellow
}

$cimList = Get-Win32PythonProcesses
if ($cimList.Count -eq 0) {
    Write-Host "INFO: No python.exe / pythonw.exe processes." -ForegroundColor Green
    exit 0
}

# 先收集所有「应结束」的进程；仅对「父进程不在该集合内」的根执行 taskkill /T，避免对子进程单独 /T 触发
# 「无法终止 PID xxx（属于 PID yyy 子进程）」类错误，并避免对已由父树杀掉的 PID 重复 taskkill。
# Windows PowerShell 5.1 无 [ArrayList]::new() / [HashSet[int]]::new() 的便捷写法，用 New-Object 与 Hashtable。
$matchedRows = New-Object System.Collections.ArrayList
foreach ($wp in $cimList) {
    $exePathKill = [string]$wp.ExecutablePath
    $cmdLineKill = [string]$wp.CommandLine
    $matchDeploy = Test-MatchDeployMarkers -CmdLine $cmdLineKill
    $matchInterp = Test-MatchSameInterpreter -ExePath $exePathKill -CmdLine $cmdLineKill
    $shouldKill = $matchDeploy -or $matchInterp
    if (-not $shouldKill) {
        continue
    }
    $procIdKill = [int]$wp.ProcessId
    if ($procIdKill -le 0) {
        continue
    }
    $ppid = 0
    try {
        $ppid = [int]$wp.ParentProcessId
    }
    catch {
        $ppid = 0
    }
    $reason = if ($matchDeploy -and $matchInterp) { 'markers+interpreter' } elseif ($matchDeploy) { 'deploy-markers' } else { 'same-interpreter' }
    [void]$matchedRows.Add([pscustomobject]@{
            ProcessId         = $procIdKill
            ParentProcessId   = $ppid
            ExecutablePath    = $exePathKill
            CommandLine       = $cmdLineKill
            Reason            = $reason
        })
}

if ($matchedRows.Count -eq 0) {
    Write-Host "INFO: No matching python processes for this DeployRoot / filters." -ForegroundColor Green
    exit 0
}

$matchedIdSet = @{}
foreach ($r in $matchedRows) {
    $matchedIdSet[[int]$r.ProcessId] = $true
}

$rootRows = New-Object System.Collections.ArrayList
foreach ($r in $matchedRows) {
    $ppid = [int]$r.ParentProcessId
    if (-not $matchedIdSet.ContainsKey($ppid)) {
        [void]$rootRows.Add($r)
    }
}

$skippedNonRoot = $matchedRows.Count - $rootRows.Count
if ($skippedNonRoot -gt 0) {
    Write-Host "INFO: $skippedNonRoot matched process(es) have parent also matched — only $($rootRows.Count) taskkill /T root(s) (avoids child-only taskkill errors)." -ForegroundColor Cyan
}

$taskkillExe = [System.IO.Path]::Combine($env:SystemRoot, 'System32', 'taskkill.exe')
$killed = 0

foreach ($r in $rootRows) {
    $procIdKill = $r.ProcessId
    $reason = $r.Reason
    $exePathKill = $r.ExecutablePath
    $cmdLineKill = $r.CommandLine

    if ($WhatIf) {
        $exeDisp = if ([string]::IsNullOrWhiteSpace($exePathKill)) { 'NO_EXE_PATH' } else { $exePathKill }
        Write-Host "WHATIF: PID=$procIdKill reason=$reason exe=$exeDisp (taskkill /T root; subtree included)" -ForegroundColor Magenta
        if (-not [string]::IsNullOrWhiteSpace($cmdLineKill)) {
            $snippet = $cmdLineKill
            if ($snippet.Length -gt 200) {
                $snippet = $snippet.Substring(0, 200) + '...'
            }
            Write-Host "cmd: $snippet" -ForegroundColor DarkGray
        }
        $killed++
        continue
    }

    # taskkill 会向 stderr 写中文提示；脚本顶部为 Stop 时会变成终止错误，故临时忽略
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        if (Test-Path -LiteralPath $taskkillExe) {
            $null = & $taskkillExe /F /T /PID $procIdKill 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "KILL: taskkill /F /T PID=$procIdKill reason=$reason" -ForegroundColor DarkYellow
                $killed++
            }
            else {
                Write-Host "WARN: taskkill /F /T exit=$LASTEXITCODE PID=$procIdKill reason=$reason — trying Stop-Process" -ForegroundColor Yellow
                try {
                    $ErrorActionPreference = 'Stop'
                    Stop-Process -Id $procIdKill -Force -ErrorAction Stop
                    Write-Host "KILL: Stop-Process PID=$procIdKill reason=$reason" -ForegroundColor DarkYellow
                    $killed++
                }
                catch {
                    Write-Host "WARN: Stop-Process PID=$procIdKill msg=$($_.Exception.Message)" -ForegroundColor Yellow
                }
            }
        }
        else {
            $ErrorActionPreference = 'Stop'
            try {
                Stop-Process -Id $procIdKill -Force -ErrorAction Stop
                Write-Host "KILL: Stop-Process PID=$procIdKill reason=$reason (no System32\taskkill.exe)" -ForegroundColor DarkYellow
                $killed++
            }
            catch {
                Write-Host "WARN: Stop-Process PID=$procIdKill msg=$($_.Exception.Message)" -ForegroundColor Yellow
            }
        }
    }
    finally {
        $ErrorActionPreference = $prevEap
    }
}

Write-Host "DONE: taskkill /T root count=$killed (matched total=$($matchedRows.Count))" -ForegroundColor Green
