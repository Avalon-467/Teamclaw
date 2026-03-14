#!/usr/bin/env python3
"""
TeamClaw CLI — 命令行控制工具

像人操作前端一样，通过命令行控制 Agent 的各项功能。
直接调用后端 API（绕过 front.py session），使用 INTERNAL_TOKEN 认证。

用法:  python scripts/cli.py <command> [options]
"""
import argparse, json, os, signal, subprocess, sys, time
import urllib.error, urllib.parse, urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# ── 加载 .env ────────────────────────────────────────────────────────
def _load_env():
    env_path = os.path.join(PROJECT_ROOT, "config", ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k and k not in os.environ:
                os.environ[k] = v

_load_env()

PORT_AGENT = int(os.getenv("PORT_AGENT", "51200"))
PORT_OASIS = int(os.getenv("PORT_OASIS", "51202"))
PORT_FRONTEND = int(os.getenv("PORT_FRONTEND", "51209"))
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "")
AGENT_BASE = f"http://127.0.0.1:{PORT_AGENT}"
OASIS_BASE = f"http://127.0.0.1:{PORT_OASIS}"
DEFAULT_USER = os.getenv("CLI_USER", "admin")


# ═══════════════════════════════════════════════════════════════════════
#  HTTP 工具
# ═══════════════════════════════════════════════════════════════════════

def _req(method, url, headers=None, data=None, params=None, timeout=30):
    """发送 HTTP 请求，返回 (status, body_dict_or_bytes)"""
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body_bytes = None
    if data is not None:
        body_bytes = json.dumps(data).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body_bytes, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ct = resp.headers.get("Content-Type", "")
            raw = resp.read()
            if "json" in ct:
                return resp.status, json.loads(raw)
            return resp.status, raw
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
        except Exception:
            err = {"error": e.reason}
        return e.code, err
    except urllib.error.URLError as e:
        return 0, {"error": f"连接失败: {e.reason}"}

def _stream_req(url, headers=None, data=None, params=None, timeout=300):
    """SSE 流式请求，yield 每行"""
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body_bytes = json.dumps(data).encode("utf-8") if data else None
    hdrs = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body_bytes, headers=hdrs, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        for raw_line in resp:
            yield raw_line.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.reason}", file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"❌ 连接失败: {e.reason}", file=sys.stderr)

def _agent_headers():
    return {"X-Internal-Token": INTERNAL_TOKEN}

def _group_headers(user_id):
    return {"Authorization": f"Bearer {INTERNAL_TOKEN}:{user_id}"}

def _check_token():
    if not INTERNAL_TOKEN:
        print("❌ INTERNAL_TOKEN 未配置，请先启动服务或在 config/.env 中设置", file=sys.stderr)
        sys.exit(1)

def _pp(obj):
    """美化打印 JSON"""
    print(json.dumps(obj, ensure_ascii=False, indent=2))

