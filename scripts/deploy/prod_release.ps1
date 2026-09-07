# Prod one-click release: pick latest zip under DeployRoot\tmp, then call release.ps1
# Usage on prod:
#   powershell -ExecutionPolicy Bypass -File .\scripts\deploy\prod_release.ps1
#   or double-click prod_release.bat at DeployRoot / current root

param(
    [string]$DeployRoot = "C:\work\stock_quote_analayze",
    [string]$PythonExe = "C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe",
    [string]$NginxHome = "C:\work\stock_quote_analayze\tools\nginx-1.28.0",
    [string]$TmpDir = "",
    [string]$PackagePath = "",
    [string]$ReleaseScript = "",
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Msg) {
    Write-Host "==> $Msg" -ForegroundColor Cyan
}

try {
    if ([string]::IsNullOrWhiteSpace($TmpDir)) {
        $TmpDir = Join-Path $DeployRoot "tmp"
    }

    # Prefer sibling release.ps1 (works under current\scripts\deploy)
    if ([string]::IsNullOrWhiteSpace($ReleaseScript)) {
        $sibling = Join-Path $PSScriptRoot "release.ps1"
        $underRoot = Join-Path $DeployRoot "scripts\deploy\release.ps1"
        if (Test-Path -LiteralPath $sibling) {
            $ReleaseScript = $sibling
        }
        else {
            $ReleaseScript = $underRoot
        }
    }

    Write-Host "========================================"
    Write-Host " Prod Release"
    Write-Host " DeployRoot : $DeployRoot"
    Write-Host " TmpDir     : $TmpDir"
    Write-Host " Release    : $ReleaseScript"
    Write-Host "========================================"
    Write-Host ""

    if (-not (Test-Path -LiteralPath $ReleaseScript)) {
        throw "release.ps1 not found: $ReleaseScript"
    }

    if (-not (Test-Path -LiteralPath $TmpDir)) {
        throw "tmp dir not found: $TmpDir"
    }

    if ([string]::IsNullOrWhiteSpace($PackagePath)) {
        Write-Step "Find latest package: $TmpDir\stock_quote_release_*.zip"
        $latest = Get-ChildItem -LiteralPath $TmpDir -Filter "stock_quote_release_*.zip" -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1

        if ($null -eq $latest) {
            throw "No zip matched: $TmpDir\stock_quote_release_*.zip"
        }

        $PackagePath = $latest.FullName
        Write-Host ("Selected : {0}" -f $PackagePath) -ForegroundColor Green
        Write-Host ("Modified : {0}" -f $latest.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))
        Write-Host ("Size     : {0:N2} MB" -f ($latest.Length / 1MB))
    }
    else {
        if (-not (Test-Path -LiteralPath $PackagePath)) {
            throw "PackagePath not found: $PackagePath"
        }
        Write-Host ("Using    : {0}" -f $PackagePath) -ForegroundColor Green
    }

    Write-Host ""
    Write-Step "Invoke release.ps1"
    Write-Host "  -PackagePath `"$PackagePath`""
    Write-Host "  -DeployRoot `"$DeployRoot`""
    Write-Host "  -PythonExe `"$PythonExe`""
    Write-Host "  -NginxHome `"$NginxHome`""
    Write-Host "  -ManualProcessDeploy"
    Write-Host "  -SkipHealthCheck"
    Write-Host "  -AllowScriptPathMismatch"
    Write-Host ""

    if ($WhatIf) {
        Write-Host "[WhatIf] Preview only; release not executed." -ForegroundColor Yellow
        exit 0
    }

    $args = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $ReleaseScript,
        "-PackagePath", $PackagePath,
        "-DeployRoot", $DeployRoot,
        "-PythonExe", $PythonExe,
        "-NginxHome", $NginxHome,
        "-ManualProcessDeploy",
        "-SkipHealthCheck",
        "-AllowScriptPathMismatch"
    )
    $p = Start-Process -FilePath "powershell.exe" -ArgumentList $args -Wait -PassThru -NoNewWindow
    if ($null -eq $p -or $p.ExitCode -ne 0) {
        $code = if ($null -eq $p) { -1 } else { $p.ExitCode }
        throw ("release.ps1 failed, exit code: {0}" -f $code)
    }

    Write-Host ""
    Write-Host "=== Prod release completed ===" -ForegroundColor Green
    exit 0
}
catch {
    Write-Host ""
    Write-Host ("[ERROR] {0}" -f $_.Exception.Message) -ForegroundColor Red
    exit 1
}
