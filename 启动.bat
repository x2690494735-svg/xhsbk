@echo off
chcp 65001 >nul
title 小红书热点收集器
cd /d "%~dp0"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Please install Python: https://python.org
    pause
    exit /b 1
)

pip install -r requirements.txt -q 2>nul
if %errorlevel% neq 0 (
    pip install -r requirements.txt
)

start http://127.0.0.1:5000
python app.py
pause