def _err(code, body):
    msg = body.get("error", body) if isinstance(body, dict) else body
    print(f"❌ [{code}] {msg}", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════════════
#  子命令实现
# ═══════════════════════════════════════════════════════════════════════

# ── chat: 发送消息 ───────────────────────────────────────────────────
def cmd_chat(args):
    """通过 OpenAI 兼容接口发送消息（流式输出）"""
    if not args.user:
        print("❌ 请指定 -u/--user 用户名", file=sys.stderr); return
    _check_token()
    url = f"{AGENT_BASE}/v1/chat/completions"
    payload = {
        "model": args.model or "default",
        "messages": [{"role": "user", "content": args.message}],
        "stream": True,
        "user": args.user,
    }
    payload["session_id"] = args.session
    hdrs = {"Authorization": f"Bearer {INTERNAL_TOKEN}:{args.user}"}

    collected = []
    for line in _stream_req(url, headers=hdrs, data=payload):
        line = line.strip()
        if not line or not line.startswith("data:"):
            continue
        data_str = line[5:].strip()
        if data_str == "[DONE]":
            break
        try:
            chunk = json.loads(data_str)
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            text = delta.get("content", "")
            if text:
                print(text, end="", flush=True)
                collected.append(text)
        except json.JSONDecodeError:
            pass
    if collected:
        print()  # 换行


# ── sessions: 会话管理 ──────────────────────────────────────────────
def cmd_sessions(args):
    """查看会话列表"""
    _check_token()
    code, body = _req("POST", f"{AGENT_BASE}/sessions",
                       headers=_agent_headers(),
                       data={"user_id": args.user})
    if code == 200:
        if isinstance(body, dict) and "sessions" in body:
            sessions = body["sessions"]
        elif isinstance(body, list):
            sessions = body
        else:
            _pp(body)
            return
        if not sessions:
            print("📭 暂无会话")
            return
        print(f"📋 会话列表 ({len(sessions)} 个):\n")
        for s in sessions:
            sid = s.get("session_id", s.get("id", "?"))
            title = s.get("title", s.get("name", ""))
            status = s.get("status", "")
            updated = s.get("updated_at", s.get("last_active", ""))
            flag = "🟢" if status == "active" else "⚪"
            line = f"  {flag} {sid}"
            if title:
                line += f"  {title}"
            if updated:
                line += f"  ({updated})"
            print(line)
    else:
        _err(code, body)


def cmd_history(args):
    """查看会话历史"""
    _check_token()
    data = {"user_id": args.user, "session_id": args.session or "default"}
    code, body = _req("POST", f"{AGENT_BASE}/session_history",
                       headers=_agent_headers(), data=data)
    if code == 200:
        messages = body if isinstance(body, list) else body.get("messages", body.get("history", [body]))
        if not messages:
            print("📭 暂无历史记录")
            return
        limit = args.limit or len(messages)
        for msg in messages[-limit:]:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            icon = {"user": "👤", "assistant": "🤖", "system": "⚙️", "tool": "🔧"}.get(role, "❓")
            if isinstance(content, list):
                content = " ".join(
                    p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
                ) or str(content)
            # 截断过长内容
            if len(content) > 500 and not args.full:
                content = content[:500] + "..."
            print(f"{icon} [{role}]: {content}\n")
    else:
        _err(code, body)


def cmd_delete_session(args):
    """删除会话"""
    _check_token()
    data = {"user_id": args.user, "session_id": args.session}
    code, body = _req("POST", f"{AGENT_BASE}/delete_session",
                       headers=_agent_headers(), data=data)
    if code == 200:
        print(f"✅ 会话 '{args.session}' 已删除")
    else:
        _err(code, body)


# ── settings: 设置 ──────────────────────────────────────────────────
def cmd_settings(args):
    """查看或修改设置"""
    _check_token()
    if args.set_key:
        # 修改设置
        data = {"user_id": args.user, args.set_key: args.set_value}
        code, body = _req("POST", f"{AGENT_BASE}/settings",
                           headers=_agent_headers(), data=data)
        if code == 200:
            print(f"✅ 设置已更新: {args.set_key} = {args.set_value}")
        else:
            _err(code, body)
    else:
        # 查看设置
        endpoint = "/settings/full" if args.full else "/settings"
        code, body = _req("GET", f"{AGENT_BASE}{endpoint}",
                           headers=_agent_headers(),
                           params={"user_id": args.user})
        if code == 200:
            _pp(body)
        else:
            _err(code, body)


# ── tools: 工具列表 ──────────────────────────────────────────────────
def cmd_tools(args):
    """查看可用工具"""
    _check_token()
    code, body = _req("GET", f"{AGENT_BASE}/tools",
                       headers=_agent_headers(),
                       params={"user_id": args.user})
    if code == 200:
        tools = body if isinstance(body, list) else body.get("tools", [body])
        if not tools:
            print("📭 无可用工具")
            return
        print(f"🔧 可用工具 ({len(tools)} 个):\n")
        for t in tools:
            name = t.get("name", t.get("function", {}).get("name", "?"))
            desc = t.get("description", t.get("function", {}).get("description", ""))
            print(f"  • {name}")
            if desc and not args.brief:
                print(f"    {desc[:100]}")
    else:
        _err(code, body)


# ── tts: 语音合成 ───────────────────────────────────────────────────
def cmd_tts(args):
    """文字转语音"""
    _check_token()
    data = {"user_id": args.user, "text": args.text}
    if args.voice:
        data["voice"] = args.voice
    code, body = _req("POST", f"{AGENT_BASE}/tts",
                       headers=_agent_headers(), data=data, timeout=60)
    if code == 200:
        if isinstance(body, bytes):
            out = args.output or "tts_output.mp3"
            with open(out, "wb") as f:
                f.write(body)
            print(f"✅ 音频已保存: {out} ({len(body)} bytes)")
        else:
            _pp(body)
    else:
        _err(code, body)


# ── cancel: 取消生成 ─────────────────────────────────────────────────
def cmd_cancel(args):
    """取消当前生成"""
    _check_token()
    data = {"user_id": args.user, "session_id": args.session or "default"}
    code, body = _req("POST", f"{AGENT_BASE}/cancel",
                       headers=_agent_headers(), data=data)
    if code == 200:
        print("✅ 已取消")
    else:
        _err(code, body)


# ── restart: 重启 Agent ──────────────────────────────────────────────
def cmd_restart(args):
    """重启 Agent 服务"""
    flag = os.path.join(PROJECT_ROOT, ".restart_flag")
    with open(flag, "w") as f:
        f.write("restart")
    print("✅ 重启信号已发送（等待 launcher 处理）")


# ── groups: 群组管理 ─────────────────────────────────────────────────
def cmd_groups(args):
    """群组管理"""
    hdrs = _group_headers(args.user)
    base = f"{AGENT_BASE}/groups"

    if args.action == "list":
        code, body = _req("GET", base, headers=hdrs)
        if code == 200:
            groups = body if isinstance(body, list) else body.get("groups", [body])
            if not groups:
                print("📭 暂无群组")
                return
            print(f"👥 群组列表 ({len(groups)} 个):\n")
            for g in groups:
                gid = g.get("id", g.get("group_id", "?"))
                name = g.get("name", "")
                print(f"  • [{gid}] {name}")
        else:
            _err(code, body)

    elif args.action == "create":
        data = json.loads(args.data) if args.data else {"name": args.name or "新群组"}
        code, body = _req("POST", base, headers=hdrs, data=data)
        if code in (200, 201):
            print("✅ 群组已创建")
            _pp(body)
        else:
            _err(code, body)

    elif args.action == "messages":
        if not args.group_id:
            print("❌ 请指定 --group-id", file=sys.stderr); return
        url = f"{base}/{args.group_id}/messages"
        code, body = _req("GET", url, headers=hdrs)
        if code == 200:
            msgs = body if isinstance(body, list) else body.get("messages", [body])
            for m in msgs[-20:]:
                sender = m.get("sender", m.get("user_id", "?"))
                content = m.get("content", "")
                print(f"  [{sender}]: {content}")
        else:
            _err(code, body)

    elif args.action == "send":
        if not args.group_id:
            print("❌ 请指定 --group-id", file=sys.stderr); return
        url = f"{base}/{args.group_id}/messages"
        data = {"content": args.message or ""}
        code, body = _req("POST", url, headers=hdrs, data=data)
        if code in (200, 201):
            print("✅ 消息已发送")
        else:
            _err(code, body)

    elif args.action == "get":
        if not args.group_id:
            print("❌ 请指定 --group-id", file=sys.stderr); return
        code, body = _req("GET", f"{base}/{args.group_id}", headers=hdrs)
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif args.action == "update":
        if not args.group_id:
            print("❌ 请指定 --group-id", file=sys.stderr); return
        data = json.loads(args.data) if args.data else {}
        code, body = _req("PUT", f"{base}/{args.group_id}", headers=hdrs, data=data)
        if code == 200:
            print("✅ 群组已更新")
            _pp(body)
        else:
            _err(code, body)

    elif args.action == "delete":
        if not args.group_id:
            print("❌ 请指定 --group-id", file=sys.stderr); return
        code, body = _req("DELETE", f"{base}/{args.group_id}", headers=hdrs)
        if code == 200:
            print(f"✅ 群组 {args.group_id} 已删除")
        else:
            _err(code, body)

    elif args.action == "mute":
        if not args.group_id:
            print("❌ 请指定 --group-id", file=sys.stderr); return
        code, body = _req("POST", f"{base}/{args.group_id}/mute", headers=hdrs)
        if code == 200:
            print("✅ 群组已静音")
        else:
            _err(code, body)

    elif args.action == "unmute":
        if not args.group_id:
            print("❌ 请指定 --group-id", file=sys.stderr); return
        code, body = _req("POST", f"{base}/{args.group_id}/unmute", headers=hdrs)
        if code == 200:
            print("✅ 群组已取消静音")
        else:
            _err(code, body)

    elif args.action == "mute-status":
        if not args.group_id:
            print("❌ 请指定 --group-id", file=sys.stderr); return
        code, body = _req("GET", f"{base}/{args.group_id}/mute_status", headers=hdrs)
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif args.action == "sessions":
        if not args.group_id:
            print("❌ 请指定 --group-id", file=sys.stderr); return
        code, body = _req("GET", f"{base}/{args.group_id}/sessions", headers=hdrs)
        if code == 200:
            _pp(body)
        else:
            _err(code, body)


# ── sessions-status: 所有会话忙碌状态 ────────────────────────────────
def cmd_sessions_status(args):
    """查看所有会话的忙碌状态"""
    _check_token()
    code, body = _req("POST", f"{AGENT_BASE}/sessions_status",
                       headers=_agent_headers(),
                       data={"user_id": args.user})
    if code == 200:
        _pp(body)
    else:
        _err(code, body)


# ── session-status: 单个会话状态 ─────────────────────────────────────
def cmd_session_status(args):
    """查看单个会话是否有新消息"""
    _check_token()
    data = {"user_id": args.user, "session_id": args.session or "default"}
    code, body = _req("POST", f"{AGENT_BASE}/session_status",
                       headers=_agent_headers(), data=data)
    if code == 200:
        _pp(body)
    else:
        _err(code, body)


# ── topics: OASIS 话题 ───────────────────────────────────────────────
def cmd_topics(args):
    """OASIS 话题管理"""
    params = {"user_id": args.user}

    if args.action == "list":
        code, body = _req("GET", f"{OASIS_BASE}/topics", params=params)
        if code == 200:
            topics = body if isinstance(body, list) else body.get("topics", [body])
            if not topics:
                print("📭 暂无话题")
                return
            print(f"💬 OASIS 话题 ({len(topics)} 个):\n")
            for t in topics:
                tid = t.get("id", t.get("topic_id", "?"))
                title = t.get("title", t.get("question", ""))
                status = t.get("status", "")
                print(f"  • [{tid}] {title}  ({status})")
        else:
            _err(code, body)

    elif args.action == "show":
        if not args.topic_id:
            print("❌ 请指定 --topic-id", file=sys.stderr); return
        code, body = _req("GET", f"{OASIS_BASE}/topics/{args.topic_id}", params=params)
        if code == 200:
            if args.raw:
                _pp(body)
                return
            # ── 美化输出 ──
            q = body.get("question", "")
            status = body.get("status", "?")
            cur_r = body.get("current_round", "?")
            max_r = body.get("max_rounds", "?")
            is_disc = body.get("discussion", True)
            status_icon = {"pending": "⏳", "discussing": "🔄", "concluded": "✅",
                           "error": "❌"}.get(status, "❓")
            print(f"{'─' * 60}")
            print(f"📋 话题: {q}")
            print(f"   状态: {status_icon} {status}  |  轮次: {cur_r}/{max_r}  |  {'讨论模式' if is_disc else '执行模式'}")
            print(f"{'─' * 60}")

            # 时间线（执行模式下更有意义，讨论模式也展示）
            timeline = body.get("timeline", [])
            if timeline:
                print(f"\n⏱️  时间线 ({len(timeline)} 事件):")
                for ev in timeline:
                    elapsed = ev.get("elapsed", 0)
                    event = ev.get("event", "")
                    agent = ev.get("agent", "")
                    detail = ev.get("detail", "")
                    ev_icon = {"start": "🚀", "round": "📢", "agent_call": "⏳",
                               "agent_done": "✅", "conclude": "🏁"}.get(event, "•")
                    parts = [f"  {ev_icon} [{elapsed:.1f}s] {event}"]
                    if agent:
                        parts.append(agent)
                    if detail:
                        parts.append(f"— {detail}")
                    print(" ".join(parts))

            # 帖子/发言
            posts = body.get("posts", [])
            if posts:
                print(f"\n💬 发言记录 ({len(posts)} 条):\n")
                for p in posts:
                    author = p.get("author", "?")
                    content = p.get("content", "")
                    reply_to = p.get("reply_to")
                    upvotes = p.get("upvotes", 0)
                    elapsed = p.get("elapsed", 0)
                    pid = p.get("id", "?")

                    header = f"  ┌─ #{pid} [{author}]"
                    if reply_to:
                        header += f" ↳回复#{reply_to}"
                    header += f"  ({elapsed:.1f}s)"
                    if upvotes:
                        header += f"  👍{upvotes}"
                    print(header)

                    # 内容缩进显示，限制过长内容
                    lines = content.strip().split("\n")
                    max_lines = 30 if not args.full else len(lines)
                    for i, line in enumerate(lines[:max_lines]):
                        print(f"  │ {line}")
                    if len(lines) > max_lines:
                        print(f"  │ ... (共 {len(lines)} 行，用 --full 查看完整)")
                    print(f"  └{'─' * 40}")
            else:
                print("\n📭 暂无发言")

            # 结论
            conclusion = body.get("conclusion")
            if conclusion:
                print(f"\n{'═' * 60}")
                print(f"🏆 结论:\n")
                print(conclusion)
                print(f"{'═' * 60}")
        else:
            _err(code, body)

    elif args.action == "watch":
        if not args.topic_id:
            print("❌ 请指定 --topic-id", file=sys.stderr); return
        print(f"👀 实时跟踪话题 {args.topic_id}（Ctrl+C 退出）...\n")
        stream_url = f"{OASIS_BASE}/topics/{args.topic_id}/stream"
        if params:
            stream_url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(stream_url, method="GET",
                                      headers={"Accept": "text/event-stream"})
        try:
            resp = urllib.request.urlopen(req, timeout=600)
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        print("\n✅ 讨论结束")
                        break
                    print(data_str)
        except KeyboardInterrupt:
            print("\n⏹️ 已停止跟踪")
        except urllib.error.HTTPError as e:
            print(f"❌ HTTP {e.code}: {e.reason}", file=sys.stderr)
        except urllib.error.URLError as e:
            print(f"❌ 连接失败: {e.reason}", file=sys.stderr)

    elif args.action == "cancel":
        if not args.topic_id:
            print("❌ 请指定 --topic-id", file=sys.stderr); return
        code, body = _req("DELETE", f"{OASIS_BASE}/topics/{args.topic_id}", params=params)
        if code == 200:
            print(f"✅ 话题 {args.topic_id} 已取消")
        else:
            _err(code, body)

    elif args.action == "purge":
        if not args.topic_id:
            print("❌ 请指定 --topic-id", file=sys.stderr); return
        code, body = _req("POST", f"{OASIS_BASE}/topics/{args.topic_id}/purge", params=params)
        if code == 200:
            print(f"✅ 话题 {args.topic_id} 已清除")
        else:
            _err(code, body)

    elif args.action == "delete-all":
        code, body = _req("DELETE", f"{OASIS_BASE}/topics", params=params)
        if code == 200:
            print("✅ 所有话题已删除")
        else:
            _err(code, body)


# ── experts: OASIS 专家 ──────────────────────────────────────────────
def cmd_experts(args):
    """OASIS 专家管理"""
    act = args.action

    if act == "list":
        params = {"user_id": args.user}
        if args.team:
            params["team"] = args.team
        code, body = _req("GET", f"{OASIS_BASE}/experts", params=params)
        if code == 200:
            experts = body if isinstance(body, list) else body.get("experts", [body])
            if not experts:
                print("📭 暂无专家")
                return
            print(f"🧑‍🏫 专家列表 ({len(experts)} 个):\n")
            for e in experts:
                tag = e.get("tag", e.get("id", "?"))
                name = e.get("name", tag)
                role = e.get("role", "")
                print(f"  • [{tag}] {name}")
                if role:
                    print(f"    {role[:80]}")
        else:
            _err(code, body)

    elif act == "add":
        if not args.tag:
            print("❌ 请指定 --tag <专家标签>", file=sys.stderr); return
        if not args.expert_name:
            print("❌ 请指定 --expert-name <专家名称>", file=sys.stderr); return
        data = {
            "user_id": args.user,
            "tag": args.tag,
            "name": args.expert_name,
            "team": args.team or "",
        }
        if args.persona:
            data["persona"] = args.persona
        if args.temperature is not None:
            data["temperature"] = args.temperature
        code, body = _req("POST", f"{OASIS_BASE}/experts/user", data=data)
        if code == 200:
            print(f"✅ 专家已添加: [{args.tag}] {args.expert_name}")
            _pp(body)
        else:
            _err(code, body)

    elif act == "update":
        if not args.tag:
            print("❌ 请指定 --tag <专家标签>", file=sys.stderr); return
        data = {
            "user_id": args.user,
            "tag": args.tag,
            "name": args.expert_name or "",
            "team": args.team or "",
        }
        if args.persona:
            data["persona"] = args.persona
        if args.temperature is not None:
            data["temperature"] = args.temperature
        code, body = _req("PUT", f"{OASIS_BASE}/experts/user/{args.tag}", data=data)
        if code == 200:
            print(f"✅ 专家已更新: [{args.tag}]")
            _pp(body)
        else:
            _err(code, body)

    elif act == "delete":
        if not args.tag:
            print("❌ 请指定 --tag <专家标签>", file=sys.stderr); return
        params = {"user_id": args.user}
        if args.team:
            params["team"] = args.team
        code, body = _req("DELETE", f"{OASIS_BASE}/experts/user/{args.tag}", params=params)
        if code == 200:
            print(f"✅ 专家已删除: [{args.tag}]")
        else:
            _err(code, body)

    else:
        print(f"❌ 未知操作: {act}", file=sys.stderr)


# ── workflows: OASIS Workflow 管理 ────────────────────────────────────
def cmd_workflows(args):
    """OASIS Workflow 管理"""
    act = args.action

    if act == "list":
        params = {"user_id": args.user}
        if args.team:
            params["team"] = args.team
        code, body = _req("GET", f"{OASIS_BASE}/workflows", params=params)
        if code == 200:
            wfs = body.get("workflows", []) if isinstance(body, dict) else body
            if not wfs:
                print("📭 暂无 workflow")
                return
            print(f"📋 Workflows ({len(wfs)} 个):\n")
            for w in wfs:
                fname = w.get("file", "?")
                desc = w.get("description", "")
                print(f"  • {fname}")
                if desc:
                    print(f"    {desc}")
        else:
            _err(code, body)

    elif act == "show":
        if not args.name:
            print("❌ 请指定 --name <workflow文件名>", file=sys.stderr); return
        # 读取 workflow YAML 文件内容
        params = {"user_id": args.user}
        if args.team:
            params["team"] = args.team
        # 先列出所有 workflow 确认文件存在，然后直接读文件
        yaml_dir = os.path.join(PROJECT_ROOT, "data", "user_files", args.user)
        if args.team:
            yaml_dir = os.path.join(yaml_dir, "teams", args.team)
        yaml_dir = os.path.join(yaml_dir, "oasis", "yaml")
        fname = args.name if args.name.endswith(".yaml") else args.name + ".yaml"
        yaml_path = os.path.join(yaml_dir, fname)
        if os.path.isfile(yaml_path):
            with open(yaml_path, "r", encoding="utf-8") as f:
                print(f.read())
        else:
            print(f"❌ 文件不存在: {yaml_path}", file=sys.stderr)

    elif act == "save":
        if not args.name:
            print("❌ 请指定 --name <workflow名称>", file=sys.stderr); return
        # 从 --yaml-file 读取 YAML 内容，或从 --yaml 直接传入
        yaml_content = None
        if args.yaml_file:
            try:
                with open(args.yaml_file, "r", encoding="utf-8") as f:
                    yaml_content = f.read()
            except Exception as e:
                print(f"❌ 读取文件失败: {e}", file=sys.stderr); return
        elif args.yaml:
            yaml_content = args.yaml
        else:
            print("❌ 请指定 --yaml <YAML内容> 或 --yaml-file <YAML文件路径>", file=sys.stderr); return
        data = {
            "user_id": args.user,
            "name": args.name,
            "schedule_yaml": yaml_content,
            "description": args.description or "",
            "team": args.team or "",
        }
        code, body = _req("POST", f"{OASIS_BASE}/workflows", data=data)
        if code == 200:
            print(f"✅ Workflow 已保存: {body.get('file', args.name)}")
        else:
            _err(code, body)

    elif act == "run":
        # 需要 question + (schedule_file 或 schedule_yaml)
        if not args.question:
            print("❌ 请指定 --question <讨论问题/任务>", file=sys.stderr); return

        data = {
            "user_id": args.user,
            "question": args.question,
            "team": args.team or "",
        }
        # 优先用 schedule_file（已保存的 workflow 文件名 → 转为绝对路径）
        if args.name:
            fname = args.name if args.name.endswith(".yaml") else args.name + ".yaml"
            if args.team:
                yaml_dir = os.path.join(PROJECT_ROOT, "data", "user_files", args.user,
                                         "teams", args.team, "oasis", "yaml")
            else:
                yaml_dir = os.path.join(PROJECT_ROOT, "data", "user_files", args.user,
                                         "oasis", "yaml")
            data["schedule_file"] = os.path.join(yaml_dir, fname)
        elif args.yaml_file:
            try:
                with open(args.yaml_file, "r", encoding="utf-8") as f:
                    data["schedule_yaml"] = f.read()
            except Exception as e:
                print(f"❌ 读取文件失败: {e}", file=sys.stderr); return
        elif args.yaml:
            data["schedule_yaml"] = args.yaml
        else:
            print("❌ 请指定 --name <已保存的workflow名> 或 --yaml-file <YAML文件> 或 --yaml <YAML内容>", file=sys.stderr); return

        if args.max_rounds:
            data["max_rounds"] = args.max_rounds
        if args.discussion is not None:
            data["discussion"] = args.discussion
        if args.early_stop:
            data["early_stop"] = True

        code, body = _req("POST", f"{OASIS_BASE}/topics", data=data, timeout=30)
        if code == 200:
            tid = body.get("topic_id", "?")
            msg = body.get("message", "")
            print(f"🚀 Workflow 已启动!")
            print(f"   Topic ID: {tid}")
            print(f"   {msg}")
            print(f"\n   查看详情: uv run scripts/cli.py -u {args.user} topics show --topic-id {tid}")
            print(f"   实时跟踪: uv run scripts/cli.py -u {args.user} topics watch --topic-id {tid}")
            print(f"   等待结论: uv run scripts/cli.py -u {args.user} workflows conclusion --topic-id {tid}")
        else:
            _err(code, body)

    elif act == "conclusion":
        if not args.topic_id:
            print("❌ 请指定 --topic-id <话题ID>", file=sys.stderr); return
        params = {"user_id": args.user}
        timeout = args.timeout or 300
        params["timeout"] = timeout
        print(f"⏳ 等待话题 {args.topic_id} 结论 (最多 {timeout}s)...")
        code, body = _req("GET", f"{OASIS_BASE}/topics/{args.topic_id}/conclusion",
                           params=params, timeout=timeout + 10)
        if code == 200:
            status = body.get("status", "")
            if status == "running":
                print(f"⏳ 话题仍在运行中 (第 {body.get('current_round', '?')} 轮, {body.get('total_posts', 0)} 条发言)")
                print("   稍后再试")
            else:
                print(f"✅ 话题已结束 ({body.get('rounds', '?')} 轮, {body.get('total_posts', 0)} 条发言)\n")
                print("📋 结论:")
                print(body.get("conclusion", "(无)"))
        else:
            _err(code, body)

    else:
        print(f"❌ 未知操作: {act}", file=sys.stderr)


# ── tunnel: Tunnel 管理 ──────────────────────────────────────────────
def cmd_tunnel(args):
    """Cloudflare Tunnel 管理"""
    pidfile = os.path.join(PROJECT_ROOT, ".tunnel.pid")

    def _running():
        if not os.path.exists(pidfile):
            return False, 0
        with open(pidfile) as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, 0)
            return True, pid
        except OSError:
            return False, pid

    def _public_domain():
        env_path = os.path.join(PROJECT_ROOT, "config", ".env")
        if not os.path.exists(env_path):
            return None
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith("PUBLIC_DOMAIN="):
                    v = line.strip().split("=", 1)[1].strip()
                    if v and v != "wait to set":
                        return v
        return None

    if args.action == "status":
        ok, pid = _running()
        if ok:
            domain = _public_domain()
            print(f"✅ Tunnel 运行中 (PID: {pid})")
            if domain:
                print(f"🌍 公网地址: {domain}")
            else:
                print("⏳ 公网地址尚未就绪")
        else:
            print("❌ Tunnel 未运行")

    elif args.action == "start":
        ok, pid = _running()
        if ok:
            print(f"⚠️ Tunnel 已在运行 (PID: {pid})")
            return
        print("🌐 启动 Tunnel...")
        log = os.path.join(PROJECT_ROOT, "logs", "tunnel.log")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        proc = subprocess.Popen(
            [sys.executable, os.path.join(PROJECT_ROOT, "scripts", "tunnel.py")],
            stdout=open(log, "w"), stderr=subprocess.STDOUT,
            cwd=PROJECT_ROOT, start_new_session=True
        )
        with open(pidfile, "w") as f:
            f.write(str(proc.pid))
        print(f"✅ Tunnel 已启动 (PID: {proc.pid})")
        print(f"   日志: {log}")
        # 等待公网地址
        for _ in range(30):
            time.sleep(2)
            domain = _public_domain()
            if domain:
                print(f"🌍 公网地址: {domain}")
                return
        print("⏳ 公网地址尚未就绪，请查看日志")

    elif args.action == "stop":
        ok, pid = _running()
        if not ok:
            print("Tunnel 未运行")
            return
        os.kill(pid, signal.SIGTERM)
        for _ in range(10):
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
            except OSError:
                break
        else:
            os.kill(pid, signal.SIGKILL)
        if os.path.exists(pidfile):
            os.remove(pidfile)
        print("✅ Tunnel 已停止")


