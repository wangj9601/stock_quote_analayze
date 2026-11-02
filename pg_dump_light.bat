@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "SCRIPT=%~dp0scripts\deploy\pg_dump_light.bat"
if not exist "%SCRIPT%" (
  echo [错误] 未找到 %SCRIPT%
  exit /b 1
)
call "%SCRIPT%" %*
exit /b %ERRORLEVEL%
