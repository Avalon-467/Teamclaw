"""
MCP Tool Server: OASIS Forum

Exposes tools for the user's Agent to interact with the OASIS discussion forum:
  - list_oasis_experts: List all available expert personas (public + user custom)
  - add_oasis_expert / update_oasis_expert / delete_oasis_expert: CRUD for expert personas
  - list_oasis_sessions: List oasis-managed sessions (containing #oasis# in session_id)
    by scanning the Agent checkpoint DB — no separate storage needed
  - post_to_oasis: Submit a discussion — supports direct LLM experts and session-backed experts
  - check_oasis_discussion / cancel_oasis_discussion: Monitor or cancel a discussion
  - list_oasis_topics: List all discussion topics

Runs as a stdio MCP server, just like the other mcp_*.py tools.
"""

import os
import httpx
import aiosqlite
from mcp.server.fastmcp import FastMCP
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

mcp = FastMCP("OASIS Forum")

OASIS_BASE_URL = os.getenv("OASIS_BASE_URL", "http://127.0.0.1:51202")
_FALLBACK_USER = os.getenv("MCP_OASIS_USER", "agent_user")

_CONN_ERR = "❌ 无法连接 OASIS 论坛服务器。请确认 OASIS 服务已启动 (端口 51202)。"

# Checkpoint DB (same as agent.py / mcp_session.py)
_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "agent_memory.db",
)
_serde = JsonPlusSerializer()


# ======================================================================
# Expert persona management tools
# ======================================================================

@mcp.tool()
async def list_oasis_experts(username: str = "") -> str:
    """
    List all available expert personas on the OASIS forum.
    Shows both public (built-in) experts and the current user's custom experts.
    Call this BEFORE post_to_oasis to see which experts can participate.

    Args:
        username: (auto-injected) current user identity; do NOT set manually

    Returns:
        Formatted list of experts with their tags, personas, and source (public/custom)
    """
    effective_user = username or _FALLBACK_USER
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{OASIS_BASE_URL}/experts",
                params={"user_id": effective_user},
            )
            if resp.status_code != 200:
                return f"❌ 查询失败: {resp.text}"

            experts = resp.json().get("experts", [])
            if not experts:
                return "📭 暂无可用专家"

            public = [e for e in experts if e.get("source") == "public"]
            custom = [e for e in experts if e.get("source") == "custom"]

            lines = [f"🏛️ OASIS 可用专家 - 共 {len(experts)} 位\n"]

            if public:
                lines.append(f"📋 公共专家 ({len(public)} 位):")
                for e in public:
                    persona_preview = e["persona"][:60] + "..." if len(e["persona"]) > 60 else e["persona"]
                    lines.append(f"  • {e['name']} (tag: \"{e['tag']}\") — {persona_preview}")

            if custom:
                lines.append(f"\n🔧 自定义专家 ({len(custom)} 位):")
                for e in custom:
                    persona_preview = e["persona"][:60] + "..." if len(e["persona"]) > 60 else e["persona"]
                    lines.append(f"  • {e['name']} (tag: \"{e['tag']}\") — {persona_preview}")

            lines.append(
                "\n💡 在 schedule_yaml 中使用 expert 的 tag 来指定参与者。"
                "\n   格式: \"tag#temp#N\" (直连LLM)、\"tag#oasis#随机ID\" (有状态session)、\"标题#session_id\" (普通agent)。"
            )
            return "\n".join(lines)

    except httpx.ConnectError:
        return _CONN_ERR
    except Exception as e:
        return f"❌ 查询异常: {str(e)}"


