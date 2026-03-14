---
name: "TeamClaw"
description: "A multi-agent orchestration platform with visual workflow (OASIS). Create and configure agents (OpenClaw/external API), orchestrate them into Teams, design workflows via visual canvas. Supports Team conversations, scheduled tasks, Telegram/QQ bots, and Cloudflare Tunnel for remote access."
user-invokable: true
compatibility:
  - "deepseek"
  - "openai"
  - "gemini"
  - "claude"
  - "anthropic"
  - "ollama"

argument-hint: "[REQUIRED] LLM_API_KEY, LLM_BASE_URL, LLM_MODEL. [OPTIONAL] TTS_MODEL/TTS_VOICE, OPENCLAW_*, TELEGRAM_BOT_TOKEN/QQ_APP_ID, PORT_*. [TUNNEL] PUBLIC_DOMAIN (user must explicitly request). Agent MUST NOT auto-download or start tunnel."

metadata:
  version: "1.0.2"
  github: "https://github.com/Avalon-467/Teamclaw"
  ports:
    agent: 51200
    scheduler: 51201
    oasis: 51202
    frontend: 51209
  auth_methods:
    - "user_password"
    - "internal_token"
    - "chatbot_whitelist"
  integrations:
    - "openclaw"
    - "telegram"
    - "qq"
    - "cloudflare_tunnel"
---

# TeamClaw

## 是什么

TeamClaw 是一个**多 Agent 编排平台**，核心能力：

1. **可视化编排团队 Agent**
   - 将 OpenClaw Agent、TeamClaw 内置 Agent 或任意外部 API Agent 编排为"团队"
   - 通过 Web UI 画布（OASIS）拖拽添加专家，设置协作关系
   - **Expert（专家）**：人设，是特殊的 prompt，定义 Agent 的角色和能力
   - **Agent（智能体）**：具有工具、技能和提示词的实体，可执行具体任务
   - **OpenClaw Agent**：可添加、配置可用工具、可用 Skill、提示词等
   
2. **团队工作流**
   - 多AGENT并行讨论/执行，汇总结论
   - **状态图编排**：支持串行、并行、选择、循环

3. **便携分享**
   - 将团队配置导出为压缩包，一键分享给他人
   - 导入他人分享的团队配置，快速复用

## 内置轻量级 Agent

TeamClaw 内置了**轻量级 Agent**（类似简化版 OpenClaw）：

| 能力 | 说明 |
|------|------|
| **文件管理** | 读取、写入、搜索文件 |
| **指令执行** | 执行 shell 命令 |
| **社交媒体** | 与 Telegram/QQ 用户沟通 |

- **更轻量**：相比 OpenClaw，prompt 更简洁、工具集更精简
- **快速启动**：无需安装 OpenClaw，开箱即用
- **可扩展**：可添加自定义工具和 Skill

| 功能 | 说明 |
|------|------|
| **Team 对话** | 多专家并行讨论/执行，支持 4 种专家类型 |
| **OASIS 工作流** | 可视化画布编排，支持驱动并行 AGENT TEAM|
| **定时任务** | APScheduler 任务调度中心 |
| **Web UI** | 完整聊天界面，支持 127.0.0.1 免密登录 |
| **Bot 集成** | Telegram / QQ Bot（可选配置） |
| **公网访问** | Cloudflare Tunnel（用户明确要求时启用） |

---

## 快速启动

```bash
# 1. 安装依赖
bash selfskill/scripts/run.sh setup

# 2. 初始化配置
bash selfskill/scripts/run.sh configure --init

# 3. 配置 LLM（必填）
bash selfskill/scripts/run.sh configure --batch \
  LLM_API_KEY=sk-xxx \
  LLM_BASE_URL=https://api.deepseek.com \
  LLM_MODEL=deepseek-chat

# 4. 启动服务
bash selfskill/scripts/run.sh start
```

**启动后访问**：`http://127.0.0.1:51209`

---

## 用户账号

### 免密登录（默认，首次运行推荐）

- 无需运行 `add-user`
- 询问用户设置用户名，或者用户可以使用默认 `admin`，"请设置您统领agent team的身份"
- 通过 **127.0.0.1** 访问 Web UI → 自动免密登录
- 密码登录不可用

### 密码登录（可选）

```bash
bash selfskill/scripts/run.sh add-user <用户名> <密码>
```

