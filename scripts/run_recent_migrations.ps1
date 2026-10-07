#Requires -Version 4.0
<#
.SYNOPSIS
  [已弃用] 执行 migrations 目录下最近 N 天内修改过的 .py 迁移脚本。
  兼容 Windows PowerShell 4.0+（生产环境常见）。
  推荐优先使用: python scripts/run_recent_migrations.py
.DESCRIPTION
  自 2026-10-07 起，schema 变更已改用 Alembic 管理：
      python scripts/db_migrate.py status / check / upgrade
  详见 docs/database/Alembic_guide.md 与 migrations/README.md。
  本脚本保留仅供历史库应急补齐。
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

Write-Host "============================================================" -ForegroundColor Yellow
Write-Host " [DEPRECATED] 该脚本按 mtime 排序执行，无版本账本、无回滚，已被 Alembic 取代。" -ForegroundColor Yellow
Write-Host " 新变更请用: python scripts/db_migrate.py revision -m \`"说明\`"" -ForegroundColor Yellow
Write-Host "             python scripts/db_migrate.py check / upgrade" -ForegroundColor Yellow
Write-Host " 文档: docs/database/Alembic_guide.md" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host ""
if (-not $Yes) {
    $go = Read-Host "仍要继续吗？(Y/N)"
    if ($go -notin @("Y", "y")) {
        Write-Host "已取消。建议改用: python scripts/db_migrate.py upgrade"
        exit 0
    }
}

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
