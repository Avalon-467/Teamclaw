# Mini TimeBot 端口大全

> 最后更新：2026-03-13

## 端口总览

| 端口 | 环境变量 | 服务文件 | 说明 | 绑定地址 | 对外暴露 |
|------|----------|----------|------|----------|----------|
| **51200** | `PORT_AGENT` | `src/mainagent.py` | AI Agent 主服务（OpenAI 兼容 API） | `127.0.0.1` | ❌ |
| **51201** | `PORT_SCHEDULER` | `src/time.py` | 定时任务调度中心 | `127.0.0.1` | ❌ |
| **51202** | `PORT_OASIS` | `oasis/server.py` | OASIS 论坛 / Agent 管理与编排中心 | `127.0.0.1` | ❌ |
| **51209** | `PORT_FRONTEND` | `src/front.py` | 前端 Web UI（Flask） | `0.0.0.0` | ✅ Tunnel |
| **51210** | —（硬编码） | `visual/main.py` | 可视化编排系统（开发用） | `0.0.0.0` | ❌ |
| **58010** | `PORT_BARK` | 外部二进制 `bin/bark-server` | Bark 推送服务器 | — | ✅ Tunnel |
| **18789** | `OPENCLAW_API_URL`（可选） | 外部服务 | OpenClaw 后端（外部集成） | 不适用 | 不适用 |

## 详细说明

### 51200 — AI Agent 主服务

- **文件**：`src/mainagent.py`
- **职责**：
  - 提供 OpenAI 兼容的 `/v1/chat/completions` 接口
  - Agent 核心逻辑（工具调用、多轮对话、记忆管理）
  - `/system_trigger` 内部触发端点（定时任务回调等）
  - `/login`、`/sessions`、`/tools`、`/tts`、`/settings`、`/groups` 等 API
- **调用方**：前端 `front.py`（代理转发）、chatbot、MCP 模块、OASIS 回调
- **鉴权**：`X-Internal-Token` 或用户密码

### 51201 — 定时任务调度中心

- **文件**：`src/time.py`
- **职责**：
  - 管理 cron / 一次性定时任务
  - 提供 `/tasks` 端点供 `mcp_scheduler.py` 调用
  - 任务到期时回调 Agent 的 `/system_trigger`
- **调用方**：`mcp_scheduler.py`、Agent 内部

### 51202 — OASIS 论坛服务

- **文件**：`oasis/server.py`
- **职责**：
  - 多专家讨论引擎（Topics / Experts / Sessions）
  - OpenClaw 快照管理
  - `/publicnet/info` 公网信息查询
  - Agent 管理与编排中心（迁移中）
- **调用方**：`mcp_oasis.py`、前端代理、外部脚本
- **注意**：默认绑定 `127.0.0.1`，可用 `--host 0.0.0.0` 启动

### 51209 — 前端 Web UI

- **文件**：`src/front.py`
- **职责**：
  - 用户交互界面（聊天、登录、设置、OASIS 面板）
  - 反向代理：将浏览器请求转发到 Agent / OASIS 等内部服务
  - Session 管理、PWA 支持
- **安全策略**：
  - 本地直连（`127.0.0.1`，无 CF 头）→ 信任放行
  - Cloudflare Tunnel 流量（`127.0.0.1` + `Cf-*` 头）→ 要求 Session 登录
  - 公开路由（login、static、OpenAI compat）→ 始终放行
- **唯一对外暴露的核心端口**

### 51210 — 可视化编排系统（开发用）

- **文件**：`visual/main.py`
- **职责**：独立 Flask 应用，提供 2D 画布拖拽编排 Agent 节点，导出 OASIS 兼容的 YAML 工作流
- **注意**：不在 `launcher.py` 启动序列中，需手动 `python visual/main.py` 启动

### 58010 — Bark 推送服务器

- **来源**：外部二进制 `bin/bark-server`
- **职责**：接收推送请求并转发到 iOS/macOS 设备
- **数据**：`data/bark/bark.db`
- **公网地址**：由 tunnel 写入 `BARK_PUBLIC_URL`

### 18789 — OpenClaw 后端（可选）

- **来源**：外部 OpenClaw Gateway 服务
- **职责**：连接外部 Agent Session，在 OASIS 工作流 YAML 中作为 `api_url` 引用
- **条件**：仅在配置了 OpenClaw 集成时使用

## 启动顺序

由 `scripts/launcher.py` 定义：

| 步骤 | 服务 | 端口 | 等待时间 |
|------|------|------|----------|
| 1/5 | 定时调度中心 | 51201 | 2s |
| 2/5 | OASIS 论坛 | 51202 | 2s |
| 3/5 | AI Agent | 51200 | 3s |
| 4/5 | Chatbot 配置 | — | 交互式 |
| 5/5 | 前端 Web UI | 51209 | 1s |