# ── openclaw: OpenClaw Agent 管理 ─────────────────────────────────────
def cmd_openclaw(args):
    """OpenClaw Agent 管理"""
    _check_token()
    act = args.action

    if act == "sessions":
        params = {}
        if args.filter:
            params["filter"] = args.filter
        code, body = _req("GET", f"{OASIS_BASE}/sessions/openclaw",
                           params=params)
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "add":
        data = json.loads(args.data) if args.data else {}
        code, body = _req("POST", f"{OASIS_BASE}/sessions/openclaw/add",
                           data=data, timeout=35)
        if code == 200:
            print("✅ Agent 已添加")
            _pp(body)
        else:
            _err(code, body)

    elif act == "default-workspace":
        code, body = _req("GET", f"{OASIS_BASE}/sessions/openclaw/default-workspace")
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "workspace-files":
        code, body = _req("GET", f"{OASIS_BASE}/sessions/openclaw/workspace-files",
                           params={"workspace": args.workspace or ""})
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "workspace-file-read":
        code, body = _req("GET", f"{OASIS_BASE}/sessions/openclaw/workspace-file",
                           params={"workspace": args.workspace or "",
                                   "filename": args.filename or ""})
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "workspace-file-save":
        data = json.loads(args.data) if args.data else {}
        code, body = _req("POST", f"{OASIS_BASE}/sessions/openclaw/workspace-file",
                           data=data, timeout=15)
        if code == 200:
            print("✅ 文件已保存")
            _pp(body)
        else:
            _err(code, body)

    elif act == "detail":
        code, body = _req("GET", f"{OASIS_BASE}/sessions/openclaw/agent-detail",
                           params={"name": args.name or ""}, timeout=15)
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "skills":
        params = {}
        if args.agent:
            params["name"] = args.agent
        code, body = _req("GET", f"{OASIS_BASE}/sessions/openclaw/skills",
                           params=params, timeout=20)
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "tool-groups":
        code, body = _req("GET", f"{OASIS_BASE}/sessions/openclaw/tool-groups")
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "update-config":
        data = json.loads(args.data) if args.data else {}
        code, body = _req("POST", f"{OASIS_BASE}/sessions/openclaw/update-config",
                           data=data, timeout=15)
        if code == 200:
            print("✅ 配置已更新")
            _pp(body)
        else:
            _err(code, body)

    elif act == "channels":
        code, body = _req("GET", f"{OASIS_BASE}/sessions/openclaw/channels",
                           timeout=15)
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "bindings":
        code, body = _req("GET", f"{OASIS_BASE}/sessions/openclaw/agent-bindings",
                           params={"agent": args.agent or ""}, timeout=15)
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "bind":
        data = json.loads(args.data) if args.data else {}
        code, body = _req("POST", f"{OASIS_BASE}/sessions/openclaw/agent-bind",
                           data=data, timeout=15)
        if code == 200:
            print("✅ 绑定成功")
            _pp(body)
        else:
            _err(code, body)

    elif act == "remove":
        data = {"name": args.name or ""}
        code, body = _req("DELETE", f"{OASIS_BASE}/sessions/openclaw/remove",
                           data=data, timeout=15)
        if code == 200:
            print("✅ Agent 已删除")
            _pp(body)
        else:
            _err(code, body)

    else:
        print(f"❌ 未知操作: {act}", file=sys.stderr)


