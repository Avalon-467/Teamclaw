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

## What Is TeamClaw

TeamClaw is a **multi-agent orchestration platform**. Core concepts:

### Team

A Team is the unit of collaboration, composed of:

| Component | Description |
|-----------|-------------|
| **Members (Agents)** | Task-executing entities, including: |
| └─ Built-in Agent | TeamClaw's lightweight agents (file management, command execution, social media) |
| └─ OpenClaw Agent | Agents from the external OpenClaw platform |
| └─ External API Agent | Any external API service (e.g. GPT-4 API) |
| **Custom Expert** | A persona defined via prompt — identity, personality, capabilities |
| **Workflow** | Defines how members collaborate (sequential, parallel, conditional, loop) |

> **Public vs Private**:
> - **Public Agent/Expert**: Available outside any team; can be added to a team for use within it
> - **Private Agent/Expert**: Only available within the current team
> - **Public Workflow**: Can only use public Agents/Experts
> - **Private Workflow**: Only available within the current team; can only use agents already added to the team

### Core Capabilities

1. **Visual Agent Orchestration**
   - Compose OpenClaw Agents, built-in Agents, or any external API Agent into a "Team"
   - Drag-and-drop experts on the Web UI canvas (OASIS), configure collaboration relationships
   - **Expert**: A persona — a special prompt that defines an Agent's role and capabilities
   - **Agent**: An entity with tools, skills, and prompts that can execute concrete tasks
   - **OpenClaw Agent**: Configurable with custom tools, skills, and prompts via OpenClaw

2. **Team Workflows**
   - Multi-agent parallel discussion/execution with aggregated conclusions
   - **State-graph orchestration**: Sequential, parallel, conditional, loop

3. **Portable Sharing**
   - Export team configurations as a compressed archive for one-click sharing
   - Import shared team configurations for quick reuse

### Built-in Lightweight Agents

TeamClaw includes **lightweight agents** (a streamlined version of OpenClaw):

| Capability | Description |
|------------|-------------|
| **File Management** | Read, write, search files |
| **Command Execution** | Execute shell commands |
| **Social Media** | Communicate with Telegram/QQ users |

- **Lighter weight**: Simpler prompts and a more focused toolset compared to OpenClaw
- **Quick start**: Works out of the box without installing OpenClaw
- **Extensible**: Custom tools and skills can be added

### Feature Overview

| Feature | Description |
|---------|-------------|
| **Team Chat** | Multi-expert parallel discussion/execution, supports 4 expert types |
| **OASIS Workflow** | Visual canvas orchestration, drives parallel agent teams |
| **Scheduled Tasks** | APScheduler-based task scheduling center |
| **Web UI** | Full chat interface with passwordless login via 127.0.0.1 |
| **Bot Integration** | Telegram / QQ Bot (optional) |
| **Public Access** | Cloudflare Tunnel (only when user explicitly requests) |

---

## Purpose

Use this skill to install, configure, and run TeamClaw locally.

For non-install background material, see:

- [docs/windows.md](./docs/windows.md)
- [docs/cli.md](./docs/cli.md)
- [docs/overview.md](./docs/overview.md)

## Agent Rules

1. Install and configure TeamClaw first. Do not spend time on unrelated feature explanations unless the user asks.
2. Ask for `LLM_API_KEY` and `LLM_BASE_URL` before starting services if they are not already configured.
3. Do not create a password user unless the user explicitly wants password-based login.
4. Do not install or configure OpenClaw unless the user explicitly asks for it.
5. Do not start Cloudflare Tunnel unless the user explicitly asks for public access.
6. On Windows, prefer the PowerShell flow. Use WSL only if the user prefers it or native Windows tooling is unsuitable.
7. If the user did not specify `LLM_MODEL`, do not auto-select and do not ask the user to choose one first.
8. When `LLM_MODEL` is missing, print all available models only, let the caller or agent read the output and decide, then run `configure LLM_MODEL <model>`.

## Quick Start