@mcp.tool()
async def add_oasis_expert(
    username: str,
    name: str,
    tag: str,
    persona: str,
    temperature: float = 0.7,
) -> str:
    """
    Create a custom expert persona for the current user.

    Args:
        username: (auto-injected) current user identity; do NOT set manually
        name: Expert display name (e.g. "产品经理", "前端架构师")
        tag: Unique identifier tag (e.g. "pm", "frontend_arch")
        persona: Expert persona description
        temperature: LLM temperature (0.0-1.0, default 0.7)

    Returns:
        Confirmation with the created expert info
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{OASIS_BASE_URL}/experts/user",
                json={
                    "user_id": username,
                    "name": name,
                    "tag": tag,
                    "persona": persona,
                    "temperature": temperature,
                },
            )
            if resp.status_code != 200:
                return f"❌ 创建失败: {resp.json().get('detail', resp.text)}"

            expert = resp.json()["expert"]
            return (
                f"✅ 自定义专家已创建\n"
                f"  名称: {expert['name']}\n"
                f"  Tag: {expert['tag']}\n"
                f"  Persona: {expert['persona']}\n"
                f"  Temperature: {expert['temperature']}"
            )

    except httpx.ConnectError:
        return _CONN_ERR
    except Exception as e:
        return f"❌ 创建异常: {str(e)}"


@mcp.tool()
async def update_oasis_expert(
    username: str,
    tag: str,
    name: str = "",
    persona: str = "",
    temperature: float = -1,
) -> str:
    """
    Update an existing custom expert persona.

    Args:
        username: (auto-injected) current user identity; do NOT set manually
        tag: The tag of the custom expert to update
        name: New display name (leave empty to keep current)
        persona: New persona description (leave empty to keep current)
        temperature: New temperature (-1 = keep current)

    Returns:
        Confirmation with the updated expert info
    """
    try:
        body: dict = {"user_id": username}
        if name:
            body["name"] = name
        if persona:
            body["persona"] = persona
        if temperature >= 0:
            body["temperature"] = temperature

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                f"{OASIS_BASE_URL}/experts/user/{tag}",
                json=body,
            )
            if resp.status_code != 200:
                return f"❌ 更新失败: {resp.json().get('detail', resp.text)}"

            expert = resp.json()["expert"]
            return (
                f"✅ 自定义专家已更新\n"
                f"  名称: {expert['name']}\n"
                f"  Tag: {expert['tag']}\n"
                f"  Persona: {expert['persona']}\n"
                f"  Temperature: {expert['temperature']}"
            )

    except httpx.ConnectError:
        return _CONN_ERR
    except Exception as e:
        return f"❌ 更新异常: {str(e)}"


@mcp.tool()
async def delete_oasis_expert(username: str, tag: str) -> str:
    """
    Delete a custom expert persona.

    Args:
        username: (auto-injected) current user identity; do NOT set manually
        tag: The tag of the custom expert to delete

    Returns:
        Confirmation of deletion
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                f"{OASIS_BASE_URL}/experts/user/{tag}",
                params={"user_id": username},
            )
            if resp.status_code != 200:
                return f"❌ 删除失败: {resp.json().get('detail', resp.text)}"

            deleted = resp.json()["deleted"]
            return f"✅ 已删除自定义专家: {deleted['name']} (tag: \"{deleted['tag']}\")"

    except httpx.ConnectError:
        return _CONN_ERR
    except Exception as e:
        return f"❌ 删除异常: {str(e)}"


# ======================================================================
# Oasis session discovery (scans checkpoint DB for #oasis# sessions)
# ======================================================================

@mcp.tool()
async def list_oasis_sessions(username: str = "") -> str:
    """
    List all oasis-managed expert sessions for the current user.

    Oasis sessions are identified by "#oasis#" in their session_id
    (e.g. "creative#oasis#ab12cd34", where "creative" is the expert tag).
    They live in the normal Agent checkpoint DB and are auto-created
    when first used in a discussion.

    No separate storage or pre-creation is needed.  Just use session_ids
    in "tag#oasis#<random>" format in your schedule_yaml expert names.
    Append "#new" to force a brand-new session (ID replaced with random UUID).

    Args:
        username: (auto-injected) current user identity; do NOT set manually

    Returns:
        Formatted list of oasis sessions with tag, session_id and message count
    """
    effective_user = username or _FALLBACK_USER

    if not os.path.exists(_DB_PATH):
        return "📭 暂无 oasis 专家 session（数据库不存在）"

    prefix = f"{effective_user}#"
    sessions = []

    try:
        async with aiosqlite.connect(_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT DISTINCT thread_id FROM checkpoints "
                "WHERE thread_id LIKE ? ORDER BY thread_id",
                (f"{prefix}%#oasis#%",),
            )
            rows = await cursor.fetchall()

            for (thread_id,) in rows:
                sid = thread_id[len(prefix):]  # strip "user#" prefix → session_id
                tag = sid.split("#")[0] if "#" in sid else sid

                # Get message count from latest checkpoint
                ckpt_cursor = await db.execute(
                    "SELECT type, checkpoint FROM checkpoints "
                    "WHERE thread_id = ? ORDER BY ROWID DESC LIMIT 1",
                    (thread_id,),
                )
                ckpt_row = await ckpt_cursor.fetchone()
                msg_count = 0
                if ckpt_row:
                    try:
                        ckpt_data = _serde.loads_typed((ckpt_row[0], ckpt_row[1]))
                        messages = ckpt_data.get("channel_values", {}).get("messages", [])
                        msg_count = len(messages)
                    except Exception:
                        pass

                sessions.append({
                    "session_id": sid,
                    "tag": tag,
                    "message_count": msg_count,
                })

    except Exception as e:
        return f"❌ 查询失败: {str(e)}"

    if not sessions:
        return (
            "📭 暂无 oasis 专家 session。\n\n"
            "💡 无需预创建。在 schedule_yaml 中使用\n"
            "   \"tag#oasis#随机ID\" 格式的名称即可，首次使用时自动创建。\n"
            "   加 \"#new\" 后缀可确保创建全新 session。"
        )

    lines = [f"🏛️ OASIS 专家 Sessions — 共 {len(sessions)} 个\n"]
    for s in sessions:
        lines.append(
            f"  • Tag: {s['tag']}\n"
            f"    Session ID: {s['session_id']}\n"
            f"    消息数: {s['message_count']}"
        )

    lines.append(
        "\n💡 在 schedule_yaml 中使用 session_id 即可让这些专家参与讨论。"
        "\n   也可在 schedule_yaml 中精确指定发言顺序。"
    )
    return "\n".join(lines)


