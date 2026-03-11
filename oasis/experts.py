"""
OASIS Forum - Expert Agent definitions

Three expert backends:
  1. ExpertAgent  — direct LLM call (stateless, single-shot)
     name = "display_name#temp#N" (display_name from preset by tag)
  2. SessionExpert — calls mini_timebot's /v1/chat/completions endpoint
     using an existing or auto-created session_id.
     - session_id format "tag#oasis#id" → oasis-managed session, first-round
       identity injection (tag → name/persona from preset configs)
     - other session_id (e.g. "助手#default") → regular agent,
       no identity injection, relies on session's own system prompt
  3. ExternalExpert — direct call to any external OpenAI-compatible API
     name = "display_name#ext#id"
     Connects to external endpoints (DeepSeek, GPT-4, Moonshot, Ollama, etc)
     with their own URL and API key. External service is assumed stateful
     (holds conversation history server-side); only incremental context is sent.
     **OpenClaw CLI priority**: When model matches "agent:<name>:<session>",
     prefers `openclaw agent --agent <name> --session-id <session> --message ...`
     CLI over HTTP API. Falls back to HTTP if CLI unavailable or fails.
     To integrate with OpenClaw sessions via HTTP, pass x-openclaw-session-key
     via the YAML headers field, e.g.:
       headers:
         x-openclaw-session-key: "my-session-id"

Expert pool is built from schedule_yaml or schedule_file (YAML-only mode).
schedule_file takes priority if both provided.
Session IDs can be freely chosen; new IDs auto-create sessions on first use.
Append "#new" to any session name in YAML to force a fresh session (ID
replaced with random UUID, guaranteeing no reuse).
No separate expert-session storage: oasis sessions are identified by the
"#oasis#" pattern in their session_id and live in the normal Agent
checkpoint DB.

Both participate() methods accept an optional `instruction` parameter,
which is injected into the expert's prompt to guide their focus.
"""

import asyncio
import json
import os
import re
import shutil
import sys

import httpx
from langchain_core.messages import HumanMessage

# 确保 src/ 在 import 路径中，以便导入 llm_factory
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
from llm_factory import create_chat_model, extract_text

from oasis.forum import DiscussionForum


# --- 加载 prompt 和专家配置（模块级别，导入时执行一次） ---
_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_prompts_dir = os.path.join(_data_dir, "prompts")
_agency_prompts_dir = os.path.join(_prompts_dir, "agency_agents")


def _load_prompt_file(prompt_file: str) -> str:
    """Load the full prompt content from an agency_agents .md file.

    Strips YAML frontmatter (--- ... ---) and returns the body text.
    Returns empty string if file not found.
    """
    import re as _re
    fpath = os.path.join(_agency_prompts_dir, prompt_file)
    if not os.path.isfile(fpath):
        return ""
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        # Strip YAML frontmatter
        fm_match = _re.match(r'^---\s*\n.*?\n---\s*\n', content, _re.DOTALL)
        body = content[fm_match.end():] if fm_match else content
        return body.strip()
    except Exception:
        return ""


# 加载公共专家配置（原始简版）
_experts_json_path = os.path.join(_prompts_dir, "oasis_experts.json")
try:
    with open(_experts_json_path, "r", encoding="utf-8") as f:
        EXPERT_CONFIGS: list[dict] = json.load(f)
    print(f"[prompts] ✅ oasis 已加载 oasis_experts.json ({len(EXPERT_CONFIGS)} 位公共专家)")
except FileNotFoundError:
    print(f"[prompts] ⚠️ 未找到 {_experts_json_path}，使用内置默认配置")
    EXPERT_CONFIGS = [
        {"name": "创意专家", "tag": "creative", "persona": "你是一个乐观的创新者，善于发现机遇和非常规解决方案。你喜欢挑战传统观念，提出大胆且具有前瞻性的想法。", "temperature": 0.9},
        {"name": "批判专家", "tag": "critical", "persona": "你是一个严谨的批判性思考者，善于发现风险、漏洞和逻辑谬误。你会指出方案中的潜在问题，确保讨论不会忽视重要细节。", "temperature": 0.3},
        {"name": "数据分析师", "tag": "data", "persona": "你是一个数据驱动的分析师，只相信数据和事实。你用数字、案例和逻辑推导来支撑你的观点。", "temperature": 0.5},
        {"name": "综合顾问", "tag": "synthesis", "persona": "你善于综合不同观点，寻找平衡方案，关注实际可操作性。你会识别各方共识，提出兼顾多方利益的务实建议。", "temperature": 0.5},
    ]

# 加载 agency-agents 丰富版专家 prompt 库
_agency_json_path = os.path.join(_prompts_dir, "agency_experts.json")
AGENCY_EXPERT_CONFIGS: list[dict] = []
try:
    with open(_agency_json_path, "r", encoding="utf-8") as f:
        _raw_agency = json.load(f)
    # 为每个 agency 专家加载完整 prompt 并设置 persona
    _existing_tags = {c["tag"] for c in EXPERT_CONFIGS}
    for item in _raw_agency:
        if item["tag"] in _existing_tags:
            continue  # 跳过与原始专家 tag 冲突的（不应出现）
        prompt_body = _load_prompt_file(item["prompt_file"])
        if not prompt_body:
            continue  # 跳过加载失败的
        item["persona"] = prompt_body  # 用完整 md 正文作为 persona
        AGENCY_EXPERT_CONFIGS.append(item)
    print(f"[prompts] ✅ oasis 已加载 agency_experts.json ({len(AGENCY_EXPERT_CONFIGS)} 位 Agency 专家)")
