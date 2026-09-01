@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  Git Pull - %CD%
echo ========================================
echo.

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo [错误] 当前目录不是 Git 仓库。
    goto :end
)

echo 当前分支:
git branch --show-current
echo.

echo 正在拉取远程更新...
git pull
if errorlevel 1 (
    echo.
    echo [失败] git pull 未成功，请检查网络、冲突或上游分支设置。
) else (
    echo.
    echo [完成] 已与远程同步。
)

echo.
echo 当前状态:
git status -sb

:end
echo.
pause
