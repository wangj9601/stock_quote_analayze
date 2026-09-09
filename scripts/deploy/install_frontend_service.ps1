# Register only stock-quote-frontend via NSSM: auto-start + restart on exit.
# Usage on prod (Admin PowerShell):
#   powershell -ExecutionPolicy Bypass -File .\scripts\deploy\install_frontend_service.ps1 -StartAfterInstall
# Or double-click install_frontend_service.bat at DeployRoot / repo root.
param(
    [string]$DeployRoot = "C:\work\stock_quote_analayze",
    [string]$PythonExe = "python",
    [string]$NssmExe = "",
    [switch]$StartAfterInstall,
    [switch]$StopManualFrontendFirst
)

$ErrorActionPreference = "Stop"

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

function Resolve-PythonExeToFullPath([string]$Preferred) {
    $s = if ([string]::IsNullOrWhiteSpace($Preferred)) { "python" } else { $Preferred.Trim() }
    if ([System.IO.Path]::IsPathRooted($s) -and (Test-Path -LiteralPath $s)) {
        return (Resolve-Path -LiteralPath $s).Path
    }
    $cmd = Get-Command -Name $s -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $cmd -and $cmd.Source -and (Test-Path -LiteralPath $cmd.Source)) {
        return (Resolve-Path -LiteralPath $cmd.Source).Path
    }
    $whereExe = Join-Path $env:SystemRoot "System32\where.exe"
    if (Test-Path -LiteralPath $whereExe) {
        foreach ($line in @(& $whereExe $s 2>$null)) {
            $p = ([string]$line).Trim()
            if ($p -and (Test-Path -LiteralPath $p)) {
                return (Resolve-Path -LiteralPath $p).Path
            }
        }
    }
    throw "Cannot resolve python.exe. Pass -PythonExe full path."
}

function Test-PortListening([int]$Port) {
    $lines = netstat -ano | Select-String -Pattern (":{0}\s" -f $Port)
    return ($null -ne $lines -and @($lines).Count -gt 0)
}

function Stop-ListenersOnPort([int]$Port) {
    $pids = @()
    foreach ($line in @(netstat -ano | Select-String -Pattern (":{0}\s+.*LISTENING" -f $Port))) {
        $parts = (($line.ToString()) -split "\s+") | Where-Object { $_ -ne "" }
        if ($parts.Count -ge 5) {
            $procId = 0
            if ([int]::TryParse($parts[-1], [ref]$procId) -and $procId -gt 0) {
                $pids += $procId
            }
        }
    }
    foreach ($procId in ($pids | Select-Object -Unique)) {
        try {
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Host ("[OK] Stopped PID {0} on port {1}" -f $procId, $Port) -ForegroundColor Yellow
        }
        catch {
            Write-Host ("[WARN] Could not stop PID {0}: {1}" -f $procId, $_.Exception.Message) -ForegroundColor Yellow
        }
    }
}

if ([string]::IsNullOrWhiteSpace($NssmExe)) {
    $candidates = @(
        (Join-Path $DeployRoot "tools\nssm.exe"),
        "C:\work\stock_quote_analayze\tools\nssm.exe",
        (Join-Path $PSScriptRoot "..\..\tools\nssm.exe")
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) {
            $NssmExe = (Resolve-Path -LiteralPath $c).Path
            break
        }
    }
}
if (-not (Test-Path -LiteralPath $NssmExe)) {
    throw ("NSSM not found. Place nssm.exe under DeployRoot\tools\ or pass -NssmExe. Tried DeployRoot={0}" -f $DeployRoot)
}

$PythonExe = Resolve-PythonExeToFullPath $PythonExe
$current = Join-Path $DeployRoot "current"
$sharedLogs = Join-Path $DeployRoot "shared\logs"
$scriptPath = Join-Path $current "start_frontend.py"
$serviceName = "stock-quote-frontend"

if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw ("Missing: {0} (run release first)" -f $scriptPath)
}
New-Item -ItemType Directory -Path $sharedLogs -Force | Out-Null

Write-Host "========================================"
Write-Host " Install Frontend Service (NSSM)"
Write-Host " DeployRoot : $DeployRoot"
Write-Host " Python     : $PythonExe"
Write-Host " NSSM       : $NssmExe"
Write-Host " Script     : $scriptPath"
Write-Host "========================================"
Write-Host ""

if ($StopManualFrontendFirst -or (Test-PortListening 8000)) {
    Write-Host "==> Free port 8000 (stop manual frontend if any)" -ForegroundColor Cyan
    Stop-ListenersOnPort 8000
    Start-Sleep -Seconds 1
}

$exists = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($null -ne $exists) {
    try { Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue } catch {}
    $null = Invoke-Nssm @("remove", $serviceName, "confirm")
    Start-Sleep -Seconds 2
}

$null = Invoke-Nssm @("install", $serviceName, $PythonExe, $scriptPath)
if ($null -eq (Get-Service -Name $serviceName -ErrorAction SilentlyContinue)) {
    throw "NSSM install failed: $serviceName"
}

$envExtra = @"
PYTHONNOUSERSITE=1
FRONTEND_PORT=8000
ENVIRONMENT=production
"@

$null = Invoke-Nssm @("set", $serviceName, "AppDirectory", $current)
$null = Invoke-Nssm @("set", $serviceName, "Start", "SERVICE_AUTO_START")
$null = Invoke-Nssm @("set", $serviceName, "AppStdout", (Join-Path $sharedLogs "stock-quote-frontend.out.log"))
$null = Invoke-Nssm @("set", $serviceName, "AppStderr", (Join-Path $sharedLogs "stock-quote-frontend.err.log"))
$null = Invoke-Nssm @("set", $serviceName, "AppRotateFiles", "1")
$null = Invoke-Nssm @("set", $serviceName, "AppRotateOnline", "1")
$null = Invoke-Nssm @("set", $serviceName, "AppRotateSeconds", "86400")
$null = Invoke-Nssm @("set", $serviceName, "AppExit", "Default", "Restart")
$null = Invoke-Nssm @("set", $serviceName, "AppRestartDelay", "3000")
$null = Invoke-Nssm @("set", $serviceName, "AppEnvironmentExtra", $envExtra)

Write-Host "[OK] Service installed: $serviceName (AUTO_START + Restart on exit)" -ForegroundColor Green

if ($StartAfterInstall) {
    Start-Service -Name $serviceName
    Start-Sleep -Seconds 3
    $svc = Get-Service -Name $serviceName
    Write-Host ("[OK] Status: {0}" -f $svc.Status)
    if ($svc.Status -ne "Running") {
        Write-Host "[ERROR] Service not running. Tail stderr:" -ForegroundColor Red
        Get-Content (Join-Path $sharedLogs "stock-quote-frontend.err.log") -Tail 40 -ErrorAction SilentlyContinue
        throw "stock-quote-frontend failed to start"
    }
    if (-not (Test-PortListening 8000)) {
        Write-Host "[WARN] Service Running but :8000 not listening yet; check logs." -ForegroundColor Yellow
    }
    else {
        Write-Host "[OK] Port 8000 is listening" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Useful commands:"
Write-Host "  Get-Service stock-quote-frontend"
Write-Host "  Restart-Service stock-quote-frontend"
Write-Host "  netstat -ano | findstr `":8000 `""
Write-Host ("  logs: {0}" -f (Join-Path $sharedLogs "stock-quote-frontend.*.log"))
