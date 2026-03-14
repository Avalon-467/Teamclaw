**[English](#english) | [中文](#中文)**

---

<a id="english"></a>

# TeamClaw
https://github.com/Avalon-467/Teamclaw

![TeamClaw Poster](docs/poster.png)

> **OpenAI-compatible AI Agent with a built-in programmable multi-expert orchestration engine and one-click public deployment.**
>
> **Skill Mode:** This repository is designed to run and be documented in a Skill-oriented workflow (see `SKILL.md`).

TeamClaw exposes a standard `/v1/chat/completions` endpoint that any OpenAI-compatible client can call directly. Internally it integrates the **OASIS orchestration engine** — using YAML schedule definitions to flexibly compose expert roles, speaking orders, and collaboration patterns, breaking complex problems into multi-perspective debates, voting consensus, and automated summaries.

---

## Quick Start

### Install via AI Code CLI (Recommended)

Open any AI Code CLI — such as **Cursor**, **Codex**, **Claude Code**, **CodeBuddy**, **Trae**, or any agent-capable coding assistant — and type:

```
Clone https://github.com/Avalon-467/Teamclaw.git and read the SKILL.md inside, then install TeamClaw.
```

That's it. The AI agent will automatically:

1. Clone the repository
2. Read `SKILL.md` (the complete installation & operation guide)
3. Set up the Python environment
4. Prompt you for API Key configuration
5. Create a user account
6. Start all services

> **Why this works:** TeamClaw is designed as a **Skill-oriented project**. The `SKILL.md` file contains everything an AI agent needs to install, configure, and operate TeamClaw — from environment setup to deployment. Any AI coding assistant that can read files and run commands will handle the entire process autonomously.

### Manual Setup

<details>
<summary>Click to expand manual setup steps (if not using AI Code CLI)</summary>

**1. Environment**

```bash
# Auto (recommended)
scripts/setup_env.sh   # Linux/macOS
scripts/setup_env.ps1  # Windows PowerShell

# Manual
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -r config/requirements.txt
```

```powershell
# PowerShell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_env.ps1
```

**2. API Key**

Set in `config/.env`:
```
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

```powershell
# PowerShell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_apikey.ps1
```

**3. Create User**

```bash
scripts/adduser.sh     # Linux/macOS
scripts/adduser.ps1    # Windows PowerShell
```

```powershell
# PowerShell
powershell -ExecutionPolicy Bypass -File .\scripts\adduser.ps1
```

**4. Start Services**

```bash
# One-click
scripts/start.sh       # Linux/macOS
scripts/start.ps1      # Windows PowerShell

# Manual (3 terminals)
python src/time.py         # Scheduler
python src/mainagent.py    # Agent + MCP tools
python src/front.py        # Web UI
```

```powershell
# PowerShell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

Visit http://127.0.0.1:51209 after startup.

</details>

### Public Deployment (Optional)

One-click exposure via Cloudflare Tunnel:
```bash
python scripts/tunnel.py
# Or interactively via run.sh / run.ps1 — prompts "Deploy to public network? (y/N)"
```
Auto-downloads `cloudflared`, starts tunnels for Web UI + Bark push, captures public URLs, and writes them to `.env`. No account or DNS setup required.

---

<details>
<summary><h2>Highlights</h2></summary>

### 1. OpenAI-Compatible API

```bash
curl http://127.0.0.1:51200/v1/chat/completions \
  -H "Authorization: Bearer <user>:<password>" \
  -H "Content-Type: application/json" \
  -d '{"model":"teambot","messages":[{"role":"user","content":"Hello"}],"stream":true}'
```

- Fully compatible with OpenAI Chat Completions format, streaming & non-streaming
- Multi-turn conversation, image input (Vision), audio input, file upload, TTS
- Works with ChatBox, Open WebUI, Cursor, or any OpenAI-compatible client
- Multi-user + multi-session isolation, SQLite-persisted conversation memory

### 2. OASIS Orchestration — A Programmable Expert Collaboration Engine

**This is the core design of the entire project.**

Traditional multi-agent systems are either fully parallel or fixed pipelines, unable to adapt to different scenarios. The OASIS engine uses a concise **YAML schedule definition** that lets users (or the AI Agent itself) precisely orchestrate every step of expert collaboration:

```yaml
# Example: Creative and Critical experts clash first, then everyone summarizes
version: 1
repeat: true
plan:
  - expert: "Creative Expert"      # Single expert speaks sequentially
  - expert: "Critical Expert"      # Immediately rebuts
  - parallel:                      # Multiple experts speak in parallel
      - "Economist"
      - "Legal Expert"
  - all_experts: true              # All participants speak simultaneously
```

#### Three Layers of Control

| Dimension | Control | Description |
|-----------|---------|-------------|
| **Who participates** | `expert_tags` | Select from 78 built-in experts (10 core + 68 agency) + user-defined custom expert pool |
| **How they discuss** | `schedule_yaml` | 4 step types freely combined (sequential / parallel / all / manual injection) |
| **How deep** | `max_rounds` + `use_bot_session` | Control round depth; choose stateful (memory + tools) or stateless (lightweight & fast) |

#### Four Schedule Step Types + DAG Mode

| Step Type | Format | Effect |
|-----------|--------|--------|
| `expert` | `- expert: "Name"` | Single expert speaks sequentially |
| `parallel` | `- parallel: ["A", "B"]` | Multiple experts speak simultaneously |
| `all_experts` | `- all_experts: true` | All selected experts speak at once |
| `manual` | `- manual: {author: "Host", content: "..."}` | Inject fixed content (bypasses LLM) |

Set `repeat: true` to loop the plan each round; `repeat: false` executes plan steps once then ends.

**DAG Mode (Dependency-Driven Parallelism):**

When the workflow has fan-in or fan-out, use `id` and `depends_on` fields on each step. The engine automatically runs independent steps in parallel and waits for all dependencies before starting a node:

```yaml
version: 1
repeat: false
plan:
  - id: research
    expert: "creative#temp#1"              # Starts immediately (no depends_on)
  - id: analysis
    expert: "critical#temp#1"              # Runs in parallel with research
  - id: synthesis
    expert: "synthesis#temp#1"
    depends_on: [research, analysis]       # Waits for both to complete
```

#### Expert Pool

**10 Built-in Public Experts:**

| Expert | Tag | Temp | Role |
|--------|-----|------|------|
| 🎨 Creative Expert | `creative` | 0.9 | Finds opportunities, proposes visionary ideas |
| 🔍 Critical Expert | `critical` | 0.3 | Spots risks, flaws, and logical fallacies |
| 📊 Data Analyst | `data` | 0.5 | Data-driven, speaks with facts |
| 🎯 Synthesis Advisor | `synthesis` | 0.5 | Integrates perspectives, proposes pragmatic plans |
| 📈 Economist | `economist` | 0.5 | Macro/micro economic perspective |
| ⚖️ Legal Expert | `lawyer` | 0.3 | Compliance and legal risk analysis |
| 💰 Cost Controller | `cost_controller` | 0.4 | Budget-sensitive, cost reduction |
| 📊 Revenue Planner | `revenue_planner` | 0.6 | Revenue maximization strategy |
| 🚀 Entrepreneur | `entrepreneur` | 0.8 | 0-to-1 hands-on perspective |
| 🧑 Common Person | `common_person` | 0.7 | Down-to-earth common sense feedback |

**68 Agency Experts (Professional Prompt Library):**

Integrated from [agency-agents](https://github.com/msitarzewski/agency-agents), covering 9 professional domains with deeply crafted prompts:

| Category | Count | Example Experts |
|----------|-------|----------------|
| 🎨 Design | 8 | UX Architect, UI Designer, Brand Guardian, Image Prompt Engineer |
| 🛠 Engineering | 11 | Senior Developer, Backend Architect, Frontend Developer, DevOps Automator, Security Engineer |
| 📢 Marketing | 11 | Content Creator, Growth Hacker, Social Media Strategist, TikTok/WeChat/Xiaohongshu Specialists |
| 📦 Product | 4 | Sprint Prioritizer, Trend Researcher, Feedback Synthesizer |
| 📋 Project Management | 5 | Senior PM, Studio Producer, Experiment Tracker |
| 🥽 Spatial Computing | 6 | VisionOS Engineer, XR Developer, Metal Engineer |
| 🔬 Specialized | 9 | Agents Orchestrator, Developer Advocate, Data Analytics Reporter |
| 🛡 Support | 6 | Finance Tracker, Legal Compliance, Infrastructure Maintainer |
| 🧪 Testing | 8 | API Tester, Performance Benchmarker, Accessibility Auditor |

These expert prompts are loaded automatically at startup and can be selected by tag in OASIS schedules, providing professional-grade expertise across the full product lifecycle.

**User-Defined Custom Experts:** Each user can create private experts (name, tag, persona, temperature) through the Agent, mixed with public experts, isolated per user.

#### Discussion Mechanics

Each expert per round:
1. **Post** — Opinion within 200 characters, can reference an existing post
2. **Vote** — Up/down vote on other posts

Engine auto-executes:
- **Consensus Detection** — Top-voted post reaches ≥70% expert approval → early termination
- **Conclusion Generation** — Synthesizes Top 5 highest-voted posts via LLM summary

#### Two Expert Running Modes

| Mode | `use_bot_session` | Features |
|------|-------------------|----------|
| **Stateless** (default) | `False` | Lightweight & fast, independent LLM call per round, no memory, no tools |
| **Stateful** | `True` | Each expert gets a persistent session with memory, can invoke search/file/code tools, sessions visible in frontend |

### 3. Multi-Platform Bot Integration (Telegram & QQ)

TeamClaw integrates with popular messaging platforms, allowing users to interact with the Agent through Telegram or QQ:

#### Telegram Bot

**Features:**
- Multimodal input: text, images, voice messages
- User isolation: each Telegram user maps to a system account
- Whitelist security: only authorized users can interact with the bot
- 30-second hot-reload whitelist (no restart needed)
- Push notifications: Agent can proactively send messages to users

**Setup:**
1. Create a Telegram bot via [@BotFather](https://t.me/botfather) and get the token
2. Set `TELEGRAM_BOT_TOKEN` in `config/.env`
3. Start the bot: `python chatbot/telegrambot.py`
4. Tell Agent your Telegram chat_id: "Set my Telegram chat_id to 123456789"

**User commands:**
- Send any message/image/voice to the bot → Agent responds
- Agent can push notifications to your Telegram proactively

#### QQ Bot

**Features:**
- Private chat (C2C) and group chat (@mention)
- Image and voice support (SILK format auto-transcoding)
- OpenAI-compatible multimodal input

**Setup:**
1. Register a QQ bot at [QQ Open Platform](https://bot.q.qq.com/)
2. Set `QQ_APP_ID` and `QQ_BOT_SECRET` in `config/.env`
3. Start the bot: `python chatbot/QQbot.py`

### 4. Advanced Agent Interaction

TeamClaw provides sophisticated user-Agent interaction features:

#### User Profile System

Each user can maintain a personalized profile that the Agent references:

```
data/user_files/{username}/user_profile.txt
```

Tell Agent: "Remember that I'm a Python developer interested in AI" → Profile saved and injected into future conversations.

#### Skill System

Users can define custom skills (reusable prompt templates):

```json
// data/user_files/{username}/skills_manifest.json
[
  {
    "name": "Code Reviewer",
    "description": "Review code for best practices",
    "file": "code_reviewer.md"
  }
]
```

Agent shows available skills in each session and can execute them on demand.

#### Dynamic Tool Management

- Tools can be enabled/disabled per-session
- Agent notifies user when tool status changes
- Security-critical tools protected by default

#### External Tool Injection

External systems can inject custom tools via OpenAI-compatible API:

```python
# Caller sends tool definitions
response = client.chat.completions.create(
    model="teambot",
    messages=[...],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {...}
        }
    }]
)
# Agent may call the tool → returns tool_calls to caller
# Caller executes tool and sends result back
```

### 5. One-Click Public Deployment

Run a single command to expose the entire service to the internet — **zero configuration, no account needed**:

```bash
python scripts/tunnel.py
```

- Uses **Cloudflare Quick Tunnel** to automatically obtain a temporary `*.trycloudflare.com` domain
- Auto-detects platform → downloads `cloudflared` if missing → starts tunnels → captures public URLs → writes to `.env`
- Exposes both the **Web UI** (port 51209) and **Bark push service** (port 58010) simultaneously
- Also available interactively via `run.sh` / `run.ps1` ("Deploy to public network? y/N")
- Push notification click-through URLs are automatically configured — users can also override via AI chat

#### Bidirectional OASIS

The Agent has both "convene" and "participate" capabilities:

| | 🏠 Internal OASIS (Convene) | 🌐 External OASIS (Participate) |
|---|---|---|
| **Initiator** | Agent calls `post_to_oasis` | External system sends message via OpenAI-compatible API |
| **Participants** | Local expert pool | Multiple independent Agent nodes |
| **Trigger** | User question → Agent decides | External request via `/v1/chat/completions` |
| **Result** | Conclusion returned to user | Agent opinion returned in standard OpenAI response format |

</details>

---

<details>
<summary><h2>OASIS Guide</h2></summary>

> Comprehensive guide to the OASIS orchestration engine — agent types, YAML control, OpenClaw integration, operating modes, and API reference.


### Four Agent Types

| # | Type | Name Format | Engine Class | Stateful | Backend |
|---|------|-------------|-------------|----------|---------|
| 1 | Direct LLM | `tag#temp#N` | `ExpertAgent` | No | Local LLM |
| 2 | Oasis Session | `tag#oasis#id` | `SessionExpert` (oasis) | Yes | Internal bot API |
| 3 | Regular Agent | `Title#session_id` | `SessionExpert` (regular) | Yes | Internal bot API |
| 4 | External API | `tag#ext#id` | `ExternalExpert` | Yes (assumed) | External HTTP API |

#### Type 1: Direct LLM (`tag#temp#N`)

Stateless single LLM call. Each round: reads all posts, one LLM call, publish + vote. No cross-round memory. `tag` maps to preset expert (name/persona), `N` is instance number.

```yaml
- expert: "creative#temp#1"
  instruction: "Focus on innovation"    # optional
```

#### Type 2: Oasis Session (`tag#oasis#id`)

OASIS-managed stateful bot session. `tag` maps to preset, persona injected as system prompt on first round. Bot retains conversation memory across rounds. `id` can be any string, new ID auto-creates session.

```yaml
- expert: "data#oasis#analysis01"
- expert: "synthesis#oasis#fresh#new"    # #new forces new session (UUID)
```

#### Type 3: Regular Agent Session (`Title#session_id`)

Connects to existing agent session (e.g. `Assistant#default`). No identity injection. The session's own system prompt defines the agent.

```yaml
- expert: "Assistant#default"
- expert: "Coder#my-project"
```

#### Type 4: External API (`tag#ext#id`) — OpenClaw & Others

Directly calls any OpenAI-compatible API. External service assumed stateful. Sends incremental context (first call = full, subsequent = delta only).

```yaml
- expert: "analyst#ext#ds1"
  api_url: "https://api.deepseek.com"
  api_key: "****"                    # Masked — real key auto-read from OPENCLAW_GATEWAY_TOKEN env var
  model: "deepseek-chat"
  headers:
    X-Custom-Header: "value"
  instruction: "Analyze from data perspective"
```

> 🔒 **API Key Security**: Set `api_key: "****"` (or omit it) and the system auto-reads the real key from the `OPENCLAW_GATEWAY_TOKEN` environment variable at runtime. Plaintext keys still work (backward compatible).

#### Special Suffix: `#new`

Appending `#new` forces a brand new session (ID replaced with random UUID):

```yaml
- expert: "creative#oasis#abc#new"      # UUID replaces "abc"
- expert: "Assistant#my-session#new"    # UUID replaces "my-session"
```

---

### YAML Control Directives

#### Top-Level Fields

```yaml
version: 1              # Required (currently 1)
repeat: true/false       # true = repeat plan each round; false = run once
discussion: true/false   # true = forum discussion; false = execution mode
plan: [...]              # Required: list of steps
```

#### Two Scheduling Modes: Linear vs DAG

OASIS supports two scheduling modes, automatically selected based on the YAML content:

| Mode | Detection | Execution | Use Case |
|------|-----------|-----------|----------|
| **Linear** | No `id`/`depends_on` fields in steps | Steps execute sequentially, one after another | Simple chains, debates, round-table discussions |
| **DAG** | Any step has an `id` field | Steps run in parallel when all their dependencies are satisfied | Fan-in/fan-out pipelines, complex multi-branch workflows |

**Linear mode** is the default. **DAG mode** activates automatically when the engine detects `id` fields in the plan steps.

#### Linear Step Types

##### 1. `expert` — Single Expert (Sequential)

```yaml
- expert: "critical#temp#1"
  instruction: "Focus on risks"
  api_url: "https://..."          # only for #ext#
  api_key: "****"               # only for #ext#, masked — auto-read from env
  model: "deepseek-chat"          # only for #ext#
  headers:                        # only for #ext#
    x-openclaw-session-key: "agent:main:test1"
```

##### 2. `parallel` — Multiple Experts (Concurrent)

```yaml
- parallel:
    - expert: "creative#temp#1"
      instruction: "Innovation angle"
    - expert: "critical#temp#2"
      instruction: "Risk analysis"
```

##### 3. `all_experts` — All Pool Experts Speak

```yaml
- all_experts: true
```

##### 4. `manual` — Inject Post (No LLM)

```yaml
- manual:
    author: "Moderator"
    content: "Focus on feasibility"
    reply_to: null
```

##### 5. Mix freely

```yaml
plan:
  - manual: ...
  - parallel: [...]
  - expert: ...
  - all_experts: true
```

#### DAG Mode — Dependency-Driven Parallel Execution

When the workflow has **fan-in** (a node has multiple predecessors) or **fan-out** (a node has multiple successors), use DAG mode with `id` and `depends_on` fields. The engine uses an event-driven dataflow model to maximize parallelism — each node starts as soon as all its dependencies are satisfied, without waiting for unrelated nodes.

##### DAG Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes (DAG) | Unique step identifier (typically the canvas node id) |
| `depends_on` | No | List of step `id`s that must complete before this step starts. Omit for root nodes. |

##### DAG Example: Fan-in Pipeline

```yaml
# A and B run in parallel; C waits for both; D waits for C
version: 1
repeat: false
plan:
  - id: research
    expert: "creative#temp#1"                # Root — starts immediately
  - id: analysis
    expert: "critical#temp#1"                # Root — runs in PARALLEL with research
  - id: synthesis
    expert: "synthesis#temp#1"
    depends_on: [research, analysis]         # Fan-in: waits for BOTH
  - id: review
    expert: "data#temp#1"
    depends_on: [synthesis]                  # Sequential after synthesis
```

##### DAG Example: Fan-out Pipeline

```yaml
# Architect designs, then backend and frontend work in parallel, reviewer waits for both
version: 1
repeat: false
plan:
  - id: design
    expert: "architect#ext#oc1"
    api_url: "http://127.0.0.1:18789"
    api_key: "****"
    model: "agent:main:architect"
    headers:
      x-openclaw-session-key: "agent:main:architect"
  - id: backend
    expert: "backend#ext#oc2"
    api_url: "http://127.0.0.1:18789"
    api_key: "****"
    model: "agent:main:backend"
    headers:
      x-openclaw-session-key: "agent:main:backend"
    depends_on: [design]                     # Fan-out from design
  - id: frontend
    expert: "frontend#ext#oc3"
    api_url: "http://127.0.0.1:18789"
    api_key: "****"
    model: "agent:main:frontend"
    headers:
      x-openclaw-session-key: "agent:main:frontend"
    depends_on: [design]                     # Fan-out from design
  - id: review
    expert: "reviewer#ext#oc4"
    api_url: "http://127.0.0.1:18789"
    api_key: "****"
    model: "agent:main:reviewer"
    headers:
      x-openclaw-session-key: "agent:main:reviewer"
    depends_on: [backend, frontend]          # Fan-in: waits for both
```

##### DAG with Manual Steps

```yaml
- id: briefing
  manual:
    author: "Commander"
    content: "Phase 1 complete. Proceed to analysis."
  depends_on: [scout1, scout2]
```

##### DAG Rules

1. Every step **must** have a unique `id` field.
2. `depends_on` is a list of step ids. Omit for root nodes (no predecessors).
3. The graph **must** be acyclic — circular dependencies will be rejected with an error.
4. Steps with no dependency relationship run in **parallel** automatically.
5. The visual Canvas auto-detects fan-in/fan-out and generates DAG format YAML.

##### How DAG Scheduling Works (Algorithm)

The engine uses an **event-driven dataflow model**:

1. For each step, an `asyncio.Event` is created (completion signal).
2. All steps are launched as concurrent `asyncio.Task`s.
3. Each task first `await`s all its predecessors' Events (blocks until all done).
4. After execution, the task `set()`s its own Event (notifies successors).
5. `asyncio.gather()` waits for all tasks to complete.

This achieves **maximum parallelism** — no unnecessary waiting, no explicit topological sort needed at runtime.

#### Type 4 Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `expert` | Yes | Name (format determines type) |
| `instruction` | No | Per-step instruction |
| `api_url` | Yes (ext) | Base URL (auto-completes to `/v1/chat/completions`) |
| `api_key` | No | Use `****` mask — auto-read from `OPENCLAW_GATEWAY_TOKEN` env var. Plaintext also supported. |
| `model` | No | Default `gpt-3.5-turbo` |
| `headers` | No | Extra HTTP headers (dict) |

---

### OpenClaw Integration

#### Prerequisites

> LLM API and OpenClaw API are completely separate credentials!

#### `model` Format

```
agent:<agent_name>:<session_name>
```

Examples: `agent:main:default`, `agent:main:test1`, `agent:main:code-review`
Non-existent sessions are auto-created.

#### OpenClaw CLI Priority

When the `model` field matches `agent:<name>:<session>`, the system **automatically** prefers the OpenClaw CLI:
```
openclaw agent --agent "<name>" --session-id "<session>" --message "<message>"
```
If the `openclaw` CLI is not in PATH or the call fails, it **falls back** to the HTTP API below.

#### `x-openclaw-session-key` — Deterministic Session Routing (HTTP fallback)

**The key mechanism** for routing to a specific OpenClaw session when using HTTP API.

- Visual Canvas **auto-sets** this header when dragging OpenClaw sessions
- Manual YAML: **must** include in `headers`
- Value **must match** `model` field

#### Complete OpenClaw Config

```yaml
- expert: "coder#ext#oc1"
  api_url: "http://127.0.0.1:18789"
  api_key: "****"                                  # Masked — real key from OPENCLAW_GATEWAY_TOKEN env var
  model: "agent:main:my-session"
  headers:
    x-openclaw-session-key: "agent:main:my-session"
  instruction: "Implement login feature"
```

#### Request Headers Sent

```
Content-Type: application/json
Authorization: Bearer <resolved_api_key>   # The actual key resolved from env var (never visible in YAML)
x-openclaw-session-key: agent:main:my-session
```

#### Multi-OpenClaw Pipeline

```yaml
version: 1
repeat: false
discussion: false
plan:
  - expert: "architect#ext#oc_arch"
    api_url: "http://127.0.0.1:18789"
    api_key: "****"                              # Masked — auto-read from env
    model: "agent:main:architect"
    headers:
      x-openclaw-session-key: "agent:main:architect"
    instruction: "Design the system architecture"

  - parallel:
    - expert: "backend#ext#oc_be"
      api_url: "http://127.0.0.1:18789"
      api_key: "****"
      model: "agent:main:backend"
      headers:
        x-openclaw-session-key: "agent:main:backend"
      instruction: "Implement backend API"
    - expert: "frontend#ext#oc_fe"
      api_url: "http://127.0.0.1:18789"
      api_key: "****"
      model: "agent:main:frontend"
      headers:
        x-openclaw-session-key: "agent:main:frontend"
      instruction: "Implement frontend"

  - expert: "reviewer#ext#oc_rev"
    api_url: "http://127.0.0.1:18789"
    api_key: "****"
    model: "agent:main:reviewer"
    headers:
      x-openclaw-session-key: "agent:main:reviewer"
    instruction: "Review everything"
```

---

### Operating Modes

#### Two Orthogonal Switches

| | Discussion (`true`) | Execution (`false`) |
|-|---------------------|---------------------|
| **Sync** (`detach=false`) | Forum debate, returns conclusion | Direct deliverables |
| **Async** (`detach=true`) | Returns topic_id, check later | Returns topic_id, check later |

#### Discussion Mode (`discussion=true`)

JSON responses with `content`, `reply_to`, `votes`. LLM summarizer produces final conclusion.
Use: reviews, debates, multi-perspective analysis.

#### Execution Mode (`discussion=false`)

Direct task output (code/plans/reports). No voting. Output = concatenation.
Use: code generation, pipelines, automated workflows.

#### `repeat` Flag

| `repeat` | Behavior |
|----------|----------|
| `true` | Plan repeats `max_rounds` times. For iterative discussions. |
| `false` | Steps run once sequentially. `max_rounds` ignored. For pipelines. |

---

### API Reference

Base URL: `http://127.0.0.1:51202`

#### Create Topic

```bash
curl -X POST 'http://127.0.0.1:51202/topics' \
  -H 'Content-Type: application/json' \
  -d '{"question":"task","user_id":"system","max_rounds":3,"discussion":false,"schedule_yaml":"...","schedule_file":"..."}'
```

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `question` | string | Yes | Task/discussion topic |
| `user_id` | string | Yes | User ID |
| `max_rounds` | int | No | 1-20, default 5 |
| `discussion` | bool | No | null=YAML, true=discuss, false=execute |
| `schedule_yaml` | string | Yes* | Inline YAML |
| `schedule_file` | string | Yes* | YAML file path (priority) |
| `early_stop` | bool | No | Early stop on consensus |
| `callback_url` | string | No | POST result here (detach) |
| `callback_session_id` | string | No | For callback |

#### Check / Stream / Cancel

```bash
curl 'http://127.0.0.1:51202/topics/{id}?user_id=system'
curl 'http://127.0.0.1:51202/topics/{id}/conclusion?user_id=system&timeout=300'
curl 'http://127.0.0.1:51202/topics/{id}/stream?user_id=system'
curl -X DELETE 'http://127.0.0.1:51202/topics/{id}?user_id=system'
curl 'http://127.0.0.1:51202/topics?user_id=system'
```

#### Expert Management

```bash
curl 'http://127.0.0.1:51202/experts?user_id=system'
curl -X POST 'http://127.0.0.1:51202/experts/user' -H 'Content-Type: application/json' \
  -d '{"user_id":"system","name":"PM","tag":"pm","persona":"...","temperature":0.7}'
curl -X PUT 'http://127.0.0.1:51202/experts/user/pm' -H 'Content-Type: application/json' \
  -d '{"user_id":"system","persona":"updated"}'
curl -X DELETE 'http://127.0.0.1:51202/experts/user/pm?user_id=system'
```

#### Workflow Management

```bash
curl -X POST 'http://127.0.0.1:51202/workflows' -H 'Content-Type: application/json' \
  -d '{"user_id":"system","name":"wf","schedule_yaml":"..."}'
curl 'http://127.0.0.1:51202/workflows?user_id=system'
curl -X POST 'http://127.0.0.1:51202/layouts/from-yaml' -H 'Content-Type: application/json' \
  -d '{"user_id":"system","yaml_source":"...","layout_name":"layout1"}'
```

#### Storage

| Data | Path |
|------|------|
| Workflows | `data/user_files/{user}/oasis/yaml/` |
| Custom experts | `data/oasis_user_experts/{user}.json` |
| Topics | `data/oasis_topics/{user}/{topic_id}.json` |
| Session memory | `data/agent_memory.db` |

---

### Examples

#### Simple Discussion

```yaml
version: 1
repeat: true
discussion: true
plan:
  - all_experts: true
```

#### Phased Pipeline (Linear)

```yaml
version: 1
repeat: false
discussion: false
plan:
  - manual:
      author: "Lead"
      content: "Requirements: OAuth2, session management, rate limiting."
  - parallel:
    - expert: "creative#temp#1"
      instruction: "Architecture design"
    - expert: "critical#temp#1"
      instruction: "Risk analysis"
  - expert: "synthesis#temp#1"
    instruction: "Final plan"
```

#### DAG Pipeline (Fan-in/Fan-out)

```yaml
version: 1
repeat: false
discussion: false
plan:
  - id: research
    expert: "creative#temp#1"
    instruction: "Research innovative approaches"
  - id: risk
    expert: "critical#temp#1"
    instruction: "Identify risks and blockers"
  - id: data
    expert: "data#temp#1"
    instruction: "Gather supporting data"
  - id: plan
    expert: "synthesis#temp#1"
    instruction: "Create final plan from all inputs"
    depends_on: [research, risk, data]
```

#### Mixed Agents

```yaml
version: 1
repeat: false
discussion: true
plan:
  - parallel:
    - expert: "creative#temp#1"
    - expert: "critical#temp#2"
  - expert: "coder#ext#oc1"
    api_url: "http://127.0.0.1:18789"
    api_key: "****"                                # Masked — from env
    model: "agent:main:research"
    headers:
      x-openclaw-session-key: "agent:main:research"
  - expert: "analyst#ext#ds1"
    api_url: "https://api.deepseek.com"
    api_key: "****"                                # Masked — from env
    model: "deepseek-chat"
```

#### Stateful Oasis Sessions (Multi-Phase)

```yaml
version: 1
repeat: false
plan:
  - manual:
      author: "Commander"
      content: "Phase 1: Recon"
  - parallel:
    - expert: "scout1#oasis#alpha#new"
      instruction: "Scout north"
    - expert: "scout2#oasis#bravo#new"
      instruction: "Scout east"
  - manual:
      author: "Commander"
      content: "Phase 2: Plan (sessions retain Phase 1 memory)"
  - parallel:
    - expert: "scout1#oasis#alpha"
      instruction: "Propose approach"
    - expert: "scout2#oasis#bravo"
      instruction: "Propose approach"
  - all_experts: true
```

---

### Troubleshooting

| Symptom | Solution |
|---------|----------|
| "name has no '#', skipping" | Use format: `tag#temp#N`, `tag#oasis#id`, `Title#sid`, `tag#ext#id` |
| "missing 'api_url'" | Add `api_url` to Type 4 expert |
| Wrong OpenClaw session | Ensure `model` uses `agent:<name>:<session>` format (CLI priority); or add `headers: {x-openclaw-session-key: ...}` for HTTP fallback |
| Canvas missing OpenClaw sessions | Ensure OpenClaw CLI is available |
| API timeout | Check port, verify OpenAI-compatible interface enabled |

**Debug**: Check `logs/launcher.log` for `[OASIS]` messages. Use SSE stream for real-time monitoring.

---

### Quick Reference

| Task | Config |
|------|--------|
| Quick opinions | `tag#temp#N` + `discussion: true` |
| Stateful sessions | `tag#oasis#id` + `repeat: true` |
| Existing bot | `Title#session_id` |
| OpenClaw agents | `tag#ext#id` + `api_url` + `model: agent:<name>:<session>` (CLI priority, HTTP fallback) |
| External LLMs | `tag#ext#id` + `api_url` + `api_key` |
| Simple pipeline | `repeat: false` (linear steps) |
| DAG pipeline | `repeat: false` + steps with `id` + `depends_on` |
| Iterative | `repeat: true` + `discussion: true` |
| Background | `callback_url` + `callback_session_id` |

</details>

---

<details>
<summary><h2>Architecture</h2></summary>

```
Browser (Chat UI + Login + OASIS Panel)
    │  HTTP :51209
    ▼
front.py (Flask + Session)     ── Frontend proxy, login/chat pages, session management
    │  HTTP :51200
    ▼
mainagent.py (FastAPI + LangGraph)  ── OpenAI-compatible API + Core Agent
    │  stdio (MCP)                      (External OASIS also via OpenAI API)
    ├── mcp_scheduler.py   ── Alarm/scheduled task management
    │       │  HTTP :51201
    │       ▼
    ├── time.py (APScheduler)  ── Scheduling center
    ├── mcp_search.py      ── DuckDuckGo web search
    ├── mcp_filemanager.py ── User file management (sandboxed)
    ├── mcp_oasis.py       ── OASIS discussion + expert management
    │       │  HTTP :51202
    │       ▼
    │   oasis/server.py    ── OASIS forum service (engine + expert pool)
    ├── mcp_bark.py        ── Bark mobile push notifications
    ├── mcp_telegram.py    ── Telegram push + whitelist sync
    └── mcp_commander.py   ── Sandboxed command/code execution

┌─────────────────────────────────────────────────────────────────┐
│                    External Bot Services                         │
├─────────────────────────────────────────────────────────────────┤
│  telegrambot.py         ── Telegram Bot (text/image/voice)       │
│  QQbot.py               ── QQ Bot (C2C/Group, SILK transcoding)  │
│                                                                  │
│  Both bots call mainagent.py via OpenAI-compatible API           │
│  with user-isolated sessions (INTERNAL_TOKEN:user:BOT)           │
└─────────────────────────────────────────────────────────────────┘
```

### Ports

| Service | Port | Description |
|---------|------|-------------|
| `front.py` | 51209 | Web UI (login + chat + OASIS panel) |
| `mainagent.py` | 51200 | OpenAI-compatible API + Agent core |
| `time.py` | 51201 | Scheduling center |
| `oasis/server.py` | 51202 | OASIS forum service |

> Ports configurable in `config/.env`.

### MCP Toolset

7 tool services integrated via MCP protocol. All `username` parameters are auto-injected, fully isolated between users:

| Tool Service | Capability |
|-------------|------------|
| **Search** | DuckDuckGo web search |
| **Scheduler** | Natural language alarms/reminders, Cron expressions |
| **File Manager** | User file CRUD, path traversal protection |
| **Commander** | Shell commands and Python code in secure sandbox |
| **OASIS Forum** | Start discussions, check progress, manage custom experts |
| **Bark Push** | Push notifications to iOS/macOS devices |
| **Telegram** | Push messages to Telegram, whitelist management |

</details>

---

<details>
<summary><h2>API Reference</h2></summary>

### OpenAI-Compatible Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | Chat completions (streaming/non-streaming), fully OpenAI-compatible |
| `/login` | POST | User login authentication |
| `/sessions` | POST | List user sessions |
| `/session_history` | POST | Get session history |

### OASIS Forum Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/topics` | POST | Create discussion topic |
| `/topics` | GET | List all topics |
| `/topics/{id}` | GET | Get topic details |
| `/topics/{id}/stream` | GET | SSE real-time update stream |
| `/topics/{id}/conclusion` | GET | Block until conclusion ready |
| `/experts` | GET | List experts (public + user custom) |
| `/experts/user` | POST/PUT/DELETE | User custom expert CRUD |
| `/sessions/oasis` | GET | List OASIS-managed expert sessions |
| `/workflows` | POST | Save YAML workflow |
| `/workflows` | GET | List user's saved workflows |
| `/layouts/from-yaml` | POST | Generate layout JSON from YAML |

</details>

---

<details>
<summary><h2>Authentication</h2></summary>

- **Password Storage**: SHA-256 hash only, no plaintext on disk
- **Session Management**: Flask signed Cookie, `sessionStorage` expires on tab close
- **Request Verification**: Every `/ask` re-verifies password
- **Internal Auth**: Inter-service communication via `INTERNAL_TOKEN` (auto-generated 64-char hex)
- **User Isolation**: Conversation memory, file storage, custom experts all isolated by `user_id`
- **OASIS API Key Masking**: External API keys (e.g. `OPENCLAW_GATEWAY_TOKEN`) are never exposed in YAML or the frontend canvas. Set `api_key: "****"` in YAML and the system auto-reads the real key from environment variables at runtime.

</details>

---

<details>
<summary><h2>Project Structure</h2></summary>

```
TeamClaw/
├── run.sh / run.ps1               # One-click run
├── scripts/                       # Env setup, start, tunnel, user management
├── packaging/                     # Windows exe / macOS DMG packaging
├── chatbot/                       # External bot services
│   ├── telegrambot.py             # Telegram Bot (text/image/voice)
│   ├── QQbot.py                   # QQ Bot (C2C/Group, SILK transcoding)
│   └── setup.py                   # Bot configuration helper
├── config/
│   ├── .env                       # API keys and env vars
│   ├── requirements.txt           # Python dependencies
│   └── users.json                 # Username-password hash
├── data/
│   ├── agent_memory.db            # Conversation memory (SQLite)
│   ├── telegram_whitelist.json    # Telegram bot whitelist
│   ├── prompts/                   # System prompts + expert configs
│   │   ├── oasis_experts.json     # 10 public expert definitions
│   │   ├── agency_experts.json    # 68 agency expert index
│   │   ├── agency_agents/         # 68 expert prompts (9 categories)
│   │   ├── oasis_expert_discuss.txt  # Expert discussion prompt template
│   │   └── oasis_summary.txt     # Conclusion generation prompt template
│   ├── schedules/                 # YAML schedule examples
│   ├── oasis_user_experts/        # User custom experts (per-user JSON)
│   ├── timeset/                   # Scheduled task persistence
│   └── user_files/                # User files (isolated per user)
├── src/
│   ├── mainagent.py               # OpenAI-compatible API + Agent core
│   ├── agent.py                   # LangGraph workflow + tool orchestration
│   ├── front.py                   # Flask Web UI
│   ├── time.py                    # Scheduling center
│   └── mcp_*.py                   # 7 MCP tool services
├── oasis/
│   ├── server.py                  # OASIS FastAPI service
│   ├── engine.py                  # Discussion engine (rounds + consensus + conclusion)
│   ├── experts.py                 # Expert definitions + user expert storage
│   ├── scheduler.py               # YAML schedule parsing & execution
│   ├── forum.py                   # Forum data structures
│   └── models.py                  # Pydantic models
├── tools/
│   └── gen_password.py            # Password hash generator
└── test/
    ├── chat.py                    # CLI test client
    └── view_history.py            # View chat history
```

</details>

---

<details>
<summary><h2>Tech Stack</h2></summary>

| Layer | Technology |
|-------|-----------|
| LLM | DeepSeek (`deepseek-chat`) |
| Agent Framework | LangGraph + LangChain |
| Tool Protocol | MCP (Model Context Protocol) |
| Backend | FastAPI + Flask |
| Auth | SHA-256 Hash + Flask Session |
| Scheduling | APScheduler |
| Persistence | SQLite (aiosqlite) |
| Frontend | Tailwind CSS + Marked.js + Highlight.js |

</details>

## License

MIT License

---

<a id="中文"></a>

# TeamClaw

**[English](#english) | [中文](#中文)**

> **OpenAI 兼容的 AI Agent，内置可编程多专家协作引擎，支持一键部署到公网。**

TeamClaw 对外暴露标准 `/v1/chat/completions` 接口，可以被任何 OpenAI 兼容客户端直接调用；对内集成 **OASIS 智能编排引擎**——通过 YAML 调度定义，灵活组合专家角色、发言顺序和协作模式，将复杂问题拆解为多视角辩论、投票共识、自动总结的完整流程。

---

## 快速开始

### 通过 AI Code CLI 安装（推荐）

打开任意 AI Code CLI —— 如 **Cursor**、**Codex**、**Claude Code**、**CodeBuddy**、**Trae**，或任何支持 Agent 的编程助手 —— 输入：

```
下载 https://github.com/Avalon-467/Teamclaw.git 并阅读里面的 SKILL.md，安装 TeamClaw
```

然后等待即可。AI Agent 会自动完成：

1. 克隆仓库
2. 阅读 `SKILL.md`（完整的安装与操作指南）
3. 配置 Python 环境
4. 提示你设置 API Key
5. 创建用户账户
6. 启动全部服务

> **原理：** TeamClaw 是一个 **Skill 驱动的项目**。`SKILL.md` 包含了 AI Agent 安装、配置和运行 TeamClaw 所需的一切信息——从环境搭建到部署上线。任何能读文件、能跑命令的 AI 编程助手都可以自主完成整个流程。

### 手动配置

<details>
<summary>点击展开手动配置步骤（不使用 AI Code CLI 时）</summary>

**1. 环境配置**

```bash
# 自动（推荐）
scripts/setup_env.sh   # Linux/macOS
scripts/setup_env.ps1  # Windows PowerShell

# 手动
uv venv .venv --python 3.11
source .venv/bin/activate
uv pip install -r config/requirements.txt
```

```powershell
# PowerShell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_env.ps1
```

**2. 配置 API Key**

在 `config/.env` 中设置：

```
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

```powershell
# PowerShell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_apikey.ps1
```

**3. 创建用户**

```bash
scripts/adduser.sh     # Linux/macOS
scripts/adduser.ps1    # Windows PowerShell
```

```powershell
# PowerShell
powershell -ExecutionPolicy Bypass -File .\scripts\adduser.ps1
```

**4. 启动服务**

```bash
# 一键启动
scripts/start.sh       # Linux/macOS
scripts/start.ps1      # Windows PowerShell

# 手动分别启动（3 个终端）
python src/time.py         # 定时调度
python src/mainagent.py    # Agent + MCP 工具
python src/front.py        # Web UI
```

```powershell
# PowerShell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

启动后访问 http://127.0.0.1:51209 登录使用。

</details>

### 公网部署（可选）

通过 Cloudflare Tunnel 一键暴露到公网：

```bash
python scripts/tunnel.py
# 或通过 run.sh / run.ps1 交互启动——提示"是否部署到公网？(y/N)"
```
自动下载 `cloudflared`，启动 Web UI + Bark 推送双隧道，捕获公网地址写入 `.env`，无需账户或 DNS 配置。

---

<details>
<summary><h2>核心亮点</h2></summary>

### 1. OpenAI 兼容 API

```bash
curl http://127.0.0.1:51200/v1/chat/completions \
  -H "Authorization: Bearer <user>:<password>" \
  -H "Content-Type: application/json" \
  -d '{"model":"teambot","messages":[{"role":"user","content":"你好"}],"stream":true}'
```

- 完全兼容 OpenAI Chat Completions 格式，支持流式/非流式响应
- 支持多轮对话、图片输入（Vision）、音频输入、文件上传、TTS
- 可被 ChatBox、Open WebUI、Cursor 等任何 OpenAI 兼容客户端直接接入
- 多用户 + 多会话隔离，SQLite 持久化对话记忆

### 2. OASIS 智能编排——可编程的专家协作引擎

**这是整个项目的核心设计。**

传统的多 Agent 系统要么全部并行、要么固定流水线，无法灵活应对不同场景。OASIS 引擎通过一份简洁的 **YAML 调度定义**，让用户（或 AI Agent 自身）能精确编排专家协作的每一个环节：

```yaml
# 示例：先让创意和批判两位专家交锋，再让所有人总结
version: 1
repeat: true
plan:
  - expert: "创意专家"           # 单人顺序发言
  - expert: "批判专家"           # 紧接着反驳
  - parallel:                    # 多人并行发言
      - "经济学家"
      - "法学家"
  - all_experts: true            # 所有参与者同时发言
```

#### 三层可控性

| 维度 | 控制方式 | 说明 |
|------|----------|------|
| **谁参与** | `expert_tags` | 从 78 位内置专家（10 核心 + 68 agency）+ 用户自定义专家池中选人 |
| **怎么讨论** | `schedule_yaml` | 4 种步骤类型自由组合（顺序 / 并行 / 全员 / 手动注入） |
| **多深入** | `max_rounds` + `use_bot_session` | 控制轮次深度，可选有状态（记忆+工具）或无状态（轻量快速） |

#### 四种调度步骤 + DAG 模式

| 步骤类型 | 格式 | 效果 |
|----------|------|------|
| `expert` | `- expert: "专家名"` | 单个专家顺序发言 |
| `parallel` | `- parallel: ["A", "B"]` | 多个专家同时并行发言 |
| `all_experts` | `- all_experts: true` | 所有选中专家同时发言 |
| `manual` | `- manual: {author: "主持人", content: "..."}` | 注入固定内容（不经过 LLM） |

设置 `repeat: true` 时，调度计划每轮循环执行；`repeat: false` 则按步骤顺序执行一次后结束。

**DAG 模式（依赖驱动的并行执行）：**

当工作流存在 fan-in（多个前驱汇聚到一个节点）或 fan-out（一个节点分发到多个后继）时，给每个步骤加上 `id` 和 `depends_on` 字段。引擎自动并行执行无依赖关系的步骤，并等待所有前驱完成后再启动下游节点：

```yaml
version: 1
repeat: false
plan:
  - id: research
    expert: "creative#temp#1"              # 立即启动（无 depends_on）
  - id: analysis
    expert: "critical#temp#1"              # 与 research 并行执行
  - id: synthesis
    expert: "synthesis#temp#1"
    depends_on: [research, analysis]       # 等待两者都完成
```

#### 专家池

**10 位内置公共专家**：

| 专家 | Tag | 温度 | 定位 |
|------|-----|------|------|
| 🎨 创意专家 | `creative` | 0.9 | 发现机遇，提出前瞻性想法 |
| 🔍 批判专家 | `critical` | 0.3 | 发现风险漏洞，严谨质疑 |
| 📊 数据分析师 | `data` | 0.5 | 数据驱动，用事实说话 |
| 🎯 综合顾问 | `synthesis` | 0.5 | 综合各方，提出务实方案 |
| 📈 经济学家 | `economist` | 0.5 | 宏观/微观经济视角 |
| ⚖️ 法学家 | `lawyer` | 0.3 | 合规性与法律风险 |
| 💰 成本限制者 | `cost_controller` | 0.4 | 预算敏感，降本增效 |
| 📊 收益规划者 | `revenue_planner` | 0.6 | 收益最大化策略 |
| 🚀 创新企业家 | `entrepreneur` | 0.8 | 从 0 到 1 的实战视角 |
| 🧑 普通人 | `common_person` | 0.7 | 接地气的常识反馈 |

**68 位 Agency 专业专家（Prompt 工程库）：**

集成自 [agency-agents](https://github.com/msitarzewski/agency-agents)，涵盖 9 大专业领域，每位专家配备深度打磨的 Prompt：

| 分类 | 数量 | 代表专家 |
|------|------|----------|
| 🎨 设计 | 8 | UX 架构师、UI 设计师、品牌守护者、图像 Prompt 工程师 |
| 🛠 工程 | 11 | 高级开发者、后端架构师、前端开发者、DevOps 自动化师、安全工程师 |
| 📢 营销 | 11 | 内容创作者、增长黑客、社交媒体策略师、抖音/微信/小红书专家 |
| 📦 产品 | 4 | 迭代优先级规划师、趋势研究员、反馈整合师 |
| 📋 项目管理 | 5 | 高级项目经理、工作室制片人、实验追踪器 |
| 🥽 空间计算 | 6 | VisionOS 工程师、XR 开发者、Metal 工程师 |
| 🔬 专项 | 9 | Agent 编排器、开发者布道师、数据分析报告员 |
| 🛡 支持 | 6 | 财务追踪、法律合规、基础设施维护 |
| 🧪 测试 | 8 | API 测试员、性能基准测试、无障碍审计师 |

这些专家 Prompt 在启动时自动加载，可在 OASIS 调度中通过 tag 选用，为产品全生命周期提供专业级视角。

**用户自定义专家**：每个用户可通过 Agent 创建私有专家（定义名称、tag、persona、温度），与公共专家混合使用，按用户隔离。

#### 讨论机制

每位专家每轮：
1. **发帖** — 200 字以内的观点，可标注回复某个已有帖子
2. **投票** — 对其他帖子投 up/down

引擎自动执行：
- **共识检测** — 最高票帖子获得 ≥70% 专家赞成 → 提前结束
- **结论生成** — 综合 Top 5 高赞帖子，LLM 生成最终总结

#### 两种专家运行模式

| 模式 | `use_bot_session` | 特点 |
|------|-------------------|------|
| **无状态**（默认） | `False` | 轻量快速，每轮独立调 LLM，无记忆无工具 |
| **有状态** | `True` | 每位专家创建持久 session，有记忆、能调用搜索/文件/代码执行等全部工具，session 可在前端查看和继续对话 |

### 3. 多平台 Bot 接入（Telegram & QQ）

TeamClaw 集成主流即时通讯平台，用户可通过 Telegram 或 QQ 与 Agent 交互：

#### Telegram Bot

**功能特性：**
- 多模态输入：文字、图片、语音消息
- 用户隔离：每个 Telegram 用户映射到独立系统账户
- 白名单安全：仅授权用户可与机器人交互
- 30 秒热重载白名单（无需重启）
- 主动推送：Agent 可主动向用户发送 Telegram 消息

**配置步骤：**
1. 通过 [@BotFather](https://t.me/botfather) 创建 Telegram Bot 并获取 Token
2. 在 `config/.env` 中设置 `TELEGRAM_BOT_TOKEN`
3. 启动机器人：`python chatbot/telegrambot.py`
4. 告诉 Agent 你的 Telegram chat_id："设置我的 Telegram chat_id 为 123456789"

**用户使用：**
- 向机器人发送任意消息/图片/语音 → Agent 回复
- Agent 可主动推送通知到你的 Telegram

#### QQ Bot

**功能特性：**
- 私聊（C2C）和群聊（@机器人）
- 图片和语音支持（SILK 格式自动转码）
- OpenAI 兼容多模态输入

**配置步骤：**
1. 在 [QQ 开放平台](https://bot.q.qq.com/) 注册机器人
2. 在 `config/.env` 中设置 `QQ_APP_ID` 和 `QQ_BOT_SECRET`
3. 启动机器人：`python chatbot/QQbot.py`

### 4. 高级 Agent 互动

TeamClaw 提供丰富的用户-Agent 互动功能：

#### 用户画像系统

每个用户可维护专属画像，Agent 在对话中自动参考：

```
data/user_files/{用户名}/user_profile.txt
```

告诉 Agent："记住我是 Python 开发者，关注 AI 领域" → 画像保存并在后续对话中注入。

#### 技能系统

用户可定义自定义技能（可复用的提示词模板）：

```json
// data/user_files/{用户名}/skills_manifest.json
[
  {
    "name": "代码审查员",
    "description": "审查代码并提出最佳实践建议",
    "file": "code_reviewer.md"
  }
]
```

Agent 在每个会话中显示可用技能，并按需执行。

#### 动态工具管理

- 工具可按会话启用/禁用
- 工具状态变更时 Agent 通知用户
- 安全敏感工具默认受保护

#### 外部工具注入

外部系统可通过 OpenAI 兼容 API 注入自定义工具：

```python
# 调用方发送工具定义
response = client.chat.completions.create(
    model="teambot",
    messages=[...],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取当前天气",
            "parameters": {...}
        }
    }]
)
# Agent 可能调用工具 → 返回 tool_calls 给调用方
# 调用方执行工具并发送结果回去
```

### 5. 一键部署到公网

一条命令将整个服务暴露到互联网——**零配置、无需账户**：

```bash
python scripts/tunnel.py
```

- 使用 **Cloudflare Quick Tunnel**，自动获取临时 `*.trycloudflare.com` 域名
- 全自动流程：检测平台 → 下载 `cloudflared`（若缺失）→ 启动隧道 → 捕获公网地址 → 写入 `.env`
- 同时暴露 **Web UI**（端口 51209）和 **Bark 推送服务**（端口 58010）
- 也可通过 `run.sh` / `run.ps1` 交互启动（提示"是否部署到公网？y/N"）
- 推送通知的点击跳转地址自动配置——用户还可通过 AI 对话自行覆盖

#### 双向 OASIS 能力

Agent 同时具备"主动召集"和"被邀参与"两种角色：

| | 🏠 内部 OASIS（主动召集） | 🌐 外部 OASIS（被邀参与） |
|---|---|---|
| **发起方** | Agent 调用 `post_to_oasis` | 外部系统通过 OpenAI 兼容 API 发送消息 |
| **参与者** | 本地专家池 | 多个独立 Agent 节点 |
| **触发** | 用户提问 → Agent 自主决策 | 外部请求通过 `/v1/chat/completions` |
| **结果** | 结论直接返回用户 | Agent 意见以标准 OpenAI 格式返回 |

</details>

---

<details>
<summary><h2>OASIS 使用指南</h2></summary>

> OASIS 编排引擎完整指南——Agent 类型、YAML 控制指令、OpenClaw 集成、运行模式和 API 参考。

#### 四种 Agent 类型

| # | 类型 | 名称格式 | 引擎类 | 有状态 | 后端 |
|---|------|----------|--------|--------|------|
| 1 | 直接 LLM | `tag#temp#N` | `ExpertAgent` | 否 | 本地 LLM |
| 2 | Oasis 会话 | `tag#oasis#id` | `SessionExpert` (oasis) | 是 | 内部 bot API |
| 3 | 常规 Agent | `Title#session_id` | `SessionExpert` (regular) | 是 | 内部 bot API |
| 4 | 外部 API | `tag#ext#id` | `ExternalExpert` | 是（假定） | 外部 HTTP API |

##### 类型 1：直接 LLM（`tag#temp#N`）

无状态单次 LLM 调用。每轮：读取所有帖子，一次 LLM 调用，发布 + 投票。无跨轮记忆。`tag` 映射到预设专家（名称/角色），`N` 是实例编号。

```yaml
- expert: "creative#temp#1"
  instruction: "聚焦创新"    # 可选
```

##### 类型 2：Oasis 会话（`tag#oasis#id`）

OASIS 管理的有状态 bot 会话。`tag` 映射到预设专家，persona 在首轮作为系统提示注入。Bot 跨轮保持对话记忆。`id` 可以是任意字符串，新 ID 自动创建会话。

```yaml
- expert: "data#oasis#analysis01"
- expert: "synthesis#oasis#fresh#new"    # #new 强制新建会话（UUID）
```

##### 类型 3：常规 Agent 会话（`Title#session_id`）

连接到已有的 agent 会话（如 `Assistant#default`）。不注入身份信息。会话自身的系统提示定义了 agent。

```yaml
- expert: "Assistant#default"
- expert: "Coder#my-project"
```

##### 类型 4：外部 API（`tag#ext#id`）— OpenClaw 及其他

直接调用任意 OpenAI 兼容 API。外部服务假定有状态。发送增量上下文（首次 = 完整，后续 = 仅增量）。

```yaml
- expert: "analyst#ext#ds1"
  api_url: "https://api.deepseek.com"
  api_key: "****"
  model: "deepseek-chat"
  headers:
    X-Custom-Header: "value"
  instruction: "从数据角度分析"
```

> 🔒 **API Key 安全**：设置 `api_key: "****"`（或省略），系统运行时自动从 `OPENCLAW_GATEWAY_TOKEN` 环境变量读取真实密钥。明文密钥仍然支持（向后兼容）。

##### 特殊后缀：`#new`

追加 `#new` 强制创建全新会话（ID 替换为随机 UUID）：

```yaml
- expert: "creative#oasis#abc#new"      # UUID 替换 "abc"
- expert: "Assistant#my-session#new"    # UUID 替换 "my-session"
```

##### YAML 控制指令

**顶层字段：**

```yaml
version: 1              # 必填（当前版本 1）
repeat: true/false       # true = 每轮重复计划；false = 执行一次
discussion: true/false   # true = 论坛讨论；false = 执行模式
plan: [...]              # 必填：步骤列表
```

**两种调度模式：线性 vs DAG**

| 模式 | 检测方式 | 执行方式 | 适用场景 |
|------|----------|----------|----------|
| **线性** | 步骤中没有 `id`/`depends_on` 字段 | 步骤按顺序逐个执行 | 简单链式、辩论、圆桌讨论 |
| **DAG** | 任一步骤有 `id` 字段 | 依赖满足时并行执行 | Fan-in/fan-out 流水线、复杂多分支工作流 |

**线性步骤类型：**

| 步骤 | 格式 | 效果 |
|------|------|------|
| `expert` | `- expert: "名称"` | 单个专家顺序发言 |
| `parallel` | `- parallel: [...]` | 多个专家并发 |
| `all_experts` | `- all_experts: true` | 全部专家发言 |
| `manual` | `- manual: {author, content}` | 注入固定内容 |

**DAG 模式：** 使用 `id` + `depends_on` 字段实现依赖驱动的并行执行。引擎使用事件驱动数据流模型最大化并行。

##### OpenClaw 集成

`model` 格式：`agent:<agent_name>:<session_name>`（如 `agent:main:default`）

系统**自动优先**使用 OpenClaw CLI，失败则回退到 HTTP API。使用 `x-openclaw-session-key` 头进行确定性会话路由。

##### 运行模式

| | 讨论（`true`） | 执行（`false`） |
|-|----------------|-----------------|
| **同步** | 论坛辩论，返回结论 | 直接交付物 |
| **异步** | 返回 topic_id | 返回 topic_id |

##### 故障排除

| 症状 | 解决方案 |
|------|----------|
| "name has no '#', skipping" | 使用正确格式：`tag#temp#N`、`tag#oasis#id` 等 |
| "missing 'api_url'" | 给类型 4 专家添加 `api_url` |
| OpenClaw 会话错误 | 确保 `model` 使用 `agent:<name>:<session>` 格式 |

**调试**：检查 `logs/launcher.log` 中的 `[OASIS]` 消息。

</details>

---

<details>
<summary><h2>架构概览</h2></summary>

```
浏览器 (聊天 UI + 登录页 + OASIS 论坛面板)
    │  HTTP :51209
    ▼
front.py (Flask + Session)     ── 前端代理，渲染登录/聊天页面，管理会话凭证
    │  HTTP :51200
    ▼
mainagent.py (FastAPI + LangGraph)  ── OpenAI 兼容 API + 核心 Agent
    │  stdio (MCP)                      （外部 OASIS 同样通过 OpenAI API 接入）
    ├── mcp_scheduler.py   ── 闹钟/定时任务管理
    │       │  HTTP :51201
    │       ▼
    ├── time.py (APScheduler)  ── 定时调度中心
    ├── mcp_search.py      ── DuckDuckGo 联网搜索
    ├── mcp_filemanager.py ── 用户文件管理（沙箱隔离）
    ├── mcp_oasis.py       ── OASIS 多专家讨论 + 专家管理
    │       │  HTTP :51202
    │       ▼
    │   oasis/server.py    ── OASIS 论坛服务（调度引擎 + 专家池）
    ├── mcp_bark.py        ── Bark 手机推送通知
    ├── mcp_telegram.py    ── Telegram 推送 + 白名单同步
    └── mcp_commander.py   ── 安全沙箱命令/代码执行

┌─────────────────────────────────────────────────────────────────┐
│                      外部 Bot 服务                               │
├─────────────────────────────────────────────────────────────────┤
│  telegrambot.py         ── Telegram Bot（文字/图片/语音）         │
│  QQbot.py               ── QQ Bot（私聊/群聊，SILK 转码）         │
│                                                                  │
│  两个 Bot 均通过 OpenAI 兼容 API 调用 mainagent.py               │
│  使用用户隔离会话（INTERNAL_TOKEN:用户名:BOT）                    │
└─────────────────────────────────────────────────────────────────┘
```

### 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| `front.py` | 51209 | Web UI（登录 + 聊天 + OASIS 面板） |
| `mainagent.py` | 51200 | OpenAI 兼容 API + Agent 核心 |
| `time.py` | 51201 | 定时任务调度中心 |
| `oasis/server.py` | 51202 | OASIS 论坛服务 |

> 端口可在 `config/.env` 中自定义。

### MCP 工具集

Agent 通过 MCP 协议集成 7 个工具服务，所有工具的 `username` 参数由系统自动注入，用户间完全隔离：

| 工具服务 | 能力 |
|----------|------|
| **搜索** | DuckDuckGo 联网搜索 |
| **定时任务** | 自然语言设置闹钟/提醒，Cron 表达式 |
| **文件管理** | 用户文件 CRUD，路径穿越防护 |
| **命令执行** | 安全沙箱中运行 Shell 命令和 Python 代码 |
| **OASIS 论坛** | 发起讨论、查看进展、管理自定义专家 |
| **Bark 推送** | 向 iOS/macOS 设备发送推送通知 |
| **Telegram** | 向 Telegram 发送消息、白名单管理 |

</details>

---

<details>
<summary><h2>API 参考</h2></summary>

### OpenAI 兼容端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/chat/completions` | POST | 聊天补全（流式/非流式），完全兼容 OpenAI 格式 |
| `/login` | POST | 用户登录认证 |
| `/sessions` | POST | 列出用户会话 |
| `/session_history` | POST | 获取会话历史 |

### OASIS 论坛端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/topics` | POST | 创建讨论话题 |
| `/topics` | GET | 列出所有话题 |
| `/topics/{id}` | GET | 获取话题详情 |
| `/topics/{id}/stream` | GET | SSE 实时更新流 |
| `/topics/{id}/conclusion` | GET | 阻塞等待讨论结论 |
| `/experts` | GET | 列出专家（公共 + 用户自定义） |
| `/experts/user` | POST/PUT/DELETE | 用户自定义专家 CRUD |
| `/sessions/oasis` | GET | 列出 OASIS 管理的专家会话 |
| `/workflows` | POST | 保存 YAML workflow |
| `/workflows` | GET | 列出用户保存的 workflows |
| `/layouts/from-yaml` | POST | 从 YAML 生成 layout JSON |

</details>

---

<details>
<summary><h2>认证机制</h2></summary>

- **密码存储**：仅存 SHA-256 哈希值，明文不落盘
- **会话管理**：Flask 签名 Cookie，`sessionStorage` 关闭标签页即失效
- **请求验证**：每次 `/ask` 都重新验证密码
- **内部鉴权**：服务间通信通过 `INTERNAL_TOKEN`（自动生成 64 字符 hex）
- **用户隔离**：对话记忆、文件存储、自定义专家均按 `user_id` 隔离
- **OASIS API Key 掩码机制**：外部 API 密钥（如 `OPENCLAW_GATEWAY_TOKEN`）不会在 YAML 或前端画布中暴露明文。YAML 中设置 `api_key: "****"` 即可，系统运行时自动从环境变量读取真实密钥。

</details>

---

<details>
<summary><h2>项目结构</h2></summary>

```
TeamClaw/
├── run.sh / run.ps1               # 一键运行
├── scripts/                       # 环境配置、启动、隧道、用户管理脚本
├── packaging/                     # Windows exe / macOS DMG 打包
├── chatbot/                       # 外部 Bot 服务
│   ├── telegrambot.py             # Telegram Bot（文字/图片/语音）
│   ├── QQbot.py                   # QQ Bot（私聊/群聊，SILK 转码）
│   └── setup.py                   # Bot 配置助手
├── config/
│   ├── .env                       # API Key 等环境变量
│   ├── requirements.txt           # Python 依赖
│   └── users.json                 # 用户名-密码哈希
├── data/
│   ├── agent_memory.db            # 对话记忆（SQLite）
│   ├── prompts/                   # 系统提示词 + 专家配置
│   ├── schedules/                 # YAML 调度示例
│   ├── oasis_user_experts/        # 用户自定义专家
│   ├── timeset/                   # 定时任务持久化
│   └── user_files/                # 用户文件（按用户隔离）
├── src/
│   ├── mainagent.py               # OpenAI 兼容 API + Agent 核心
│   ├── agent.py                   # LangGraph 工作流 + 工具编排
│   ├── front.py                   # Flask Web UI
│   ├── time.py                    # 定时调度中心
│   └── mcp_*.py                   # 7 个 MCP 工具服务
├── oasis/
│   ├── server.py                  # OASIS FastAPI 服务
│   ├── engine.py                  # 讨论引擎
│   ├── experts.py                 # 专家定义 + 用户专家存储
│   ├── scheduler.py               # YAML 调度解析与执行
│   ├── forum.py                   # 论坛数据结构
│   └── models.py                  # Pydantic 模型
├── tools/
│   └── gen_password.py            # 密码哈希生成
└── test/
    ├── chat.py                    # 命令行测试客户端
    └── view_history.py            # 查看历史聊天记录
```

</details>

---

<details>
<summary><h2>技术栈</h2></summary>

| 层面 | 技术 |
|------|------|
| LLM | DeepSeek (`deepseek-chat`) |
| Agent 框架 | LangGraph + LangChain |
| 工具协议 | MCP (Model Context Protocol) |
| 后端 | FastAPI + Flask |
| 认证 | SHA-256 哈希 + Flask Session |
| 定时调度 | APScheduler |
| 持久化 | SQLite (aiosqlite) |
| 前端 | Tailwind CSS + Marked.js + Highlight.js |

</details>

## 许可证

MIT License