> ⚠️ 执行前必须先询问用户想要的用户名和密码

---

## 高权限功能

### 新建用户

```bash
bash selfskill/scripts/run.sh add-user <username> <password>
# 可创建多个用户
```

### OpenClaw 集成（可视化工作流）

```bash
# 检测/安装 OpenClaw
bash selfskill/scripts/run.sh check-openclaw

# 如果未安装，会提示安装（需要用户确认）
# 安装后自动配置 OPENCLAW_API_URL
```

**OASIS 画布中配置 OpenClaw Agent：**
- 拖拽 OpenClaw 专家到画布
- model 格式：`agent:<agent_name>:<session_name>`
- 示例：`agent:main:default`

### 配置管理

```bash
# 查看配置
bash selfskill/scripts/run.sh configure --show

# 修改配置
bash selfskill/scripts/run.sh configure <KEY> <VALUE>

# 批量设置
bash selfskill/scripts/run.sh configure --batch KEY1=val1 KEY2=val2
```

#### 必填配置

首次启动必须配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | LLM 服务商 API 密钥 | - |
| `LLM_BASE_URL` | LLM API 基础地址 | `https://api.deepseek.com` |
| `LLM_MODEL` | 模型名称（用户未指定时自动检测） | `deepseek-chat` |

#### 选填配置（需要时再配置）

Agent 询问用户"是否需要拓展设置"后，按需配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| **TTS 语音** | | |
| `TTS_MODEL` | TTS 模型 | - |
| `TTS_VOICE` | TTS 声音 | - |
| **OpenClaw 集成** | | |
| `OPENCLAW_API_URL` | OpenClaw Gateway 地址 | 自动探测 |
| `OPENCLAW_GATEWAY_TOKEN` | OpenClaw 认证令牌 | 自动探测 |
| `OPENCLAW_SESSIONS_FILE` | OpenClaw sessions 文件路径 | 自动探测 |
| **Bot 集成** | | |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | - |
| `TELEGRAM_ALLOWED_USERS` | Telegram 白名单用户 ID | - |
| `QQ_APP_ID` | QQ Bot App ID | - |
| `QQ_BOT_SECRET` | QQ Bot Secret | - |
| `QQ_BOT_USERNAME` | QQ Bot 用户名 | - |
| `AI_MODEL_TG` | Telegram Bot 使用的模型 | `LLM_MODEL` |
| `AI_MODEL_QQ` | QQ Bot 使用的模型 | `LLM_MODEL` |
| `AI_API_URL` | Bot 调用的 AI API 地址 | `LLM_BASE_URL` |
| **高级选项** | | |
| `PORT_AGENT` | Agent 主服务端口 | `51200` |
| `PORT_SCHEDULER` | 定时任务端口 | `51201` |
| `PORT_OASIS` | OASIS 工作流端口 | `51202` |
| `PORT_FRONTEND` | Web UI 端口 | `51209` |
| `OPENAI_STANDARD_MODE` | OpenAI 兼容模式 | `false` |

> 默认值说明："自动探测"表示运行 `check-openclaw` 等命令时自动配置；"自动生成"表示首次启动时系统生成。

### 启动/停止

```bash
bash selfskill/scripts/run.sh start     # 启动（后台）
bash selfskill/scripts/run.sh status    # 查看状态
bash selfskill/scripts/run.sh stop      # 停止
```

### 公网隧道（用户明确要求时）

```bash
bash selfskill/scripts/run.sh start-tunnel   # 启动隧道
bash selfskill/scripts/run.sh stop-tunnel    # 停止隧道
```

> ⚠️ Agent 禁止主动启动隧道，必须用户明确要求

---

## API 概览

**Base URL**: `http://127.0.0.1:51200`

```bash
# 对话接口（OpenAI 兼容）
curl -X POST http://127.0.0.1:51200/v1/chat/completions \
  -H "Authorization: Bearer <username>:<password>" \
  -d '{"model":"teambot","messages":[{"role":"user","content":"Hello"}],"stream":false}'
```

---

## 使用方式

除了 Web 可视化前端，**用户还可以直接与使用此 Skill 的 Agent 对话**，由 Agent 辅助和指导操作：
- 配置 LLM、创建用户、启动服务
- 创建和管理团队、编排工作流
- 发起讨论、执行任务

> 完整命令列表和细节请参考 [docs/cli.md](./docs/cli.md)

