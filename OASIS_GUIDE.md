# OASIS External Usage Guide

> For TeamClaw deployment/config, see [SKILL.md](./SKILL.md). This doc focuses on OASIS usage, especially OpenClaw integration.

---

## Four Agent Types

| # | Type | Name Format | Engine Class | Stateful | Backend |
|---|------|-------------|-------------|----------|---------|
| 1 | Direct LLM | `tag#temp#N` | `ExpertAgent` | No | Local LLM |
| 2 | Oasis Session | `tag#oasis#id` | `SessionExpert` (oasis) | Yes | Internal bot API |
| 3 | Regular Agent | `Title#session_id` | `SessionExpert` (regular) | Yes | Internal bot API |
| 4 | External API | `tag#ext#id` | `ExternalExpert` | Yes (assumed) | External HTTP API |

### Type 1: Direct LLM (`tag#temp#N`)

Stateless single LLM call. Each round: reads all posts, one LLM call, publish + vote. No cross-round memory. `tag` maps to preset expert (name/persona), `N` is instance number.

```yaml
- expert: "creative#temp#1"
  instruction: "Focus on innovation"    # optional
```

### Type 2: Oasis Session (`tag#oasis#id`)

OASIS-managed stateful bot session. `tag` maps to preset, persona injected as system prompt on first round. Bot retains conversation memory across rounds. `id` can be any string, new ID auto-creates session.

```yaml
- expert: "data#oasis#analysis01"
- expert: "synthesis#oasis#fresh#new"    # #new forces new session (UUID)
```

### Type 3: Regular Agent Session (`Title#session_id`)

Connects to existing agent session (e.g. `Assistant#default`). No identity injection. The session's own system prompt defines the agent.

```yaml
- expert: "Assistant#default"
- expert: "Coder#my-project"
```

### Type 4: External API (`tag#ext#id`) — OpenClaw & Others

Directly calls any OpenAI-compatible API. External service assumed stateful. Sends incremental context (first call = full, subsequent = delta only).

```yaml
- expert: "analyst#ext#ds1"
  api_url: "https://api.deepseek.com"
  api_key: "****"                    # Masked — real key auto-read from OPENCLAW_API_KEY env var
  model: "deepseek-chat"
  headers:
    X-Custom-Header: "value"
  instruction: "Analyze from data perspective"
```

> 🔒 **API Key Security**: Set `api_key: "****"` (or omit it) and the system auto-reads the real key from the `OPENCLAW_API_KEY` environment variable at runtime. Plaintext keys still work (backward compatible).

### Special Suffix: `#new`

Appending `#new` forces a brand new session (ID replaced with random UUID):

```yaml
- expert: "creative#oasis#abc#new"      # UUID replaces "abc"
- expert: "Assistant#my-session#new"    # UUID replaces "my-session"
```

---

## YAML Control Directives

### Top-Level Fields

```yaml
version: 1              # Required (currently 1)
repeat: true/false       # true = repeat plan each round; false = run once
discussion: true/false   # true = forum discussion; false = execution mode
plan: [...]              # Required: list of steps
```

### Five Step Types

#### 1. `expert` — Single Expert (Sequential)

```yaml
- expert: "critical#temp#1"
  instruction: "Focus on risks"
  api_url: "https://..."          # only for #ext#
  api_key: "****"               # only for #ext#, masked — auto-read from env
  model: "deepseek-chat"          # only for #ext#
  headers:                        # only for #ext#
    x-openclaw-session-key: "agent:main:test1"
```

#### 2. `parallel` — Multiple Experts (Concurrent)

```yaml
- parallel:
    - expert: "creative#temp#1"
      instruction: "Innovation angle"
    - expert: "critical#temp#2"
      instruction: "Risk analysis"
```

#### 3. `all_experts` — All Pool Experts Speak

```yaml
- all_experts: true
```

#### 4. `manual` — Inject Post (No LLM)

```yaml
- manual:
    author: "Moderator"
    content: "Focus on feasibility"
    reply_to: null
```

#### 5. Mix freely

```yaml
plan:
  - manual: ...
  - parallel: [...]
  - expert: ...
  - all_experts: true
```

### Type 4 Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `expert` | Yes | Name (format determines type) |
| `instruction` | No | Per-step instruction |
| `api_url` | Yes (ext) | Base URL (auto-completes to `/v1/chat/completions`) |
| `api_key` | No | Use `****` mask — auto-read from `OPENCLAW_API_KEY` env var. Plaintext also supported. |
| `model` | No | Default `gpt-3.5-turbo` |
| `headers` | No | Extra HTTP headers (dict) |

---

## OpenClaw Integration

### Prerequisites

```bash
bash selfskill/scripts/run.sh configure --batch \
  OPENCLAW_SESSIONS_FILE=/path/to/agents/main/sessions/sessions.json \
  OPENCLAW_API_URL=http://127.0.0.1:18789/v1/chat/completions \
  OPENCLAW_API_KEY=your-key
```

| Variable | Description |
|----------|-------------|
| `OPENCLAW_SESSIONS_FILE` | Path to OpenClaw `sessions.json`. Required for visual Canvas. |
| `OPENCLAW_API_URL` | Full path with `/v1/chat/completions`. Must match gateway port. |
| `OPENCLAW_API_KEY` | API key (if auth enabled). |

> LLM API and OpenClaw API are completely separate credentials!

### `model` Format

```
agent:<agent_name>:<session_name>
```

