# 部署脚本共用：结束进程树前检查是否仍存在，避免 taskkill exit=128 / Stop-Process「找不到进程」误报。
# 用法：. (Join-Path $PSScriptRoot 'ProcessKillHelpers.ps1')

function Test-WinProcessExists {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId
    )
    if ($ProcessId -le 0) {
        return $false
    }
    try {
        $p = Get-Process -Id $ProcessId -ErrorAction Stop
        return ($null -ne $p)
    }
    catch {
        return $false
    }
}

function Test-ProcessNotFoundMessage {
    param(
        [AllowNull()][string]$Message
    )
    if ([string]::IsNullOrWhiteSpace($Message)) {
        return $false
    }
    $m = $Message.Trim()
    if ($m -match '找不到进程|找不到.*进程标识符|not found|No such process|does not exist|There is no process') {
        return $true
    }
    return $false
}

function Invoke-StopProcessTreeIfAlive {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId,
        [Parameter(Mandatory = $true)]
        [string]$Reason,
        [string]$ExecutablePath = '',
        [string]$TaskkillExe = ''
    )
    if ($ProcessId -le 0) {
        return $true
    }
    if (-not (Test-WinProcessExists -ProcessId $ProcessId)) {
        Write-Host ('[INFO] Kill skip PID={0} — already exited (reason={1})' -f $ProcessId, $Reason) -ForegroundColor DarkGray
        return $true
    }

    $exeDisp = if ([string]::IsNullOrWhiteSpace($ExecutablePath)) { 'NO_EXE_PATH' } else { $ExecutablePath }
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        if (-not [string]::IsNullOrWhiteSpace($TaskkillExe) -and (Test-Path -LiteralPath $TaskkillExe)) {
            $null = & $TaskkillExe /F /T /PID $ProcessId 2>&1
            $tkExit = $LASTEXITCODE
            if ($tkExit -eq 0) {
                Write-Host ('KILL: taskkill /F /T PID={0} reason={1} exe={2}' -f $ProcessId, $Reason, $exeDisp) -ForegroundColor DarkYellow
                return $true
            }
            if (-not (Test-WinProcessExists -ProcessId $ProcessId)) {
                Write-Host ('[INFO] Kill PID={0} already gone after taskkill exit={1} (reason={2})' -f $ProcessId, $tkExit, $Reason) -ForegroundColor DarkGray
                return $true
            }
            # Windows taskkill：128 = 进程不存在
            if ($tkExit -eq 128) {
                Write-Host ('[INFO] Kill PID={0} taskkill exit=128 (not found), treat as done (reason={1})' -f $ProcessId, $Reason) -ForegroundColor DarkGray
                return $true
            }
            Write-Host ("[WARN] taskkill /F /T exit={0} PID={1} — trying Stop-Process" -f $tkExit, $ProcessId) -ForegroundColor Yellow
        }

        $ErrorActionPreference = 'Stop'
        try {
            Stop-Process -Id $ProcessId -Force -ErrorAction Stop
            Write-Host ('KILL: Stop-Process PID={0} reason={1}' -f $ProcessId, $Reason) -ForegroundColor DarkYellow
            return $true
        }
        catch {
            if (-not (Test-WinProcessExists -ProcessId $ProcessId)) {
                Write-Host ('[INFO] Kill PID={0} already exited during Stop-Process (reason={1})' -f $ProcessId, $Reason) -ForegroundColor DarkGray
                return $true
            }
            if (Test-ProcessNotFoundMessage -Message $_.Exception.Message) {
                Write-Host ('[INFO] Kill PID={0} not found: {1}' -f $ProcessId, $_.Exception.Message) -ForegroundColor DarkGray
                return $true
            }
            Write-Host ("[WARN] Stop-Process PID {0}: {1}" -f $ProcessId, $_.Exception.Message) -ForegroundColor Yellow
            return $false
        }
    }
    finally {
        $ErrorActionPreference = $prevEap
    }
}
