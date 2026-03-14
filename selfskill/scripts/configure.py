#!/usr/bin/env python3
"""
非交互式 .env 配置工具。供外部 agent 调用。

用法:
    python selfskill/scripts/configure.py <KEY> <VALUE>          # 设置单个配置项
    python selfskill/scripts/configure.py --show                 # 显示当前配置（隐藏敏感值）
    python selfskill/scripts/configure.py --show-raw             # 显示当前配置（含原始值）
    python selfskill/scripts/configure.py --init                 # 从 .env.example 初始化 .env（不覆盖已有）
    python selfskill/scripts/configure.py --batch K1=V1 K2=V2    # 批量设置
    python selfskill/scripts/configure.py --auto-model           # 查询 API 可用模型列表（供 agent 选择）

示例:
    python skill/scripts/configure.py LLM_API_KEY sk-xxxx
    python skill/scripts/configure.py LLM_BASE_URL https://api.deepseek.com
    python skill/scripts/configure.py LLM_MODEL deepseek-chat
    python skill/scripts/configure.py --batch LLM_API_KEY=sk-xxx LLM_BASE_URL=https://api.deepseek.com LLM_MODEL=deepseek-chat
    python skill/scripts/configure.py --auto-model
"""
import os
import re
import subprocess
import sys
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(PROJECT_ROOT, "config", ".env")
ENV_EXAMPLE = os.path.join(PROJECT_ROOT, "config", ".env.example")

SENSITIVE_KEYS = {"LLM_API_KEY", "INTERNAL_TOKEN", "TELEGRAM_BOT_TOKEN", "QQ_BOT_SECRET"}

# 合法的环境变量key列表（基于SKILL.md文档）
VALID_KEYS = {
    # LLM配置
    "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_PROVIDER", "LLM_VISION_SUPPORT",
    # 端口配置
    "PORT_AGENT", "PORT_SCHEDULER", "PORT_OASIS", "PORT_FRONTEND",
    # TTS配置
    "TTS_MODEL", "TTS_VOICE",
    # OpenClaw配置
    "OPENCLAW_API_URL", "OPENCLAW_GATEWAY_TOKEN", "OPENCLAW_SESSIONS_FILE",
    # 内部配置
    "INTERNAL_TOKEN", "OPENAI_STANDARD_MODE",
    # 命令执行配置
    "ALLOWED_COMMANDS", "EXEC_TIMEOUT", "MAX_OUTPUT_LENGTH",
    # 服务配置
    "OASIS_BASE_URL", "PUBLIC_DOMAIN",
    # 聊天机器人配置
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USERS", "QQ_APP_ID", "QQ_BOT_SECRET", 
    "QQ_BOT_USERNAME", "AI_MODEL_TG", "AI_MODEL_QQ", "AI_API_URL"
}


def validate_key(key):
    """验证key是否合法"""
    if key not in VALID_KEYS:
        print(f"❌ 错误: '{key}' 不是合法的配置项")
        print(f"   支持的配置项: {', '.join(sorted(VALID_KEYS))}")
        return False
    return True


def read_env():
    """读取 .env 为 (行列表, {key: value} 字典)"""
    if not os.path.exists(ENV_PATH):
        return [], {}
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    kvs = {}
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, v = s.split("=", 1)
            kvs[k.strip()] = v.strip()
    return lines, kvs


def set_env_with_validation(key, value):
    """设置单个 key=value，包含合法性检查和详细回显"""
    # 验证key合法性
    if not validate_key(key):
        return False
    
    # 设置环境变量
    lines, _ = read_env()
    key_found = False
    new_lines = []
    for line in lines:
        s = line.strip()
        if s.startswith(f"{key}=") or s.startswith(f"# {key}="):
            new_lines.append(f"{key}={value}\n")
            key_found = True
        else:
            new_lines.append(line)
    if not key_found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"{key}={value}\n")
    
    os.makedirs(os.path.dirname(ENV_PATH), exist_ok=True)
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    # 详细回显设置内容
    display_value = value[:4] + "****" + value[-4:] if key in SENSITIVE_KEYS and len(value) > 8 else value
    print(f"✅ {key}={display_value} 已设置")
    print(f"📁 配置文件: {ENV_PATH}")
    
    return True


