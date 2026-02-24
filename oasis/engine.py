"""
OASIS Forum - Discussion Engine

Manages the full lifecycle of a discussion:
  Round loop -> scheduled/parallel expert participation -> consensus check -> summarize

Two expert backends:
  1. ExpertAgent  — direct LLM (stateless, name="title#temp#N")
  2. SessionExpert — existing bot session (stateful, name="title#session_id")
     - "#oasis#" in session_id → oasis-managed, first-round identity injection
     - other session_id → regular agent, no identity injection

Expert pool sourcing (YAML-only, schedule_yaml is required):
  Pool is built entirely from YAML expert names (deduplicated).
  Names MUST contain '#' to specify type:
    "tag#temp#N"              → ExpertAgent (tag looked up in presets for name/persona)
    "tag#oasis#<random_id>"  → SessionExpert (oasis, tag→name/persona from presets)
    "title#<session_id>"     → SessionExpert (regular agent, no injection)
  Names without '#' are skipped with a warning.

  Session IDs can be anything — new IDs automatically create new sessions
  in the Agent checkpoint DB on first API call (lazy creation).
  To explicitly ensure a fresh session, append "#new" to the name:
    "tag#oasis#ab12#new"  → "#new" is stripped, "ab12" replaced with a random UUID
    "助手#my_session#new" → "#new" is stripped, "my_session" replaced with a random UUID
  This guarantees no accidental reuse of an existing session.

  If YAML uses `all_experts: true`, all experts in the pool speak in parallel.
  Even for simple all-parallel scenarios, a minimal YAML suffices:
    version: 1
    repeat: true
    plan:
      - all_experts: true

No separate expert-session storage: oasis sessions identified by "#oasis#"
in session_id, lazily created in Agent checkpoint DB on first bot API call.

Execution modes:
  1. Default (repeat + all_experts): all experts participate in parallel each round
  2. Scheduled: follow a YAML schedule that defines speaking order per step
"""

import asyncio
import os
import sys
import uuid

from langchain_core.messages import HumanMessage

# 确保 src/ 在 import 路径中，以便导入 llm_factory
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
from llm_factory import create_chat_model, extract_text

from oasis.forum import DiscussionForum
from oasis.experts import ExpertAgent, SessionExpert, get_all_experts
from oasis.scheduler import Schedule, ScheduleStep, StepType, parse_schedule, load_schedule_file, extract_expert_names

# 加载总结 prompt 模板（模块级别，导入时执行一次）
_prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "prompts")
_summary_tpl_path = os.path.join(_prompts_dir, "oasis_summary.txt")
try:
    with open(_summary_tpl_path, "r", encoding="utf-8") as f:
        _SUMMARY_PROMPT_TPL = f.read().strip()
    print("[prompts] ✅ oasis 已加载 oasis_summary.txt")
except FileNotFoundError:
    print(f"[prompts] ⚠️ 未找到 {_summary_tpl_path}，使用内置默认模板")
    _SUMMARY_PROMPT_TPL = ""


def _get_summarizer():
    """Create a low-temperature LLM for reliable summarization."""
    return create_chat_model(temperature=0.3, max_tokens=2048)


