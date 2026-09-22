@echo off
chcp 65001 >nul
setlocal EnableExtensions

REM ============================================================
REM  执行 migrations 目录下「最近 N 天内修改过」的 .py 迁移脚本
REM  默认 N=2
REM
REM  用法:
REM    run_recent_migrations.bat
REM    run_recent_migrations.bat 1
REM    run_recent_migrations.bat 2
REM    run_recent_migrations.bat 2 -Yes   （跳过确认）
REM ============================================================

cd /d "%~dp0"

set "DAYS=%~1"
if "%DAYS%"=="" set "DAYS=2"

set "YES_FLAG="
if /i "%~2"=="-Yes" set "YES_FLAG=-Yes"
if /i "%~2"=="/Yes" set "YES_FLAG=-Yes"
if /i "%~1"=="-Yes" (
  set "DAYS=2"
  set "YES_FLAG=-Yes"
)

where python >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 python，请先加入 PATH。
  pause
  exit /b 1
)

if not exist "scripts\run_recent_migrations.ps1" (
  echo [错误] 找不到 scripts\run_recent_migrations.ps1
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_recent_migrations.ps1" -Days %DAYS% %YES_FLAG%
set "RC=%ERRORLEVEL%"

echo.
pause
exit /b %RC%
