@echo off
REM ASCII-only critical lines: avoid UTF-8 echo breaking cmd parse (e.g. '输入' not recognized)
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
set "RC=1"

call :main %*
set "RC=%ERRORLEVEL%"
goto :hold

:main
echo ========================================
echo  Aliyun public deploy
echo ========================================
echo.
echo Default: pack + scp + linux/release.sh + alembic upgrade
echo Host: 47.99.185.87  User: root  Root: /opt/stock_quote
echo.
echo Options:
echo   deploy_aliyun.bat -PackOnly
echo   deploy_aliyun.bat -SkipAdminBuild
echo   deploy_aliyun.bat -WhatIf
echo   deploy_aliyun.bat -SkipHealth
echo   deploy_aliyun.bat -SkipDbMigrate
echo   deploy_aliyun.bat -RunRecentMigrations
echo   deploy_aliyun.bat -RunRecentMigrations -MigrationDays 5
echo.
echo Env override: ALIYUN_SSH_KEY / ALIYUN_HOST / ALIYUN_USER
echo.

set "ALIYUN_SCRIPT=%~dp0scripts\deploy\deploy_aliyun.ps1"
if not exist "%ALIYUN_SCRIPT%" (
    echo [ERROR] missing: %ALIYUN_SCRIPT%
    exit /b 1
)

echo Will run:
echo   powershell -ExecutionPolicy Bypass -File .\scripts\deploy\deploy_aliyun.ps1 %*
echo.
echo Starting (admin build may take a few minutes)...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ALIYUN_SCRIPT%" %*
exit /b %ERRORLEVEL%

:hold
echo.
if "%RC%"=="0" (
    echo [OK] Aliyun deploy finished.
    echo.
    pause
    endlocal & exit /b 0
)

echo [FAILED] Aliyun deploy failed. ExitCode=%RC%
echo.
echo ========================================
echo  Error: window will stay open.
echo  Scroll up to read the error.
echo  Type exit then Enter to close.
echo ========================================
echo.
cmd /k
endlocal & exit /b %RC%