# ── openclaw-snapshot: OpenClaw 快照管理 ──────────────────────────────
FRONT_BASE = f"http://127.0.0.1:{PORT_FRONTEND}"

def _front_headers(args=None):
    """前端接口的请求头（带 session cookie 模拟 + 用户身份）"""
    h = {"X-Internal-Token": INTERNAL_TOKEN}
    # 将 CLI 的 -u/--user 通过 X-User-Id 传给 front.py
    uid = getattr(args, "user", None) if args else None
    if not uid:
        uid = _cli_user  # fallback 到全局缓存
    if uid:
        h["X-User-Id"] = uid
    return h

def cmd_openclaw_snapshot(args):
    """OpenClaw 快照管理 (通过 front.py 接口)"""
    _check_token()
    act = args.action

    if act == "get":
        code, body = _req("GET", f"{FRONT_BASE}/team_openclaw_snapshot",
                           headers=_front_headers(),
                           params={"team": args.team or ""})
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "export":
        data = {"team": args.team or "", "agent_name": args.agent_name or "",
                "short_name": args.short_name or ""}
        code, body = _req("POST", f"{FRONT_BASE}/team_openclaw_snapshot/export",
                           headers=_front_headers(), data=data, timeout=30)
        if code == 200:
            print("✅ 导出成功")
            _pp(body)
        else:
            _err(code, body)

    elif act == "sync-all":
        data = {"team": args.team or ""}
        code, body = _req("POST", f"{FRONT_BASE}/team_openclaw_snapshot/sync_all",
                           headers=_front_headers(), data=data, timeout=60)
        if code == 200:
            print("✅ 同步完成")
            _pp(body)
        else:
            _err(code, body)

    elif act == "restore":
        data = {"team": args.team or "", "short_name": args.short_name or ""}
        if args.target_name:
            data["target_agent_name"] = args.target_name
        code, body = _req("POST", f"{FRONT_BASE}/team_openclaw_snapshot/restore",
                           headers=_front_headers(), data=data, timeout=60)
        if code == 200:
            print("✅ 恢复成功")
            _pp(body)
        else:
            _err(code, body)

    elif act == "export-all":
        data = {"team": args.team or ""}
        code, body = _req("POST", f"{FRONT_BASE}/team_openclaw_snapshot/export_all",
                           headers=_front_headers(), data=data, timeout=120)
        if code == 200:
            print("✅ 全部导出完成")
            _pp(body)
        else:
            _err(code, body)

    elif act == "restore-all":
        data = {"team": args.team or ""}
        code, body = _req("POST", f"{FRONT_BASE}/team_openclaw_snapshot/restore_all",
                           headers=_front_headers(), data=data, timeout=120)
        if code == 200:
            print("✅ 全部恢复完成")
            _pp(body)
        else:
            _err(code, body)

    else:
        print(f"❌ 未知操作: {act}", file=sys.stderr)