## Tunnel 暴露策略

由 `scripts/tunnel.py` 管理：

```
公网用户
  ↓ HTTPS
[Cloudflare Tunnel]
  ├─→ 127.0.0.1:51209 (front.py)    → PUBLIC_DOMAIN
  └─→ 127.0.0.1:58010 (bark-server) → BARK_PUBLIC_URL
```

- Tunnel 只暴露 `front.py` 和 `bark-server`
- 所有内部服务（Agent、Scheduler、OASIS）**不对外暴露**
- 前端到内部服务的通信全部通过 `front.py` 反向代理

## 环境变量配置

在 `config/.env` 中设置（一般无需修改默认值）：

```env
PORT_AGENT=51200
PORT_SCHEDULER=51201
PORT_OASIS=51202
PORT_FRONTEND=51209
```

---

## 反向代理安全检查

> 以下是 `front.py` 中实施的安全措施，以及常见反向代理攻防场景说明。

### 当前已实施的安全层

#### 1. Tunnel 流量识别（Loopback 信任分离）

**威胁**：Cloudflare Tunnel（cloudflared）在本机运行，转发公网流量到 `127.0.0.1:51209`，导致 `remote_addr` = `127.0.0.1`。如果无差别信任 loopback，公网攻击者可绕过登录。

**措施**：检测 Cloudflare 注入的特征头来区分：

| 检测头 | 说明 |
|--------|------|
| `Cf-Connecting-Ip` | 真实客户端 IP |
| `Cf-Ray` | 请求的唯一追踪 ID |
| `Cf-Ipcountry` | 客户端所在国家 |

**逻辑**：
```python
# 本地直连（无 CF 头）→ 信任
if _is_loopback_request() and not _is_tunnel_request():
    return None  # 放行

# 经 tunnel 进来（有 CF 头）→ 必须登录
if not session.get('user_id'):
    return 401
```

| 场景 | remote_addr | CF 头 | 结果 |
|------|-------------|-------|------|
| 本地浏览器直连 | `127.0.0.1` | ❌ 无 | ✅ 信任放行 |
| 本地 agent / MCP 工具 | `127.0.0.1` | ❌ 无 | ✅ 信任放行 |
| 公网经 Cloudflare Tunnel | `127.0.0.1` | ✅ 有 | ⛔ 要求 Session 登录 |
| 外网直连（无 tunnel） | 外部 IP | ❌ 无 | ⛔ 要求 Session 登录 |

#### 2. 代理头伪造检测（Header Injection 防御）

**威胁**：攻击者在**非代理**的直连请求中伪造 `X-Forwarded-For`、`X-Real-Ip` 等头，试图欺骗应用认为请求来自可信 IP。

**措施**：如果请求不是来自已知代理（无 CF 头），但携带了代理专属头，直接拒绝（403）：

```
被检测的伪造头：
├── X-Forwarded-For
├── X-Forwarded-Proto
├── X-Forwarded-Host
└── X-Real-Ip
```

**为什么重要**：很多应用使用 `X-Forwarded-For` 的第一个值做 IP 访问控制，如果不清洗这些头，攻击者可以伪造成任意 IP。

#### 3. URL / 请求头注入防御

**威胁**：
- **Null byte 注入**（`%00`）：在 URL 中插入空字节，可能导致路径截断、绕过安全检查、目录遍历
- **超长 URL / Header**：通过异常长的 URL 或头值，造成缓冲区溢出、DoS、或 smuggling 攻击

**措施**：
| 检查项 | 阈值 | 响应码 |
|--------|------|--------|
| URL 中含 `\x00` 或 `%00` | 发现即拒绝 | 400 |
| URL 总长度 | > 8192 字节 | 414 |
| 任意 Header 值 | > 8192 字节 | 431 |

#### 4. 内部服务通信鉴权

**措施**：`front.py` 向内部服务（Agent、OASIS）转发请求时，使用 `X-Internal-Token` 而非用户密码：

```
浏览器 → front.py (Session 鉴权) → Agent/OASIS (X-Internal-Token 鉴权)
```

这确保即使 Session 被窃取，也无法直接调用内部 API（因为 `INTERNAL_TOKEN` 不会暴露给浏览器）。

### 常见反向代理攻击场景 & 应对

#### 🔴 HTTP Request Smuggling

**描述**：利用前端代理（如 Nginx）和后端应用对 HTTP 请求边界的解析差异，在一个 TCP 连接中"走私"第二个请求。

**本项目风险**：**低**。`front.py` 使用 Python `requests` 库向后端发起**独立的** HTTP 请求（不是 TCP 流量透传），每次转发都是全新连接，不存在连接复用的 smuggling 窗口。

