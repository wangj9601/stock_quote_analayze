param(
    [Parameter(Mandatory = $true)]
    [string]$PackagePath,
    [string]$DeployRoot = "C:\deploy\stock_quote",
    [string]$PythonExe = "python",
    [string]$NpmExe = "npm",
    [string]$NginxHome = ""
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Assert-RequirementsProdMinimal.ps1")

function Assert-LastExitCode([string]$StepName) {
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "$StepName failed (exit code $LASTEXITCODE)."
    }
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    throw "PythonExe is empty. Pass e.g. -PythonExe (Get-Command python).Source"
}

# npm.ps1 + `& npm ...` breaks under PowerShell; use npm.cmd on Windows when using the call operator.
if ($env:OS -eq 'Windows_NT' -and ([string]::IsNullOrWhiteSpace($NpmExe) -or $NpmExe.Trim() -eq 'npm')) {
    $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($null -ne $npmCmd) {
        $NpmExe = [string]$npmCmd.Source
    }
}

$npmResolved = Get-Command $NpmExe -ErrorAction SilentlyContinue
if ($null -eq $npmResolved) {
    throw "Cannot resolve npm for '&': '$NpmExe'. Install Node.js (ensure npm.cmd is on PATH) or pass -NpmExe with full path to npm.cmd."
}
$NpmExe = [string]$npmResolved.Source

function Write-Step([string]$Msg) {
    Write-Host "==> $Msg" -ForegroundColor Cyan
}

function Restart-IfExists([string]$Name) {
    $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if ($null -ne $svc) {
        Restart-Service -Name $Name -Force
        Write-Host "[RESTART] $Name"
    }
    else {
        Write-Host "[SKIP] Service not installed: $Name"
    }
}

function Get-NginxExe {
    if ($NginxHome -ne "") {
        $exe = Join-Path $NginxHome "nginx.exe"
        if (Test-Path -LiteralPath $exe) {
            return $exe
        }
        Write-Host "[WARN] nginx.exe not found at $exe, using nginx from PATH" -ForegroundColor Yellow
    }
    return "nginx"
}

function Expand-ZipToDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ZipPath,
        [Parameter(Mandatory = $true)]
        [string]$DestinationDirectory
    )
    $zipResolved = (Resolve-Path -LiteralPath $ZipPath).Path
    if (Get-Command Expand-Archive -ErrorAction SilentlyContinue) {
        Expand-Archive -LiteralPath $zipResolved -DestinationPath $DestinationDirectory -Force
        return
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction Stop
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zipResolved, $DestinationDirectory)
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
    throw "Package zip not found: $PackagePath"
}

$releasesDir = Join-Path $DeployRoot "releases"
$sharedDir = Join-Path $DeployRoot "shared"
$currentDir = Join-Path $DeployRoot "current"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$newRelease = Join-Path $releasesDir $timestamp
$backupCurrent = "${currentDir}_backup_${timestamp}"

Write-Step "Create release folder"
New-Item -ItemType Directory -Path $newRelease -Force | Out-Null

Write-Step "Expand zip"
Expand-ZipToDirectory -ZipPath $PackagePath -DestinationDirectory $newRelease

Write-Step "Copy shared .env"
$sharedEnv = Join-Path $sharedDir ".env"
if (Test-Path -LiteralPath $sharedEnv) {
    Copy-Item -Path $sharedEnv -Destination (Join-Path $newRelease ".env") -Force
}
else {
    Write-Host "[WARN] shared\.env not found; backend may fail to start"
}

Write-Step 'pip install (requirements-prod.txt -> backend_api/requirements-minimal.txt + backend_core/requirements-minimal.txt)'
Push-Location $newRelease
& $PythonExe -m pip install --upgrade pip
Assert-LastExitCode "pip install --upgrade pip"
$prodReq = Join-Path $newRelease "requirements-prod.txt"
if (-not (Test-Path -LiteralPath $prodReq)) {
    throw 'requirements-prod.txt not found in release package (expected to aggregate backend_api/requirements-minimal.txt and backend_core/requirements-minimal.txt).'
}
Assert-RequirementsProdMinimalDeps -RequirementsProdPath $prodReq
Write-Host '[pip] requirements-prod only (backend_api + backend_core minimal); no torch/tensorflow ML stacks.' -ForegroundColor DarkGray
& $PythonExe -m pip install -r requirements-prod.txt
Assert-LastExitCode "pip install -r requirements-prod.txt"

Write-Step "Build admin"
if (Test-Path -LiteralPath (Join-Path $newRelease "admin\package.json")) {
    Push-Location (Join-Path $newRelease "admin")
    & $NpmExe install
    & $NpmExe run build
    Pop-Location
}
else {
    Write-Host "[WARN] admin/package.json not found, skip admin build"
}

Write-Step "Optional migrate_db.py"
if (Test-Path -LiteralPath (Join-Path $newRelease "migrate_db.py")) {
    & $PythonExe migrate_db.py
}

Write-Step "Switch current"
if (Test-Path -LiteralPath $currentDir) {
    Move-Item -Path $currentDir -Destination $backupCurrent -Force
}
Move-Item -Path $newRelease -Destination $currentDir -Force

try {
    Write-Step 'Restart Windows services (if exist)'
    Restart-IfExists "stock-quote-api"
    Restart-IfExists "stock-quote-core"
    Restart-IfExists "stock-quote-notify"

    Write-Step "nginx -t and reload"
    $nginxExe = Get-NginxExe
    & $nginxExe -t
    if ($LASTEXITCODE -eq 0) {
        & $nginxExe -s reload
    }
    else {
        Write-Host "[WARN] nginx -t failed, skip reload" -ForegroundColor Yellow
    }

    Write-Step "Health check"
    $okApi = Test-Health "http://127.0.0.1:5000/"
    $okWeb = Test-Health "https://www.icemaplecity.com/"
    $okAdmin = Test-Health "https://www.icemaplecity.com/admin/"

    if (-not ($okApi -and $okWeb -and $okAdmin)) {
        throw "Health check failed: api=$okApi web=$okWeb admin=$okAdmin"
    }

    if (Test-Path -LiteralPath $backupCurrent) {
        Remove-Item -LiteralPath $backupCurrent -Recurse -Force
    }
    Write-Host "[SUCCESS] Released: $timestamp"
}
catch {
    Write-Host ("ERROR: Release failed, rollback: " + $_.Exception.Message) -ForegroundColor Red
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