# ── visual: 可视化编排 ───────────────────────────────────────────────
def cmd_visual(args):
    """可视化编排管理"""
    _check_token()
    act = args.action

    if act == "experts":
        params = {}
        if args.team:
            params["team"] = args.team
        code, body = _req("GET", f"{FRONT_BASE}/proxy_visual/experts",
                           headers=_front_headers(), params=params)
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "add-expert":
        data = json.loads(args.data) if args.data else {}
        if args.team:
            data["team"] = args.team
        code, body = _req("POST", f"{FRONT_BASE}/proxy_visual/experts/custom",
                           headers=_front_headers(), data=data)
        if code == 200:
            print("✅ 自定义专家已添加")
            _pp(body)
        else:
            _err(code, body)

    elif act == "delete-expert":
        params = {}
        if args.team:
            params["team"] = args.team
        code, body = _req("DELETE",
                           f"{FRONT_BASE}/proxy_visual/experts/custom/{args.tag}",
                           headers=_front_headers(), params=params)
        if code == 200:
            print("✅ 专家已删除")
        else:
            _err(code, body)

    elif act == "generate-yaml":
        data = json.loads(args.data) if args.data else {}
        code, body = _req("POST", f"{FRONT_BASE}/proxy_visual/generate-yaml",
                           headers=_front_headers(), data=data)
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "agent-generate-yaml":
        data = json.loads(args.data) if args.data else {}
        if args.team:
            data["team"] = args.team
        code, body = _req("POST", f"{FRONT_BASE}/proxy_visual/agent-generate-yaml",
                           headers=_front_headers(), data=data, timeout=60)
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "save-layout":
        data = json.loads(args.data) if args.data else {}
        if args.team:
            data["team"] = args.team
        code, body = _req("POST", f"{FRONT_BASE}/proxy_visual/save-layout",
                           headers=_front_headers(), data=data)
        if code == 200:
            print("✅ 布局已保存")
        else:
            _err(code, body)

    elif act == "load-layouts":
        params = {}
        if args.team:
            params["team"] = args.team
        code, body = _req("GET", f"{FRONT_BASE}/proxy_visual/load-layouts",
                           headers=_front_headers(), params=params)
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "load-layout":
        params = {}
        if args.team:
            params["team"] = args.team
        code, body = _req("GET",
                           f"{FRONT_BASE}/proxy_visual/load-layout/{args.name}",
                           headers=_front_headers(), params=params)
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "load-yaml-raw":
        params = {}
        if args.team:
            params["team"] = args.team
        code, body = _req("GET",
                           f"{FRONT_BASE}/proxy_visual/load-yaml-raw/{args.name}",
                           headers=_front_headers(), params=params)
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "delete-layout":
        params = {}
        if args.team:
            params["team"] = args.team
        code, body = _req("DELETE",
                           f"{FRONT_BASE}/proxy_visual/delete-layout/{args.name}",
                           headers=_front_headers(), params=params)
        if code == 200:
            print("✅ 布局已删除")
        else:
            _err(code, body)

    elif act == "upload-yaml":
        data = json.loads(args.data) if args.data else {}
        if args.team:
            data["team"] = args.team
        code, body = _req("POST", f"{FRONT_BASE}/proxy_visual/upload-yaml",
                           headers=_front_headers(), data=data)
        if code == 200:
            print("✅ YAML 已上传")
            _pp(body)
        else:
            _err(code, body)

    elif act == "sessions-status":
        code, body = _req("GET", f"{FRONT_BASE}/proxy_visual/sessions-status",
                           headers=_front_headers())
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    else:
        print(f"❌ 未知操作: {act}", file=sys.stderr)