def set_env(key, value):
    """设置单个 key=value，如果 key 已存在则更新，否则追加（兼容旧版本）"""
    return set_env_with_validation(key, value)


def show_env(raw=False):
    """显示当前配置，包含详细回显"""
    _, kvs = read_env()
    if not kvs:
        print("⚠️  config/.env 不存在或为空")
        return
    
    print(f"📁 配置文件: {ENV_PATH}")
    print(f"📊 当前配置项数量: {len(kvs)}")
    print("=" * 60)
    
    for k, v in kvs.items():
        # 验证key的合法性
        is_valid = k in VALID_KEYS
        validity_indicator = "✅" if is_valid else "⚠️"
        
        if not raw and k in SENSITIVE_KEYS and v:
            display = v[:4] + "****" + v[-4:] if len(v) > 8 else "****"
        else:
            display = v
        
        print(f"{validity_indicator} {k}={display}")
        if not is_valid:
            print(f"   ⚠️ 注意: '{k}' 不是标准配置项，请检查拼写")
    
    print("=" * 60)
    print(f"💡 提示: 使用 '--show-raw' 查看原始值（包含敏感信息）")


_DEFAULT_ENV_TEMPLATE = """\
# === LLM API 配置（支持 DeepSeek / OpenAI / Gemini / Claude 等多厂商）===
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
# LLM_PROVIDER: 可选，显式指定模型厂商（google / anthropic / deepseek / openai）
# 不设置时根据模型名自动推断（gemini→google, claude→anthropic, deepseek→deepseek），
# 推断失败则 fallback 到 openai 兼容格式
# LLM_PROVIDER=
# 是否支持图片识别（vision），可选，不设置时根据模型名自动推断：
#   gpt-4o/gpt-5/o1/o3/o4/gemini/claude → 自动开启
#   deepseek/qwen/glm 等 → 自动关闭
# 如需强制覆盖，显式设为 true 或 false
# LLM_VISION_SUPPORT=

# === TTS 文本转语音配置（可选，使用与 LLM 相同的 API 代理）===
# TTS_MODEL=gemini-2.5-flash-preview-tts
# TTS_VOICE=charon

# === 前端与 Agent 通信模式 ===
# true: 前端使用 OpenAI 标准 /v1/chat/completions 格式与 agent 交互
# false: 使用自定义 WebSocket 协议（默认）
OPENAI_STANDARD_MODE=false

# === 端口配置（可选，以下为默认值，一般无需修改）===
PORT_SCHEDULER=51201
PORT_AGENT=51200
PORT_FRONTEND=51209

# === 指令执行模块配置（可选，以下为默认值）===
# 命令白名单，逗号分隔。留空或不设置则使用内置默认白名单
# ALLOWED_COMMANDS=ls,cat,head,tail,wc,du,find,file,stat,grep,awk,sed,sort,uniq,cut,tr,diff,comm,echo,date,cal,whoami,uname,hostname,uptime,free,df,env,printenv,pwd,which,expr,seq,yes,true,false,base64,md5sum,sha256sum,xxd,python,python3,ping,curl,wget
# 命令执行超时（秒）
# EXEC_TIMEOUT=30
# 输出最大字符数
# MAX_OUTPUT_LENGTH=8000

# === OASIS 论坛服务配置（可选，以下为默认值）===
PORT_OASIS=51202
OASIS_BASE_URL=http://127.0.0.1:51202

# === 内部服务通信密钥（可选）===
# 保护 /system_trigger、/oasis/ask、/_internal/oasis_response 等内部端点
# 留空则 mainagent 首次启动时自动生成并写入 .env
# INTERNAL_TOKEN=

# === QQ Bot 配置 ===
QQ_APP_ID=your_qq_app_id
QQ_BOT_SECRET=your_qq_bot_secret
# QQ Bot 以哪个系统用户身份调用 Agent（默认 qquser）
QQ_BOT_USERNAME=qquser

# === Telegram Bot 配置 ===
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# === Chatbot 通用配置 ===
# TG/QQ Bot 通过 INTERNAL_TOKEN + 白名单中的用户名以用户身份调用 Agent
AI_API_URL=http://127.0.0.1:51200/v1/chat/completions
AI_MODEL_QQ=gemini-3-flash-preview
AI_MODEL_TG=gemini-2.0-flash

# === OpenClaw 集成配置（默认自动探测，也可手动覆盖）===
# OPENCLAW_API_URL: 默认通过 openclaw config get gateway.port 自动探测
# 如需手动指定，取消注释并填写完整地址（含 /v1/chat/completions）
# OPENCLAW_API_URL=http://127.0.0.1:23001/v1/chat/completions
# OPENCLAW_GATEWAY_TOKEN: 自动探测，不在前端暴露
# 注：Agents 通过 openclaw agents list CLI 实时获取
"""


