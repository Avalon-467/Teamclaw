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

argument-hint: "[REQUIRED] LLM_API_KEY, LLM_BASE_URL. [MODEL] If LLM_MODEL is not provided, print all available models only, let the caller or agent decide, then run configure LLM_MODEL <model>. [OPTIONAL] TTS_MODEL/TTS_VOICE, STT_MODEL/WHISPER_MODEL, OPENCLAW_*, TELEGRAM_BOT_TOKEN/QQ_APP_ID, PORT_*. [TUNNEL] PUBLIC_DOMAIN only when the user explicitly asks for public access."

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
9. If the user wants OpenAI audio features, prefer `TTS_MODEL=gpt-4o-mini-tts`, `TTS_VOICE=alloy`, and `STT_MODEL=whisper-1` unless the user explicitly asks for different audio models.

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

If the user wants to reuse the existing shell scripts directly:

```powershell
wsl --install -d Ubuntu
```

This first step must be run in an elevated PowerShell window. If the current shell is not Administrator, WSL installation and Windows feature checks will fail.

Then inside WSL:

```bash
sudo apt update
sudo apt install -y curl git python3 python3-venv python3-pip rsync
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Prefer a Linux-side copy instead of running directly from /mnt/c.
# This avoids slower virtualenv behavior and shell-script CRLF issues.
mkdir -p ~/TeamClaw-wsl
rsync -a --delete \
  --exclude .git \
  --exclude .venv \
  --exclude logs \
  --exclude __pycache__ \
  /mnt/c/Users/<user>/Downloads/BorisGuo6.github.io/TeamClaw/ \
  ~/TeamClaw-wsl/

cd ~/TeamClaw-wsl
bash selfskill/scripts/run.sh setup
bash selfskill/scripts/run.sh configure --init
bash selfskill/scripts/run.sh start
```

If native Windows TeamClaw is already running on the same machine, keep WSL in a separate copy with its own `.env` and ports. Do not point both installs at the same writable working tree and expect shared runtime state.

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

## Optional Audio Configuration

These are optional, but they matter if the user expects voice input or read-aloud:

| Key | Purpose | Recommended for OpenAI |
|---|---|---|
| `TTS_MODEL` | Text-to-speech model | `gpt-4o-mini-tts` |
| `TTS_VOICE` | Voice preset for TTS | `alloy` |
| `STT_MODEL` | Speech-to-text model for voice input | `whisper-1` |

Notes:

- `Whisper` / `STT_MODEL` is for speech-to-text only. It does not power read-aloud.
- TeamClaw read-aloud uses the `/tts` path.
- TeamClaw voice input now tries speech-to-text first, then only falls back to raw multimodal audio if transcription is unavailable.

## Startup Expectations

After `start`, these four services should come up:

| Service | Port variable | Default port | Purpose |
|---|---|---|---|
| Agent | `PORT_AGENT` | `51200` | OpenAI-compatible API and core agent backend |
| Scheduler | `PORT_SCHEDULER` | `51201` | Scheduled task runner |
| OASIS | `PORT_OASIS` | `51202` | Workflow and discussion engine |
| Frontend | `PORT_FRONTEND` | `51209` | Web UI |

Useful checks:

- `bash selfskill/scripts/run.sh status`
- `powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 status`
- `GET http://127.0.0.1:<PORT_AGENT>/v1/models`
- Open the Web UI at `http://127.0.0.1:<PORT_FRONTEND>`

## Tested Installation Notes

These notes come from a full Windows installation that was verified locally.

- On some Windows machines, the default ports `51200`, `51201`, `51202`, and `51209` fall inside Windows excluded port ranges. The PowerShell entrypoints now auto-remap them to a safe set and write the new values into `config/.env`.
- Because of that remap, the correct local URL is always `http://127.0.0.1:<PORT_FRONTEND>`, not a hardcoded `http://127.0.0.1:51209`.
- On Windows, all PowerShell entrypoints and all MCP subprocesses must use `.venv\Scripts\python.exe`. Relying on the system `python` command or App Execution Alias can break startup.
- `scripts/start.ps1` should run headless. Otherwise `chatbot/setup.py` may block startup in non-interactive PowerShell runs.
- `gpt-5.4` has been tested successfully with `LLM_BASE_URL=https://api.openai.com/` and TeamClaw's `/v1/chat/completions` endpoint.
- OpenAI audio has also been tested successfully with `TTS_MODEL=gpt-4o-mini-tts`, `TTS_VOICE=alloy`, and `STT_MODEL=whisper-1`.
- `auto-model` is for discovery only. It should print the model list, and the caller or agent should pick one model explicitly afterward.
- If WSL is not already installed, the first WSL setup step requires Administrator privileges on Windows before the Linux-side TeamClaw install can be tested.
- For WSL installs, a Linux-side copy such as `~/TeamClaw-wsl` is more reliable than running from `/mnt/c/...`.
- If a WSL copy was created from an older Windows checkout and shell scripts fail with `$'\\r': command not found`, re-copy after the `.gitattributes` fix or convert the copied `*.sh` files to LF line endings.
- On some WSL setups, Windows host access to TeamClaw does not forward cleanly through `127.0.0.1`. When that happens, use the WSL VM IP shown by `status` or `start`, for example `http://172.x.x.x:51209`.
- On WSL IP access from Windows, the request is not treated as local `127.0.0.1`, so passwordless login does not apply. Create a password user first if the user needs to log in from Windows through the WSL IP.
- If native Windows TeamClaw and WSL TeamClaw run at the same time, they must use different copies and different ports.

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

- Default local Web UI is `http://127.0.0.1:51209`, but Windows may auto-switch it to another local port. Check `PORT_FRONTEND` in `config/.env` or run `status`.
- Local `127.0.0.1` access supports passwordless login.
- WSL IP access from Windows should usually use password login, not passwordless login.
- Password users are optional.
- OpenClaw, bots, and tunnel setup are optional and should be user-driven.
- The frontend is the only user-facing service that should normally be opened directly in a browser. The other ports are internal service endpoints unless the user is intentionally calling APIs.

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
