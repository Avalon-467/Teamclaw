---
name: "TeamClaw"
description: "A multi-agent orchestration platform with visual workflow (OASIS). Create and configure agents, wire them into Teams, and run local services with optional bot and tunnel integrations."
user-invokable: true
compatibility:
  - "deepseek"
  - "openai"
  - "gemini"
  - "claude"
  - "anthropic"
  - "ollama"

argument-hint: "[REQUIRED] LLM_API_KEY, LLM_BASE_URL. [MODEL] If LLM_MODEL is not provided, print all available models only, let the caller or agent decide, then run configure LLM_MODEL <model>. [OPTIONAL] TTS_MODEL/TTS_VOICE, OPENCLAW_*, TELEGRAM_BOT_TOKEN/QQ_APP_ID, PORT_*. [TUNNEL] PUBLIC_DOMAIN only when the user explicitly asks for public access."

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

## Tested Installation Notes

These notes come from a full Windows installation that was verified locally.

- On some Windows machines, the default ports `51200`, `51201`, `51202`, and `51209` fall inside Windows excluded port ranges. The PowerShell entrypoints now auto-remap them to a safe set and write the new values into `config/.env`.
- Because of that remap, the correct local URL is always `http://127.0.0.1:<PORT_FRONTEND>`, not a hardcoded `http://127.0.0.1:51209`.
- On Windows, all PowerShell entrypoints and all MCP subprocesses must use `.venv\Scripts\python.exe`. Relying on the system `python` command or App Execution Alias can break startup.
- `scripts/start.ps1` should run headless. Otherwise `chatbot/setup.py` may block startup in non-interactive PowerShell runs.
- `gpt-5.4` has been tested successfully with `LLM_BASE_URL=https://api.openai.com/` and TeamClaw's `/v1/chat/completions` endpoint.
- `auto-model` is for discovery only. It should print the model list, and the caller or agent should pick one model explicitly afterward.
- If WSL is not already installed, the first WSL setup step requires Administrator privileges on Windows before the Linux-side TeamClaw install can be tested.
- For WSL installs, a Linux-side copy such as `~/TeamClaw-wsl` is more reliable than running from `/mnt/c/...`.
- On some WSL setups, Windows host access to TeamClaw does not forward cleanly through `127.0.0.1`. When that happens, use the WSL VM IP shown by `status` or `start`, for example `http://172.x.x.x:51209`.

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
- Password users are optional.
- OpenClaw, bots, and tunnel setup are optional and should be user-driven.

## Optional Commands

### OpenClaw

```bash
bash selfskill/scripts/run.sh check-openclaw
```

```powershell
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 check-openclaw
```

### Tunnel

```bash
bash selfskill/scripts/run.sh start-tunnel
bash selfskill/scripts/run.sh stop-tunnel
```

```powershell
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 start-tunnel
powershell -ExecutionPolicy Bypass -File selfskill/scripts/run.ps1 stop-tunnel
```
