@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

rem ============================================================
rem  Stock quote - start web services (NO backend_core collect)
rem  Runnable from ANY cwd (Desktop / Temp / etc.)
rem
rem  Root resolve order:
rem    1) env STOCK_QUOTE_ROOT
rem    2) PROJECT_ROOT below
rem    3) this script directory (when bat is in repo root)
rem    4) start_web_services.root beside this bat (one-line path)
rem    5) DEFAULT_PROJECT_ROOT below
rem ============================================================

rem Optional: set absolute project path (useful when bat is copied to Desktop)
set "PROJECT_ROOT="

rem Default repo path on this PC (edit after clone/move)
set "DEFAULT_PROJECT_ROOT=E:\wangxw\work\stock_quote_analayze"

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "ROOT="

if defined STOCK_QUOTE_ROOT (
    call :normalize_root "%STOCK_QUOTE_ROOT%"
    if exist "!ROOT!\start_backend_api.py" goto :root_ok
    set "ROOT="
)

if defined PROJECT_ROOT (
    call :normalize_root "%PROJECT_ROOT%"
    if exist "!ROOT!\start_backend_api.py" goto :root_ok
    set "ROOT="
)

if exist "%SCRIPT_DIR%\start_backend_api.py" (
    call :normalize_root "%SCRIPT_DIR%"
    goto :root_ok
)

if exist "%SCRIPT_DIR%\start_web_services.root" (
    set /p _ROOT_FROM_FILE=<"%SCRIPT_DIR%\start_web_services.root"
    call :normalize_root "!_ROOT_FROM_FILE!"
    if exist "!ROOT!\start_backend_api.py" goto :root_ok
    set "ROOT="
)

if defined DEFAULT_PROJECT_ROOT (
    call :normalize_root "%DEFAULT_PROJECT_ROOT%"
    if exist "!ROOT!\start_backend_api.py" goto :root_ok
    set "ROOT="
)

echo [ERROR] Cannot locate project root (start_backend_api.py not found).
echo   - set STOCK_QUOTE_ROOT=absolute\path
echo   - or edit PROJECT_ROOT / DEFAULT_PROJECT_ROOT in this bat
echo   - or create start_web_services.root (one-line absolute path) beside this bat
echo   - or keep this bat in the repo root
goto :fail

:root_ok
set "CALLER_CWD=%CD%"
cd /d "%ROOT%"
if errorlevel 1 (
    echo [ERROR] Cannot cd to: %ROOT%
    goto :fail
)

if not exist "%ROOT%\start_frontend.py" (
    echo [ERROR] Missing start_frontend.py: %ROOT%
    goto :fail
)
if not exist "%ROOT%\admin\package.json" (
    echo [ERROR] Missing admin: %ROOT%\admin
    goto :fail
)

set "PYTHON=python"
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if exist "%ROOT%\venv\Scripts\python.exe" set "PYTHON=%ROOT%\venv\Scripts\python.exe"

echo ========================================
echo   Stock Quote - Web Services
echo   (backend_core collectors NOT started)
echo ========================================
echo.
echo Caller cwd : %CALLER_CWD%
echo Project    : %ROOT%
echo Python     : %PYTHON%
echo.

if /i "%~1"=="dry-run" (
    echo [dry-run] path check only, services not started.
    exit /b 0
)
if /i "%~1"=="-n" (
    echo [dry-run] path check only, services not started.
    exit /b 0
)

"%PYTHON%" -c "import sys; print(sys.version)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python or create .venv.
    goto :fail
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm not found. Install Node.js for admin.
    goto :fail
)

if not exist "%ROOT%\admin\node_modules\" (
    echo [INFO] admin\node_modules missing, running npm install ...
    pushd "%ROOT%\admin"
    call npm install
    if errorlevel 1 (
        popd
        echo [ERROR] npm install failed.
        goto :fail
    )
    popd
)

echo [1/3] Backend API (port 5000) ...
start "Stock-Backend-API" /D "%ROOT%" cmd /k ""%PYTHON%" "%ROOT%\start_backend_api.py""
timeout /t 2 /nobreak >nul

echo [2/3] Frontend (port 8000) ...
start "Stock-Frontend" /D "%ROOT%" cmd /k ""%PYTHON%" "%ROOT%\start_frontend.py""
timeout /t 2 /nobreak >nul

echo [3/3] Admin Vite (port 8001) ...
start "Stock-Admin" /D "%ROOT%\admin" cmd /k "npm run dev"
timeout /t 2 /nobreak >nul

echo.
echo ----------------------------------------
echo Started 3 consoles. Close a window to stop that service.
echo.
echo URLs:
echo   API      http://localhost:5000
echo   Frontend http://localhost:8000/login.html
echo   Admin    http://localhost:8001/login
echo.
echo Browsers open automatically: Frontend login + Admin login
echo.
echo NOT started: backend_core / collectors (use start_news_scheduler.bat)
echo ----------------------------------------
echo.
pause
exit /b 0

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
