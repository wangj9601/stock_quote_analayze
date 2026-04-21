param(
    [Parameter(Mandatory = $true)]
    [string]$PackagePath,
    [string]$DeployRoot = "C:\deploy\stock_quote",
    [string]$PythonExe = "python",
    [string]$NpmExe = "npm"
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Restart-IfExists([string]$name) {
    $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
    if ($null -ne $svc) {
        Restart-Service -Name $name -Force
        Write-Host "[RESTART] $name"
    }
    else {
        Write-Host "[SKIP] 服务不存在: $name"
    }
}

function Test-Health([string]$url, [int]$retry = 20) {
    for ($i = 1; $i -le $retry; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                return $true
            }
        }
        catch {}
        Start-Sleep -Seconds 2
    }
    return $false
}

if (-not (Test-Path -LiteralPath $PackagePath)) {
    throw "部署包不存在: $PackagePath"
}

$releasesDir = Join-Path $DeployRoot "releases"
$sharedDir = Join-Path $DeployRoot "shared"
$currentDir = Join-Path $DeployRoot "current"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$newRelease = Join-Path $releasesDir $timestamp
$backupCurrent = "${currentDir}_backup_${timestamp}"

Write-Step "创建新版本目录"
New-Item -ItemType Directory -Path $newRelease -Force | Out-Null

Write-Step "解压部署包"
Expand-Archive -LiteralPath $PackagePath -DestinationPath $newRelease -Force

Write-Step "复制共享配置"
$sharedEnv = Join-Path $sharedDir ".env"
if (Test-Path -LiteralPath $sharedEnv) {
    Copy-Item -Path $sharedEnv -Destination (Join-Path $newRelease ".env") -Force
}
else {
    Write-Host "[WARN] 未找到 shared\.env，后端可能无法启动"
}

Write-Step "安装 Python 依赖"
Push-Location $newRelease
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r requirements-prod.txt

if (Test-Path -LiteralPath (Join-Path $newRelease "backend_core\requirements.txt")) {
    & $PythonExe -m pip install -r backend_core\requirements.txt
}

Write-Step "构建 admin 前端"
if (Test-Path -LiteralPath (Join-Path $newRelease "admin\package.json")) {
    Push-Location (Join-Path $newRelease "admin")
    & $NpmExe install
    & $NpmExe run build
    Pop-Location
}
else {
    Write-Host "[WARN] 未找到 admin/package.json，跳过 admin 构建"
}

Write-Step "执行可选数据库迁移"
if (Test-Path -LiteralPath (Join-Path $newRelease "migrate_db.py")) {
    & $PythonExe migrate_db.py
}

Write-Step "切换 current 版本"
if (Test-Path -LiteralPath $currentDir) {
    Move-Item -Path $currentDir -Destination $backupCurrent -Force
}
Move-Item -Path $newRelease -Destination $currentDir -Force

try {
    Write-Step "重启应用服务"
    Restart-IfExists "stock-quote-api"
    Restart-IfExists "stock-quote-core"
    Restart-IfExists "stock-quote-notify"

    Write-Step "校验并重载 Nginx（复用现有配置）"
    & nginx -t
    if ($LASTEXITCODE -eq 0) {
        & nginx -s reload
    }

    Write-Step "健康检查"
    $okApi = Test-Health "http://127.0.0.1:5000/"
    $okWeb = Test-Health "https://www.icemaplecity.com/"
    $okAdmin = Test-Health "https://www.icemaplecity.com/admin/"

    if (-not ($okApi -and $okWeb -and $okAdmin)) {
        throw "健康检查失败: api=$okApi web=$okWeb admin=$okAdmin"
    }

    if (Test-Path -LiteralPath $backupCurrent) {
        Remove-Item -LiteralPath $backupCurrent -Recurse -Force
    }
    Write-Host "[SUCCESS] 发布成功: $timestamp"
}
catch {
    Write-Host "[ERROR] 发布失败，开始回滚: $($_.Exception.Message)" -ForegroundColor Red
    if (Test-Path -LiteralPath $currentDir) {
        Remove-Item -LiteralPath $currentDir -Recurse -Force
    }
    if (Test-Path -LiteralPath $backupCurrent) {
        Move-Item -Path $backupCurrent -Destination $currentDir -Force
    }
    Restart-IfExists "stock-quote-api"
    Restart-IfExists "stock-quote-core"
    Restart-IfExists "stock-quote-notify"
    throw
}
finally {
    Pop-Location
}