except FileNotFoundError:
    print(f"[prompts] ⚠️ 未找到 {_agency_json_path}，Agency 专家库未启用")


# ======================================================================
# Per-user custom expert storage (persona definitions)
# ======================================================================
_USER_EXPERTS_DIR = os.path.join(_data_dir, "oasis_user_experts")
os.makedirs(_USER_EXPERTS_DIR, exist_ok=True)


def _user_experts_path(user_id: str) -> str:
    """Return the JSON file path for a user's custom experts."""
    safe = user_id.replace("/", "_").replace("\\", "_").replace("..", "_")
    return os.path.join(_USER_EXPERTS_DIR, f"{safe}.json")


def load_user_experts(user_id: str) -> list[dict]:
    """Load a user's custom expert list (returns [] if none)."""
    path = _user_experts_path(user_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_user_experts(user_id: str, experts: list[dict]) -> None:
    with open(_user_experts_path(user_id), "w", encoding="utf-8") as f:
        json.dump(experts, f, ensure_ascii=False, indent=2)


def _validate_expert(data: dict) -> dict:
    """Validate and normalize an expert config dict. Raises ValueError on bad input."""
    name = data.get("name", "").strip()
    tag = data.get("tag", "").strip()
    persona = data.get("persona", "").strip()
    if not name:
        raise ValueError("专家 name 不能为空")
    if not tag:
        raise ValueError("专家 tag 不能为空")
    if not persona:
        raise ValueError("专家 persona 不能为空")
    result = {
        "name": name,
        "tag": tag,
        "persona": persona,
        "temperature": float(data.get("temperature", 0.7)),
    }
    # 保留可选扩展字段
    for key in ("category", "description", "prompt_file"):
        if data.get(key):
            result[key] = data[key]
    return result


def add_user_expert(user_id: str, data: dict) -> dict:
    """Add a custom expert for a user. Returns the normalized expert dict."""
    expert = _validate_expert(data)
    experts = load_user_experts(user_id)
    if any(e["tag"] == expert["tag"] for e in experts):
        raise ValueError(f"用户已有 tag=\"{expert['tag']}\" 的专家，请换一个 tag 或使用更新功能")
    if any(e["tag"] == expert["tag"] for e in EXPERT_CONFIGS):
        raise ValueError(f"tag=\"{expert['tag']}\" 与公共专家冲突，请换一个 tag")
    if any(e["tag"] == expert["tag"] for e in AGENCY_EXPERT_CONFIGS):
        raise ValueError(f"tag=\"{expert['tag']}\" 与 Agency 专家库冲突，请换一个 tag")
    experts.append(expert)
    _save_user_experts(user_id, experts)
    return expert


def update_user_expert(user_id: str, tag: str, data: dict) -> dict:
    """Update an existing custom expert by tag. Returns the updated dict."""
    experts = load_user_experts(user_id)
    for i, e in enumerate(experts):
        if e["tag"] == tag:
            updated = _validate_expert({**e, **data, "tag": tag})
            experts[i] = updated
            _save_user_experts(user_id, experts)
            return updated
    raise ValueError(f"未找到用户自定义专家 tag=\"{tag}\"")


def delete_user_expert(user_id: str, tag: str) -> dict:
    """Delete a custom expert by tag. Returns the deleted dict."""
    experts = load_user_experts(user_id)
    for i, e in enumerate(experts):
        if e["tag"] == tag:
            deleted = experts.pop(i)
            _save_user_experts(user_id, experts)
            return deleted
    raise ValueError(f"未找到用户自定义专家 tag=\"{tag}\"")


def get_all_experts(user_id: str | None = None) -> list[dict]:
    """Return public experts + agency experts + user's custom experts (marked with source)."""
    result = [
        {**c, "source": "public"} for c in EXPERT_CONFIGS
    ]
    result.extend(
        {**c, "source": "agency"} for c in AGENCY_EXPERT_CONFIGS
    )
    if user_id:
        result.extend(
            {**c, "source": "custom"} for c in load_user_experts(user_id)
        )
    return result


# ======================================================================
# Prompt helpers (shared by both backends)
# ======================================================================

# 加载讨论 prompt 模板
_discuss_tpl_path = os.path.join(_prompts_dir, "oasis_expert_discuss.txt")
try:
    with open(_discuss_tpl_path, "r", encoding="utf-8") as f:
        _DISCUSS_PROMPT_TPL = f.read().strip()
    print("[prompts] ✅ oasis 已加载 oasis_expert_discuss.txt")
except FileNotFoundError:
    print(f"[prompts] ⚠️ 未找到 {_discuss_tpl_path}，使用内置默认模板")
    _DISCUSS_PROMPT_TPL = ""


def _get_llm(temperature: float = 0.7):
    """Create an LLM instance (reuses the same env config & vendor routing as main agent)."""
    return create_chat_model(temperature=temperature, max_tokens=1024)


def _build_discuss_prompt(
    expert_name: str,
    persona: str,
    question: str,
    posts_text: str,
    split: bool = False,
) -> str | tuple[str, str]:
    """Build the prompt that asks the expert to respond with JSON.

    Args:
        split: If True, return (system_prompt, user_prompt) tuple for session mode.
               If False, return a single combined string for direct LLM mode.
    """
    if _DISCUSS_PROMPT_TPL and not split:
        return _DISCUSS_PROMPT_TPL.format(
            expert_name=expert_name,
            persona=persona,
            question=question,
            posts_text=posts_text,
        )

    # --- Build system part (identity + behavior) ---
    # 判断是否是丰富的 agency 专家 prompt（含 markdown 标题）
    _is_rich_persona = persona and ("## " in persona or "# " in persona)
    if _is_rich_persona:
        # Agency 专家：完整 prompt 已包含身份/职责/规则等，直接使用
        identity = (
            f"你在 OASIS 论坛中的显示名称是「{expert_name}」。\n\n"
            f"以下是你的完整身份与行为指南：\n\n{persona}"
        )
    else:
        identity = f"你是论坛专家「{expert_name}」。{persona}" if persona else ""
    sys_parts = [p for p in [
        identity,
        "在接下来的讨论中，你将收到论坛的新增内容，需要以 JSON 格式回复你的观点和投票。",
        "你拥有工具调用能力，如需搜索资料、分析数据来支撑你的观点，可以使用可用的工具。",
        "注意：后续轮次只会发送新增帖子，之前的帖子请参考你的对话记忆。",
    ] if p]
    system_prompt = "\n".join(sys_parts)

    # --- Build user part (topic + forum content + JSON format) ---
    user_prompt = (
        f"讨论主题: {question}\n\n"
        f"当前论坛内容:\n{posts_text}\n\n"
        "请以严格的 JSON 格式回复（有时需要包裹zai（不要包含 markdown 代码块标记，不要包含注释）:\n"
        "{\n"
        '  "reply_to": 2,\n'
        '  "content": "你的观点（200字以内，观点鲜明）",\n'
        '  "votes": [\n'
        '    {"post_id": 1, "direction": "up"}\n'
        "  ]\n"
        "}\n\n"
        "说明:\n"
        "- reply_to: 如果论坛中已有其他人的帖子，你**必须**选择一个帖子ID进行回复；只有在论坛为空时才填 null\n"
        "- content: 你的发言内容，要有独到见解，可以赞同、反驳或补充你所回复的帖子\n"
        '- votes: 对其他帖子的投票列表，direction 只能是 "up" 或 "down"。如果没有要投票的帖子，填空列表 []\n'
    )

    if split:
        return system_prompt, user_prompt
    else:
        return f"{system_prompt}\n\n{user_prompt}"


def _build_identity_prompt(expert_name: str, persona: str) -> str:
    """Build identity text for execute mode. Handles both short and rich personas."""
    if not persona:
        return ""
    _is_rich = "## " in persona or "# " in persona
    if _is_rich:
        return (
            f"你在 OASIS 论坛中的显示名称是「{expert_name}」。\n\n"
            f"以下是你的完整身份与行为指南：\n\n{persona}\n\n"
        )
    else:
        return f"你是「{expert_name}」。{persona}\n\n"


def _format_posts(posts) -> str:
    """Format posts for display in the prompt."""
    lines = []
    for p in posts:
        prefix = f"  ↳ 回复#{p.reply_to}" if p.reply_to else "📌"
        lines.append(
            f"{prefix} [#{p.id}] {p.author} "
            f"(👍{p.upvotes} 👎{p.downvotes}): {p.content}"
        )
    return "\n".join(lines)


def _parse_expert_response(raw: str):
    """Strip markdown fences / oasis reply tags and parse JSON.

    Tries multiple strategies to extract valid JSON:
      1. Strip markdown code fences (```...```)
      2. Strip [oasis reply start/end] tags
      3. Direct json.loads
      4. Regex extraction of first {...} object from the text
    Raises json.JSONDecodeError if all strategies fail.
    """
    raw = raw.strip()
    # Strip markdown code fences
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    # Strip [oasis reply start/end] tags (flexible matching)
    raw = re.sub(r"\[/?oasis\s+reply\s+/?start\]", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"\[/?oasis\s+reply\s+/?end\]", "", raw, flags=re.IGNORECASE).strip()

    # Attempt 1: direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract first JSON object {...} from the text
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # All strategies failed — raise for caller to handle
    raise json.JSONDecodeError("No valid JSON found in response", raw, 0)


async def _apply_response(
    result: dict,
    expert_name: str,
    forum: DiscussionForum,
    others: list,
):
    """Apply the parsed JSON response: publish post + cast votes."""
    reply_to = result.get("reply_to")
    if reply_to is None and others:
        reply_to = others[-1].id
        print(f"  [OASIS] 🔧 {expert_name} reply_to 为 null，自动设为 #{reply_to}")

    await forum.publish(
        author=expert_name,
        content=result.get("content", "（发言内容为空）"),
        reply_to=reply_to,
    )

    for v in result.get("votes", []):
        pid = v.get("post_id")
        direction = v.get("direction", "up")
        if pid is not None and direction in ("up", "down"):
            await forum.vote(expert_name, int(pid), direction)

    print(f"  [OASIS] ✅ {expert_name} 发言完成")


# ======================================================================
# Backend 1: ExpertAgent — direct LLM call (stateless)
#   name = "title#temp#1", "title#temp#2", ...
# ======================================================================

class ExpertAgent:
    """
    A forum-resident expert agent (direct LLM backend).

    Each call is stateless: reads posts → single LLM call → publish + vote.
    name is "title#temp#N" to ensure uniqueness.
    """

    # Class-level counter for generating unique temp IDs (used when no explicit sid)
    _counter: int = 0

    def __init__(self, name: str, persona: str, temperature: float = 0.7, tag: str = "",
                 temp_id: int | None = None):
        if temp_id is not None:
            # Explicit temp id from YAML (e.g. "创意专家#temp#1" → temp_id=1)
            self.session_id = f"temp#{temp_id}"
        else:
            ExpertAgent._counter += 1
            self.session_id = f"temp#{ExpertAgent._counter}"
        self.title = name
        self.name = f"{name}#{self.session_id}"
        self.persona = persona
        self.tag = tag
        self.llm = _get_llm(temperature)

    async def participate(
        self,
        forum: DiscussionForum,
        instruction: str = "",
        discussion: bool = True,
        visible_authors: set[str] | None = None,
        from_round: int | None = None,
    ):
        others = await forum.browse(
            viewer=self.name,
            exclude_self=True,
            visible_authors=visible_authors if not discussion else None,
            from_round=from_round if not discussion else None,
        )

        if not discussion:
            # ── Execute mode: just run the task, no discussion format ──
            task_prompt = _build_identity_prompt(self.title, self.persona)
            task_prompt += f"任务主题: {forum.question}\n"
            if instruction:
                task_prompt += f"\n执行指令: {instruction}\n"
            if others:
                task_prompt += f"\n前序 agent 的执行结果:\n{_format_posts(others)}\n"
            task_prompt += "\n请直接执行任务并返回结果。"

            try:
                resp = await self.llm.ainvoke([HumanMessage(content=task_prompt)])
                text = extract_text(resp.content)
                await forum.publish(author=self.name, content=text.strip()[:2000])
                print(f"  [OASIS] ✅ {self.name} 执行完成")
            except Exception as e:
                print(f"  [OASIS] ❌ {self.name} error: {e}")
            return

        # ── Discussion mode (original) ──
        posts_text = _format_posts(others) if others else "(还没有其他人发言，你来开启讨论吧)"
        prompt = _build_discuss_prompt(self.title, self.persona, forum.question, posts_text)
        if instruction:
            prompt += f"\n\n📋 本轮你的专项指令：{instruction}\n请在回复中重点关注和执行这个指令。"

        try:
            resp = await self.llm.ainvoke([HumanMessage(content=prompt)])
            text = extract_text(resp.content)
            result = _parse_expert_response(text)
            await _apply_response(result, self.name, forum, others)
        except json.JSONDecodeError as e:
            print(f"  [OASIS] ⚠️ {self.name} JSON parse error: {e}")
            try:
                await forum.publish(author=self.name, content=extract_text(resp.content).strip()[:300])
            except Exception:
                pass
        except Exception as e:
            print(f"  [OASIS] ❌ {self.name} error: {e}")


# ======================================================================
# Backend 2: SessionExpert — calls mini_timebot /v1/chat/completions
#   using an existing session_id.  name = "title#session_id"
# ======================================================================

class SessionExpert:
    """
    Expert backed by a mini_timebot session.

    Two sub-types determined by session_id format:
      - "#oasis#" in session_id → oasis-managed session.
        First round: inject persona as system prompt so the bot knows its
        discussion identity.  Persona is looked up from preset configs by
        title, or left empty if not found.
      - Other session_id → regular agent session.
        No identity injection; the session's own system prompt defines who
        it is.  Just send the discussion invitation.

    Sessions are lazily created: first call to the bot API auto-creates the
    thread in the checkpoint DB.  No separate record table needed.

    Incremental context: first call sends full discussion context; subsequent
    calls only send new posts since last participation.
    """

    def __init__(
        self,
        name: str,
        session_id: str,
        user_id: str,
        persona: str = "",
        bot_base_url: str | None = None,
        enabled_tools: list[str] | None = None,
        timeout: float | None = None,
        tag: str = "",
        extra_headers: dict[str, str] | None = None,
    ):
        self.title = name
        self.session_id = session_id
        self.name = f"{name}#{session_id}"
        self.persona = persona
        self.is_oasis = "#oasis#" in session_id
        self.timeout = timeout or 500.0
        self.tag = tag
        self._extra_headers = extra_headers or {}

        port = os.getenv("PORT_AGENT", "51200")
        self._bot_url = (bot_base_url or f"http://127.0.0.1:{port}") + "/v1/chat/completions"

        self._user_id = user_id
        self._internal_token = os.getenv("INTERNAL_TOKEN", "")

        self.enabled_tools = enabled_tools
        self._initialized = False
        self._seen_post_ids: set[int] = set()

    def _auth_header(self) -> dict:
        h = {"Authorization": f"Bearer {self._internal_token}:{self._user_id}"}
        h.update(self._extra_headers)
        return h

    async def participate(
        self,
        forum: DiscussionForum,
        instruction: str = "",
        discussion: bool = True,
        visible_authors: set[str] | None = None,
        from_round: int | None = None,
    ):
        """
        Participate in one round.

        discussion=True: forum discussion mode (JSON reply/vote)
        discussion=False: execute mode — agent just runs the task, output logged to forum
        visible_authors: (execute mode only) if set, only see posts from these authors (DAG upstream)
        from_round: (execute mode only) if set, only see posts from this round onward (non-DAG prev round)
        """
        others = await forum.browse(
            viewer=self.name,
            exclude_self=True,
            visible_authors=visible_authors if not discussion else None,
            from_round=from_round if not discussion else None,
        )

        if not discussion:
            # ── Execute mode: send task directly, no JSON format requirement ──
            new_posts = [p for p in others if p.id not in self._seen_post_ids]
            self._seen_post_ids.update(p.id for p in others)

            messages = []
            if not self._initialized:
                # First call
                task_parts = []
                if self.is_oasis and self.persona:
                    messages.append({"role": "system", "content": _build_identity_prompt(self.title, self.persona).strip()})
                task_parts.append(f"任务主题: {forum.question}")
                if instruction:
                    task_parts.append(f"\n执行指令: {instruction}")
                if others:
                    task_parts.append(f"\n前序 agent 的执行结果:\n{_format_posts(others)}")
                task_parts.append("\n请直接执行任务并返回结果。")
                messages.append({"role": "user", "content": "\n".join(task_parts)})
                self._initialized = True
            else:
                # Subsequent calls
                ctx_parts = [f"【第 {forum.current_round} 轮】"]
                if instruction:
                    ctx_parts.append(f"执行指令: {instruction}")
                if new_posts:
                    ctx_parts.append(f"其他 agent 的新结果:\n{_format_posts(new_posts)}")
                ctx_parts.append("请继续执行任务并返回结果。")
                messages.append({"role": "user", "content": "\n".join(ctx_parts)})

            body: dict = {
                "model": "teambot",
                "messages": messages,
                "stream": False,
                "session_id": self.session_id,
            }
            if self.enabled_tools is not None:
                body["enabled_tools"] = self.enabled_tools

            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=None)) as client:
                    resp = await client.post(
                        self._bot_url, json=body, headers=self._auth_header(),
                    )
                if resp.status_code != 200:
                    print(f"  [OASIS] ❌ {self.name} bot API error {resp.status_code}: {resp.text[:200]}")
                    return
                data = resp.json()
                raw_content = data["choices"][0]["message"]["content"]
                await forum.publish(author=self.name, content=raw_content.strip()[:2000])
                print(f"  [OASIS] ✅ {self.name} 执行完成")
            except Exception as e:
                print(f"  [OASIS] ❌ {self.name} error: {e}")
            return

        # ── Discussion mode (original) ──
        others = await forum.browse(viewer=self.name, exclude_self=True)

        new_posts = [p for p in others if p.id not in self._seen_post_ids]
        self._seen_post_ids.update(p.id for p in others)

        instr_suffix = f"\n\n📋 本轮你的专项指令：{instruction}\n请在回复中重点关注和执行这个指令。" if instruction else ""

        messages = []
        if not self._initialized:
            posts_text = _format_posts(others) if others else "(还没有其他人发言，你来开启讨论吧)"

            if self.is_oasis:
                # Oasis session → inject identity as system prompt
                system_prompt, user_prompt = _build_discuss_prompt(
                    self.title, self.persona, forum.question, posts_text, split=True,
                )
                messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": user_prompt + instr_suffix})
            else:
                # Regular agent session → no identity injection
                user_prompt = (
                    f"你被邀请参加一场 OASIS 论坛多专家讨论。\n\n"
                    f"讨论主题: {forum.question}\n\n"
                    f"当前论坛内容:\n{posts_text}\n\n"
                    "请以你自身的专业视角参与讨论。以严格的 JSON 格式回复（不要包含 markdown 代码块标记）:\n"
                    "{\n"
                    '  "reply_to": 2,\n'
                    '  "content": "你的观点（200字以内，观点鲜明）",\n'
                    '  "votes": [\n'
                    '    {"post_id": 1, "direction": "up"}\n'
                    "  ]\n"
                    "}\n\n"
                    "说明:\n"
                    "- reply_to: 如果论坛中已有其他人的帖子，你**必须**选择一个帖子ID进行回复；只有在论坛为空时才填 null\n"
                    "- content: 你的发言内容，要有独到见解\n"
                    '- votes: 对其他帖子的投票列表，direction 只能是 "up" 或 "down"。如果没有要投票的帖子，填空列表 []\n'
                    "- 你拥有工具调用能力，如需搜索资料、分析数据来支撑你的观点，可以使用可用的工具。\n"
                    "- 后续轮次只会发送新增帖子，之前的帖子请参考你的对话记忆。"
                )
                messages.append({"role": "user", "content": user_prompt + instr_suffix})

            self._initialized = True
        else:
            if new_posts:
                new_text = _format_posts(new_posts)
                prompt = (
                    f"【第 {forum.current_round} 轮讨论更新】\n"
                    f"以下是自你上次发言后的 {len(new_posts)} 条新帖子：\n\n"
                    f"{new_text}\n\n"
                    "请基于这些新观点以及你之前看到的讨论内容，以 JSON 格式回复：\n"
                    "{\n"
                    '  "reply_to": <某个帖子ID>,\n'
                    '  "content": "你的观点（200字以内）",\n'
                    '  "votes": [{"post_id": <ID>, "direction": "up或down"}]\n'
                    "}"
                )
            else:
                prompt = (
                    f"【第 {forum.current_round} 轮讨论更新】\n"
                    "本轮没有新的帖子。如果你有新的想法或补充，可以继续发言；"
                    "如果没有，回复一个空 content 即可。\n"
                    "{\n"
                    '  "reply_to": null,\n'
                    '  "content": "",\n'
                    '  "votes": []\n'
                    "}"
                )
            messages.append({"role": "user", "content": prompt})

        body: dict = {
            "model": "teambot",
            "messages": messages,
            "stream": False,
            "session_id": self.session_id,
        }
        if self.enabled_tools is not None:
            body["enabled_tools"] = self.enabled_tools

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=self.timeout)) as client:
                resp = await client.post(
                    self._bot_url,
                    json=body,
                    headers=self._auth_header(),
                )

            if resp.status_code != 200:
                print(f"  [OASIS] ❌ {self.name} bot API error {resp.status_code}: {resp.text[:200]}")
                return

            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"]
            result = _parse_expert_response(raw_content)
            await _apply_response(result, self.name, forum, others)

        except json.JSONDecodeError as e:
            print(f"  [OASIS] ⚠️ {self.name} JSON parse error: {e}")
            try:
                await forum.publish(author=self.name, content=raw_content.strip()[:300])
            except Exception:
                pass
        except Exception as e:
            print(f"  [OASIS] ❌ {self.name} error: {e}")