```bash
# 1. Install dependencies
bash selfskill/scripts/run.sh setup

# 2. Initialize configuration
bash selfskill/scripts/run.sh configure --init

# 3. Configure LLM (required)
bash selfskill/scripts/run.sh configure --batch \
  LLM_API_KEY=sk-xxx \
  LLM_BASE_URL=https://api.deepseek.com \
  LLM_MODEL=deepseek-chat

# 4. Start services
bash selfskill/scripts/run.sh start
```

**After startup, visit**: `http://127.0.0.1:51209`

## Standard Install Flow

### Linux / macOS

```bash
bash selfskill/scripts/run.sh setup
bash selfskill/scripts/run.sh configure --init

# If the user already specified a model:
bash selfskill/scripts/run.sh configure --batch \
  LLM_API_KEY=sk-xxx \
  LLM_BASE_URL=https://api.deepseek.com \
  LLM_MODEL=deepseek-chat

# If the user did not specify a model:
bash selfskill/scripts/run.sh configure LLM_API_KEY sk-xxx
bash selfskill/scripts/run.sh configure LLM_BASE_URL https://api.deepseek.com
bash selfskill/scripts/run.sh auto-model
# Print all available models only. Do not auto-select.
# The caller or agent reads the output, chooses one model,
# then runs:
bash selfskill/scripts/run.sh configure LLM_MODEL <model>

bash selfskill/scripts/run.sh start
```

### Windows PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 setup
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 configure --init

# If the user already specified a model:
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 configure --batch LLM_API_KEY=sk-xxx LLM_BASE_URL=https://api.deepseek.com LLM_MODEL=deepseek-chat

# If the user did not specify a model:
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 configure LLM_API_KEY sk-xxx
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 configure LLM_BASE_URL https://api.deepseek.com
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 auto-model
# Print all available models only. Do not auto-select.
# The caller or agent reads the output, chooses one model,
# then runs:
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 configure LLM_MODEL <model>

powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 start
```

### Windows WSL Fallback

If the user wants to reuse the shell scripts directly, follow [docs/windows.md](./docs/windows.md) and use the Linux or macOS commands inside WSL.

## User Accounts

### Passwordless Login (Default, recommended for first run)

- No need to run `add-user`
- Ask the user for a username, or they can use the default `admin` — "Set your identity for commanding the agent team"
- Access Web UI via **127.0.0.1** → automatic passwordless login
- Password login is unavailable in this mode

### Password Login (Optional)

```bash
bash selfskill/scripts/run.sh add-user <username> <password>
```

> ⚠️ Always ask the user for their desired username and password before running this command.

## Required Configuration

These keys are required before first start:

| Key | Purpose | Default |
|---|---|---|
| `LLM_API_KEY` | Provider API key | - |
| `LLM_BASE_URL` | OpenAI-compatible base URL | `https://api.deepseek.com` |
| `LLM_MODEL` | Model name | `deepseek-chat` |

When `LLM_MODEL` is not given by the user:

1. Configure `LLM_API_KEY`
2. Configure `LLM_BASE_URL`
3. Run `auto-model`
4. Print the available model list only
5. Let the caller or agent choose one model from the output
6. Run `configure LLM_MODEL <model>`

### Optional Configuration (configure as needed)

After asking the user "Do you need advanced settings?", configure on demand:

| Variable | Description | Default |
|----------|-------------|---------|
| **TTS Voice** | | |
| `TTS_MODEL` | TTS model | - |
| `TTS_VOICE` | TTS voice | - |
| **OpenClaw Integration** | | |
| `OPENCLAW_API_URL` | OpenClaw Gateway URL | Auto-detected |
| `OPENCLAW_GATEWAY_TOKEN` | OpenClaw auth token | Auto-detected |
| `OPENCLAW_SESSIONS_FILE` | OpenClaw sessions file path | Auto-detected |
| **Bot Integration** | | |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | - |
| `TELEGRAM_ALLOWED_USERS` | Telegram whitelisted user IDs | - |
| `QQ_APP_ID` | QQ Bot App ID | - |
| `QQ_BOT_SECRET` | QQ Bot Secret | - |
| `QQ_BOT_USERNAME` | QQ Bot username | - |
| `AI_MODEL_TG` | Model used by Telegram Bot | `LLM_MODEL` |
| `AI_MODEL_QQ` | Model used by QQ Bot | `LLM_MODEL` |
| `AI_API_URL` | AI API URL for bots | `LLM_BASE_URL` |
| **Advanced** | | |
| `PORT_AGENT` | Agent main service port | `51200` |
| `PORT_SCHEDULER` | Scheduler port | `51201` |
| `PORT_OASIS` | OASIS workflow port | `51202` |
| `PORT_FRONTEND` | Web UI port | `51209` |
| `OPENAI_STANDARD_MODE` | OpenAI compatibility mode | `false` |

