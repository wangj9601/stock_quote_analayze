@echo off
chcp 65001 >nul
echo ========================================
echo PostgreSQL数据库快速导出工具
echo ========================================
echo.

REM 设置数据库连接信息
set DB_HOST=192.168.31.237
set DB_PORT=5446
set DB_USER=postgres
set DB_NAME=stock_analysis
set PGPASSWORD=qidianspacetime

REM 创建导出目录
if not exist "exports" mkdir exports

REM 生成时间戳
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YY=%dt:~2,2%" & set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%" & set "Min=%dt:~10,2%" & set "Sec=%dt:~12,2%"
set "timestamp=%YYYY%%MM%%DD%_%HH%%Min%%Sec%"

echo 正在导出数据库...
echo 时间戳: %timestamp%
echo.

REM 导出完整数据库备份
echo 1. 导出完整数据库备份...
pg_dump -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% > "exports\full_backup_%timestamp%.sql"
if %errorlevel% equ 0 (
    echo ✅ 完整数据库备份导出成功
) else (
    echo ❌ 完整数据库备份导出失败
)

echo.

REM 导出表结构
echo 2. 导出表结构...
pg_dump -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% --schema-only > "exports\schema_backup_%timestamp%.sql"
if %errorlevel% equ 0 (
    echo ✅ 表结构导出成功
) else (
    echo ❌ 表结构导出失败
)

echo.

REM 导出数据
echo 3. 导出数据...
pg_dump -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% --data-only > "exports\data_backup_%timestamp%.sql"
if %errorlevel% equ 0 (
    echo ✅ 数据导出成功
) else (
    echo ❌ 数据导出失败
)

echo.

REM 导出主要表数据
echo 4. 导出主要表数据...

REM 导出实时行情表
echo    - 导出 stock_realtime_quote 表...
pg_dump -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -t stock_realtime_quote --data-only > "exports\stock_realtime_quote_%timestamp%.sql"

REM 导出历史行情表
echo    - 导出 historical_quotes 表...
pg_dump -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -t historical_quotes --data-only > "exports\historical_quotes_%timestamp%.sql"

REM 导出股票新闻表
echo    - 导出 stock_news 表...
pg_dump -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -t stock_news --data-only > "exports\stock_news_%timestamp%.sql"

REM 导出用户表
echo    - 导出 users 表...
pg_dump -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -t users --data-only > "exports\users_%timestamp%.sql"

REM 导出自选股表
echo    - 导出 watchlist 表...
pg_dump -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -t watchlist --data-only > "exports\watchlist_%timestamp%.sql"

echo ✅ 主要表数据导出完成

echo.
echo ========================================
echo 导出完成！
echo 文件保存在: exports\ 目录
echo 时间戳: %timestamp%
echo ========================================

REM 显示导出文件列表
echo.
echo 导出的文件:
dir /b exports\*%timestamp%*.sql

echo.
pause 