class DiscussionEngine:
    """
    Orchestrates one complete discussion session.

    Flow:
      1. Execute steps in schedule-defined order
      2. After each round, check if consensus is reached
      3. When done (consensus or max rounds), summarize top posts into conclusion

    Pool construction (YAML-only):
      Expert pool is built entirely from YAML expert names (deduplicated).
      "tag#temp#N"          → ExpertAgent (tag→name/persona from presets)
      "tag#oasis#id"        → SessionExpert (oasis, tag→name/persona)
      "title#session_id"    → SessionExpert (regular, no injection)
      Any name + "#new"     → force fresh session (id replaced with random UUID)
    """

    def __init__(
        self,
        forum: DiscussionForum,
        schedule: Schedule | None = None,
        schedule_yaml: str | None = None,
        schedule_file: str | None = None,
        bot_base_url: str | None = None,
        bot_enabled_tools: list[str] | None = None,
        bot_timeout: float | None = None,
        user_id: str = "anonymous",
        early_stop: bool = False,
    ):
        self.forum = forum
        self._cancelled = False
        self._early_stop = early_stop

        # ── Step 1: Parse schedule (required) ──
        self.schedule: Schedule | None = None
        if schedule:
            self.schedule = schedule
        elif schedule_yaml:
            self.schedule = parse_schedule(schedule_yaml)
        elif schedule_file:
            self.schedule = load_schedule_file(schedule_file)

        if not self.schedule:
            raise ValueError(
                "schedule_yaml or schedule_file is required. "
                "For simple all-parallel, use: version: 1\\nrepeat: true\\nplan:\\n  - all_experts: true"
            )

        # ── Step 2: Build expert pool from YAML ──
        experts_list: list[ExpertAgent | SessionExpert] = []

        yaml_names = extract_expert_names(self.schedule)
        seen: set[str] = set()
        for full_name in yaml_names:
            if full_name in seen:
                continue
            seen.add(full_name)

            if "#" not in full_name:
                print(f"  [OASIS] ⚠️ YAML expert name '{full_name}' has no '#', skipping. "
                      f"Use 'tag#temp#N' or 'tag#oasis#id' or 'title#session_id'.")
                continue

            # Handle #new suffix: strip it and generate a random session part
            force_new = full_name.endswith("#new")
            working_name = full_name[:-4] if force_new else full_name  # strip "#new"

            first, sid = working_name.split("#", 1)
            if sid.startswith("temp#"):
                # e.g. "creative#temp#1" → ExpertAgent with explicit temp_id
                config = self._lookup_by_tag(first, user_id)
                expert_name = config["name"] if config else first
                persona = config.get("persona", "") if config else ""
                temp_num = sid.split("#", 1)[1]
                experts_list.append(ExpertAgent(
                    name=expert_name,
                    persona=persona,
                    temp_id=int(temp_num) if temp_num.isdigit() else None,
                    tag=first,
                ))
            elif "#oasis#" in sid or sid.startswith("oasis#"):
                # e.g. "creative#oasis#ab12cd34" → SessionExpert (oasis)
                config = self._lookup_by_tag(first, user_id)
                expert_name = config["name"] if config else first
                persona = config.get("persona", "") if config else ""
                if force_new:
                    # Replace the id part with a fresh UUID
                    actual_sid = f"oasis#{uuid.uuid4().hex[:8]}"
                    print(f"  [OASIS] 🆕 #new: '{full_name}' → new session '{first}#{actual_sid}'")
                else:
                    actual_sid = sid
                experts_list.append(SessionExpert(
                    name=expert_name,
                    session_id=f"{first}#{actual_sid}",
                    user_id=user_id,
                    persona=persona,
                    bot_base_url=bot_base_url,
                    enabled_tools=bot_enabled_tools,
                    timeout=bot_timeout,
                    tag=first,
                ))
            else:
                # e.g. "助手#default" → SessionExpert (regular agent, no injection)
                if force_new:
                    actual_sid = uuid.uuid4().hex[:8]
                    print(f"  [OASIS] 🆕 #new: '{full_name}' → new session '{actual_sid}'")
                else:
                    actual_sid = sid
                experts_list.append(SessionExpert(
                    name=first,
                    session_id=actual_sid,
                    user_id=user_id,
                    persona="",
                    bot_base_url=bot_base_url,
                    enabled_tools=bot_enabled_tools,
                    timeout=bot_timeout,
                ))

        self.experts = experts_list

        # Build lookup map: register by full name, title, tag, and session_id
        self._expert_map: dict[str, ExpertAgent | SessionExpert] = {}
        # Also register YAML original names for scheduled lookup
        self._yaml_name_map: dict[str, ExpertAgent | SessionExpert] = {}
        for e in self.experts:
            self._expert_map[e.name] = e          # "创意专家#temp#1" or "创意专家#creative#oasis#ab12"
            if e.title not in self._expert_map:
                self._expert_map[e.title] = e     # title shortcut (first-come wins)
            if e.tag and e.tag not in self._expert_map:
                self._expert_map[e.tag] = e       # tag shortcut
            if hasattr(e, "session_id") and e.session_id not in self._expert_map:
                self._expert_map[e.session_id] = e  # session_id shortcut

        # Map original YAML names (e.g. "creative#temp#1") to experts
        for full_name in extract_expert_names(self.schedule):
            if full_name not in self._expert_map:
                # Try matching by tag + session_id pattern
                first = full_name.split("#", 1)[0] if "#" in full_name else full_name
                for e in self.experts:
                    if e.tag == first or (hasattr(e, "session_id") and e.session_id == full_name):
                        self._expert_map[full_name] = e
                        break

        self.summarizer = _get_summarizer()

    @staticmethod
    def _lookup_by_tag(tag: str, user_id: str) -> dict | None:
        """Find expert config by tag. Returns {"name", "persona", ...} or None."""
        for c in get_all_experts(user_id):
            if c["tag"] == tag:
                return c
        return None

    def _resolve_experts(self, names: list[str]) -> list:
        """Resolve expert references to Expert objects.

        Matching priority: full name > title > tag > session_id.
        Skip unknown names.
        """
        resolved = []
        for name in names:
            agent = self._expert_map.get(name)
            if agent:
                resolved.append(agent)
            else:
                print(f"  [OASIS] ⚠️ Schedule references unknown expert: '{name}', skipping")
        return resolved

    def cancel(self):
        """Request graceful cancellation. Takes effect before the next round."""
        self._cancelled = True

    def _check_cancelled(self):
        if self._cancelled:
            raise asyncio.CancelledError("Discussion cancelled by user")

    async def run(self):
        """Run the full discussion loop (called as a background task)."""
        self.forum.status = "discussing"

        session_count = sum(1 for e in self.experts if isinstance(e, SessionExpert))
        direct_count = len(self.experts) - session_count
        print(
            f"[OASIS] 🏛️ Discussion started: {self.forum.topic_id} "
            f"({len(self.experts)} experts [{direct_count} direct, {session_count} session], "
            f"max {self.forum.max_rounds} rounds, mode=scheduled)"
        )

        try:
            await self._run_scheduled()

            self.forum.conclusion = await self._summarize()
            self.forum.status = "concluded"
            print(f"[OASIS] ✅ Discussion concluded: {self.forum.topic_id}")

        except asyncio.CancelledError:
            print(f"[OASIS] 🛑 Discussion cancelled: {self.forum.topic_id}")
            self.forum.status = "error"
            self.forum.conclusion = "讨论已被用户强制终止"

        except Exception as e:
            print(f"[OASIS] ❌ Discussion error: {e}")
            self.forum.status = "error"
            self.forum.conclusion = f"讨论过程中出现错误: {str(e)}"

    async def _run_scheduled(self):
        """Execute the schedule."""
        steps = self.schedule.steps

        if self.schedule.repeat:
            for round_num in range(self.forum.max_rounds):
                self._check_cancelled()
                self.forum.current_round = round_num + 1
                print(f"[OASIS] 📢 Round {self.forum.current_round}/{self.forum.max_rounds}")

                for step in steps:
                    self._check_cancelled()
                    await self._execute_step(step)

                if self._early_stop and round_num >= 1 and await self._consensus_reached():
                    print(f"[OASIS] 🤝 Consensus reached at round {self.forum.current_round}")
                    break
        else:
            for step_idx, step in enumerate(steps):
                self._check_cancelled()
                self.forum.current_round = step_idx + 1
                self.forum.max_rounds = len(steps)
                print(f"[OASIS] 📢 Step {step_idx + 1}/{len(steps)}")

                await self._execute_step(step)

                if self._early_stop and step_idx >= 1 and await self._consensus_reached():
                    print(f"[OASIS] 🤝 Consensus reached at step {step_idx + 1}")
                    break

    async def _execute_step(self, step: ScheduleStep):
        """Execute a single schedule step."""
        if step.step_type == StepType.MANUAL:
            print(f"  [OASIS] 📝 Manual post by {step.manual_author}")
            await self.forum.publish(
                author=step.manual_author,
                content=step.manual_content,
                reply_to=step.manual_reply_to,
            )

        elif step.step_type == StepType.ALL:
            print(f"  [OASIS] 👥 All experts speak")
            await asyncio.gather(
                *[expert.participate(self.forum) for expert in self.experts],
                return_exceptions=True,
            )

        elif step.step_type == StepType.EXPERT:
            agents = self._resolve_experts(step.expert_names)
            if agents:
                print(f"  [OASIS] 🎤 {agents[0].name} speaks")
                await agents[0].participate(self.forum)

        elif step.step_type == StepType.PARALLEL:
            agents = self._resolve_experts(step.expert_names)
            if agents:
                names = ", ".join(a.name for a in agents)
                print(f"  [OASIS] 🎤 Parallel: {names}")
                await asyncio.gather(
                    *[agent.participate(self.forum) for agent in agents],
                    return_exceptions=True,
                )

    async def _consensus_reached(self) -> bool:
        top = await self.forum.get_top_posts(1)
        if not top:
            return False
        threshold = len(self.experts) * 0.7
        return top[0].upvotes >= threshold

    async def _summarize(self) -> str:
        top_posts = await self.forum.get_top_posts(5)
        all_posts = await self.forum.browse()

        if not top_posts:
            return "讨论未产生有效观点。"

        posts_text = "\n".join([
            f"[👍{p.upvotes} 👎{p.downvotes}] {p.author}: {p.content}"
            for p in top_posts
        ])

        if _SUMMARY_PROMPT_TPL:
            prompt = _SUMMARY_PROMPT_TPL.format(
                question=self.forum.question,
                post_count=len(all_posts),
                round_count=self.forum.current_round,
                posts_text=posts_text,
            )
        else:
            prompt = (
                f"你是一个讨论总结专家。以下是关于「{self.forum.question}」的多专家讨论结果。\n\n"
                f"共 {len(all_posts)} 条帖子，经过 {self.forum.current_round} 轮讨论。\n\n"
                f"获得最高认可的观点:\n{posts_text}\n\n"
                "请综合以上高赞观点，给出一个全面、平衡、有结论性的最终回答（300字以内）。\n"
                "要求:\n"
                "1. 清晰概括各方核心观点\n"
                "2. 指出主要共识和分歧\n"
                "3. 给出明确的结论性建议\n"
            )

        try:
            resp = await self.summarizer.ainvoke([HumanMessage(content=prompt)])
            return extract_text(resp.content)
        except Exception as e:
            return f"总结生成失败: {str(e)}"
