# 转发到仓库内唯一维护的 scripts\deploy\release.ps1。
# PS5.1：对子脚本写 -Switch:$false 个别环境会 AmbiguousParameterSet；仅在为 $true 时传入开关。
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
    [switch]$SkipStopServicesBeforePip,
    [switch]$SkipKillPythonBeforePip
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -LiteralPath (Split-Path -LiteralPath (Split-Path -LiteralPath $PSScriptRoot -Parent) -Parent) -Parent
$canonical = Join-Path $repoRoot 'scripts\deploy\release.ps1'
if (-not (Test-Path -LiteralPath $canonical)) {
    throw "找不到部署脚本: $canonical"
}

$forward = @{
    PackagePath       = $PackagePath
    DeployRoot        = $DeployRoot
    PythonExe         = $PythonExe
    NpmExe            = $NpmExe
    NginxHome         = $NginxHome
    HealthRetry       = $HealthRetry
    HealthTimeoutSec  = $HealthTimeoutSec
    HealthIntervalSec = $HealthIntervalSec
}
if ($SkipHealthCheck) {
    $forward['SkipHealthCheck'] = $true
}
if ($SkipStopServicesBeforePip) {
    $forward['SkipStopServicesBeforePip'] = $true
}
if ($SkipKillPythonBeforePip) {
    $forward['SkipKillPythonBeforePip'] = $true
}
& $canonical @forward
