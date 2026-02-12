@echo off
chcp 65001 >nul 2>&1

:: Mini TimeBot 启动脚本（直接启动服务，跳过环境配置）
:: 实际启动逻辑统一由 launcher.py 管理

cd /d "%~dp0\.."

:: 激活虚拟环境（如果存在）
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: 调用 Python 启动器
python scripts\launcher.py