# ── internal-agents: 内部 Agent CRUD ─────────────────────────────────
def cmd_internal_agents(args):
    """内部 Agent 管理"""
    _check_token()
    act = args.action
    params = {}
    if args.team:
        params["team"] = args.team

    if act == "list":
        code, body = _req("GET", f"{FRONT_BASE}/internal_agents",
                           headers=_front_headers(), params=params)
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "add":
        data = json.loads(args.data) if args.data else {}
        if "session" not in data and args.session:
            data["session"] = args.session
        code, body = _req("POST", f"{FRONT_BASE}/internal_agents",
                           headers=_front_headers(), data=data,
                           params=params)
        if code == 200:
            print("✅ Agent 已添加")
            _pp(body)
        else:
            _err(code, body)

    elif act == "update":
        if not args.sid:
            print("❌ 请指定 --sid", file=sys.stderr); return
        data = json.loads(args.data) if args.data else {}
        code, body = _req("PUT", f"{FRONT_BASE}/internal_agents/{args.sid}",
                           headers=_front_headers(), data=data,
                           params=params)
        if code == 200:
            print("✅ Agent 已更新")
            _pp(body)
        else:
            _err(code, body)

    elif act == "delete":
        if not args.sid:
            print("❌ 请指定 --sid", file=sys.stderr); return
        code, body = _req("DELETE", f"{FRONT_BASE}/internal_agents/{args.sid}",
                           headers=_front_headers(), params=params)
        if code == 200:
            print(f"✅ Agent {args.sid} 已删除")
        else:
            _err(code, body)

    else:
        print(f"❌ 未知操作: {act}", file=sys.stderr)


# ── teams: Team 管理 ─────────────────────────────────────────────────
def cmd_teams(args):
    """Team 管理"""
    _check_token()
    act = args.action

    if act == "list":
        code, body = _req("GET", f"{FRONT_BASE}/teams",
                           headers=_front_headers())
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "create":
        data = {"team": args.team_name or ""}
        code, body = _req("POST", f"{FRONT_BASE}/teams",
                           headers=_front_headers(), data=data)
        if code == 200:
            print("✅ Team 已创建")
            _pp(body)
        else:
            _err(code, body)

    elif act == "delete":
        if not args.team_name:
            print("❌ 请指定 --team-name", file=sys.stderr); return
        code, body = _req("DELETE", f"{FRONT_BASE}/teams/{args.team_name}",
                           headers=_front_headers(), timeout=30)
        if code == 200:
            print(f"✅ Team {args.team_name} 已删除")
            _pp(body)
        else:
            _err(code, body)

    elif act == "info":
        if not args.team_name:
            print("❌ 请指定 --team-name", file=sys.stderr); return
        team = args.team_name
        hdrs = _front_headers()
        print(f"{'═' * 60}")
        print(f"📋 Team: {team}")
        print(f"{'═' * 60}")

        # ── 1. 成员 ──
        code, body = _req("GET", f"{FRONT_BASE}/teams/{team}/members", headers=hdrs)
        if code == 200:
            members = body.get("members", [])
            oasis_members = [m for m in members if m.get("type") == "oasis"]
            ext_members = [m for m in members if m.get("type") != "oasis"]
            print(f"\n👥 成员 ({len(members)} 个):")
            if oasis_members:
                print(f"\n  内部 Agent ({len(oasis_members)}):")
                for m in oasis_members:
                    name = m.get("name", "?")
                    tag = m.get("tag", "")
                    gn = m.get("global_name", "")
                    parts = [f"    • {name}"]
                    if tag:
                        parts.append(f"[{tag}]")
                    if gn:
                        parts.append(f"(session: {gn})")
                    print(" ".join(parts))
            if ext_members:
                print(f"\n  外部 Agent ({len(ext_members)}):")
                for m in ext_members:
                    name = m.get("name", "?")
                    tag = m.get("tag", "")
                    gn = m.get("global_name", "")
                    meta = m.get("meta", {})
                    parts = [f"    • {name}"]
                    if tag:
                        parts.append(f"[{tag}]")
                    if gn:
                        parts.append(f"(global: {gn})")
                    print(" ".join(parts))
                    if meta:
                        model = meta.get("model", "")
                        if model:
                            print(f"      model: {model}")
            if not members:
                print("  📭 暂无成员")
        else:
            print(f"  ⚠️ 获取成员失败: [{code}]", file=sys.stderr)

        # ── 2. 专家 ──
        code2, body2 = _req("GET", f"{FRONT_BASE}/teams/{team}/experts", headers=hdrs)
        if code2 == 200:
            experts = body2.get("experts", [])
            print(f"\n🧑‍🏫 自定义专家 ({len(experts)} 个):")
            if experts:
                for e in experts:
                    tag = e.get("tag", "?")
                    name = e.get("name", tag)
                    prompt = e.get("prompt", e.get("persona", ""))
                    print(f"  • [{tag}] {name}")
                    if prompt:
                        preview = prompt[:80].replace("\n", " ")
                        if len(prompt) > 80:
                            preview += "..."
                        print(f"    {preview}")
            else:
                print("  📭 暂无自定义专家")
        else:
            print(f"  ⚠️ 获取专家失败: [{code2}]", file=sys.stderr)

        # ── 3. Workflows ──
        params_wf = {"user_id": args.user, "team": team}
        code3, body3 = _req("GET", f"{OASIS_BASE}/workflows", params=params_wf)
        if code3 == 200:
            wfs = body3.get("workflows", []) if isinstance(body3, dict) else body3
            print(f"\n📐 Workflows ({len(wfs)} 个):")
            if wfs:
                for w in wfs:
                    fname = w.get("file", "?")
                    desc = w.get("description", "")
                    line = f"  • {fname}"
                    if desc:
                        line += f"  — {desc}"
                    print(line)
            else:
                print("  📭 暂无 workflow")
        else:
            print(f"  ⚠️ 获取 workflows 失败: [{code3}]", file=sys.stderr)

        # ── 4. 最近话题 ──
        params_tp = {"user_id": args.user}
        code4, body4 = _req("GET", f"{OASIS_BASE}/topics", params=params_tp)
        if code4 == 200:
            all_topics = body4 if isinstance(body4, list) else body4.get("topics", [])
            # 过滤属于当前 team 的话题 (通过 team 字段或 schedule_file 路径)
            team_topics = []
            for t in all_topics:
                t_team = t.get("team", "")
                if t_team == team:
                    team_topics.append(t)
            print(f"\n💬 话题 ({len(team_topics)} 个):")
            if team_topics:
                status_icon = {"pending": "⏳", "discussing": "🔄", "concluded": "✅",
                               "error": "❌"}
                for t in team_topics[-10:]:  # 最多展示最近 10 个
                    tid = t.get("id", t.get("topic_id", "?"))
                    q = t.get("title", t.get("question", ""))
                    st = t.get("status", "?")
                    icon = status_icon.get(st, "❓")
                    # 截断过长标题
                    if len(q) > 60:
                        q = q[:60] + "..."
                    print(f"  {icon} [{tid}] {q}  ({st})")
                if len(team_topics) > 10:
                    print(f"  ... 共 {len(team_topics)} 个话题，仅展示最近 10 个")
            else:
                print("  📭 暂无话题")
        else:
            print(f"  ⚠️ 获取话题失败: [{code4}]", file=sys.stderr)

        # ── 5. OpenClaw 快照 ──
        code5, body5 = _req("GET", f"{FRONT_BASE}/team_openclaw_snapshot",
                             headers=hdrs, params={"team": team})
        if code5 == 200:
            snapshots = body5.get("snapshots", body5.get("agents", []))
            if isinstance(body5, dict) and not snapshots:
                # 尝试其他可能的字段
                for k, v in body5.items():
                    if isinstance(v, list) and v:
                        snapshots = v
                        break
            if snapshots:
                print(f"\n📸 OpenClaw 快照 ({len(snapshots)} 个):")
                for s in snapshots:
                    sname = s.get("short_name", s.get("name", "?"))
                    agent_name = s.get("agent_name", "")
                    line = f"  • {sname}"
                    if agent_name:
                        line += f"  → {agent_name}"
                    print(line)

        print(f"\n{'═' * 60}")

    elif act == "members":
        if not args.team_name:
            print("❌ 请指定 --team-name", file=sys.stderr); return
        code, body = _req("GET", f"{FRONT_BASE}/teams/{args.team_name}/members",
                           headers=_front_headers())
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "add-ext-member":
        if not args.team_name:
            print("❌ 请指定 --team-name", file=sys.stderr); return
        data = json.loads(args.data) if args.data else {}
        code, body = _req("POST",
                           f"{FRONT_BASE}/teams/{args.team_name}/members/external",
                           headers=_front_headers(), data=data)
        if code == 200:
            print("✅ 外部成员已添加")
            _pp(body)
        else:
            _err(code, body)

    elif act == "delete-ext-member":
        if not args.team_name:
            print("❌ 请指定 --team-name", file=sys.stderr); return
        data = json.loads(args.data) if args.data else {}
        code, body = _req("DELETE",
                           f"{FRONT_BASE}/teams/{args.team_name}/members/external",
                           headers=_front_headers(), data=data)
        if code == 200:
            print("✅ 外部成员已删除")
            _pp(body)
        else:
            _err(code, body)

    elif act == "update-ext-member":
        if not args.team_name:
            print("❌ 请指定 --team-name", file=sys.stderr); return
        data = json.loads(args.data) if args.data else {}
        code, body = _req("PUT",
                           f"{FRONT_BASE}/teams/{args.team_name}/members/external",
                           headers=_front_headers(), data=data)
        if code == 200:
            print("✅ 外部成员已更新")
            _pp(body)
        else:
            _err(code, body)

    elif act == "experts":
        if not args.team_name:
            print("❌ 请指定 --team-name", file=sys.stderr); return
        code, body = _req("GET",
                           f"{FRONT_BASE}/teams/{args.team_name}/experts",
                           headers=_front_headers())
        if code == 200:
            _pp(body)
        else:
            _err(code, body)

    elif act == "add-expert":
        if not args.team_name:
            print("❌ 请指定 --team-name", file=sys.stderr); return
        data = json.loads(args.data) if args.data else {}
        code, body = _req("POST",
                           f"{FRONT_BASE}/teams/{args.team_name}/experts",
                           headers=_front_headers(), data=data)
        if code == 200:
            print("✅ 专家已添加")
            _pp(body)
        else:
            _err(code, body)

    elif act == "update-expert":
        if not args.team_name or not args.tag:
            print("❌ 请指定 --team-name 和 --tag", file=sys.stderr); return
        data = json.loads(args.data) if args.data else {}
        code, body = _req("PUT",
                           f"{FRONT_BASE}/teams/{args.team_name}/experts/{args.tag}",
                           headers=_front_headers(), data=data)
        if code == 200:
            print("✅ 专家已更新")
            _pp(body)
        else:
            _err(code, body)

    elif act == "delete-expert":
        if not args.team_name or not args.tag:
            print("❌ 请指定 --team-name 和 --tag", file=sys.stderr); return
        code, body = _req("DELETE",
                           f"{FRONT_BASE}/teams/{args.team_name}/experts/{args.tag}",
                           headers=_front_headers())
        if code == 200:
            print("✅ 专家已删除")
            _pp(body)
        else:
            _err(code, body)

    elif act == "snapshot-download":
        data = {"team": args.team_name or ""}
        code, body = _req("POST", f"{FRONT_BASE}/teams/snapshot/download",
                           headers=_front_headers(), data=data, timeout=60)
        if code == 200:
            if isinstance(body, bytes):
                out = args.output or f"team_{args.team_name}_snapshot.zip"
                with open(out, "wb") as f:
                    f.write(body)
                print(f"✅ 快照已保存: {out} ({len(body)} bytes)")
            else:
                _pp(body)
        else:
            _err(code, body)

    elif act == "snapshot-upload":
        if not args.team_name:
            print("❌ 请指定 --team-name", file=sys.stderr); return
        if not args.file:
            print("❌ 请指定 --file (zip 文件路径)", file=sys.stderr); return
        # 使用 multipart/form-data 上传
        import mimetypes
        boundary = "----CLIUploadBoundary"
        body_parts = []
        # team field
        body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"team\"\r\n\r\n{args.team_name}")
        # file field
        fname = os.path.basename(args.file)
        ct = mimetypes.guess_type(args.file)[0] or "application/zip"
        with open(args.file, "rb") as f:
            file_data = f.read()
        body_parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fname}\"\r\nContent-Type: {ct}\r\n\r\n"
        )
        # 手动拼装
        encoded = b""
        for i, part in enumerate(body_parts):
            encoded += part.encode("utf-8")
            if i == len(body_parts) - 1:
                encoded += file_data
            encoded += b"\r\n"
        encoded += f"--{boundary}--\r\n".encode("utf-8")
        req_obj = urllib.request.Request(
            f"{FRONT_BASE}/teams/snapshot/upload",
            data=encoded,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "X-Internal-Token": INTERNAL_TOKEN,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req_obj, timeout=120) as resp:
                result = json.loads(resp.read())
                _pp(result)
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode())
            except Exception:
                err = {"error": e.reason}
            _err(e.code, err)
        except urllib.error.URLError as e:
            print(f"❌ 连接失败: {e.reason}", file=sys.stderr)

    else:
        print(f"❌ 未知操作: {act}", file=sys.stderr)


