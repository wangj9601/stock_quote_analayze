param(
    [string]$DeployRoot = "C:\deploy\stock_quote",
    [string]$PythonExe = "python",
    [string]$NssmExe = "C:\tools\nssm\nssm.exe",
    [switch]$StartAfterInstall
)

$ErrorActionPreference = "Stop"

function Ensure-Service([string]$ServiceName, [string]$ScriptPath, [string]$WorkDir, [string]$StdoutFile, [string]$StderrFile) {
    if (-not (Test-Path -LiteralPath $ScriptPath)) {
        throw "脚本不存在: $ScriptPath"
    }

    $exists = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($exists) {
        & $NssmExe remove $ServiceName confirm | Out-Null
        Start-Sleep -Seconds 1
    }

    & $NssmExe install $ServiceName $PythonExe $ScriptPath | Out-Null
    & $NssmExe set $ServiceName AppDirectory $WorkDir | Out-Null
    & $NssmExe set $ServiceName Start SERVICE_AUTO_START | Out-Null
    & $NssmExe set $ServiceName AppStdout $StdoutFile | Out-Null
    & $NssmExe set $ServiceName AppStderr $StderrFile | Out-Null
    & $NssmExe set $ServiceName AppRotateFiles 1 | Out-Null
    & $NssmExe set $ServiceName AppRotateOnline 1 | Out-Null
    & $NssmExe set $ServiceName AppRotateSeconds 86400 | Out-Null
    & $NssmExe set $ServiceName AppExit Default Restart | Out-Null

    Write-Host "[OK] 服务已安装: $ServiceName"
}

if (-not (Test-Path -LiteralPath $NssmExe)) {
    throw "未找到 NSSM: $NssmExe"
}

$current = Join-Path $DeployRoot "current"
$sharedLogs = Join-Path $DeployRoot "shared\logs"

if (-not (Test-Path -LiteralPath $current)) {
    throw "未找到 current 目录，请先执行一次 release.ps1: $current"
}

Ensure-Service `
    -ServiceName "stock-quote-api" `
    -ScriptPath (Join-Path $current "start_backend_api.py") `
    -WorkDir $current `
    -StdoutFile (Join-Path $sharedLogs "stock-quote-api.out.log") `
    -StderrFile (Join-Path $sharedLogs "stock-quote-api.err.log")

Ensure-Service `
    -ServiceName "stock-quote-core" `
    -ScriptPath (Join-Path $current "start_backend_core.py") `
    -WorkDir $current `
    -StdoutFile (Join-Path $sharedLogs "stock-quote-core.out.log") `
    -StderrFile (Join-Path $sharedLogs "stock-quote-core.err.log")

Ensure-Service `
    -ServiceName "stock-quote-notify" `
    -ScriptPath (Join-Path $current "start_scheduler.py") `
    -WorkDir $current `
    -StdoutFile (Join-Path $sharedLogs "stock-quote-notify.out.log") `
    -StderrFile (Join-Path $sharedLogs "stock-quote-notify.err.log")

if ($StartAfterInstall) {
    Start-Service "stock-quote-api"
    Start-Service "stock-quote-core"
    Start-Service "stock-quote-notify"
    Write-Host "[OK] 所有服务已启动"
}

Write-Host "服务安装完成。可用命令：Get-Service stock-quote-*"
