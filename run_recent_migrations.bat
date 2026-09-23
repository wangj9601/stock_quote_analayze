@echo off
setlocal EnableExtensions

REM ============================================================
REM  执行 migrations 目录下「最近 N 天内修改过」的 .py 迁移脚本
REM  默认 N=2
REM
REM  用法:
REM    run_recent_migrations.bat
REM    run_recent_migrations.bat 1
REM    run_recent_migrations.bat 2
REM    run_recent_migrations.bat 2 -Yes   （跳过确认，适合生产/无人值守）
REM
REM  说明:
REM    优先用 Python 执行 scripts\run_recent_migrations.py，
REM    不依赖 Windows PowerShell 版本（生产常见 PS 4.0）。
REM ============================================================

cd /d "%~dp0"
if errorlevel 1 (
  echo [ERROR] cannot cd to script directory: %~dp0
  exit /b 1
)

set "DAYS=%~1"
if "%DAYS%"=="" set "DAYS=2"

set "YES_FLAG="
if /i "%~2"=="-Yes" set "YES_FLAG=1"
if /i "%~2"=="/Yes" set "YES_FLAG=1"
if /i "%~1"=="-Yes" (
  set "DAYS=2"
  set "YES_FLAG=1"
)
if /i "%~1"=="/Yes" (
  set "DAYS=2"
  set "YES_FLAG=1"
)

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] python not found in PATH.
  if not defined YES_FLAG pause
  exit /b 1
)

if not exist "scripts\run_recent_migrations.py" (
  echo [ERROR] missing scripts\run_recent_migrations.py
  if not defined YES_FLAG pause
  exit /b 1
)

if defined YES_FLAG (
  python "%~dp0scripts\run_recent_migrations.py" --days %DAYS% --yes
) else (
  python "%~dp0scripts\run_recent_migrations.py" --days %DAYS%
)
set "RC=%ERRORLEVEL%"

if not defined YES_FLAG (
  echo.
  pause
)
exit /b %RC%
