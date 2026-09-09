@echo off
REM Install stock-quote-frontend NSSM service (auto-start + auto-restart)
cd /d "%~dp0"
set "RC=1"

echo ========================================
echo  Install Frontend Service
echo ========================================
echo.

set "SCRIPT=%~dp0scripts\deploy\install_frontend_service.ps1"
if not exist "%SCRIPT%" set "SCRIPT=%~dp0current\scripts\deploy\install_frontend_service.ps1"
if not exist "%SCRIPT%" set "SCRIPT=C:\work\stock_quote_analayze\current\scripts\deploy\install_frontend_service.ps1"
if not exist "%SCRIPT%" (
    echo [ERROR] install_frontend_service.ps1 not found
    goto :end
)

echo Script: %SCRIPT%
echo.
echo Will:
echo   - Register Windows service stock-quote-frontend
echo   - FRONTEND_PORT=8000 ENVIRONMENT=production
echo   - Auto-start on boot, restart on crash
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -DeployRoot "C:\work\stock_quote_analayze" -StopManualFrontendFirst -StartAfterInstall %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo [FAILED] ExitCode=%RC%
) else (
    echo.
    echo [OK] Frontend service installed and started.
)

:end
echo.
pause
exit /b %RC%