# ── status: 服务状态 ─────────────────────────────────────────────────
def cmd_status(args):
    """检查各服务状态"""
    services = [
        ("Agent",     f"http://127.0.0.1:{PORT_AGENT}/v1/models"),
        ("OASIS",     f"http://127.0.0.1:{PORT_OASIS}/experts"),
        ("Frontend",  f"http://127.0.0.1:{PORT_FRONTEND}/"),
    ]
    print("📊 服务状态:\n")
    for name, url in services:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3):
                print(f"  ✅ {name:12s}  :{url.split(':')[2].split('/')[0]}  正常")
        except Exception:
            print(f"  ❌ {name:12s}  :{url.split(':')[2].split('/')[0]}  不可达")


# ═══════════════════════════════════════════════════════════════════════
#  参数解析
# ═══════════════════════════════════════════════════════════════════════

def build_parser():
    p = argparse.ArgumentParser(
        prog="teamclaw",
        description="TeamClaw CLI — 命令行控制工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-u", "--user", default=DEFAULT_USER, help="用户名 (默认: admin, chat 时必须显式指定)")
    sub = p.add_subparsers(dest="command", help="子命令")

    # chat
    c = sub.add_parser("chat", help="发送消息（流式输出）")
    c.add_argument("message", help="消息内容")
    c.add_argument("-s", "--session", required=True, help="会话 ID（必填）")
    c.add_argument("-m", "--model", help="模型名称")

    # sessions
    sub.add_parser("sessions", help="查看会话列表")

    # sessions-status
    sub.add_parser("sessions-status", help="查看所有会话忙碌状态")

    # session-status
    c = sub.add_parser("session-status", help="查看单个会话状态")
    c.add_argument("-s", "--session", help="会话 ID (默认: default)")

    # history
    c = sub.add_parser("history", help="查看会话历史")
    c.add_argument("-s", "--session", help="会话 ID (默认: default)")
    c.add_argument("-n", "--limit", type=int, help="最近 N 条")
    c.add_argument("--full", action="store_true", help="不截断长消息")

    # delete-session
    c = sub.add_parser("delete-session", help="删除会话")
    c.add_argument("session", help="会话 ID")

    # settings
    c = sub.add_parser("settings", help="查看/修改设置")
    c.add_argument("--full", action="store_true", help="完整设置（含高级项）")
    c.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), dest="set_pair", help="修改设置")

    # tools
    c = sub.add_parser("tools", help="查看可用工具")
    c.add_argument("--brief", action="store_true", help="仅显示名称")

    # tts
    c = sub.add_parser("tts", help="文字转语音")
    c.add_argument("text", help="要转换的文本")
    c.add_argument("-o", "--output", help="输出文件 (默认: tts_output.mp3)")
    c.add_argument("--voice", help="语音角色")

    # cancel
    c = sub.add_parser("cancel", help="取消当前生成")
    c.add_argument("-s", "--session", help="会话 ID")

    # restart
    sub.add_parser("restart", help="重启 Agent 服务")

    # groups
    c = sub.add_parser("groups", help="群组管理")
    c.add_argument("action", nargs="?", default="list",
                   choices=["list", "create", "get", "update", "delete",
                            "messages", "send", "mute", "unmute",
                            "mute-status", "sessions"],
                   help="操作 (默认: list)")
    c.add_argument("--group-id", help="群组 ID")
    c.add_argument("--name", help="群组名称 (创建时)")
    c.add_argument("--message", help="消息内容 (send 时)")
    c.add_argument("--data", help="JSON 数据")
    c.add_argument("--after-id", help="增量获取消息 (messages 时)")

    # openclaw
    c = sub.add_parser("openclaw", help="OpenClaw Agent 管理")
    c.add_argument("action", nargs="?", default="sessions",
                   choices=["sessions", "add", "default-workspace",
                            "workspace-files", "workspace-file-read",
                            "workspace-file-save", "detail", "skills",
                            "tool-groups", "update-config", "channels",
                            "bindings", "bind", "remove"],
                   help="操作 (默认: sessions)")
    c.add_argument("--filter", help="过滤关键词 (sessions 时)")
    c.add_argument("--name", help="Agent 名称 (detail/remove 时)")
    c.add_argument("--agent", help="Agent 名称 (skills/bindings 时)")
    c.add_argument("--workspace", help="工作区路径")
    c.add_argument("--filename", help="文件名 (workspace-file-read 时)")
    c.add_argument("--data", help="JSON 数据")

    # openclaw-snapshot
    c = sub.add_parser("openclaw-snapshot", help="OpenClaw 快照管理")
    c.add_argument("action", nargs="?", default="get",
                   choices=["get", "export", "sync-all", "restore",
                            "export-all", "restore-all"],
                   help="操作 (默认: get)")
    c.add_argument("--team", help="Team 名称 (必需)")
    c.add_argument("--agent-name", help="Agent 全名 (export 时)")
    c.add_argument("--short-name", help="显示名 (export/restore 时)")
    c.add_argument("--target-name", help="恢复目标 Agent 名 (restore 时)")

    # visual
    c = sub.add_parser("visual", help="可视化编排管理")
    c.add_argument("action", nargs="?", default="experts",
                   choices=["experts", "add-expert", "delete-expert",
                            "generate-yaml", "agent-generate-yaml",
                            "save-layout", "load-layouts", "load-layout",
                            "load-yaml-raw", "delete-layout", "upload-yaml",
                            "sessions-status"],
                   help="操作 (默认: experts)")
    c.add_argument("--team", help="Team 名称")
    c.add_argument("--tag", help="专家 tag (delete-expert 时)")
    c.add_argument("--name", help="布局名称 (load-layout/load-yaml-raw/delete-layout 时)")
    c.add_argument("--data", help="JSON 数据")

    # internal-agents
    c = sub.add_parser("internal-agents", help="内部 Agent CRUD")
    c.add_argument("action", nargs="?", default="list",
                   choices=["list", "add", "update", "delete"],
                   help="操作 (默认: list)")
    c.add_argument("--team", help="Team 名称")
    c.add_argument("--sid", help="Session ID (update/delete 时)")
    c.add_argument("--session", help="Session ID (add 时)")
    c.add_argument("--data", help="JSON 数据")

    # teams
    c = sub.add_parser("teams", help="Team 管理")
    c.add_argument("action", nargs="?", default="list",
                   choices=["list", "info", "create", "delete", "members",
                            "add-ext-member", "delete-ext-member",
                            "update-ext-member", "experts", "add-expert",
                            "update-expert", "delete-expert",
                            "snapshot-download", "snapshot-upload"],
                   help="操作 (默认: list)")
    c.add_argument("--team-name", help="Team 名称")
    c.add_argument("--tag", help="专家 tag (update-expert/delete-expert 时)")
    c.add_argument("--data", help="JSON 数据")
    c.add_argument("-o", "--output", help="输出文件 (snapshot-download 时)")
    c.add_argument("--file", help="上传文件路径 (snapshot-upload 时)")

    # topics
    c = sub.add_parser("topics", help="OASIS 话题管理")
    c.add_argument("action", nargs="?", default="list",
                   choices=["list", "show", "watch", "cancel", "purge", "delete-all"],
                   help="操作 (默认: list)")
    c.add_argument("--topic-id", help="话题 ID")
    c.add_argument("--raw", action="store_true", help="输出原始 JSON (show 时)")
    c.add_argument("--full", action="store_true", help="不截断长内容 (show 时)")

    # experts
    c = sub.add_parser("experts", help="OASIS 专家管理")
    c.add_argument("action", nargs="?", default="list",
                   choices=["list", "add", "update", "delete"],
                   help="操作 (默认: list)")
    c.add_argument("--tag", help="专家标签 (唯一标识)")
    c.add_argument("--expert-name", help="专家显示名称")
    c.add_argument("--persona", help="专家人设描述")
    c.add_argument("--temperature", type=float, help="温度参数 (0-2)")
    c.add_argument("--team", help="Team 名称")

    # workflows
    c = sub.add_parser("workflows", help="OASIS Workflow 管理")
    c.add_argument("action", nargs="?", default="list",
                   choices=["list", "show", "save", "run", "conclusion"],
                   help="操作 (默认: list)")
    c.add_argument("--team", help="Team 名称")
    c.add_argument("--name", help="Workflow 文件名 (show/save/run 时)")
    c.add_argument("--yaml", help="YAML 内容 (save/run 时，直接传入)")
    c.add_argument("--yaml-file", help="YAML 文件路径 (save/run 时，从文件读取)")
    c.add_argument("--description", help="Workflow 描述 (save 时)")
    c.add_argument("--question", help="讨论问题/任务 (run 时)")
    c.add_argument("--max-rounds", type=int, help="最大轮数 (run 时, 1-20)")
    c.add_argument("--discussion", type=lambda x: x.lower() in ("true", "1", "yes"),
                   default=None, help="讨论模式 (run 时, true/false)")
    c.add_argument("--early-stop", action="store_true", help="提前终止 (run 时)")
    c.add_argument("--topic-id", help="话题 ID (conclusion 时)")
    c.add_argument("--timeout", type=int, help="等待超时秒数 (conclusion 时, 默认 300)")

    # tunnel
    c = sub.add_parser("tunnel", help="Cloudflare Tunnel 管理")
    c.add_argument("action", nargs="?", default="status",
                   choices=["status", "start", "stop"],
                   help="操作 (默认: status)")

    # status
    sub.add_parser("status", help="检查各服务状态")

    return p


def main():
    global _cli_user
    parser = build_parser()
    args = parser.parse_args()
    _cli_user = getattr(args, "user", "") or ""

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # settings 特殊处理
    if args.command == "settings":
        args.set_key = args.set_pair[0] if args.set_pair else None
        args.set_value = args.set_pair[1] if args.set_pair else None

    dispatch = {
        "chat": cmd_chat,
        "sessions": cmd_sessions,
        "sessions-status": cmd_sessions_status,
        "session-status": cmd_session_status,
        "history": cmd_history,
        "delete-session": cmd_delete_session,
        "settings": cmd_settings,
        "tools": cmd_tools,
        "tts": cmd_tts,
        "cancel": cmd_cancel,
        "restart": cmd_restart,
        "groups": cmd_groups,
        "openclaw": cmd_openclaw,
        "openclaw-snapshot": cmd_openclaw_snapshot,
        "visual": cmd_visual,
        "internal-agents": cmd_internal_agents,
        "teams": cmd_teams,
        "topics": cmd_topics,
        "experts": cmd_experts,
        "workflows": cmd_workflows,
        "tunnel": cmd_tunnel,
        "status": cmd_status,
    }

    fn = dispatch.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
