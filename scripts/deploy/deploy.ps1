param(
    [Parameter(Mandatory = $true)]
    [string]$ServerHost,
    [Parameter(Mandatory = $true)]
    [string]$ServerUser,
    [string]$ServerDeployRoot = "C:\deploy\stock_quote",
    [string]$ServerReleaseScript = "C:\deploy\stock_quote\scripts\deploy\release.ps1",
    [string]$SshKeyPath = "",
    [string]$RemoteTempDir = "C:\deploy\stock_quote\tmp"
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Run-Command([string]$exe, [string[]]$args) {
    & $exe @args
    if ($LASTEXITCODE -ne 0) {
        throw "命令执行失败: $exe $($args -join ' ')"
    }
}

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\")
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$packageName = "stock_quote_release_$timestamp.zip"
$localDist = Join-Path $projectRoot "dist"
$localPackage = Join-Path $localDist $packageName

if (-not (Test-Path -LiteralPath $localDist)) {
    New-Item -ItemType Directory -Path $localDist | Out-Null
}

Write-Step "创建发布包"
if (Test-Path -LiteralPath $localPackage) {
    Remove-Item -LiteralPath $localPackage -Force
}

$exclude = @(
    ".git",
    ".cursor",
    "dist",
    "node_modules",
    "test\test-results",
    "backend_api\database\stock_analysis.db"
)

Compress-Archive -Path (Join-Path $projectRoot "*") -DestinationPath $localPackage -Force

$sshTarget = "$ServerUser@$ServerHost"
$scpArgs = @()
$sshArgs = @()

if ($SshKeyPath -ne "") {
    $scpArgs += @("-i", $SshKeyPath)
    $sshArgs += @("-i", $SshKeyPath)
}

Write-Step "确保远端临时目录存在"
$sshEnsureDir = "powershell -NoProfile -Command `"New-Item -ItemType Directory -Force -Path '$RemoteTempDir' | Out-Null`""
Run-Command "ssh" ($sshArgs + $sshTarget + $sshEnsureDir)

Write-Step "上传发布包到远端"
Run-Command "scp" ($scpArgs + $localPackage + "$sshTarget`:$RemoteTempDir\$packageName")

Write-Step "远端触发 release.ps1"
$remotePackage = "$RemoteTempDir\$packageName"
$remoteCmd = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$ServerReleaseScript`" -PackagePath `"$remotePackage`" -DeployRoot `"$ServerDeployRoot`""
Run-Command "ssh" ($sshArgs + $sshTarget + $remoteCmd)

Write-Step "部署完成"
Write-Host "URL: https://www.icemaplecity.com/  |  https://www.icemaplecity.com/admin"
