@echo off
chcp 65001 >nul
title 小红书热点收集器
cd /d "%~dp0"

echo.
echo ⏳ 检查环境...
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未检测到 Python，请先安装：https://python.org
    echo    安装时务必勾选 "Add Python to PATH"
    pause
    exit /b 1
)

:: 自动安装依赖
pip install -r requirements.txt -q 2>nul
if %errorlevel% neq 0 (
    echo ⚠️ 依赖安装失败，尝试手动安装...
    pip install -r requirements.txt
)

:: 检查 Playwright 浏览器
python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); p.chromium.launch(); p.stop()" >nul 2>&1
if %errorlevel% neq 0 (
    echo ⏳ 首次运行，下载浏览器内核（约130MB，仅此一次）...
    python -m playwright install chromium
)

:: 启动
echo.
echo 🔥 启动成功，浏览器打开 http://127.0.0.1:5000
echo.
start http://127.0.0.1:5000
python app.py
pause
