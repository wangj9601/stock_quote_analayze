@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

rem =============================================================================
rem  轻量 PostgreSQL 迁移：pg_dump -Fc，排除行情等可重采大表数据（保留表结构）
rem  用法:
rem    set PGPASSWORD=你的密码
rem    pg_dump_light.bat
rem    scripts\deploy\pg_dump_light.bat -Port 5446 -OutDir D:\backups
rem  环境变量: PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE OUT_DIR OUT_FILE
rem  说明: docs\prod\ubuntu-aliyun-runbook.md §4.1
rem  注意: 不要把数据库密码写进本脚本或提交到 Git
rem =============================================================================

cd /d "%~dp0..\.."
set "ROOT=%CD%"

if not defined PGHOST set "PGHOST=127.0.0.1"
if not defined PGPORT set "PGPORT=5446"
if not defined PGUSER set "PGUSER=postgres"
if not defined PGDATABASE set "PGDATABASE=stock_analysis"

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="-OutDir" set "OUT_DIR=%~2" & shift & shift & goto parse_args
if /i "%~1"=="-OutFile" set "OUT_FILE=%~2" & shift & shift & goto parse_args
if /i "%~1"=="-Host" set "PGHOST=%~2" & shift & shift & goto parse_args
if /i "%~1"=="-Port" set "PGPORT=%~2" & shift & shift & goto parse_args
if /i "%~1"=="-User" set "PGUSER=%~2" & shift & shift & goto parse_args
if /i "%~1"=="-Db" set "PGDATABASE=%~2" & shift & shift & goto parse_args
if /i "%~1"=="-h" goto usage
if /i "%~1"=="-Help" goto usage
if /i "%~1"=="/?" goto usage
echo [错误] 未知参数: %~1
goto usage

:args_done

if not defined OUT_DIR set "OUT_DIR=%ROOT%\dist\db_dumps"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "_STAMP=%%I"
if not defined OUT_FILE set "OUT_FILE=%OUT_DIR%\stock_analysis_light_%_STAMP%.dump"

echo ========================================
echo  轻量迁库 dump - stock_analysis
echo ========================================
echo  Host=%PGHOST%  Port=%PGPORT%  User=%PGUSER%  Db=%PGDATABASE%
echo  Out=%OUT_FILE%
echo.

rem PATH 常含 Program Files (x86)，禁止在 if() 块内展开 %PATH%
where pg_dump >nul 2>&1
if errorlevel 1 call :prepend_pg_bin
where pg_dump >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 pg_dump.exe，请安装 PostgreSQL 客户端并加入 PATH。
  exit /b 1
)
where psql >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 psql.exe。
  exit /b 1
)

if not defined PGPASSWORD (
  set /p PGPASSWORD=请输入数据库密码:
)
if not defined PGPASSWORD (
  echo [错误] 未设置密码。可先执行: set PGPASSWORD=你的密码
  exit /b 1
)
if "%PGPASSWORD%"=="" (
  echo [错误] 密码为空。
  exit /b 1
)

echo [1/3] 探测可排除的大表...
set "EXCLUDES="
set "EXCL_COUNT=0"
set "SKIP_COUNT=0"

for %%T in (
  historical_quotes
  historical_quotes_hk
  index_historical_quotes
  industry_board_historical_quotes
  concept_board_historical_quotes
  hk_index_historical_quotes
  fund_historical_quotes
  quote_data
  stock_realtime_quote
  stock_realtime_quote_hk
  index_realtime_quotes
  industry_board_realtime_quotes
  hk_index_realtime_quotes
  fund_realtime_quote
  stock_fund_flow_daily
  stock_fund_flow_daily_hk
  stock_fund_flow_em_daily
  board_fund_flow_daily
  stock_margin_daily
  stock_adj_factor
  stock_fina_indicator
  macd_indicators
  kdj_indicators
  rsi_indicators
  ma_indicators
  boll_indicators
  mavol_indicators
  icost_indicators
  mean_frequency_resonance_indicators
  industry_board_daily_metrics
  concept_board_daily_metrics
  rs_ratings
  rs_ratings_hk
  gms_signal_trace
  urt_signal_trace
  csb_signal_trace
  sbbr_signal_trace
  rpe_signal_trace
  stock_zt_pool_daily
  market_daily_review
  market_daily_mainline_hits
  stock_recommend_brief
  one_yang_three_lines_signals
  volume_shrink_breakout_signals
  stock_notice_report
  stock_news
  stock_research_reports
  system_monitor_metrics
  system_alerts
  system_performance_reports
  push_records
  email_send_logs
) do (
  set "FOUND="
  for /f "usebackq delims=" %%A in (`psql -h "%PGHOST%" -p "%PGPORT%" -U "%PGUSER%" -d "%PGDATABASE%" -Atc "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='%%T'" 2^>nul`) do set "FOUND=%%A"
  if "!FOUND!"=="1" (
    set "EXCLUDES=!EXCLUDES! --exclude-table-data=%%T"
    set /a EXCL_COUNT+=1
    echo   exclude data: %%T
  ) else (
    set /a SKIP_COUNT+=1
    echo   skip missing: %%T
  )
)

echo.
echo [2/3] 将排除 !EXCL_COUNT! 张表的数据，跳过不存在 !SKIP_COUNT!
echo [3/3] 执行 pg_dump ...
echo.

pg_dump -h "%PGHOST%" -p "%PGPORT%" -U "%PGUSER%" -Fc -f "%OUT_FILE%" !EXCLUDES! "%PGDATABASE%"
if errorlevel 1 (
  echo.
  echo [失败] pg_dump 未成功。
  exit /b 1
)

echo.
echo [完成] %OUT_FILE%
for %%I in ("%OUT_FILE%") do echo        大小: %%~zI bytes
echo.
echo 下一步: 上传到 ECS /opt/stock_quote/shared/backups/ 后执行 pg_restore。
echo.
exit /b 0

:prepend_pg_bin
if exist "%ProgramFiles%\PostgreSQL\18\bin\pg_dump.exe" set "PATH=%ProgramFiles%\PostgreSQL\18\bin;%PATH%" & goto :eof
if exist "%ProgramFiles%\PostgreSQL\17\bin\pg_dump.exe" set "PATH=%ProgramFiles%\PostgreSQL\17\bin;%PATH%" & goto :eof
if exist "%ProgramFiles%\PostgreSQL\16\bin\pg_dump.exe" set "PATH=%ProgramFiles%\PostgreSQL\16\bin;%PATH%" & goto :eof
if exist "%ProgramFiles%\PostgreSQL\15\bin\pg_dump.exe" set "PATH=%ProgramFiles%\PostgreSQL\15\bin;%PATH%" & goto :eof
if exist "%ProgramFiles%\PostgreSQL\14\bin\pg_dump.exe" set "PATH=%ProgramFiles%\PostgreSQL\14\bin;%PATH%" & goto :eof
goto :eof

:usage
echo.
echo 用法: %~nx0 [选项]
echo   -Host 127.0.0.1   -Port 5446   -User postgres   -Db stock_analysis
echo   -OutDir dist\db_dumps
echo   -OutFile path\to\file.dump
echo 环境变量: PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE OUT_DIR OUT_FILE
echo 示例: set PGPASSWORD=*** ^&^& %~nx0
echo.
exit /b 2
