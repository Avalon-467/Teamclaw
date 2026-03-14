#!/bin/bash
# Mini TimeBot skill 入口脚本（供外部 agent 非交互式调用）
#
# 用法:
#   bash selfskill/scripts/run.sh start                          # 后台启动服务
#   bash selfskill/scripts/run.sh stop                           # 停止服务
#   bash selfskill/scripts/run.sh status                         # 检查服务状态
#   bash selfskill/scripts/run.sh start-tunnel                   # 启动公网隧道（自动下载+暴露前端）
#   bash selfskill/scripts/run.sh stop-tunnel                    # 停止公网隧道
#   bash selfskill/scripts/run.sh tunnel-status                  # 查看隧道状态和公网地址
#   bash selfskill/scripts/run.sh setup                          # 首次：安装环境依赖
#   bash selfskill/scripts/run.sh add-user <name> <password>     # 创建/更新用户
#   bash selfskill/scripts/run.sh configure <KEY> <VALUE>        # 设置 .env 配置项
#   bash selfskill/scripts/run.sh configure --batch K1=V1 K2=V2  # 批量设置配置
#   bash selfskill/scripts/run.sh configure --show               # 查看当前配置
#   bash selfskill/scripts/run.sh configure --init               # 从模板初始化 .env
#   bash selfskill/scripts/run.sh check-openclaw                 # 检测/安装 OpenClaw
#   bash selfskill/scripts/run.sh cli chat "你好"                # CLI: 发送消息
#   bash selfskill/scripts/run.sh cli sessions                   # CLI: 查看会话
#   bash selfskill/scripts/run.sh cli settings                   # CLI: 查看设置
#   bash selfskill/scripts/run.sh cli status                     # CLI: 服务状态
#
# 所有命令均为非交互式，适合自动化调用。

set -e

# 定位项目根目录（skill/scripts/run.sh → 上两级）
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
export PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# 激活虚拟环境
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

PIDFILE="$PROJECT_ROOT/.mini_timebot.pid"

is_wsl() {
    [ -n "${WSL_DISTRO_NAME:-}" ] || grep -qi microsoft /proc/version 2>/dev/null
}

print_wsl_access_hint() {
    if ! is_wsl; then
        return
    fi

    local wsl_ip
    wsl_ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    if [ -z "$wsl_ip" ]; then
        return
    fi

    local frontend_port="${PORT_FRONTEND:-51209}"
    local agent_port="${PORT_AGENT:-51200}"
    echo "   WSL host frontend: http://$wsl_ip:$frontend_port"
    echo "   WSL host agent API: http://$wsl_ip:$agent_port"
    echo "   If Windows localhost forwarding does not work, open these WSL IP URLs from Windows."
}

