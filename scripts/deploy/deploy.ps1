param(
    # Default: pack only (no SSH). Use -RemoteDeploy to upload and run release.ps1 on server.
    [switch]$RemoteDeploy,
    [string]$ServerHost = "",
    [string]$ServerUser = "",
    [string]$ServerDeployRoot = "C:\deploy\stock_quote",
    [string]$ServerReleaseScript = "C:\deploy\stock_quote\scripts\deploy\release.ps1",
    [string]$SshKeyPath = "",
    [string]$RemoteTempDir = "C:\deploy\stock_quote\tmp",
    [string]$ServerNginxHome = "",
    [string]$NpmExe = "npm",
    [string]$PythonExe = "python",
    [switch]$SkipPackagePy,
    [string]$PackageProjectRoot = "",
    [string]$PackagePyFormat = "zip",
    [string]$PackagePyOutput = "dist"
)

$ErrorActionPreference = "Stop"

# npm.ps1 + PowerShell's call operator `& npm ...` misparses $MyInvocation (errors like Unknown command "Program"/"pm").
# Prefer npm.cmd on Windows — same as typing `npm` at an interactive prompt.
if ($env:OS -eq 'Windows_NT' -and $NpmExe -eq 'npm') {
    $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($null -ne $npmCmd) {
        $NpmExe = $npmCmd.Source
    }
}

function Write-Step([string]$Msg) {
    Write-Host "==> $Msg" -ForegroundColor Cyan
}

function Invoke-DeployCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Program,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw ("Command failed: {0} {1}" -f $Program, ($Arguments -join ' '))
    }
}

if ($RemoteDeploy) {
    if ([string]::IsNullOrWhiteSpace($ServerHost) -or [string]::IsNullOrWhiteSpace($ServerUser)) {
        throw "-RemoteDeploy requires -ServerHost and -ServerUser."
    }
}

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\")
. (Join-Path $PSScriptRoot "Assert-RequirementsProdMinimal.ps1")
Assert-RequirementsProdMinimalDeps -RequirementsProdPath (Join-Path $projectRoot.Path "requirements-prod.txt")
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$packageName = "stock_quote_release_$timestamp.zip"
$localDist = Join-Path $projectRoot "dist"
$localPackage = Join-Path $localDist $packageName

if (-not (Test-Path -LiteralPath $localDist)) {
    New-Item -ItemType Directory -Path $localDist | Out-Null
}

Write-Step "Build admin (npm install + npm run build)"
$adminDir = Join-Path $projectRoot "admin"
$adminPkg = Join-Path $adminDir "package.json"
if (-not (Test-Path -LiteralPath $adminPkg)) {
    throw "Not found: admin/package.json"
}

Push-Location $adminDir
try {
    Invoke-DeployCommand -Program $NpmExe -Arguments @("install")
    Invoke-DeployCommand -Program $NpmExe -Arguments @("run", "build")
}
finally {
    Pop-Location
}

if (-not $SkipPackagePy) {
    Write-Step "Run package.py"
    $packageScript = Join-Path $projectRoot "package.py"
    if (-not (Test-Path -LiteralPath $packageScript)) {
        throw "Not found: package.py"
    }
    $projRootForPkg = $projectRoot.Path
    if ($PackageProjectRoot -ne "") {
        $projRootForPkg = (Resolve-Path (Join-Path $projectRoot $PackageProjectRoot)).Path
    }
    Invoke-DeployCommand -Program $PythonExe -Arguments @(
        $packageScript,
        "--format", $PackagePyFormat,
        "--output", $PackagePyOutput,
        "--project-root", $projRootForPkg
    )
}

Write-Step "Create zip archive"
if (Test-Path -LiteralPath $localPackage) {
    Remove-Item -LiteralPath $localPackage -Force
}

$zipExcludeTopLevel = @(
    '.agent',
    '.auth',
    '.cursor',
    '.gemini',
    '.git',
    '.github',
    '.hypothesis',
    '.idea',
    '.kiro',
    '.pytest_cache',
    '.qoder',
    '.vs',
    '.venv',
    '.vscode',
    'dist',
    'env',
    'node_modules',
    'test',
    'venv'
)
$rootPath = $projectRoot.Path
$zipEntries = @(Get-ChildItem -LiteralPath $rootPath -Force | Where-Object { $zipExcludeTopLevel -notcontains $_.Name })
if ($zipEntries.Count -eq 0) {
    throw "Nothing to archive (all top-level entries excluded?)."
}

$stagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("stock_quote_deploy_" + $timestamp)
if (Test-Path -LiteralPath $stagingRoot) {
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $stagingRoot | Out-Null

try {
    foreach ($entry in $zipEntries) {
        $targetPath = Join-Path $stagingRoot $entry.Name
        if ($entry.PSIsContainer) {
            & robocopy $entry.FullName $targetPath /E /XD node_modules __pycache__ .pytest_cache .mypy_cache .git .agent .auth .cursor .gemini .github .hypothesis .kiro .qoder .vscode test tests /NFL /NDL /NJH /NJS /nc /ns /np
            if ($LASTEXITCODE -ge 8) {
                throw ("robocopy failed for {0} exit {1}" -f $entry.Name, $LASTEXITCODE)
            }
        }
        else {
            Copy-Item -LiteralPath $entry.FullName -Destination $targetPath -Force
        }
    }

    $itemsToZip = @(Get-ChildItem -LiteralPath $stagingRoot -Force)
    if ($itemsToZip.Count -eq 0) {
        throw "Staging folder is empty."
    }
    Compress-Archive -Path ($itemsToZip.FullName) -DestinationPath $localPackage -Force
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "=== Pack finished ===" -ForegroundColor Green
Write-Host ("Release zip: {0}" -f $localPackage)
Write-Host ""

if (-not $RemoteDeploy) {
    Write-Host "Next (manual):" -ForegroundColor Yellow
    Write-Host "  1. Upload this zip to the server (e.g. RDP paste, SMB, or cloud disk)."
    Write-Host "  2. On the server, place the zip where release.ps1 can read it (e.g. under DeployRoot\tmp)."
    Write-Host "  3. Run release.ps1 (adjust -DeployRoot / -NginxHome / -PackagePath to your paths), for example:"
    Write-Host ""
    Write-Host '  powershell -ExecutionPolicy Bypass -File "C:\work\stock_quote_analayze\current\scripts\deploy\release.ps1" `'
    Write-Host ('    -PackagePath "C:\work\stock_quote_analayze\tmp\{0}" `' -f $packageName)
    Write-Host '    -DeployRoot "C:\work\stock_quote_analayze" `'
    Write-Host '    -NginxHome "C:\work\stock_quote_analayze\tools\nginx-1.28.0"'
    Write-Host ""
    exit 0
}

$sshTarget = "$ServerUser@$ServerHost"
$scpArgs = @()
$sshArgs = @()

if ($SshKeyPath -ne "") {
    $scpArgs += @("-i", $SshKeyPath)
    $sshArgs += @("-i", $SshKeyPath)
}

Write-Step "Ensure remote temp dir"
$sshEnsureDir = 'powershell -NoProfile -Command "New-Item -ItemType Directory -Force -Path ''' + $RemoteTempDir + ''' | Out-Null"'
Invoke-DeployCommand -Program "ssh" -Arguments ($sshArgs + $sshTarget + $sshEnsureDir)

Write-Step "Upload zip"
Invoke-DeployCommand -Program "scp" -Arguments ($scpArgs + $localPackage + "$sshTarget`:$RemoteTempDir\$packageName")

Write-Step "Remote release.ps1"
$remotePackage = "$RemoteTempDir\$packageName"
$remoteCmd = 'powershell -NoProfile -ExecutionPolicy Bypass -File "' + $ServerReleaseScript + '" -PackagePath "' + $remotePackage + '" -DeployRoot "' + $ServerDeployRoot + '"'
if ($ServerNginxHome -ne "") {
    $remoteCmd += ' -NginxHome "' + $ServerNginxHome + '"'
}
Invoke-DeployCommand -Program "ssh" -Arguments ($sshArgs + $sshTarget + $remoteCmd)

Write-Step "Remote deploy done"
Write-Host 'URL: https://www.icemaplecity.com/  |  https://www.icemaplecity.com/admin'
