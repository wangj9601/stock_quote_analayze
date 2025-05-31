@echo off
echo ===================================
echo 股票实时行情采集程序
echo ===================================
echo 开始时间: %date% %time%
echo.

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 执行采集程序
python .\backend_core\data_collectors\tushare\main.py --type realtime

echo.
echo ===================================
echo 结束时间: %date% %time%
echo ===================================

:: 暂停，等待用户按键
pause 