@echo off
chcp 65001 >nul
title 构建 exe
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo.
echo ============================================
echo   🔥 小红书热点收集器 — 打包为 exe
echo ============================================
echo.

:: 1. 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 需要 Python，请先安装：https://python.org
    pause & exit /b 1
)

:: 2. 安装打包依赖
echo [1/5] 安装打包工具...
pip install -r requirements.txt -q
pip install pyinstaller -q
echo        ✓ 完成
echo.

:: 3. 确保 Playwright 浏览器已下载
echo [2/5] 检查浏览器内核...
python -m playwright install chromium
echo        ✓ 完成
echo.

:: 4. PyInstaller 打包
echo [3/5] PyInstaller 打包中（约 2-5 分钟）...
rmdir /s /q dist 2>nul
rmdir /s /q build 2>nul
pyinstaller build.spec --distpath dist --workpath build --noconfirm 2>&1
if %errorlevel% neq 0 (
    echo ❌ 打包失败，查看上方报错
    pause & exit /b 1
)
echo        ✓ 完成
echo.

:: 5. 复制浏览器内核到输出目录
echo [4/5] 打包浏览器内核...
for /f "tokens=*" %%i in ('python -c "import playwright; from playwright.sync_api import sync_playwright; p=sync_playwright().start(); print(p.chromium.executable_path); p.stop()"') do set CHROME=%%i
for %%i in ("!CHROME!") do set BROWSER_DIR=%%~dpi
set BROWSER_DIR=!BROWSER_DIR:~0,-1!
for %%i in ("!BROWSER_DIR!") do set BROWSER_ROOT=%%~dpi
set BROWSER_ROOT=!BROWSER_ROOT:~0,-1!

if exist "!BROWSER_ROOT!" (
    if not exist "dist\小红书热点收集器\browsers" mkdir "dist\小红书热点收集器\browsers"
    xcopy /e /i /q "!BROWSER_ROOT!." "dist\小红书热点收集器\browsers" >nul
    echo        ✓ 完成
) else (
    echo        ⚠ 未找到浏览器内核目录，跳过
)
echo.

:: 6. 创建启动器
echo [5/5] 创建启动器...
(
echo @echo off
echo start "" "%~dp0小红书热点收集器.exe"
)>"dist\小红书热点收集器\启动.bat"
echo        ✓ 完成
echo.

:: 完成
echo ============================================
echo   ✅ 打包完成！
echo.
echo   输出目录：dist\小红书热点收集器\
echo   大小：预计 150-200 MB
echo.
echo   使用方法：
echo     - 把「小红书热点收集器」文件夹整个复制给别人
echo     - 对方双击里面的「启动.bat」即可
echo ============================================
echo.

pause