Examples: `agent:main:default`, `agent:main:test1`, `agent:main:code-review`
Non-existent sessions are auto-created.

### `x-openclaw-session-key` — Deterministic Session Routing

**The key mechanism** for routing to a specific OpenClaw session.

- Visual Canvas **auto-sets** this header when dragging OpenClaw sessions
- Manual YAML: **must** include in `headers`
- Value **must match** `model` field

### Complete OpenClaw Config

```yaml
- expert: "coder#ext#oc1"
  api_url: "http://127.0.0.1:18789"
  api_key: "****"                                  # Masked — real key from OPENCLAW_API_KEY env var
  model: "agent:main:my-session"
  headers:
    x-openclaw-session-key: "agent:main:my-session"
  instruction: "Implement login feature"
```

### Request Headers Sent

```
Content-Type: application/json
Authorization: Bearer <resolved_api_key>   # The actual key resolved from env var (never visible in YAML)
x-openclaw-session-key: agent:main:my-session
```

### Multi-OpenClaw Pipeline

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

## Operating Modes

### Two Orthogonal Switches

| | Discussion (`true`) | Execution (`false`) |
|-|---------------------|---------------------|
| **Sync** (`detach=false`) | Forum debate, returns conclusion | Direct deliverables |
| **Async** (`detach=true`) | Returns topic_id, check later | Returns topic_id, check later |

### Discussion Mode (`discussion=true`)

JSON responses with `content`, `reply_to`, `votes`. LLM summarizer produces final conclusion.
Use: reviews, debates, multi-perspective analysis.

### Execution Mode (`discussion=false`)

Direct task output (code/plans/reports). No voting. Output = concatenation.
Use: code generation, pipelines, automated workflows.

### `repeat` Flag

| `repeat` | Behavior |
|----------|----------|
| `true` | Plan repeats `max_rounds` times. For iterative discussions. |
| `false` | Steps run once sequentially. `max_rounds` ignored. For pipelines. |

---

## API Reference

Base URL: `http://127.0.0.1:51202`

### Create Topic

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

### Check / Stream / Cancel

```bash
curl 'http://127.0.0.1:51202/topics/{id}?user_id=system'
curl 'http://127.0.0.1:51202/topics/{id}/conclusion?user_id=system&timeout=300'
curl 'http://127.0.0.1:51202/topics/{id}/stream?user_id=system'
curl -X DELETE 'http://127.0.0.1:51202/topics/{id}?user_id=system'
curl 'http://127.0.0.1:51202/topics?user_id=system'
```

### Expert Management

```bash
curl 'http://127.0.0.1:51202/experts?user_id=system'
curl -X POST 'http://127.0.0.1:51202/experts/user' -H 'Content-Type: application/json' \
  -d '{"user_id":"system","name":"PM","tag":"pm","persona":"...","temperature":0.7}'
curl -X PUT 'http://127.0.0.1:51202/experts/user/pm' -H 'Content-Type: application/json' \
  -d '{"user_id":"system","persona":"updated"}'
curl -X DELETE 'http://127.0.0.1:51202/experts/user/pm?user_id=system'
```

### Workflow Management

```bash
curl -X POST 'http://127.0.0.1:51202/workflows' -H 'Content-Type: application/json' \
  -d '{"user_id":"system","name":"wf","schedule_yaml":"..."}'
curl 'http://127.0.0.1:51202/workflows?user_id=system'
curl -X POST 'http://127.0.0.1:51202/layouts/from-yaml' -H 'Content-Type: application/json' \
  -d '{"user_id":"system","yaml_source":"...","layout_name":"layout1"}'
```

### Storage

| Data | Path |
|------|------|
| Workflows | `data/user_files/{user}/oasis/yaml/` |
| Custom experts | `data/oasis_user_experts/{user}.json` |
| Topics | `data/oasis_topics/{user}/{topic_id}.json` |
| Session memory | `data/agent_memory.db` |

---

## Examples

### Simple Discussion

```yaml
version: 1
repeat: true
discussion: true
plan:
  - all_experts: true
```

### Phased Pipeline

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

### Mixed Agents

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

### Stateful Oasis Sessions (Multi-Phase)

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

## Troubleshooting

| Symptom | Solution |
|---------|----------|
| "name has no '#', skipping" | Use format: `tag#temp#N`, `tag#oasis#id`, `Title#sid`, `tag#ext#id` |
| "missing 'api_url'" | Add `api_url` to Type 4 expert |
| Wrong OpenClaw session | Add `headers: {x-openclaw-session-key: ...}` matching `model` |
| Canvas missing OpenClaw sessions | Set `OPENCLAW_SESSIONS_FILE` in `.env` |
| API timeout | Check port, verify OpenAI-compatible interface enabled |

**Debug**: Check `logs/launcher.log` for `[OASIS]` messages. Use SSE stream for real-time monitoring.

---

## Quick Reference

| Task | Config |
|------|--------|
| Quick opinions | `tag#temp#N` + `discussion: true` |
| Stateful sessions | `tag#oasis#id` + `repeat: true` |
| Existing bot | `Title#session_id` |
| OpenClaw agents | `tag#ext#id` + `api_url` + `model` + `headers: {x-openclaw-session-key}` |
| External LLMs | `tag#ext#id` + `api_url` + `api_key` |
| Pipeline | `repeat: false` |
| Iterative | `repeat: true` + `discussion: true` |
| Background | `callback_url` + `callback_session_id` |

> See [SKILL.md](./SKILL.md) for full deployment docs.
