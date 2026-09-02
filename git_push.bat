@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

REM 默认：一键 add + commit + push（双击即用）
REM 仅 push：git_push.bat push
set "MODE=all"
set "COMMIT_MSG="

if /i "%~1"=="push" set "MODE=push"
if /i "%~1"=="only" set "MODE=push"
if /i "%~1"=="all" (
    if not "%~2"=="" set "COMMIT_MSG=%~2"
) else if not "%~1"=="" (
    if not "!MODE!"=="push" set "COMMIT_MSG=%~1"
)

if "!MODE!"=="all" (
    echo ========================================
    echo  Git Add + Commit + Push - %CD%
    echo ========================================
) else (
    echo ========================================
    echo  Git Push - %CD%
    echo ========================================
)
echo.

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo [错误] 当前目录不是 Git 仓库。
    goto :end
)

for /f "delims=" %%b in ('git branch --show-current 2^>nul') do set "BRANCH=%%b"
if not defined BRANCH (
    echo [错误] 无法获取当前分支。
    goto :end
)

echo 当前分支: %BRANCH%
echo.

git status -sb
echo.

if "!MODE!"=="all" goto :do_commit
goto :before_push

:do_commit
echo [1/3] 正在暂存所有改动 (git add .)...
git add .
if errorlevel 1 (
    echo [失败] git add 未成功。
    goto :end
)
echo.

git diff --cached --quiet
if errorlevel 1 (
    echo [2/3] 正在提交 (git commit)...
    if not defined COMMIT_MSG (
        set /p "COMMIT_MSG=请输入提交说明（留空则自动生成）: "
    )
    if not defined COMMIT_MSG (
        for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TODAY=%%i"
        set "COMMIT_MSG=commit at !TODAY!"
        echo 使用默认提交说明: !COMMIT_MSG!
    )
    git commit -m "!COMMIT_MSG!"
    if errorlevel 1 (
        echo [失败] git commit 未成功。
        goto :end
    )
    echo.
) else (
    echo [2/3] 没有需要提交的改动，跳过 commit。
    echo.
)

:before_push
if "!MODE!"=="all" (
    echo [3/3] 正在推送到远程...
) else (
    git status --porcelain | findstr /r "." >nul 2>&1
    if not errorlevel 1 (
        echo [提示] 工作区有未提交的改动，本次 push 不会包含这些文件。
        echo        一键提交并推送请直接双击本脚本，或运行: git_push.bat
        echo        带说明: git_push.bat "你的提交说明"
        echo.
    )
)

call :do_push
goto :after_push

:do_push
git rev-parse --abbrev-ref "%BRANCH%@{upstream}" >nul 2>&1
if errorlevel 1 (
    echo [提示] 当前分支尚未设置上游，将使用: origin/%BRANCH%
    git push -u origin "%BRANCH%"
) else (
    git push
)
exit /b %errorlevel%

:after_push
if errorlevel 1 (
    echo.
    echo [失败] git push 未成功，请检查网络、权限或是否需要先 pull/解决冲突。
) else (
    echo.
    if "!MODE!"=="all" (
        echo [完成] 已 add、commit 并 push 到远程。
    ) else (
        echo [完成] 已推送到远程。
    )
)

echo.
echo 当前状态:
git status -sb

:end
echo.
pause
endlocal
