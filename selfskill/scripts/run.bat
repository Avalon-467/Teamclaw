@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: Mini TimeBot skill 入口脚本 - Windows 版（供外部 agent 非交互式调用）
::
:: 用法:
::   selfskill\scripts\run.bat start                          # 后台启动服务
::   selfskill\scripts\run.bat stop                           # 停止服务
::   selfskill\scripts\run.bat status                         # 检查服务状态
::   selfskill\scripts\run.bat setup                          # 首次：安装环境依赖
::   selfskill\scripts\run.bat add-user <name> <password>     # 创建/更新用户
::   selfskill\scripts\run.bat configure <KEY> <VALUE>        # 设置 .env 配置项
::   selfskill\scripts\run.bat configure --batch K1=V1 K2=V2  # 批量设置配置
::   selfskill\scripts\run.bat configure --show               # 查看当前配置
::   selfskill\scripts\run.bat configure --init               # 从模板初始化 .env
::
:: 所有命令均为非交互式，适合自动化调用。

:: 定位项目根目录（selfskill\scripts\run.bat → 上两级）
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%\..\..\") do set "PROJECT_ROOT=%%~fI"
:: 去掉末尾反斜杠
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
cd /d "%PROJECT_ROOT%"

:: 激活虚拟环境
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

set "PIDFILE=%PROJECT_ROOT%\.mini_timebot.pid"

:: 从 config/.env 读取端口配置
set "PORT_AGENT=51200"
set "PORT_SCHEDULER=51201"
set "PORT_OASIS=51202"
set "PORT_FRONTEND=51209"
if exist "config\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("config\.env") do (
        set "LINE=%%A"
        if not "!LINE:~0,1!"=="#" (
            set "%%A=%%B"
        )
    )
)

:: 路由命令
if "%~1"=="" goto :help
if "%~1"=="start" goto :start
if "%~1"=="stop" goto :stop
if "%~1"=="status" goto :status
if "%~1"=="setup" goto :setup
if "%~1"=="add-user" goto :adduser
if "%~1"=="configure" goto :configure
if "%~1"=="help" goto :help
if "%~1"=="--help" goto :help
if "%~1"=="-h" goto :help
echo 未知命令: %~1 >&2
echo 运行 '%~0 help' 查看可用命令 >&2
exit /b 1

:start
if not exist "config\.env" (
    echo ❌ 未找到 config\.env，请先运行: %~0 configure --init 并配置必要参数 >&2
    exit /b 1
)

if exist "%PIDFILE%" (
    set /p PID=<"%PIDFILE%"
    tasklist /fi "PID eq !PID!" 2>nul | find "!PID!" >nul 2>&1
    if !errorlevel! equ 0 (
        echo ⚠️  Mini TimeBot 已在运行 (PID: !PID!)
        exit /b 0
    )
)

echo 🚀 启动 Mini TimeBot (headless)...
if not exist "%PROJECT_ROOT%\logs" mkdir "%PROJECT_ROOT%\logs"
start /b "" python scripts\launcher.py > "%PROJECT_ROOT%\logs\launcher.log" 2>&1
:: 获取最新 python 进程 PID
set "LAUNCHER_PID="
for /f "tokens=2" %%P in ('tasklist /fi "imagename eq python.exe" /fo list 2^>nul ^| findstr "PID"') do (
    set "LAUNCHER_PID=%%P"
)
if defined LAUNCHER_PID (
    echo !LAUNCHER_PID!> "%PIDFILE%"
    echo ✅ Mini TimeBot 已在后台启动 (PID: !LAUNCHER_PID!)
) else (
    echo ⚠️  启动可能失败，请查看日志
)
echo    日志: %PROJECT_ROOT%\logs\launcher.log

:: 等待服务就绪
set /a WAIT=0
:wait_loop
if !WAIT! geq 30 (
    echo.
    echo ⚠️  服务可能仍在启动中，请查看日志确认
    exit /b 0
)
curl -sf "http://127.0.0.1:!PORT_AGENT!/v1/models" >nul 2>&1
if !errorlevel! equ 0 (
    echo    等待服务就绪 ✅
    exit /b 0
)
set /a WAIT+=1
<nul set /p "=."
timeout /t 2 /nobreak >nul
goto :wait_loop

:stop
if not exist "%PIDFILE%" (
    echo 未找到 PID 文件，服务可能未运行
    exit /b 0
)
set /p PID=<"%PIDFILE%"
tasklist /fi "PID eq %PID%" 2>nul | find "%PID%" >nul 2>&1
if %errorlevel% neq 0 (
    echo 进程已不存在
    del /f "%PIDFILE%" >nul 2>&1
    exit /b 0
)
echo 正在停止 Mini TimeBot (PID: %PID%)...
taskkill /pid %PID% /t /f >nul 2>&1
del /f "%PIDFILE%" >nul 2>&1
echo ✅ 已停止
exit /b 0

:status
if not exist "%PIDFILE%" (
    echo ❌ Mini TimeBot 未运行
    exit /b 1
)
set /p PID=<"%PIDFILE%"
tasklist /fi "PID eq %PID%" 2>nul | find "%PID%" >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Mini TimeBot 未运行（PID 文件残留）
    del /f "%PIDFILE%" >nul 2>&1
    exit /b 1
)
echo ✅ Mini TimeBot 正在运行 (PID: %PID%)
for %%P in (%PORT_AGENT% %PORT_SCHEDULER% %PORT_OASIS% %PORT_FRONTEND%) do (
    netstat -an 2>nul | find ":%%P " | find "LISTENING" >nul 2>&1
    if !errorlevel! equ 0 (
        echo   ✅ 端口 %%P 已监听
    ) else (
        echo   ⚠️  端口 %%P 未监听
    )
)
exit /b 0

:setup
echo === 环境配置 ===
if exist "scripts\setup_env.bat" (
    call scripts\setup_env.bat
) else (
    echo ⚠️  未找到 scripts\setup_env.bat，请参考 scripts\setup_env.sh 手动配置
)
echo === 环境配置完成 ===
exit /b 0

:adduser
if "%~2"=="" (
    echo 用法: %~0 add-user ^<username^> ^<password^> >&2
    exit /b 1
)
if "%~3"=="" (
    echo 用法: %~0 add-user ^<username^> ^<password^> >&2
    exit /b 1
)
python selfskill\scripts\adduser.py "%~2" "%~3"
exit /b 0

:configure
shift
python selfskill\scripts\configure.py %1 %2 %3 %4 %5 %6 %7 %8 %9
exit /b 0

:help
echo Mini TimeBot Skill 入口 (Windows)
echo.
echo 用法: selfskill\scripts\run.bat ^<command^> [args]
echo.
echo 命令:
echo   start                          后台启动服务
echo   stop                           停止服务
echo   status                         检查服务状态
echo   setup                          安装环境依赖（首次）
echo   add-user ^<name^> ^<password^>     创建/更新用户
echo   configure ^<KEY^> ^<VALUE^>        设置 .env 配置项
echo   configure --batch K1=V1 K2=V2  批量设置配置
echo   configure --show               查看当前配置
echo   configure --init               从模板初始化 .env
echo   help                           显示此帮助
exit /b 0
