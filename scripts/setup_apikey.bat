@echo off
chcp 65001 >nul 2>&1

:: DeepSeek API Key 配置脚本

cd /d "%~dp0\.."

set "ENV_FILE=config\.env"
set "EXAMPLE_FILE=config\.env.example"

:: 已有 .env 且 Key 已配置，跳过
if not exist "%ENV_FILE%" goto ask_key

:: 读取当前 Key
for /f "tokens=1,* delims==" %%a in ('findstr /i "DEEPSEEK_API_KEY" "%ENV_FILE%"') do set "CURRENT_KEY=%%b"
if "%CURRENT_KEY%"=="" goto ask_key
if "%CURRENT_KEY%"=="your_deepseek_api_key_here" goto ask_key

echo [OK] API Key 已配置
exit /b 0

:ask_key
echo ================================================
echo   需要配置 DeepSeek API Key 才能使用
echo   获取地址: https://platform.deepseek.com/api_keys
echo ================================================
echo.

set /p API_KEY=请输入你的 DeepSeek API Key: 

if "%API_KEY%"=="" (
    echo [SKIP] 未输入 API Key，跳过配置
    echo        请稍后手动编辑 config\.env
    exit /b 1
)

:: 读取已有 API_BASE 或使用默认值
set "API_BASE=https://api.deepseek.com"
if exist "%ENV_FILE%" (
    for /f "tokens=1,* delims==" %%a in ('findstr /i "DEEPSEEK_API_BASE" "%ENV_FILE%"') do set "API_BASE=%%b"
)

:: 写入 .env
(
    echo DEEPSEEK_API_KEY=%API_KEY%
    echo DEEPSEEK_API_BASE=%API_BASE%
) > "%ENV_FILE%"

echo [OK] API Key 已保存到 config\.env
exit /b 0