> Default value notes: "Auto-detected" means automatically configured when running commands like `check-openclaw`; "Auto-generated" means generated by the system on first start.

## Common Operations

### Linux / macOS

```bash
bash selfskill/scripts/run.sh status
bash selfskill/scripts/run.sh stop
bash selfskill/scripts/run.sh configure --show
bash selfskill/scripts/run.sh add-user <username> <password>
bash selfskill/scripts/run.sh auto-model
```

### Windows PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 status
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 stop
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 configure --show
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 add-user <username> <password>
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 auto-model
```

## Defaults and Notes

- Default local Web UI: `http://127.0.0.1:51209`
- Local `127.0.0.1` access supports passwordless login
- Password users are optional
- OpenClaw, bots, and tunnel setup are optional and should be user-driven

---

## API Overview

**Base URL**: `http://127.0.0.1:51200`

```bash
# Chat endpoint (OpenAI-compatible)
curl -X POST http://127.0.0.1:51200/v1/chat/completions \
  -H "Authorization: Bearer <username>:<password>" \
  -d '{"model":"teambot","messages":[{"role":"user","content":"Hello"}],"stream":false}'
```

---

## Optional Commands

### OpenClaw

```bash
bash selfskill/scripts/run.sh check-openclaw
```

```powershell
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 check-openclaw
```

**Configuring OpenClaw Agent in OASIS Canvas:**
- Drag an OpenClaw expert onto the canvas
- Model format: `agent:<agent_name>:<session_name>`
- Example: `agent:main:default`

### Tunnel

> ⚠️ Agent MUST NOT start the tunnel automatically. Only start when the user explicitly requests it.

```bash
bash selfskill/scripts/run.sh start-tunnel
bash selfskill/scripts/run.sh stop-tunnel
```

```powershell
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 start-tunnel
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 stop-tunnel
```

---

## Usage

Beyond the Web visual frontend, **users can also interact directly with the Agent using this Skill** by issuing operational commands.
The Agent should use CLI tools and strictly follow user instructions.
- Configure LLM, create users, start services
- Create and manage teams, orchestrate workflows
- Initiate discussions, execute tasks

Note: Prefer CLI tools over Web UI for agent operations.

### CLI Service Status Check

After starting services (or when troubleshooting), use the `status` command to quickly check all three core services:

```bash
uv run scripts/cli.py status
```

Example output:
```
📊 Service Status:

  ✅ Agent         :51200  OK
  ✅ OASIS         :51202  OK
  ✅ Frontend      :51209  OK
```

- **Agent** (`:51200`) — Chat engine, handles chat/sessions/tools
- **OASIS** (`:51202`) — Workflow engine, handles topics/experts/workflows
- **Frontend** (`:51209`) — Web UI frontend, provides visual interface

> If a service shows ❌ unreachable, try restarting with `bash selfskill/scripts/run.sh start`.

### List Teams

```bash
uv run scripts/cli.py -u <username> teams list
```

### View Full Team Info

Use `teams info` to aggregate and display all information for a team (members, experts, workflows, topics) in one shot:

```bash
uv run scripts/cli.py -u <username> teams info --team-name <team_name>
```

> This command does not map to a single API endpoint — it combines multiple API calls and formats the output.

> For the complete command reference, see [docs/cli.md](./docs/cli.md)
