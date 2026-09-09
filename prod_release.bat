@echo off
REM ASCII-only bat: avoid chcp 65001 + non-ASCII echo on prod consoles
cd /d "%~dp0"
set "RC=1"

echo ========================================
echo  Prod Release
echo ========================================
echo.
echo Bat location: %~dp0
echo.

REM Resolve prod_release.ps1:
REM 1) next to this bat (repo root or DeployRoot\current)
REM 2) sibling DeployRoot layouts (Desktop shortcut / copied bat only)
set "PROD_SCRIPT="
if exist "%~dp0scripts\deploy\prod_release.ps1" set "PROD_SCRIPT=%~dp0scripts\deploy\prod_release.ps1"
if not defined PROD_SCRIPT if exist "%~dp0prod_release.ps1" set "PROD_SCRIPT=%~dp0prod_release.ps1"
if not defined PROD_SCRIPT if exist "C:\work\stock_quote_analayze\current\scripts\deploy\prod_release.ps1" set "PROD_SCRIPT=C:\work\stock_quote_analayze\current\scripts\deploy\prod_release.ps1"
if not defined PROD_SCRIPT if exist "C:\work\stock_quote_analayze\scripts\deploy\prod_release.ps1" set "PROD_SCRIPT=C:\work\stock_quote_analayze\scripts\deploy\prod_release.ps1"
if not defined PROD_SCRIPT if exist "C:\deploy\stock_quote\current\scripts\deploy\prod_release.ps1" set "PROD_SCRIPT=C:\deploy\stock_quote\current\scripts\deploy\prod_release.ps1"
if not defined PROD_SCRIPT if exist "C:\deploy\stock_quote\scripts\deploy\prod_release.ps1" set "PROD_SCRIPT=C:\deploy\stock_quote\scripts\deploy\prod_release.ps1"

if not defined PROD_SCRIPT (
    echo [ERROR] prod_release.ps1 not found.
    echo.
    echo DeployRoot directory check:
    if exist "C:\work\stock_quote_analayze\" (
        echo   [OK]   C:\work\stock_quote_analayze\ exists
    ) else (
        echo   [MISS] C:\work\stock_quote_analayze\  ^<= this machine has NO DeployRoot
    )
    if exist "C:\work\stock_quote_analayze\current\" (
        echo   [OK]   C:\work\stock_quote_analayze\current\
    ) else (
        echo   [MISS] C:\work\stock_quote_analayze\current\
    )
    if exist "C:\work\stock_quote_analayze\current\scripts\deploy\release.ps1" (
        echo   [OK]   ...\current\scripts\deploy\release.ps1
    ) else (
        echo   [MISS] ...\current\scripts\deploy\release.ps1
    )
    if exist "C:\work\stock_quote_analayze\current\scripts\deploy\prod_release.ps1" (
        echo   [OK]   ...\current\scripts\deploy\prod_release.ps1
    ) else (
        echo   [MISS] ...\current\scripts\deploy\prod_release.ps1
    )
    echo.
    echo If DeployRoot shows [MISS] above: you are NOT on the prod server.
    echo   Run this bat via RDP/console ON the prod machine, not on the dev PC Desktop.
    echo.
    echo If DeployRoot is [OK] but prod_release.ps1 is [MISS]:
    echo   On prod, run release.ps1 directly, for example:
    echo   powershell -ExecutionPolicy Bypass -File "C:\work\stock_quote_analayze\current\scripts\deploy\release.ps1" ^
    echo     -PackagePath "C:\work\stock_quote_analayze\tmp\YOUR.zip" ^
    echo     -DeployRoot "C:\work\stock_quote_analayze" ^
    echo     -NginxHome "C:\work\stock_quote_analayze\tools\nginx-1.28.0" ^
    echo     -ManualProcessDeploy -SkipHealthCheck -AllowScriptPathMismatch
    goto :end
)

echo Auto-pick latest zip under:
echo   C:\work\stock_quote_analayze\tmp\stock_quote_release_*.zip
echo.
echo Script:
echo   %PROD_SCRIPT%
echo.
echo Preview only: prod_release.bat -WhatIf
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROD_SCRIPT%" %*
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
    echo [FAILED] Prod release failed. ExitCode=%RC%
) else (
    echo [OK] Prod release finished.
)

:end
echo.
pause
exit /b %RC%
