<#
.SYNOPSIS
    Stop python.exe / pythonw.exe tied to this stock_quote deploy (same rules as release.ps1 manual workers).

.DESCRIPTION
    Match if CommandLine contains paths under DeployRoot\current for:
    start_backend_core.py, start_backend_api.py, start_scheduler.py, start_frontend.py, or current\admin\dist.
    Optional -PythonExe adds same-interpreter matching (ExecutablePath under that python folder, or CommandLine contains full python path).

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

Write-Host "INFO: DeployRoot=$deployFull" -ForegroundColor Cyan
Write-Host "INFO: current=$currentFull" -ForegroundColor Cyan
if ($null -ne $fullPyKill) {
    Write-Host "INFO: PythonExe=$fullPyKill" -ForegroundColor Cyan
}
if ($WhatIf) {
    Write-Host "INFO: -WhatIf list targets only; no Stop-Process/taskkill." -ForegroundColor Yellow
}

$cimList = Get-Win32PythonProcesses
if ($cimList.Count -eq 0) {
    Write-Host "INFO: No python.exe / pythonw.exe processes." -ForegroundColor Green
    exit 0
}

$taskkillExe = [System.IO.Path]::Combine($env:SystemRoot, 'System32', 'taskkill.exe')
$killed = 0

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

    $reason = if ($matchDeploy -and $matchInterp) { 'markers+interpreter' } elseif ($matchDeploy) { 'deploy-markers' } else { 'same-interpreter' }

    if ($WhatIf) {
        $exeDisp = if ([string]::IsNullOrWhiteSpace($exePathKill)) { 'NO_EXE_PATH' } else { $exePathKill }
        Write-Host "WHATIF: PID=$procIdKill reason=$reason exe=$exeDisp" -ForegroundColor Magenta
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

    try {
        Stop-Process -Id $procIdKill -Force -ErrorAction Stop
        Write-Host "KILL: PID=$procIdKill reason=$reason" -ForegroundColor DarkYellow
        $killed++
    }
    catch {
        Write-Host "WARN: Stop-Process PID=$procIdKill msg=$($_.Exception.Message)" -ForegroundColor Yellow
        if (Test-Path -LiteralPath $taskkillExe) {
            $null = & $taskkillExe /F /PID $procIdKill 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "KILL: taskkill /F PID=$procIdKill reason=$reason" -ForegroundColor DarkYellow
                $killed++
            }
            else {
                Write-Host "WARN: taskkill exit=$LASTEXITCODE PID=$procIdKill" -ForegroundColor Yellow
            }
        }
    }
}

Write-Host "DONE: matched or attempted stop count=$killed" -ForegroundColor Green
