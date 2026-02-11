@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: Mini TimeBot 自动环境配置脚本
cd /d "%~dp0\.."

echo ==========================================
echo   Mini TimeBot 环境自动配置
echo ==========================================
echo.

:: --- 1. 检查 uv ---
where uv >nul 2>&1
if !errorlevel! equ 0 goto uv_ok

echo [INSTALL] 未检测到 uv，正在安装...
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
:: 这里的路径手动添加，不使用 set PATH 拼接，防止触发括号错误
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"

:uv_ok
echo [OK] uv 已准备就绪
uv --version

:: --- 2. 检查虚拟环境 ---
:: 不使用 if (...) 块，改用 goto 逻辑避开括号解析
if exist ".venv\Scripts\python.exe" goto venv_exists

echo [SETUP] 创建虚拟环境 (.venv, Python 3.11+)...
uv venv .venv --python 3.11
if !errorlevel! neq 0 echo [ERROR] 创建失败 && pause && exit /b 1

:venv_exists
echo [OK] 虚拟环境已存在

:: --- 3. 激活虚拟环境 ---
echo [ACTIVATE] 正在激活环境...
call .venv\Scripts\activate.bat
if !errorlevel! neq 0 echo [ERROR] 激活失败 && pause && exit /b 1
python --version

:: --- 4. 安装依赖 ---
if not exist "config\requirements.txt" goto no_req
echo [INSTALL] 正在安装依赖...
uv pip install -r config\requirements.txt
echo [OK] 依赖安装完成
goto req_done

:no_req
echo [SKIP] 未找到 config\requirements.txt

:req_done

:: --- 5. 检查配置 ---
echo.
echo --- 配置检查 ---
if exist "config\.env" (echo [OK] .env 存在) else (echo [WARN] .env 缺失)
if exist "config\users.json" (echo [OK] users.json 存在) else (echo [WARN] users.json 缺失)

echo.
echo ==========================================
echo   配置完成！输入 scripts\start.bat 启动服务
echo ==========================================
pause
