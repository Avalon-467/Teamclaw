@echo off
chcp 65001 >nul 2>&1

:: LLM API Key 配置脚本 - 修复换行符解析问题

cd /d "%~dp0\.."
set "ENV_FILE=config\.env"
set "EXAMPLE_FILE=config\.env.example"

:: 1. 检查 Key 是否已配置
if not exist "%ENV_FILE%" goto ask_key
for /f "tokens=1,* delims==" %%a in ('findstr /i "LLM_API_KEY" "%ENV_FILE%"') do set "CURRENT_KEY=%%b"
if "%CURRENT_KEY%"=="" goto ask_key
if "%CURRENT_KEY%"=="your_api_key_here" goto ask_key

set "KEY_PREFIX=%CURRENT_KEY:~0,8%"
echo [OK] API Key 已配置（%KEY_PREFIX%...）
echo.
echo 是否重新配置？(y/N)
set /p RESET="> "
if /i not "%RESET%"=="y" (
    echo     保持现有配置
    timeout /t 2 >nul
    exit /b 0
)

:ask_key
:: 2. 收集用户输入
set /p API_KEY=请输入你的 API Key: 
if "%API_KEY%"=="" (
    echo [SKIP] 未输入 API Key，跳过配置
    exit /b 1
)

set /p BASE_URL=请输入 API Base URL (默认 https://api.deepseek.com): 
if "%BASE_URL%"=="" set "BASE_URL=https://api.deepseek.com"

set /p MODEL_NAME=请输入模型名称 (默认 deepseek-chat): 
if "%MODEL_NAME%"=="" set "MODEL_NAME=deepseek-chat"

set /p TTS_MODEL=请输入 TTS 模型名称 (默认 gemini-2.5-flash-preview-tts): 
if "%TTS_MODEL%"=="" set "TTS_MODEL=gemini-2.5-flash-preview-tts"

set /p TTS_VOICE=请输入 TTS 语音 (默认 charon): 
if "%TTS_VOICE%"=="" set "TTS_VOICE=charon"

echo 该模型是否支持视觉/图片输入？(y/N，默认 N)
set /p VISION_INPUT=> 
if /i "%VISION_INPUT%"=="y" (set "VISION_SUPPORT=true") else (set "VISION_SUPPORT=false")

echo 是否使用 OpenAI 标准 API 模式？(Y/n，默认 Y)
set /p STANDARD_INPUT=> 
if /i "%STANDARD_INPUT%"=="n" (set "STANDARD_MODE=false") else (set "STANDARD_MODE=true")

:: 3. 核心写入逻辑：使用双引号包裹以确保 `n 被 PowerShell 正确识别为换行符
powershell -Command "$p='%ENV_FILE%'; $data=\"LLM_API_KEY=%API_KEY%`nLLM_BASE_URL=%BASE_URL%`nLLM_MODEL=%MODEL_NAME%`nTTS_MODEL=%TTS_MODEL%`nTTS_VOICE=%TTS_VOICE%`nLLM_VISION_SUPPORT=%VISION_SUPPORT%`nOPENAI_STANDARD_MODE=%STANDARD_MODE%\"; [System.IO.File]::WriteAllText($p, $data, (New-Object System.Text.UTF8Encoding $false))"

echo [OK] API Key 已保存到 config\.env
exit /b 0