#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mini TimeBot 跨平台启动器
- 支持 Linux/macOS/Windows
- 精确管理子进程 PID
- 安全关闭：Ctrl+C、关窗口、kill 都能正常清理
"""

import subprocess
import sys
import os
import signal
import atexit
import time

# 切换到项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)

# 检查 .env 配置
if not os.path.exists("config/.env"):
    print("❌ 未找到 config/.env 文件，请先创建并填入 DEEPSEEK_API_KEY")
    sys.exit(1)

# 确定 Python 解释器路径（优先使用虚拟环境）
if sys.platform == "win32":
    venv_path = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")
else:
    venv_path = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")

venv_python = venv_path if os.path.exists(venv_path) else sys.executable

# 子进程列表
procs = []
cleanup_done = False


def cleanup():
    """清理所有子进程"""
    global cleanup_done
    if cleanup_done:
        return
    cleanup_done = True

    print("\n🛑 正在关闭所有服务...")

    # 先发 SIGTERM（优雅关闭）
    for p in procs:
        if p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass

    # 等待进程退出（最多 5 秒）
    for _ in range(50):
        if all(p.poll() is not None for p in procs):
            break
        time.sleep(0.1)

    # 超时未退出的进程强制杀掉
    for p in procs:
        if p.poll() is None:
            try:
                print(f"⚠️  进程 {p.pid} 未响应，强制终止...")
                p.kill()
            except Exception:
                pass

    # 等待所有进程结束
    for p in procs:
        try:
            p.wait(timeout=2)
        except Exception:
            pass

    print("✅ 所有服务已关闭")


# 注册退出清理
atexit.register(cleanup)


# 信号处理
def signal_handler(signum, frame):
    sys.exit(0)  # 触发 atexit


signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # kill

# Windows 特殊处理：捕获关闭窗口事件
if sys.platform == "win32":
    try:
        import win32api
        win32api.SetConsoleCtrlHandler(lambda x: cleanup() or True, True)
    except ImportError:
        try:
            signal.signal(signal.SIGBREAK, signal_handler)
        except Exception:
            pass

print("🚀 启动 Mini TimeBot...")
print()

# 服务配置：(提示信息, 脚本路径, 启动后等待秒数)
services = [
    ("⏰ [1/3] 启动定时调度中心 (port 8001)...", "src/time.py", 2),
    ("🤖 [2/3] 启动 AI Agent (port 8000)...", "src/mainagent.py", 3),
    ("🌐 [3/3] 启动前端 Web UI (port 9000)...", "src/front.py", 1),
]

for msg, script, wait_time in services:
    print(msg)
    proc = subprocess.Popen(
        [venv_python, script],
        cwd=PROJECT_ROOT,
        stdout=None,  # 继承父进程的 stdout
        stderr=None,  # 继承父进程的 stderr
    )
    procs.append(proc)
    time.sleep(wait_time)

print()
print("============================================")
print("  ✅ Mini TimeBot 已全部启动！")
print("  🌐 访问: http://127.0.0.1:9000")
print("  按 Ctrl+C 停止所有服务")
print("============================================")
print()

# 等待任意子进程退出
try:
    while True:
        for p in procs:
            if p.poll() is not None:
                print(f"⚠️ 服务 (PID {p.pid}) 异常退出，正在关闭其余服务...")
                sys.exit(1)
        time.sleep(0.5)
except KeyboardInterrupt:
    pass

sys.exit(0)