# ======================================================================
# Discussion tools
# ======================================================================

@mcp.tool()
async def post_to_oasis(
    question: str,
    schedule_yaml: str,
    username: str = "",
    max_rounds: int = 5,
    schedule_file: str = "",
    detach: bool = False,
    notify_session: str = "",
) -> str:
    """
    Submit a question or work task to the OASIS forum for multi-expert discussion.

    Expert pool is built entirely from schedule_yaml expert names (required).

    Expert name formats (must contain '#', engine parses by tag):
      "creative#temp#1"       → ExpertAgent (tag→name/persona from presets, direct LLM)
      "creative#oasis#ab12"   → SessionExpert (oasis, tag→name/persona, stateful bot)
      "助手#default"          → SessionExpert (regular, no identity injection)

    Session IDs can be anything new — new IDs auto-create new sessions on first use.
    To explicitly ensure a brand-new session (avoid reusing existing), append "#new":
      "creative#oasis#ab12#new"  → "#new" stripped, ID replaced with random UUID
      "助手#my_session#new"      → "#new" stripped, ID replaced with random UUID

    For simple all-parallel with all preset experts, use:
      version: 1
      repeat: true
      plan:
        - all_experts: true

    Args:
        question: The question/topic to discuss or work task to assign
        schedule_yaml: YAML defining expert pool AND speaking order (required).

            Example:
              version: 1
              repeat: true
              plan:
                - expert: "creative#temp#1"
                - expert: "creative#oasis#ab12cd34"
                - expert: "creative#oasis#new#new"
                - parallel:
                    - "critical#temp#2"
                    - "data#temp#3"
                - all_experts: true
                - manual:
                    author: "主持人"
                    content: "请聚焦可行性"
        username: (auto-injected) current user identity; do NOT set manually
        max_rounds: Maximum number of discussion rounds (1-20, default 5)
        schedule_file: Filename or path to a saved YAML workflow. Short names (e.g. "review.yaml")
            are resolved under data/user_files/{user}/oasis/yaml/. Prefer schedule_yaml inline.
        detach: If True, return immediately with topic_id. Use check_oasis_discussion later.
        notify_session: (auto-injected) Session ID for completion notification.

    Returns:
        The final conclusion, or (if detach=True) the topic_id for later retrieval
    """
    effective_user = username or _FALLBACK_USER

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=300.0)) as client:
            body: dict = {
                "question": question,
                "user_id": effective_user,
                "max_rounds": max_rounds,
            }
            if detach:
                port = os.getenv("PORT_AGENT", "51200")
                body["callback_url"] = f"http://127.0.0.1:{port}/system_trigger"
                body["callback_session_id"] = notify_session or "default"
            if schedule_yaml:
                body["schedule_yaml"] = schedule_yaml
            if schedule_file:
                if not os.path.isabs(schedule_file):
                    yaml_dir = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "user_files", effective_user, "oasis", "yaml",
                    )
                    schedule_file = os.path.join(yaml_dir, schedule_file)
                body["schedule_file"] = schedule_file

            resp = await client.post(
                f"{OASIS_BASE_URL}/topics",
                json=body,
            )
            if resp.status_code != 200:
                return f"❌ Failed to create topic: {resp.text}"

            topic_id = resp.json()["topic_id"]

            if detach:
                return (
                    f"🏛️ OASIS 任务已提交（脱离模式）\n"
                    f"主题: {question[:80]}\n"
                    f"Topic ID: {topic_id}\n\n"
                    f"💡 使用 check_oasis_discussion(topic_id=\"{topic_id}\") 查看进展和结论。"
                )

            result = await client.get(
                f"{OASIS_BASE_URL}/topics/{topic_id}/conclusion",
                params={"timeout": 280, "user_id": effective_user},
            )

            if result.status_code == 200:
                data = result.json()
                return (
                    f"🏛️ OASIS 论坛讨论完成\n"
                    f"主题: {data['question']}\n"
                    f"讨论轮次: {data['rounds']}\n"
                    f"总帖子数: {data['total_posts']}\n\n"
                    f"📋 结论:\n{data['conclusion']}\n\n"
                    f"💡 如需查看完整讨论过程，Topic ID: {topic_id}"
                )
            elif result.status_code == 504:
                return f"⏰ 讨论超时未完成 (Topic ID: {topic_id})，可稍后通过 check_oasis_discussion 查看结果"
            else:
                return f"❌ 获取结论失败: {result.text}"

    except httpx.ConnectError:
        return _CONN_ERR
    except Exception as e:
        return f"❌ 工具调用异常: {str(e)}"


