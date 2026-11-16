@echo off
REM ASCII-only critical lines: avoid UTF-8 echo breaking cmd parse
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
set "RC=1"

call :main %*
set "RC=%ERRORLEVEL%"
goto :hold

:main
echo ========================================
echo  Baidu Windows public deploy
echo ========================================
echo.
echo Default: pack + scp + prod_release.ps1 + alembic upgrade
echo Host: 106.12.156.20  User: administrator
echo Root: C:\work\stock_quote_analayze
echo Remote: ManualProcessDeploy, same as prod_release.bat
echo.
echo Options:
echo   deploy_baidu.bat -PackOnly
echo   deploy_baidu.bat -SkipAdminBuild
echo   deploy_baidu.bat -WhatIf
echo   deploy_baidu.bat -SkipDbMigrate
echo.
echo Env override: BAIDU_SSH_KEY / BAIDU_HOST / BAIDU_USER
echo.

set "BAIDU_SCRIPT=%~dp0scripts\deploy\deploy_baidu.ps1"
if not exist "%BAIDU_SCRIPT%" (
    echo [ERROR] missing: %BAIDU_SCRIPT%
    exit /b 1
)

echo Will run:
echo   powershell -ExecutionPolicy Bypass -File .\scripts\deploy\deploy_baidu.ps1 %*
echo.
echo Starting (admin build may take a few minutes)...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%BAIDU_SCRIPT%" %*
exit /b %ERRORLEVEL%

:hold
echo.
if "%RC%"=="0" (
    echo [OK] Baidu deploy finished.
    echo.
    pause
    endlocal & exit /b 0
)

echo [FAILED] Baidu deploy failed. ExitCode=%RC%
echo.
echo ========================================
echo  Error: window will stay open.
echo  Scroll up to read the error.
echo  Type exit then Enter to close.
echo ========================================
echo.
cmd /k
endlocal & exit /b %RC%
