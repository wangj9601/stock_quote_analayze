@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  打部署包 - %CD%
echo ========================================
echo.

set "DEPLOY_SCRIPT=%~dp0scripts\deploy\deploy.ps1"
if not exist "%DEPLOY_SCRIPT%" (
    echo [错误] 未找到部署脚本: %DEPLOY_SCRIPT%
    goto :end
)

echo 将执行:
echo   powershell -ExecutionPolicy Bypass -File .\scripts\deploy\deploy.ps1 %*
echo.
echo 说明:
echo   - 默认仅本地打包（admin 构建 + 生成 zip），不上传服务器
echo   - 输出目录: dist\stock_quote_release_*.zip
echo   - 跳过 admin 构建: deploy_pack.bat -SkipAdminBuild
echo   - 远程部署需额外参数，例如:
echo     deploy_pack.bat -RemoteDeploy -ServerHost host -ServerUser user
echo.
echo 开始打包，请稍候（admin 构建可能需数分钟）...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%DEPLOY_SCRIPT%" %*
if errorlevel 1 (
    echo.
    echo [失败] 部署包生成未成功，请查看上方错误信息。
) else (
    echo.
    echo [完成] 部署包已生成，请查看 dist 目录下的 zip 文件。
)

:end
echo.
pause