@mcp.tool()
async def check_oasis_discussion(topic_id: str, username: str = "") -> str:
    """
    Check the current status of a discussion on the OASIS forum.

    Args:
        topic_id: The topic ID returned by post_to_oasis
        username: (auto-injected) current user identity; do NOT set manually

    Returns:
        Formatted discussion status and recent posts
    """
    effective_user = username or _FALLBACK_USER
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{OASIS_BASE_URL}/topics/{topic_id}",
                params={"user_id": effective_user},
            )

            if resp.status_code == 403:
                return f"❌ 无权查看此讨论: {topic_id}"
            if resp.status_code == 404:
                return f"❌ 未找到讨论主题: {topic_id}"
            if resp.status_code != 200:
                return f"❌ 查询失败: {resp.text}"

            data = resp.json()

            lines = [
                f"🏛️ OASIS 讨论详情",
                f"主题: {data['question']}",
                f"状态: {data['status']} ({data['current_round']}/{data['max_rounds']}轮)",
                f"帖子数: {len(data['posts'])}",
                "",
                "--- 最近帖子 ---",
            ]

            for p in data["posts"][-10:]:
                prefix = f"  ↳回复#{p['reply_to']}" if p.get("reply_to") else "📌"
                content_preview = p["content"][:150]
                if len(p["content"]) > 150:
                    content_preview += "..."
                lines.append(
                    f"{prefix} [#{p['id']}] {p['author']} "
                    f"(👍{p['upvotes']} 👎{p['downvotes']}): {content_preview}"
                )

            if data.get("conclusion"):
                lines.extend(["", "🏆 === 最终结论 ===", data["conclusion"]])
            elif data["status"] == "discussing":
                lines.extend(["", "⏳ 讨论进行中..."])

            return "\n".join(lines)

    except httpx.ConnectError:
        return _CONN_ERR
    except Exception as e:
        return f"❌ 查询异常: {str(e)}"


@mcp.tool()
async def cancel_oasis_discussion(topic_id: str, username: str = "") -> str:
    """
    Force-cancel a running OASIS discussion.

    Args:
        topic_id: The topic ID to cancel
        username: (auto-injected) current user identity; do NOT set manually

    Returns:
        Cancellation result
    """
    effective_user = username or _FALLBACK_USER
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(
                f"{OASIS_BASE_URL}/topics/{topic_id}",
                params={"user_id": effective_user},
            )

            if resp.status_code == 403:
                return f"❌ 无权取消此讨论: {topic_id}"
            if resp.status_code == 404:
                return f"❌ 未找到讨论主题: {topic_id}"
            if resp.status_code != 200:
                return f"❌ 取消失败: {resp.text}"

            data = resp.json()
            return f"🛑 讨论已终止\nTopic ID: {topic_id}\n状态: {data.get('status')}\n{data.get('message', '')}"

    except httpx.ConnectError:
        return _CONN_ERR
    except Exception as e:
        return f"❌ 取消异常: {str(e)}"


@mcp.tool()
async def list_oasis_topics(username: str = "") -> str:
    """
    List all discussion topics on the OASIS forum.

    Args:
        username: (auto-injected) current user identity; leave empty to list all.

    Returns:
        Formatted list of all discussion topics
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            effective_user = username or _FALLBACK_USER
            resp = await client.get(
                f"{OASIS_BASE_URL}/topics",
                params={"user_id": effective_user},
            )

            if resp.status_code != 200:
                return f"❌ 查询失败: {resp.text}"

            topics = resp.json()
            if not topics:
                return "📭 论坛暂无讨论主题"

            lines = [f"🏛️ OASIS 论坛 - 共 {len(topics)} 个主题\n"]
            for t in topics:
                status_icon = {
                    "pending": "⏳",
                    "discussing": "💬",
                    "concluded": "✅",
                    "error": "❌",
                }.get(t["status"], "❓")
                lines.append(
                    f"{status_icon} [{t['topic_id']}] {t['question'][:50]} "
                    f"| {t['status']} | {t['post_count']}帖 | {t['current_round']}/{t['max_rounds']}轮"
                )

            return "\n".join(lines)

    except httpx.ConnectError:
        return _CONN_ERR
    except Exception as e:
        return f"❌ 查询异常: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
