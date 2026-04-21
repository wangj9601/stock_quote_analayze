param(
    [string]$DeployRoot = "C:\deploy\stock_quote",
    [string]$PythonExe = "python",
    [string]$NodeExe = "node",
    [string]$NpmExe = "npm",
    [string]$NssmExe = "C:\tools\nssm\nssm.exe"
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Assert-Command([string]$name, [string]$cmd) {
    try {
        & $cmd --version | Out-Null
        Write-Host "[OK] $name 可用: $cmd"
    }
    catch {
        throw "[FAIL] $name 不可用，请先安装并确保命令可执行: $cmd"
    }
}

Write-Step "检查运行时环境"
Assert-Command "Python" $PythonExe
Assert-Command "Node.js" $NodeExe
Assert-Command "npm" $NpmExe

if (-not (Test-Path -LiteralPath $NssmExe)) {
    throw "[FAIL] 未找到 NSSM: $NssmExe"
}
Write-Host "[OK] NSSM 可用: $NssmExe"

Write-Step "创建部署目录结构"
$dirs = @(
    $DeployRoot,
    (Join-Path $DeployRoot "releases"),
    (Join-Path $DeployRoot "shared"),
    (Join-Path $DeployRoot "shared\logs"),
    (Join-Path $DeployRoot "shared\run"),
    (Join-Path $DeployRoot "shared\uploads")
)

foreach ($d in $dirs) {
    if (-not (Test-Path -LiteralPath $d)) {
        New-Item -ItemType Directory -Path $d | Out-Null
        Write-Host "[CREATE] $d"
    }
    else {
        Write-Host "[EXISTS] $d"
    }
}

$envTemplate = Join-Path $DeployRoot "shared\.env.example"
if (-not (Test-Path -LiteralPath $envTemplate)) {
    @(
        "# 复制为 .env 并填入真实值",
        "ENVIRONMENT=production",
        "BACKEND_PORT=5000",
        "UVICORN_WORKERS=2",
        "DATABASE_URL=postgresql://user:password@127.0.0.1:5432/stock_analysis",
        "REDIS_URL=redis://127.0.0.1:6379/0"
    ) | Set-Content -Path $envTemplate -Encoding UTF8
    Write-Host "[CREATE] $envTemplate"
}

$envReal = Join-Path $DeployRoot "shared\.env"
if (-not (Test-Path -LiteralPath $envReal)) {
    Copy-Item -Path $envTemplate -Destination $envReal
    Write-Host "[CREATE] $envReal (请立即编辑真实配置)"
}
else {
    Write-Host "[EXISTS] $envReal"
}

Write-Step "初始化完成"
Write-Host "下一步：运行 scripts\deploy\install_services.ps1 注册服务。"