case "${1:-help}" in

    start)
        if [ ! -f config/.env ]; then
            echo "❌ 未找到 config/.env，请先运行: $0 configure --init 并配置必要参数" >&2
            exit 1
        fi

        # 先停止旧实例（复用 stop 逻辑）
        if [ -f "$PIDFILE" ]; then
            OLD_PID=$(cat "$PIDFILE")
            if kill -0 "$OLD_PID" 2>/dev/null; then
                echo "🧹 发现旧实例 (PID: $OLD_PID)，先停止..."
                kill "$OLD_PID"
                for i in $(seq 1 30); do
                    if ! kill -0 "$OLD_PID" 2>/dev/null; then
                        break
                    fi
                    sleep 0.5
                done
                if kill -0 "$OLD_PID" 2>/dev/null; then
                    echo "⚠️  强制终止..."
                    kill -9 "$OLD_PID" 2>/dev/null || true
                    sleep 1
                fi
                echo "✅ 旧实例已停止"
            fi
            rm -f "$PIDFILE"
        fi

        echo "🚀 启动 Mini TimeBot (headless)..."
        export MINI_TIMEBOT_HEADLESS=1
        mkdir -p "$PROJECT_ROOT/logs"
        nohup python scripts/launcher.py > "$PROJECT_ROOT/logs/launcher.log" 2>&1 &
        LAUNCHER_PID=$!
        echo "$LAUNCHER_PID" > "$PIDFILE"
        echo "✅ Mini TimeBot 已在后台启动 (PID: $LAUNCHER_PID)"
        echo "   日志: $PROJECT_ROOT/logs/launcher.log"

        # 等待服务就绪
        source config/.env 2>/dev/null || true
        AGENT_PORT=${PORT_AGENT:-51200}
        echo -n "   等待服务就绪"
        for i in $(seq 1 30); do
            if curl -sf "http://127.0.0.1:$AGENT_PORT/v1/models" > /dev/null 2>&1; then
                echo " ✅"
                print_wsl_access_hint
                exit 0
            fi
            echo -n "."
            sleep 2
        done
        echo ""
        echo "⚠️  服务可能仍在启动中，请查看日志确认"
        exit 0
        ;;

    stop)
        if [ -f "$PIDFILE" ]; then
            PID=$(cat "$PIDFILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "正在停止 Mini TimeBot (PID: $PID)..."
                kill "$PID"
                for i in $(seq 1 30); do
                    if ! kill -0 "$PID" 2>/dev/null; then
                        break
                    fi
                    sleep 0.5
                done
                if kill -0 "$PID" 2>/dev/null; then
                    echo "⚠️  强制终止..."
                    kill -9 "$PID" 2>/dev/null
                fi
                echo "✅ 已停止"
            else
                echo "进程已不存在"
            fi
            rm -f "$PIDFILE"
        else
            echo "未找到 PID 文件，服务可能未运行"
        fi
        exit 0
        ;;

    status)
        if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
            PID=$(cat "$PIDFILE")
            echo "✅ Mini TimeBot 正在运行 (PID: $PID)"
            source config/.env 2>/dev/null || true
            for port in ${PORT_AGENT:-51200} ${PORT_SCHEDULER:-51201} ${PORT_OASIS:-51202} ${PORT_FRONTEND:-51209}; do
                if ss -tlnp 2>/dev/null | grep -q ":${port} " || netstat -tlnp 2>/dev/null | grep -q ":${port} "; then
                    echo "  ✅ 端口 $port 已监听"
                else
                    echo "  ⚠️  端口 $port 未监听"
                fi
            done
            print_wsl_access_hint
            exit 0
        else
            echo "❌ Mini TimeBot 未运行"
            exit 1
        fi
        ;;

    setup)
        echo "=== 环境配置 ==="
        bash scripts/setup_env.sh
        echo "=== 环境配置完成 ==="
        ;;

    add-user)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "用法: $0 add-user <username> <password>" >&2
            exit 1
        fi
        python selfskill/scripts/adduser.py "$2" "$3"
        exit 0
        ;;

    configure)
        shift
        python selfskill/scripts/configure.py "$@"
        exit 0
        ;;

    auto-model)
        # 查询 API 可用模型列表（打印供 agent 选择，不自动写入）
        python selfskill/scripts/configure.py --auto-model
        exit 0
        ;;

    cli)
        # CLI 控制工具：像操作前端一样控制 Agent
        shift
        python scripts/cli.py "$@"
        exit $?
        ;;

    check-openclaw)
        echo "=== OpenClaw 检测 ==="

        # 1. 检测 openclaw 是否已安装
        if command -v openclaw &>/dev/null; then
            OC_VERSION=$(openclaw --version 2>/dev/null | head -1 || echo "unknown")
            echo "✅ OpenClaw 已安装: $OC_VERSION"
            OC_BIN=$(which openclaw)
            echo "   路径: $OC_BIN"

            # 自动探测并配置 + 初始化 workspace 模板
            echo ""
            echo "🔍 自动探测 OpenClaw 配置..."
            python selfskill/scripts/configure_openclaw.py --auto-detect
            echo ""
            echo "=== OpenClaw 检测完成 ==="
            exit 0
        fi

        # 2. OpenClaw 未安装
        echo "⚠️  OpenClaw 未安装"
        echo ""
        echo "OpenClaw 是一个本地 AI 助手，TeamClaw 可以通过它进行可视化工作流编排。"
        echo "安装 OpenClaw 需要："
        echo "  - Node.js ≥ 22"
        echo "  - npm install -g openclaw@latest"
        echo "  - openclaw onboard --install-daemon"
        echo ""

        # 3. 检测 Node.js
        if command -v node &>/dev/null; then
            NODE_VER=$(node --version 2>/dev/null)
            NODE_MAJOR=$(echo "$NODE_VER" | sed 's/^v//' | cut -d. -f1)
            echo "📦 Node.js 版本: $NODE_VER"
            if [ "$NODE_MAJOR" -lt 22 ] 2>/dev/null; then
                echo "❌ Node.js 版本过低（需要 ≥ 22），请先升级 Node.js"
                echo "   推荐: nvm install 22 && nvm use 22"
                echo ""
                echo "=== OpenClaw 检测完成（需先升级 Node.js）==="
                exit 1
            fi
            echo "✅ Node.js 版本满足要求"
        else
            echo "❌ Node.js 未安装（OpenClaw 需要 Node.js ≥ 22）"
            echo "   推荐安装方式："
            echo "   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"
            echo "   nvm install 22 && nvm use 22"
            echo ""
            echo "=== OpenClaw 检测完成（需先安装 Node.js）==="
            exit 1
        fi

        echo ""
        echo "🔧 准备安装 OpenClaw..."
        echo "   将执行: npm install -g openclaw@latest --ignore-scripts"
        echo "   （--ignore-scripts 避免 node-llama-cpp 因缺少 cmake 编译失败）"
        echo ""

        # 4. 询问用户确认（非交互模式跳过）
        if [ "${OPENCLAW_AUTO_INSTALL:-}" = "1" ]; then
            echo "📌 自动安装模式（OPENCLAW_AUTO_INSTALL=1）"
            REPLY="y"
        else
            read -r -p "是否现在安装 OpenClaw？[y/N] " REPLY
        fi

        case "$REPLY" in
            [yY]|[yY][eE][sS])
                echo ""
                echo "📥 正在安装 OpenClaw..."
                if npm install -g openclaw@latest --ignore-scripts; then
                    echo "✅ OpenClaw 安装成功"

                    # 确保 npm 全局 bin 在 PATH 中
                    NPM_BIN=$(npm bin -g 2>/dev/null || echo "")
                    if [ -z "$NPM_BIN" ]; then
                        NPM_BIN="$(npm prefix -g 2>/dev/null)/bin"
                    fi
                    if [ -n "$NPM_BIN" ] && [ -d "$NPM_BIN" ]; then
                        case ":$PATH:" in
                            *":$NPM_BIN:"*) ;;
                            *)
                                export PATH="$NPM_BIN:$PATH"
                                echo "📌 已将 npm 全局 bin 路径添加到 PATH: $NPM_BIN"
                                ;;
                        esac
                    fi

                    OC_VERSION=$(openclaw --version 2>/dev/null | head -1 || echo "unknown")
                    if [ "$OC_VERSION" = "unknown" ] && [ -n "$NPM_BIN" ]; then
                        OC_VERSION=$("$NPM_BIN/openclaw" --version 2>/dev/null | head -1 || echo "unknown")
                    fi
                    echo "   版本: $OC_VERSION"

                    # 初始化 workspace 默认模板
                    echo ""
                    echo "🏠 初始化 OpenClaw workspace 默认模板..."
                    python selfskill/scripts/configure_openclaw.py --init-workspace

                    echo ""
                    echo "📋 下一步：运行 OpenClaw 初始化向导"
                    echo "   openclaw onboard --install-daemon"
                    echo ""
                    echo "   向导完成后，再次运行此命令以自动配置 TeamClaw 集成："
                    echo "   bash selfskill/scripts/run.sh check-openclaw"
                else
                    echo "❌ OpenClaw 安装失败，请检查 npm 和网络状态"
                    exit 1
                fi
                ;;
            *)
                echo "⏭️  跳过 OpenClaw 安装"
                echo "   TeamClaw 仍可正常使用（无法使用 OpenClaw 可视化编排功能）"
                echo "   稍后可随时运行: bash selfskill/scripts/run.sh check-openclaw"
                ;;
        esac

        echo ""
        echo "=== OpenClaw 检测完成 ==="
        exit 0
        ;;

    start-tunnel)
        # 启动 Cloudflare Tunnel（自动下载 cloudflared + 暴露前端到公网）
        TUNNEL_PIDFILE="$PROJECT_ROOT/.tunnel.pid"
        if [ -f "$TUNNEL_PIDFILE" ] && kill -0 "$(cat "$TUNNEL_PIDFILE")" 2>/dev/null; then
            echo "⚠️  Tunnel 已在运行 (PID: $(cat "$TUNNEL_PIDFILE"))"
            # 读取当前 PUBLIC_DOMAIN
            source config/.env 2>/dev/null || true
            if [ -n "$PUBLIC_DOMAIN" ] && [ "$PUBLIC_DOMAIN" != "wait to set" ]; then
                echo "🌍 公网地址: $PUBLIC_DOMAIN"
            fi
            exit 0
        fi

        echo "🌐 正在启动 Cloudflare Tunnel..."
        mkdir -p "$PROJECT_ROOT/logs"
        nohup python scripts/tunnel.py > "$PROJECT_ROOT/logs/tunnel.log" 2>&1 &
        TUNNEL_PID=$!
        echo "$TUNNEL_PID" > "$TUNNEL_PIDFILE"

        # 等待公网地址就绪（最多 60 秒）
        echo -n "   等待公网地址"
        for i in $(seq 1 30); do
            source config/.env 2>/dev/null || true
            if [ -n "$PUBLIC_DOMAIN" ] && [ "$PUBLIC_DOMAIN" != "wait to set" ] && echo "$PUBLIC_DOMAIN" | grep -q "trycloudflare.com"; then
                echo " ✅"
                echo "🌍 公网地址: $PUBLIC_DOMAIN"
                exit 0
            fi
            echo -n "."
            sleep 2
        done
        echo ""
        echo "⚠️  Tunnel 可能仍在启动中，请查看日志: $PROJECT_ROOT/logs/tunnel.log"
        exit 0
        ;;

    stop-tunnel)
        TUNNEL_PIDFILE="$PROJECT_ROOT/.tunnel.pid"
        if [ -f "$TUNNEL_PIDFILE" ]; then
            PID=$(cat "$TUNNEL_PIDFILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "正在停止 Tunnel (PID: $PID)..."
                kill "$PID"
                for i in $(seq 1 10); do
                    if ! kill -0 "$PID" 2>/dev/null; then
                        break
                    fi
                    sleep 0.5
                done
                if kill -0 "$PID" 2>/dev/null; then
                    kill -9 "$PID" 2>/dev/null
                fi
                echo "✅ Tunnel 已停止"
            else
                echo "Tunnel 进程已不存在"
            fi
            rm -f "$TUNNEL_PIDFILE"
        else
            echo "Tunnel 未运行"
        fi
        exit 0
        ;;

    tunnel-status)
        TUNNEL_PIDFILE="$PROJECT_ROOT/.tunnel.pid"
        if [ -f "$TUNNEL_PIDFILE" ] && kill -0 "$(cat "$TUNNEL_PIDFILE")" 2>/dev/null; then
            echo "✅ Tunnel 正在运行 (PID: $(cat "$TUNNEL_PIDFILE"))"
            source config/.env 2>/dev/null || true
            if [ -n "$PUBLIC_DOMAIN" ] && [ "$PUBLIC_DOMAIN" != "wait to set" ]; then
                echo "🌍 公网地址: $PUBLIC_DOMAIN"
            else
                echo "⏳ 公网地址尚未就绪"
            fi
        else
            echo "❌ Tunnel 未运行"
            rm -f "$TUNNEL_PIDFILE" 2>/dev/null
        fi
        exit 0
        ;;

    help|--help|-h)
        echo "Mini TimeBot Skill 入口"
        echo ""
        echo "用法: bash selfskill/scripts/run.sh <command> [args]"
        echo ""
        echo "命令:"
        echo "  start                          后台启动服务"
        echo "  stop                           停止服务"
        echo "  status                         检查服务状态"
        echo "  start-tunnel                   启动公网隧道（自动下载 cloudflared）"
        echo "  stop-tunnel                    停止公网隧道"
        echo "  tunnel-status                  查看隧道状态和公网地址"
        echo "  setup                          安装环境依赖（首次）"
        echo "  add-user <name> <password>     创建/更新用户"
        echo "  configure <KEY> <VALUE>        设置 .env 配置项"
        echo "  configure --batch K1=V1 K2=V2  批量设置配置"
        echo "  configure --show               查看当前配置"
        echo "  configure --init               从模板初始化 .env"
        echo "  auto-model                     查询 API 可用模型列表（供 agent 选择）"
        echo "  check-openclaw                 检测/安装 OpenClaw 并自动配置集成"
        echo "  cli <command> [args]           命令行控制工具（chat/sessions/settings 等）"
        echo "  help                           显示此帮助"
        exit 0
        ;;

    *)
        echo "未知命令: $1" >&2
        echo "运行 '$0 help' 查看可用命令" >&2
        exit 1
        ;;
esac
