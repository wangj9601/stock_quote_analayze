@echo off
REM ASCII-only bat: avoid chcp 65001 + non-ASCII echo on prod consoles
cd /d "%~dp0"
set "RC=1"

echo ========================================
echo  Prod Release
echo ========================================
echo.

REM Prefer scripts next to this bat; also support running from DeployRoot\current
set "PROD_SCRIPT=%~dp0scripts\deploy\prod_release.ps1"
if not exist "%PROD_SCRIPT%" set "PROD_SCRIPT=%~dp0prod_release.ps1"
if not exist "%PROD_SCRIPT%" (
    echo [ERROR] Script not found:
    echo   %~dp0scripts\deploy\prod_release.ps1
    echo   %~dp0prod_release.ps1
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
