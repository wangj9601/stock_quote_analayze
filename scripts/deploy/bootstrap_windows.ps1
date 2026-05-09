param(
    [string]$DeployRoot = "C:\deploy\stock_quote",
    [string]$PythonExe = "python",
    [string]$NodeExe = "node",
    [string]$NpmExe = "npm",
    [string]$NssmExe = "C:\work\stock_quote_analayze\tools\nssm.exe"
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Msg) {
    Write-Host "==> $Msg" -ForegroundColor Cyan
}

function Assert-Command([string]$Name, [string]$Cmd) {
    try {
        & $Cmd --version | Out-Null
        Write-Host "[OK] $Name : $Cmd"
    }
    catch {
        throw "[FAIL] $Name not found or not runnable: $Cmd"
    }
}

Write-Step "Check runtime (python / node / npm)"
Assert-Command "Python" $PythonExe
Assert-Command "Node.js" $NodeExe
Assert-Command "npm" $NpmExe

if (Test-Path -LiteralPath $NssmExe) {
    Write-Host "[OK] NSSM: $NssmExe"
}
else {
    Write-Host "[WARN] NSSM not found at: $NssmExe" -ForegroundColor Yellow
    Write-Host "       Bootstrap does not need NSSM. Install NSSM before install_services.ps1 (Windows services)." -ForegroundColor Yellow
    Write-Host "       Download: https://nssm.cc/  -> copy nssm.exe to above path, or pass -NssmExe when running install_services.ps1" -ForegroundColor Yellow
}

Write-Step "Create DeployRoot layout"
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
        "# Copy to .env and fill real values",
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
    Write-Host "[CREATE] $envReal (edit this file with real secrets)"
}
else {
    Write-Host "[EXISTS] $envReal"
}

Write-Step "Bootstrap done"
Write-Host "Next: edit shared\.env -> upload zip -> release.ps1 -> install_services.ps1 (needs NSSM at path above or -NssmExe)."
