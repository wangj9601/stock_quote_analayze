#Requires -Version 5.0
<#
.SYNOPSIS
  执行 migrations 目录下最近 N 天内修改过的 .py 迁移脚本。
.PARAMETER Days
  回溯天数，默认 2。
.PARAMETER Yes
  跳过确认直接执行。
#>
param(
    [int]$Days = 2,
    [switch]$Yes
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "migrations"))) {
    # 若脚本放在仓库根目录
    if (Test-Path (Join-Path $PSScriptRoot "migrations")) {
        $Root = $PSScriptRoot
    }
}
Set-Location $Root

$migDir = Join-Path $Root "migrations"
if (-not (Test-Path $migDir)) {
    Write-Host "[ERROR] migrations dir not found: $migDir" -ForegroundColor Red
    exit 1
}

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "[ERROR] python not found in PATH." -ForegroundColor Red
    exit 1
}

$cutoff = (Get-Date).AddDays(-[Math]::Abs($Days))
$files = @(
    Get-ChildItem -Path $migDir -Filter "*.py" -File |
        Where-Object { $_.LastWriteTime -ge $cutoff } |
        Sort-Object LastWriteTime
)

Write-Host "========================================"
Write-Host " Recent migrations/*.py within $Days day(s)"
Write-Host " Cutoff: $($cutoff.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Host " Workdir: $Root"
Write-Host "========================================"
Write-Host ""

if ($files.Count -eq 0) {
    Write-Host "[INFO] No migration scripts in the last $Days day(s)."
    exit 0
}

Write-Host "Will run in LastWriteTime order:"
Write-Host "----------------------------------------"
foreach ($f in $files) {
    Write-Host ("{0}  {1}" -f $f.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"), $f.Name)
}
Write-Host "----------------------------------------"
Write-Host ""

if (-not $Yes) {
    $confirm = Read-Host "Run these scripts? (Y/N)"
    if ($confirm -notin @("Y", "y")) {
        Write-Host "Cancelled."
        exit 0
    }
}

$ok = 0
$fail = 0
foreach ($f in $files) {
    Write-Host ""
    Write-Host "-------- 执行: $($f.FullName)"
    & python $f.FullName
    if ($LASTEXITCODE -ne 0) {
        Write-Host ('[FAIL] {0} (exit={1})' -f $f.Name, $LASTEXITCODE) -ForegroundColor Red
        $fail++
    } else {
        Write-Host ('[OK] {0}' -f $f.Name) -ForegroundColor Green
        $ok++
    }
}

Write-Host ""
Write-Host "========================================"
Write-Host (" Done: ok={0} fail={1}" -f $ok, $fail)
Write-Host "========================================"
if ($fail -gt 0) { exit 1 }
exit 0