# ======================================================================
# Backend 3: ExternalExpert — direct call to external OpenAI-compatible API
#   name = "title#ext#id"
#   Does NOT go through local mini_timebot agent.
#   Calls external api_url directly using httpx + OpenAI chat format.
#   To adapt OpenClaw sessions, set x-openclaw-session-key in YAML headers.
# ======================================================================

class ExternalExpert:
    """
    Expert backed by an external OpenAI-compatible API.

    Unlike SessionExpert (which calls the local mini_timebot agent),
    ExternalExpert directly calls any OpenAI-compatible endpoint (DeepSeek,
    GPT-4, Moonshot, Ollama, another mini_timebot instance, etc).

    **OpenClaw Agent Support**: When the ``model`` field matches the pattern
    ``agent:<agent_name>`` (e.g. ``agent:main``), this expert is recognized
    as an OpenClaw agent. Communication uses the **CLI** as the primary
    method via ``openclaw agent --agent <name> --message <msg>``.
    If the CLI is unavailable or fails, the call falls back to the
    OpenAI-compatible HTTP API (ChatCompletions endpoint).

    Session management is handled entirely by OpenClaw internally —
    users cannot and do not need to specify session IDs.

    The external service is assumed to be **stateful** (maintaining its own
    conversation history server-side). Therefore this class sends only
    incremental context: first call sends full forum state + identity;
    subsequent calls send only new posts since last participation.
    No local message history is accumulated.

    Features:
      - OpenClaw agents: CLI priority, HTTP API fallback
      - Non-OpenClaw externals: direct HTTP API call
      - Incremental context (first call = full, subsequent = delta only)
      - Identity injection via system prompt on first call (persona from presets)
      - Works in both discussion mode (JSON reply/vote) and execute mode
      - Supports custom headers via YAML for service-specific needs

    The external service does NOT need to support session_id or any
    non-standard fields — just standard /v1/chat/completions.
    """

    # Regex to match OpenClaw agent model format: agent:<agent_name>
    _OPENCLAW_MODEL_RE = re.compile(r"^agent:([^:]+)$")

    # Oasis reply protocol: require agent to wrap reply with start/end tags
    _OASIS_REPLY_START = "[oasis reply start]"
    _OASIS_REPLY_END = "[oasis reply end]"
    _OASIS_REPLY_INSTRUCTION = (
        "\n\n⚠️ IMPORTANT — [oasis reply] protocol:\n"
        "当你需要发布任何给其他 agent 或公开的信息时，必须用标签包裹：\n"
        "   [oasis reply start]\n"
        "   你要发布的内容……\n"
        "   [oasis reply end]\n"
        "注意：一轮只能发布一次，没有被标签包裹的内容不会被发布。\n\n"
        "例如，讨论模式下的回复格式：\n"
        "[oasis reply start]\n"
        "{\n"
        '  "reply_to": 2,\n'
        '  "content": "你的观点（200字以内，观点鲜明）",\n'
        '  "votes": [\n'
        '    {"post_id": 1, "direction": "up"}\n'
        "  ]\n"
        "}\n"
        "[oasis reply end]"
    )
    _OASIS_REPLY_MAX_RETRIES = 10

    def __init__(
        self,
        name: str,
        ext_id: str,
        api_url: str,
        api_key: str = "",
        model: str = "gpt-3.5-turbo",
        persona: str = "",
        timeout: float | None = None,
        tag: str = "",
        extra_headers: dict[str, str] | None = None,
    ):
        self.title = name
        self.ext_id = ext_id
        self.name = f"{name}#ext#{ext_id}"
        self.persona = persona
        self.timeout = timeout or 500.0
        self.tag = tag
        self.model = model
        self._extra_headers = extra_headers or {}

        # Detect OpenClaw agent model pattern: agent:<agent_name>
        m = self._OPENCLAW_MODEL_RE.match(model)
        if m:
            self._is_openclaw_agent = True
            self._oc_agent_name = m.group(1)
            self._openclaw_bin = shutil.which("openclaw")
            print(f"  [OASIS] 🦞 OpenClaw agent detected: agent={self._oc_agent_name}"
                  f" — CLI priority"
                  f"{', CLI available' if self._openclaw_bin else ', CLI NOT found (HTTP only)'}")
        else:
            self._is_openclaw_agent = False
            self._oc_agent_name = ""
            self._openclaw_bin = None

        # Normalize api_url: strip trailing slash, build full URL
        if api_url:
            api_url = api_url.rstrip("/")
            if not api_url.endswith("/v1/chat/completions"):
                if not api_url.endswith("/v1"):
                    api_url += "/v1"
                api_url += "/chat/completions"
        self._api_url = api_url
        self._api_key = api_key

        # Track state for incremental context (external service holds history)
        self._initialized = False
        self._seen_post_ids: set[int] = set()

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        h.update(self._extra_headers)
        return h

    async def _call_openclaw_cli(self, message: str, timeout: float | None = ...) -> str:
        """Call OpenClaw agent via CLI command.

        Runs: openclaw agent --agent <name> --message <msg>
        Returns the stdout output (agent's reply).
        Raises RuntimeError if CLI fails.
        """
        cmd = [
            self._openclaw_bin,
            "agent",
            "--agent", self._oc_agent_name,
            "--message", message,
        ]
        print(f"  [OASIS] 🦞 CLI call: openclaw agent --agent {self._oc_agent_name} "
              f"--message <{len(message)} chars>")
        effective_timeout = self.timeout if timeout is ... else timeout
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=effective_timeout
            )
            stdout_text = stdout.decode("utf-8", errors="replace").strip()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                raise RuntimeError(
                    f"openclaw CLI exit code {proc.returncode}: "
                    f"{stderr_text or stdout_text}"
                )

            # OpenClaw CLI output may contain a header line like:
            # "🦞 OpenClaw 2026.3.1 (unknown) — Less middlemen, more messages."
            # and decorative lines (│, ◇, etc). Extract the actual reply.
            reply = self._parse_openclaw_output(stdout_text)
            if not reply:
                raise RuntimeError(f"Empty response from openclaw CLI. Raw: {stdout_text[:200]}")
            return reply
        except asyncio.TimeoutError:
            raise RuntimeError(f"openclaw CLI timed out after {effective_timeout}s")

    @staticmethod
    def _parse_openclaw_output(raw: str) -> str:
        """Parse openclaw agent CLI output, stripping decorative lines.

        The CLI typically outputs:
            🦞 OpenClaw 2026.3.1 (unknown) — Less middlemen, more messages.
            │
            ◇
            <actual reply content>

        We strip the header/decorative lines and return the meaningful content.
        """
        lines = raw.split("\n")
        content_lines = []
        skip_header = True
        for line in lines:
            stripped = line.strip()
            # Skip known decorative/header patterns
            if skip_header:
                if (stripped.startswith("🦞") or
                    stripped in ("│", "◇", "◆", "└", "") or
                    stripped.startswith("OpenClaw")):
                    continue
                skip_header = False
            content_lines.append(line)
        return "\n".join(content_lines).strip()

    async def _call_api(self, messages: list[dict], timeout_override: float | None = ...) -> str:
        """Send messages to external API and return the assistant response text.

        For OpenClaw agents: CLI priority, HTTP API fallback.
        For non-OpenClaw externals: direct HTTP API call.

        Args:
            timeout_override: Explicit timeout value. None = no timeout;
                              ... (default sentinel) = use self.timeout.
        """
        effective_timeout = self.timeout if timeout_override is ... else timeout_override

        # ── OpenClaw agents: CLI priority ──
        if self._is_openclaw_agent and self._openclaw_bin:
            cli_message = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    cli_message = msg.get("content", "")
                    break
            if not cli_message:
                cli_message = messages[-1].get("content", "") if messages else ""
            try:
                reply = await self._call_openclaw_cli(cli_message, timeout=effective_timeout)
                print(f"  [OASIS] 🦞 CLI success for {self.name}")
                return reply
            except Exception as cli_err:
                print(f"  [OASIS] ⚠️ CLI failed for {self.name}: {cli_err}")
                print(f"  [OASIS] 🔄 Falling back to HTTP API")
                # Fall through to HTTP API below

        # ── HTTP API call (primary for non-OpenClaw, fallback for OpenClaw) ──
        if not self._api_url:
            raise RuntimeError(f"No api_url configured for {self.name} and CLI unavailable/failed")
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=effective_timeout)) as client:
                resp = await client.post(self._api_url, json=body, headers=self._headers())
            if resp.status_code != 200:
                raise RuntimeError(f"External API error {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as api_err:
            raise RuntimeError(f"API call failed for {self.name}: {api_err}")

    def _inject_oasis_reply_instruction(self, messages: list[dict]) -> None:
        """Append [oasis reply] instruction to the last user message (openclaw only)."""
        if not self._is_openclaw_agent:
            return
        for msg in reversed(messages):
            if msg.get("role") == "user":
                msg["content"] = msg["content"] + self._OASIS_REPLY_INSTRUCTION
                return

    # Flexible regex patterns for oasis reply tags (accept variants like [/oasis reply end])
    _OASIS_START_RE = re.compile(r"\[/?oasis\s+reply\s+/?start\]", re.IGNORECASE)
    _OASIS_END_RE = re.compile(r"\[/?oasis\s+reply\s+/?end\]", re.IGNORECASE)

    @staticmethod
    def _extract_oasis_reply(text: str, start_tag: str, end_tag: str) -> tuple[str, str | None]:
        """Parse a single reply for [oasis reply start/end] tags.

        Returns (status, content):
          - ("complete", final_text)  — both start and end found
          - ("started", after_start)  — start found but no end, returns content after start
          - ("missing", None)         — no start tag found
        """
        sm = ExternalExpert._OASIS_START_RE.search(text)
        if sm is None:
            return ("missing", None)
        after = text[sm.end():]
        em = ExternalExpert._OASIS_END_RE.search(after)
        if em is not None:
            return ("complete", after[:em.start()].strip())
        return ("started", after.strip())

    async def _call_api_with_oasis_check(self, messages: list[dict], **kwargs) -> str:
        """Call API up to _OASIS_REPLY_MAX_RETRIES times within one participate turn.

        Within a single turn, call the API repeatedly (up to 3 times):
          - If a complete [oasis reply start]...[oasis reply end] is found → return content
          - If start is found without end → buffer and call again
          - If neither tag is found → buffer raw reply and call again
          - After 3 calls without complete → return all buffered content joined together

        Each participate() call is independent; no state carries across rounds.
        """
        if not self._is_openclaw_agent:
            return await self._call_api(messages, **kwargs)

        self._inject_oasis_reply_instruction(messages)

        buf: list[str] = []
        start_tag = self._OASIS_REPLY_START
        end_tag = self._OASIS_REPLY_END

        for attempt in range(1, self._OASIS_REPLY_MAX_RETRIES + 1):
            raw_reply = await self._call_api(messages, **kwargs)
            status, content = self._extract_oasis_reply(raw_reply, start_tag, end_tag)

            if status == "complete":
                # If we had buffered content before this, prepend it
                if buf:
                    buf.append(content)
                    return "\n\n".join(seg for seg in buf if seg)
                return content

            if status == "started":
                # Start tag found but no end — buffer content after start
                buf.append(content)
                print(f"  [OASIS] 📝 {self.name} [oasis reply start] found, no end yet "
                      f"(call {attempt}/{self._OASIS_REPLY_MAX_RETRIES})")
            else:
                # "missing" — no tags, expert still thinking
                buf.append(raw_reply.strip())
                print(f"  [OASIS] 💭 {self.name} thinking, no oasis reply tags "
                      f"(call {attempt}/{self._OASIS_REPLY_MAX_RETRIES})")

            # Feed reply back into conversation for next attempt
            messages.append({"role": "assistant", "content": raw_reply})
            messages.append({"role": "user", "content": "请继续。如果你已经结束发言，请添加 [oasis reply end] 标签。如果你已回复，请重新按照格式严格回复。"})

        # All attempts exhausted — return everything we collected
        print(f"  [OASIS] ⚠️ {self.name} {self._OASIS_REPLY_MAX_RETRIES} calls without "
              f"[oasis reply end], publishing collected content")
        return "\n\n".join(seg for seg in buf if seg)

    async def participate(
        self,
        forum: DiscussionForum,
        instruction: str = "",
        discussion: bool = True,
        visible_authors: set[str] | None = None,
        from_round: int | None = None,
    ):
        others = await forum.browse(
            viewer=self.name,
            exclude_self=True,
            visible_authors=visible_authors if not discussion else None,
            from_round=from_round if not discussion else None,
        )

        if not discussion:
            # ── Execute mode ──
            new_posts = [p for p in others if p.id not in self._seen_post_ids]
            self._seen_post_ids.update(p.id for p in others)

            messages: list[dict] = []
            if not self._initialized:
                if self.persona:
                    messages.append({"role": "system", "content": _build_identity_prompt(self.title, self.persona).strip()})
                task_parts = [f"任务主题: {forum.question}"]
                if instruction:
                    task_parts.append(f"\n执行指令: {instruction}")
                if others:
                    task_parts.append(f"\n前序 agent 的执行结果:\n{_format_posts(others)}")
                task_parts.append("\n请直接执行任务并返回结果。")
                messages.append({"role": "user", "content": "\n".join(task_parts)})
                self._initialized = True
            else:
                ctx_parts = [f"【第 {forum.current_round} 轮】"]
                if instruction:
                    ctx_parts.append(f"执行指令: {instruction}")
                if new_posts:
                    ctx_parts.append(f"其他 agent 的新结果:\n{_format_posts(new_posts)}")
                ctx_parts.append("请继续执行任务并返回结果。")
                messages.append({"role": "user", "content": "\n".join(ctx_parts)})

            try:
                reply = await self._call_api_with_oasis_check(messages, timeout_override=None)
                if reply is None:
                    print(f"  [OASIS] 📝 {self.name} (external) collecting oasis reply, skipping publish")
                else:
                    await forum.publish(author=self.name, content=reply.strip()[:2000])
                    print(f"  [OASIS] ✅ {self.name} (external) 执行完成")
            except Exception as e:
                print(f"  [OASIS] ❌ {self.name} (external) error: {e}")
            return

        # ── Discussion mode ──
        new_posts = [p for p in others if p.id not in self._seen_post_ids]
        self._seen_post_ids.update(p.id for p in others)

        messages: list[dict] = []
        if not self._initialized:
            posts_text = _format_posts(others) if others else "(还没有其他人发言，你来开启讨论吧)"
            system_prompt, user_prompt = _build_discuss_prompt(
                self.title, self.persona, forum.question, posts_text, split=True,
            )
            if instruction:
                user_prompt += f"\n\n📋 本轮你的专项指令：{instruction}\n请在回复中重点关注和执行这个指令。"
            messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})
            self._initialized = True
        else:
            if new_posts:
                new_text = _format_posts(new_posts)
                prompt = (
                    f"【第 {forum.current_round} 轮讨论更新】\n"
                    f"以下是自你上次发言后的 {len(new_posts)} 条新帖子：\n\n"
                    f"{new_text}\n\n"
                    "请基于这些新观点以及你之前看到的讨论内容，以严格的 JSON 格式回复"
                    "（不要包含 markdown 代码块标记，不要包含注释）：\n"
                    "[oasis reply start]\n"
                    "{\n"
                    '  "reply_to": <某个帖子ID>,\n'
                    '  "content": "你的观点（200字以内，观点鲜明）",\n'
                    '  "votes": [{"post_id": <ID>, "direction": "up或down"}]\n'
                    "}\n"
                    "[oasis reply end]"
                )
            else:
                prompt = (
                    f"【第 {forum.current_round} 轮讨论更新】\n"
                    "本轮没有新的帖子。如果你有新的想法或补充，可以继续发言；"
                    "如果没有，回复一个空 content 即可。\n"
                    "[oasis reply start]\n"
                    "{\n"
                    '  "reply_to": null,\n'
                    '  "content": "",\n'
                    '  "votes": []\n'
                    "}\n"
                    "[oasis reply end]"
                )
            if instruction:
                prompt += f"\n\n📋 本轮你的专项指令：{instruction}\n请在回复中重点关注和执行这个指令。"
            messages.append({"role": "user", "content": prompt})

        try:
            reply = await self._call_api_with_oasis_check(messages)
            result = _parse_expert_response(reply)
            await _apply_response(result, self.name, forum, others)
        except json.JSONDecodeError as e:
            print(f"  [OASIS] ⚠️ {self.name} (external) JSON parse error: {e}")
            try:
                await forum.publish(author=self.name, content=reply.strip()[:300])
            except Exception:
                pass
        except Exception as e:
            print(f"  [OASIS] ❌ {self.name} (external) error: {e}")
