@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
title backend_core collector

rem ============================================================
rem  Start backend_core only (scheduled data collectors)
rem  Entry: start_backend_core.py
rem  Does NOT start API / frontend / admin
rem
rem  Root resolve order:
rem    1) env STOCK_QUOTE_ROOT
rem    2) PROJECT_ROOT below
rem    3) this script directory
rem    4) start_backend_core.root beside this bat
rem    5) DEFAULT_PROJECT_ROOT below
rem ============================================================

set "PROJECT_ROOT="
set "DEFAULT_PROJECT_ROOT=E:\wangxw\股票分析软件\编码\stock_quote_analayze"

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "ROOT="

if defined STOCK_QUOTE_ROOT (
    call :normalize_root "%STOCK_QUOTE_ROOT%"
    if exist "!ROOT!\start_backend_core.py" goto :root_ok
    set "ROOT="
)

if defined PROJECT_ROOT (
    call :normalize_root "%PROJECT_ROOT%"
    if exist "!ROOT!\start_backend_core.py" goto :root_ok
    set "ROOT="
)

if exist "%SCRIPT_DIR%\start_backend_core.py" (
    call :normalize_root "%SCRIPT_DIR%"
    goto :root_ok
)

if exist "%SCRIPT_DIR%\start_backend_core.root" (
    set /p _ROOT_FROM_FILE=<"%SCRIPT_DIR%\start_backend_core.root"
    call :normalize_root "!_ROOT_FROM_FILE!"
    if exist "!ROOT!\start_backend_core.py" goto :root_ok
    set "ROOT="
)

if defined DEFAULT_PROJECT_ROOT (
    call :normalize_root "%DEFAULT_PROJECT_ROOT%"
    if exist "!ROOT!\start_backend_core.py" goto :root_ok
    set "ROOT="
)

echo [ERROR] Cannot locate project root: start_backend_core.py not found.
echo   - set STOCK_QUOTE_ROOT=absolute\path
echo   - or edit PROJECT_ROOT / DEFAULT_PROJECT_ROOT in this bat
echo   - or create start_backend_core.root beside this bat
echo   - or keep this bat in the repo root
goto :fail

:root_ok
cd /d "%ROOT%"
if errorlevel 1 (
    echo [ERROR] Cannot cd to: %ROOT%
    goto :fail
)

set "PYTHON=python"
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if exist "%ROOT%\venv\Scripts\python.exe" set "PYTHON=%ROOT%\venv\Scripts\python.exe"

echo ========================================
echo   backend_core collector service
echo ========================================
echo.
echo Project : %ROOT%
echo Python  : %PYTHON%
echo Entry   : start_backend_core.py
echo.
echo Starts data collectors only. No API / frontend / admin.
echo Press Ctrl+C to stop.
echo ========================================
echo.

if /i "%~1"=="dry-run" (
    echo [dry-run] path check OK, not starting.
    exit /b 0
)
if /i "%~1"=="-n" (
    echo [dry-run] path check OK, not starting.
    exit /b 0
)

"%PYTHON%" -c "import sys; print(sys.version)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python or create .venv.
    goto :fail
)

if not exist "%ROOT%\start_backend_core.py" (
    echo [ERROR] Missing: %ROOT%\start_backend_core.py
    goto :fail
)

"%PYTHON%" "%ROOT%\start_backend_core.py"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [WARN] exit code: %EXIT_CODE%
) else (
    echo Service stopped.
)
pause
exit /b %EXIT_CODE%

:fail
echo.
pause
exit /b 1

:normalize_root
set "ROOT=%~1"
if defined ROOT set "ROOT=%ROOT:"=%"
for /f "tokens=* delims= " %%A in ("%ROOT%") do set "ROOT=%%A"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
if "%ROOT:~-1%"=="/" set "ROOT=%ROOT:~0,-1%"
exit /b 0