**如果将来加 Nginx**：需要：
- 确保 Nginx 和 Flask 使用相同的 HTTP 解析器行为
- 禁用 Nginx 的 `proxy_http_version 1.0`，改用 `1.1`
- 设置 `proxy_request_buffering on`

#### 🔴 SSRF（Server-Side Request Forgery）

**描述**：攻击者通过代理让服务器向内部网络发请求（如 `http://127.0.0.1:51200/admin`）。

**本项目风险**：**低**。`front.py` 的代理端点都是**硬编码目标 URL**（如 `LOCAL_AGENT_URL`），不接受用户指定 URL。没有"开放代理"端点。

**检查清单**：
- ✅ 所有 `requests.get/post` 的 URL 是硬编码常量
- ✅ 没有 `url = request.args.get('url')` 模式
- ✅ 用户输入只作为 JSON body / query param，不拼接到 URL 路径中

#### 🔴 Host Header 攻击

**描述**：攻击者伪造 `Host` 头，可导致缓存投毒、密码重置链接篡改、或绕过虚拟主机路由。

**本项目风险**：**低**。`front.py` 不使用 `request.host` 来生成任何 URL 或做路由决策。内部转发的目标地址都是硬编码的 `127.0.0.1:PORT`。

**如果将来使用 `url_for(..., _external=True)`**：需要限制 `Host` 头的合法值。

#### 🔴 WebSocket 劫持（Cross-Site WebSocket Hijacking）

**描述**：恶意网页通过 JavaScript 发起 WebSocket 连接到目标应用，浏览器会自动带上 Cookie。如果服务端不校验 Origin，攻击者可以代替用户操作。

**本项目风险**：**中等**。前端使用 SSE（Server-Sent Events）而非 WebSocket，但如果将来引入 WebSocket：
- 必须在握手阶段校验 `Origin` 头
- 必须校验 Session

#### 🟡 Session 固定 / Session 劫持

**描述**：攻击者获取或固定一个 Session ID，然后以受害者身份访问。

**当前措施**：
- ✅ `session.permanent = True` + 8 小时过期
- ✅ 登录成功后设置新 session
- ⚠️ `app.secret_key = os.urandom(24)`：每次重启生成新密钥，所有旧 session 失效（安全但用户需重新登录）
- ⚠️ 未设置 `SESSION_COOKIE_SECURE`（因为本地开发可能非 HTTPS）
- ⚠️ 未设置 `SESSION_COOKIE_HTTPONLY`（建议开启，防止 XSS 读取 Cookie）
- ⚠️ 未设置 `SESSION_COOKIE_SAMESITE`（建议设为 `Lax`，防止 CSRF）

**建议加固**（在检测到 tunnel/公网模式时自动启用）：
```python
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# 如果配置了 PUBLIC_DOMAIN（HTTPS 公网）：
# app.config['SESSION_COOKIE_SECURE'] = True
```

#### 🟡 CORS 配置

**当前状态**：仅 `/v1/chat/completions`（OpenAI 兼容端点）设置了 `Access-Control-Allow-Origin: *`。

**风险**：该端点本身有独立的 Authorization Bearer Token 鉴权，`*` 是合理的（兼容第三方客户端）。其他端点未设置 CORS 头，浏览器同源策略默认拦截跨域请求，这是安全的。

**注意**：如果将来某个端点需要跨域，不要用 `*` + `credentials: include`，这会导致 Cookie 泄露。

### 安全检查速查表

| 检查项 | 状态 | 说明 |
|--------|------|------|
| Tunnel 流量识别 | ✅ 已实施 | 通过 CF 头区分本地 vs tunnel |
| 代理头伪造检测 | ✅ 已实施 | 拒绝直连中携带 `X-Forwarded-*` |
| Null byte 注入 | ✅ 已实施 | URL 中 `\x00` / `%00` → 400 |
| 超长 URL/Header | ✅ 已实施 | > 8KB → 414/431 |
| 内部通信鉴权 | ✅ 已实施 | `X-Internal-Token` |
| Session 过期 | ✅ 已实施 | 8 小时自动过期 |
| SSRF 防御 | ✅ 架构安全 | 无开放代理端点 |
| Request Smuggling | ✅ 架构安全 | 独立连接转发，无流复用 |
| Host Header 攻击 | ✅ 架构安全 | 不依赖 Host 头 |
| Cookie HttpOnly | ⚠️ 建议加固 | 防 XSS 读取 Session Cookie |
| Cookie SameSite | ⚠️ 建议加固 | 防 CSRF |
| Cookie Secure | ⚠️ 公网部署时 | HTTPS 场景下启用 |
| WebSocket Origin | ℹ️ 暂不适用 | 当前使用 SSE，无 WS |
| CORS | ✅ 合理配置 | 仅 OpenAI 端点允许 `*` |