# def _enable_openclaw_chat_completions():
#     """确保 OpenClaw 的 ChatCompletions 端点已开启"""
#     # 不再需要：OpenClaw agent 现已优先使用 CLI 调用，无需开启 OpenAI 兼容端口
#     try:
#         result = subprocess.run(
#             ["openclaw", "config", "set",
#              "gateway.http.endpoints.chatCompletions.enabled", "true"],
#             capture_output=True, text=True, timeout=10
#         )
#         if result.returncode == 0:
#             print("✅ OpenClaw ChatCompletions 端点已开启")
#         else:
#             print(f"⚠️  开启 ChatCompletions 端点失败: {result.stderr.strip()}")
#     except FileNotFoundError:
#         pass  # openclaw 不存在，后续 detect 会统一报错
#     except subprocess.TimeoutExpired:
#         print("⚠️  openclaw config set 命令超时")
#     except Exception as e:
#         print(f"⚠️  开启 ChatCompletions 端点失败: {e}")


import json
import urllib.request
import urllib.error

def auto_detect_model():
    """查询 API 可用模型列表并打印，供 AI agent 阅读后自行选择。

    流程:
    1. 从 .env 读取 LLM_API_KEY 和 LLM_BASE_URL
    2. 调用 /v1/models 端点获取可用模型列表
    3. 打印全部可用模型（不做自动选择）
    4. 由调用方（AI agent）阅读输出，决定使用哪个模型，
       再通过 configure LLM_MODEL <model> 设置

    返回: list[str]  可用模型 ID 列表
    """
    _, kvs = read_env()

    api_key = kvs.get("LLM_API_KEY", "").strip()
    base_url = kvs.get("LLM_BASE_URL", "").strip()

    if not api_key or api_key == "your_api_key_here":
        print("❌ LLM_API_KEY 未设置，无法检测模型")
        print("   请先设置: bash selfskill/scripts/run.sh configure LLM_API_KEY <your-key>")
        return []

    if not base_url:
        print("❌ LLM_BASE_URL 未设置，无法检测模型")
        print("   请先设置: bash selfskill/scripts/run.sh configure LLM_BASE_URL <url>")
        return []

    # 构建 /v1/models URL
    models_url = base_url.rstrip("/")
    if not models_url.endswith("/v1"):
        models_url += "/v1"
    models_url += "/models"

    print(f"🔍 正在检测可用模型...")
    print(f"   API: {base_url}")
    print(f"   请求: GET {models_url}")

    # 调用 /v1/models
    req = urllib.request.Request(
        models_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode()[:300]
        except Exception:
            pass
        print(f"❌ API 返回错误 {e.code}: {err_body}")
        if e.code == 401:
            print("   → API Key 无效，请检查 LLM_API_KEY")
        elif e.code == 404:
            print("   → /v1/models 端点不存在，该 API 可能不支持模型列表查询")
            print("   → 请手动指定: bash selfskill/scripts/run.sh configure LLM_MODEL <model-name>")
        return []
    except urllib.error.URLError as e:
        print(f"❌ 无法连接到 API: {e.reason}")
        print(f"   → 请检查 LLM_BASE_URL 是否正确: {base_url}")
        return []
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return []

    # 解析模型列表
    models_data = body.get("data", [])
    if not models_data:
        print("⚠️ API 返回了空的模型列表")
        return []

    # 提取模型 ID，过滤特殊/内部模型
    all_ids = []
    for m in models_data:
        mid = m.get("id", "")
        if mid and not mid.startswith("ft:") and not mid.startswith("dall-e"):
            all_ids.append(mid)

    all_ids.sort()

    if not all_ids:
        print("⚠️ 没有找到可用的模型")
        return []

    print(f"\n📋 API 可用模型 ({len(all_ids)} 个):")
    for mid in all_ids:
        print(f"   • {mid}")

    print(f"\n💡 请从以上列表中选择一个模型，然后执行：")
    print(f"   bash selfskill/scripts/run.sh configure LLM_MODEL <模型名>")

    return all_ids


def detect_openclaw_api_url():
    """通过 gateway.port 自动探测 OPENCLAW_API_URL"""
    try:
        result = subprocess.run(
            ["openclaw", "config", "get", "gateway.port"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            # 从输出中提取纯数字端口号（跳过 banner 行）
            for line in result.stdout.strip().splitlines():
                port = line.strip()
                if port.isdigit():
                    url = f"http://127.0.0.1:{port}/v1/chat/completions"
                    print(f"🔍 自动探测到 OpenClaw gateway 端口: {port}")
                    print(f"✅ OPENCLAW_API_URL={url}")
                    return url
    except FileNotFoundError:
        print("⚠️  openclaw 命令未找到，跳过 OPENCLAW_API_URL 自动探测")
    except subprocess.TimeoutExpired:
        print("⚠️  openclaw 命令超时，跳过 OPENCLAW_API_URL 自动探测")
    except Exception as e:
        print(f"⚠️  探测 OpenClaw 端口失败: {e}")
    return None





def init_env():
    """从 .env.example 初始化 .env（不覆盖已有）；若模板不存在则使用内置默认值"""
    if os.path.exists(ENV_PATH):
        print(f"✅ config/.env 已存在，跳过初始化")
        return
    os.makedirs(os.path.dirname(ENV_PATH), exist_ok=True)
    if os.path.exists(ENV_EXAMPLE):
        shutil.copy2(ENV_EXAMPLE, ENV_PATH)
        print(f"✅ 已从 .env.example 初始化 config/.env")
    else:
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write(_DEFAULT_ENV_TEMPLATE)
        print(f"✅ 已使用内置默认模板初始化 config/.env")
    print(f"⚠️  请编辑 {ENV_PATH} 填入 LLM_API_KEY 等必要参数")


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "--show":
        show_env(raw=False)
    elif cmd == "--show-raw":
        show_env(raw=True)
    elif cmd == "--init":
        init_env()
    elif cmd == "--auto-model":
        print("🔍 查询 API 可用模型列表...")
        print("=" * 60)
        all_models = auto_detect_model()
        print("=" * 60)
        if all_models:
            print(f"\n📋 共发现 {len(all_models)} 个可用模型")
            print(f"💡 请选择一个模型并执行:")
            print(f"   bash selfskill/scripts/run.sh configure LLM_MODEL <模型名>")
        else:
            print("\n❌ 未能获取模型列表，请检查 API 配置")
            sys.exit(1)
    elif cmd == "--batch":
        if len(sys.argv) < 3:
            print("用法: configure.py --batch KEY1=VAL1 KEY2=VAL2 ...", file=sys.stderr)
            sys.exit(1)
        
        print("🔧 批量配置开始...")
        print(f"📁 配置文件: {ENV_PATH}")
        print("-" * 60)
        
        success_count = 0
        total_count = len(sys.argv[2:])
        
        for arg in sys.argv[2:]:
            if "=" not in arg:
                print(f"❌ 跳过无效参数: {arg}", file=sys.stderr)
                continue
            k, v = arg.split("=", 1)
            k = k.strip()
            v = v.strip()
            
            if set_env_with_validation(k, v):
                success_count += 1
        
        print("-" * 60)
        print(f"📊 批量配置完成: {success_count}/{total_count} 项成功设置")
        if success_count < total_count:
            print(f"⚠️  有 {total_count - success_count} 项配置失败，请检查key名称是否正确")
    else:
        # 单个 KEY VALUE
        if len(sys.argv) != 3:
            print("用法: configure.py <KEY> <VALUE>", file=sys.stderr)
            sys.exit(1)
        
        key = sys.argv[1]
        value = sys.argv[2]
        
        print("🔧 单个配置开始...")
        print(f"📁 配置文件: {ENV_PATH}")
        print("-" * 60)
        
        if set_env_with_validation(key, value):
            print("-" * 60)
            print("✅ 配置完成")
        else:
            print("-" * 60)
            print("❌ 配置失败，请检查key名称是否正确")
            sys.exit(1)


if __name__ == "__main__":
    main()
