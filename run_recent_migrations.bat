@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

REM 执行 migrations 目录下最近 N 天内修改过的 .py 迁移脚本（默认 2 天）
REM 用法:
REM   run_recent_migrations.bat
REM   run_recent_migrations.bat 1
REM   run_recent_migrations.bat 2

cd /d "%~dp0"

set "DAYS=%~1"
if "%DAYS%"=="" set "DAYS=2"

where python >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 python，请先加入 PATH。
  pause
  exit /b 1
)

if not exist "migrations\" (
  echo [错误] 找不到 migrations 目录: %cd%\migrations
  pause
  exit /b 1
)

echo ========================================
echo  最近 %DAYS% 天内的 migrations/*.py
echo  工作目录: %cd%
echo ========================================
echo.

set "LIST_FILE=%TEMP%\stock_quote_recent_migrations_%RANDOM%.txt"
if exist "%LIST_FILE%" del /f /q "%LIST_FILE%" >nul 2>&1

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$days = [int]%DAYS%;" ^
  "$cutoff = (Get-Date).AddDays(-$days);" ^
  "$files = Get-ChildItem -Path 'migrations' -Filter '*.py' -File |" ^
  "  Where-Object { $_.LastWriteTime -ge $cutoff } |" ^
  "  Sort-Object LastWriteTime;" ^
  "if (-not $files -or $files.Count -eq 0) { exit 2 }" ^
  "$files | ForEach-Object { '{0}`t{1}' -f $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'), $_.FullName }" ^
  "| Set-Content -Encoding UTF8 -Path '%LIST_FILE%'"

if errorlevel 2 (
  echo [提示] 最近 %DAYS% 天内没有需要执行的迁移脚本。
  if exist "%LIST_FILE%" del /f /q "%LIST_FILE%" >nul 2>&1
  pause
  exit /b 0
)

if not exist "%LIST_FILE%" (
  echo [错误] 未能生成待执行列表。
  pause
  exit /b 1
)

echo 将按修改时间顺序执行:
echo ----------------------------------------
type "%LIST_FILE%"
echo ----------------------------------------
echo.
set /p "CONFIRM=确认执行以上脚本？(Y/N): "
if /i not "%CONFIRM%"=="Y" (
  echo 已取消。
  del /f /q "%LIST_FILE%" >nul 2>&1
  pause
  exit /b 0
)

set "FAIL=0"
set "OK=0"
for /f "usebackq tokens=1* delims=	" %%A in ("%LIST_FILE%") do (
  set "SCRIPT=%%B"
  echo.
  echo -------- 执行: !SCRIPT!
  python "!SCRIPT!"
  if errorlevel 1 (
    echo [失败] !SCRIPT!
    set /a FAIL+=1
  ) else (
    echo [成功] !SCRIPT!
    set /a OK+=1
  )
)

del /f /q "%LIST_FILE%" >nul 2>&1

echo.
echo ========================================
echo  完成: 成功 %OK% 个，失败 %FAIL% 个
echo ========================================
if not "%FAIL%"=="0" (
  pause
  exit /b 1
)
pause
exit /b 0
