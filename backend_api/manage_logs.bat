@echo off
chcp 65001 >nul
echo ========================================
echo 一阳穿三线策略日志管理工具
echo ========================================
echo.

:menu
echo 请选择操作:
echo 1. 列出所有日志文件
echo 2. 显示日志统计信息
echo 3. 查看最新日志文件 (最后20行)
echo 4. 清理7天前的日志文件
echo 5. 归档30天前的日志文件
echo 6. 自定义清理天数
echo 7. 自定义归档天数
echo 8. 查看指定日志文件
echo 0. 退出
echo.
set /p choice=请输入选项 (0-8): 

if "%choice%"=="1" goto list
if "%choice%"=="2" goto stats
if "%choice%"=="3" goto tail
if "%choice%"=="4" goto clean
if "%choice%"=="5" goto archive
if "%choice%"=="6" goto clean_custom
if "%choice%"=="7" goto archive_custom
if "%choice%"=="8" goto tail_custom
if "%choice%"=="0" goto exit
echo 无效选项，请重新选择
echo.
goto menu

:list
echo.
echo 正在列出日志文件...
python log_manager.py list
echo.
pause
goto menu

:stats
echo.
echo 正在显示日志统计信息...
python log_manager.py stats
echo.
pause
goto menu

:tail
echo.
echo 正在查看最新日志文件...
python log_manager.py tail
echo.
pause
goto menu

:clean
echo.
echo 正在清理7天前的日志文件...
python log_manager.py clean --days 7
echo.
pause
goto menu

:archive
echo.
echo 正在归档30天前的日志文件...
python log_manager.py archive --days 30
echo.
pause
goto menu

:clean_custom
echo.
set /p days=请输入要清理的天数: 
echo 正在清理%days%天前的日志文件...
python log_manager.py clean --days %days%
echo.
pause
goto menu

:archive_custom
echo.
set /p days=请输入要归档的天数: 
echo 正在归档%days%天前的日志文件...
python log_manager.py archive --days %days%
echo.
pause
goto menu

:tail_custom
echo.
set /p filename=请输入日志文件名 (留空查看最新): 
set /p lines=请输入要显示的行数 (默认20): 
if "%lines%"=="" set lines=20
if "%filename%"=="" (
    python log_manager.py tail --lines %lines%
) else (
    python log_manager.py tail --file "%filename%" --lines %lines%
)
echo.
pause
goto menu

:exit
echo.
echo 感谢使用日志管理工具！
pause
