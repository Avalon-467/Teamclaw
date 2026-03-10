"""
OASIS Forum - Discussion Engine

Manages the full lifecycle of a discussion:
  Round loop -> scheduled/parallel expert participation -> consensus check -> summarize

Three expert backends:
  1. ExpertAgent  — direct LLM (stateless, name="title#temp#N")
  2. SessionExpert — existing bot session (stateful, name="title#session_id")
     - "#oasis#" in session_id → oasis-managed, first-round identity injection
     - other session_id → regular agent, no identity injection
  3. ExternalExpert — external OpenAI-compatible API (name="title#ext#id")
     - Directly calls external endpoints (DeepSeek, GPT-4, Ollama, etc)
     - Configured per-expert via YAML: api_url, api_key, model
     - OpenClaw CLI priority: model "agent:<name>" uses CLI first, HTTP fallback

Expert pool sourcing (YAML-only, schedule_file or schedule_yaml required):
  Pool is built entirely from YAML expert names (deduplicated).
  Priority: schedule_file > schedule_yaml (file takes precedence if both provided).
  Names MUST contain '#' to specify type:
    "tag#temp#N"              → ExpertAgent (tag looked up in presets for name/persona)
    "tag#oasis#<random_id>"  → SessionExpert (oasis, tag→name/persona from presets)
    "name#ext#<id>"          → ExternalExpert (requires api_url in YAML)
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
import re
import sys
import uuid

from langchain_core.messages import HumanMessage

# 确保 src/ 在 import 路径中，以便导入 llm_factory
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
from llm_factory import create_chat_model, extract_text

from oasis.forum import DiscussionForum
from oasis.experts import ExpertAgent, SessionExpert, ExternalExpert, get_all_experts
from oasis.scheduler import (
    Schedule, ScheduleStep, StepType, Edge, ConditionalEdge, SelectorEdge,
    START, END, MAX_SUPER_STEPS,
    parse_schedule, load_schedule_file, extract_expert_names, collect_external_configs,
)

# Maximum total node executions across all super-steps (safety limit)
_MAX_TOTAL_NODE_EXECS = 500

# Regex for parsing selector node output: [oasis reply choose N]
_OASIS_REPLY_CHOOSE_RE = re.compile(r"\[oasis\s+reply\s+choose\s+(\d+)\]", re.IGNORECASE)

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
      "name#ext#id"         → ExternalExpert (api_url/api_key/model from YAML)
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
        discussion: bool | None = None,
    ):
        self.forum = forum
        self._cancelled = False
        self._early_stop = early_stop
        self._discussion_override = discussion  # API-level override (None = use YAML)

        # ── Step 1: Parse schedule (required) ──
        self.schedule: Schedule | None = None
        if schedule:
            self.schedule = schedule
        elif schedule_file:
            self.schedule = load_schedule_file(schedule_file)
        elif schedule_yaml:
            self.schedule = parse_schedule(schedule_yaml)

        if not self.schedule:
            raise ValueError(
                "schedule_yaml or schedule_file is required. "
                "For simple all-parallel, use: version: 1\\nrepeat: true\\nplan:\\n  - all_experts: true"
            )

        # discussion mode: API override > YAML setting > default False
        if self._discussion_override is not None:
            self._discussion = self._discussion_override
        else:
            self._discussion = self.schedule.discussion

        # ── Step 2: Build expert pool from YAML ──
        experts_list: list[ExpertAgent | SessionExpert | ExternalExpert] = []

        yaml_names = extract_expert_names(self.schedule)
        ext_configs = collect_external_configs(self.schedule)
        seen: set[str] = set()
        # Map YAML original names → expert (built during pool construction)
        yaml_to_expert: dict[str, ExpertAgent | SessionExpert | ExternalExpert] = {}
        for full_name in yaml_names:
            if full_name in seen:
                continue
            seen.add(full_name)

            if "#" not in full_name:
                print(f"  [OASIS] ⚠️ YAML expert name '{full_name}' has no '#', skipping. "
                      f"Use 'tag#temp#N' or 'tag#oasis#id' or 'name#ext#id' or 'title#session_id'.")
                continue

            # Handle #new suffix: strip only "new", keep the '#' separator
            force_new = full_name.endswith("#new")
            working_name = full_name[:-3] if force_new else full_name  # strip "new" only

            first, sid = working_name.split("#", 1)
            expert: ExpertAgent | SessionExpert | ExternalExpert
            if sid.startswith("ext#"):
                # e.g. "分析师#ext#analyst" → ExternalExpert
                ext_id = sid.split("#", 1)[1]
                if force_new:
                    ext_id = uuid.uuid4().hex[:8]
                    print(f"  [OASIS] 🆕 #new: '{full_name}' → new external session '{ext_id}'")
                cfg = ext_configs.get(full_name, {})
                is_openclaw = first.lower() == "openclaw"
                if not cfg.get("api_url") and not is_openclaw:
                    print(f"  [OASIS] ⚠️ External expert '{full_name}' missing 'api_url' in YAML, skipping.")
                    continue
                # OpenClaw agents can work via CLI without api_url
                api_url = cfg.get("api_url", "") or ""
                model_str = cfg.get("model", "gpt-3.5-turbo")
                config = self._lookup_by_tag(first, user_id)
                expert_name = config["name"] if config else first
                persona = config.get("persona", "") if config else ""
                expert = ExternalExpert(
                    name=expert_name,
                    ext_id=ext_id,
                    api_url=api_url,
                    api_key=cfg.get("api_key", "") or os.getenv("OPENCLAW_GATEWAY_TOKEN", ""),
                    model=model_str,
                    persona=persona,
                    timeout=bot_timeout,
                    tag=first,
                    extra_headers=cfg.get("headers"),
                )
                if is_openclaw and not api_url:
                    print(f"  [OASIS] 🦞 OpenClaw agent: {expert.name} (CLI only, no api_url)")
                else:
                    print(f"  [OASIS] 🌐 External expert: {expert.name} → {api_url}")
            elif sid.startswith("temp#"):
                # e.g. "creative#temp#1" → ExpertAgent with explicit temp_id
                config = self._lookup_by_tag(first, user_id)
                expert_name = config["name"] if config else first
                persona = config.get("persona", "") if config else ""
                temp_num = sid.split("#", 1)[1]
                expert = ExpertAgent(
                    name=expert_name,
                    persona=persona,
                    temp_id=int(temp_num) if temp_num.isdigit() else None,
                    tag=first,
                )
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
                cfg = ext_configs.get(full_name, {})
                expert = SessionExpert(
                    name=expert_name,
                    session_id=f"{first}#{actual_sid}",
                    user_id=user_id,
                    persona=persona,
                    bot_base_url=bot_base_url,
                    enabled_tools=bot_enabled_tools,
                    timeout=bot_timeout,
                    tag=first,
                    extra_headers=cfg.get("headers"),
                )
            else:
                # e.g. "助手#default" → SessionExpert (regular agent, no injection)
                if force_new:
                    actual_sid = uuid.uuid4().hex[:8]
                    print(f"  [OASIS] 🆕 #new: '{full_name}' → new session '{actual_sid}'")
                else:
                    actual_sid = sid
                cfg = ext_configs.get(full_name, {})
                expert = SessionExpert(
                    name=first,
                    session_id=actual_sid,
                    user_id=user_id,
                    persona="",
                    bot_base_url=bot_base_url,
                    enabled_tools=bot_enabled_tools,
                    timeout=bot_timeout,
                    extra_headers=cfg.get("headers"),
                )

            experts_list.append(expert)
            # Register YAML original name → expert immediately (handles #new correctly)
            yaml_to_expert[full_name] = expert

        self.experts = experts_list
        self._total_node_execs = 0  # safety counter for Pregel super-step execution

        # Build lookup map: YAML original names first (highest priority for scheduling),
        # then register by internal name, title, tag, session_id as shortcuts
        self._expert_map: dict[str, ExpertAgent | SessionExpert | ExternalExpert] = {}
        self._expert_map.update(yaml_to_expert)
        for e in self.experts:
            self._expert_map.setdefault(e.name, e)       # "创意专家#creative#oasis#e7f3a2b1"
            self._expert_map.setdefault(e.title, e)      # "创意专家" (first-come wins)
            if e.tag:
                self._expert_map.setdefault(e.tag, e)    # "creative" (first-come wins)
            if hasattr(e, "session_id"):
                self._expert_map.setdefault(e.session_id, e)  # session_id shortcut
            if hasattr(e, "ext_id"):
                self._expert_map.setdefault(e.ext_id, e)  # ext_id shortcut

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
        self.forum.discussion = self._discussion
        self.forum.start_clock()

        session_count = sum(1 for e in self.experts if isinstance(e, SessionExpert))
        external_count = sum(1 for e in self.experts if isinstance(e, ExternalExpert))
        direct_count = len(self.experts) - session_count - external_count
        mode_label = "discussion" if self._discussion else "execute"
        n_nodes = len(self.schedule.nodes)
        n_edges = len(self.schedule.edges) + len(self.schedule.conditional_edges)
        print(
            f"[OASIS] 🏛️ Discussion started: {self.forum.topic_id} "
            f"({len(self.experts)} experts [{direct_count} direct, {session_count} session, {external_count} external], "
            f"graph: {n_nodes} nodes, {n_edges} edges, mode={mode_label})"
        )

        try:
            max_repeats = 1
            if self.schedule.repeat:
                max_repeats = self.schedule.max_repeat if self.schedule.max_repeat > 0 else self.forum.max_rounds

            can_early_stop = self._early_stop and self._discussion

            for repeat_round in range(max_repeats):
                self._check_cancelled()
                if max_repeats > 1:
                    self.forum.current_round = repeat_round + 1
                    self.forum.log_event("repeat", detail=f"Repeat {repeat_round + 1}/{max_repeats}")
                    print(f"[OASIS] 📢 Repeat round {repeat_round + 1}/{max_repeats}")

                await self._run_graph()

                if can_early_stop and repeat_round >= 1 and await self._consensus_reached():
                    print(f"[OASIS] 🤝 Consensus reached at repeat round {repeat_round + 1}")
                    break

            if self._discussion:
                self.forum.conclusion = await self._summarize()
            else:
                # Execute mode: just collect outputs, no LLM summary
                all_posts = await self.forum.browse()
                if all_posts:
                    self.forum.conclusion = "\n\n".join(
                        f"【{p.author}】\n{p.content}" for p in all_posts
                    )
                else:
                    self.forum.conclusion = "执行完成，无输出。"
            self.forum.log_event("conclude", detail="Discussion concluded")
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

    async def _run_graph(self):
        """Execute the graph using Pregel-style super-step iteration.

        Algorithm:
          1. Initialize: activate all entry nodes (nodes with no incoming edges)
          2. Super-step loop:
             a. Execute all activated nodes in parallel
             b. For each completed node, evaluate outgoing edges:
                - Fixed edges: always fire → activate target
                - Conditional edges: evaluate condition → activate chosen target
             c. Collect newly activated nodes for next super-step
             d. If no new activations or END reached → stop
          3. Safety: stop after MAX_SUPER_STEPS to prevent infinite loops
        """
        sched = self.schedule
        node_map = sched.node_map

        # Track which nodes have been completed in this execution
        # For cycles: a node can be activated multiple times
        completed_set: set[str] = set()     # tracks last-completed nodes (for trigger checking)
        super_step = 0

        # Start with entry nodes
        activated: set[str] = set(sched.entry_nodes)
        reached_end = False

        print(f"  [OASIS] 🚀 Graph engine start: {len(sched.nodes)} nodes, entry={list(activated)}")
        self.forum.log_event("graph_start", detail=f"nodes={len(sched.nodes)}, entries={list(activated)}")

        while activated and super_step < MAX_SUPER_STEPS:
            self._check_cancelled()
            super_step += 1

            # Safety limit on total node executions
            self._total_node_execs += len(activated)
            if self._total_node_execs > _MAX_TOTAL_NODE_EXECS:
                raise RuntimeError(
                    f"Safety limit reached: {self._total_node_execs} total node executions "
                    f"(max {_MAX_TOTAL_NODE_EXECS}). Possible infinite loop in graph."
                )

            activated_list = sorted(activated)  # deterministic order
            print(f"  [OASIS] ⚡ Super-step {super_step}: executing {activated_list}")
            self.forum.log_event("super_step", detail=f"step={super_step}, nodes={activated_list}")

            # Update forum progress
            self.forum.current_round = super_step
            self.forum.max_rounds = max(super_step, len(sched.nodes))

            # Execute all activated nodes in parallel
            async def _exec_node(node_id: str):
                node = node_map[node_id]
                # Build visibility: in execute mode, only see posts from upstream nodes
                vis = self._build_visibility_filter_graph(node_id, completed_set)
                await self._execute_node(node, vis)

            if len(activated_list) == 1:
                # Single node: execute directly (avoids gather overhead)
                await _exec_node(activated_list[0])
            else:
                # Multiple nodes: execute in parallel
                results = await asyncio.gather(
                    *[_exec_node(nid) for nid in activated_list],
                    return_exceptions=True,
                )
                for nid, r in zip(activated_list, results):
                    if isinstance(r, Exception) and not isinstance(r, asyncio.CancelledError):
                        print(f"  [OASIS] ❌ Node '{nid}' error: {r}")
                        # Continue with other nodes; don't propagate error to stop entire graph

            # Mark nodes as completed
            for nid in activated_list:
                completed_set.add(nid)

            # Evaluate outgoing edges to determine next activated nodes
            next_activated: set[str] = set()

            for nid in activated_list:
                # Fixed edges: always fire
                for edge in sched.out_edges.get(nid, []):
                    if edge.target == END:
                        reached_end = True
                        continue
                    # Check if ALL incoming sources of target are completed
                    target_in = sched.in_sources.get(edge.target, set())
                    if target_in.issubset(completed_set):
                        next_activated.add(edge.target)
                    # For cycles: if this is a back-edge, activate immediately
                    # (the node was completed before, so re-activate it)
                    elif edge.target in completed_set:
                        # Back-edge: re-activate for next iteration
                        completed_set.discard(edge.target)
                        next_activated.add(edge.target)

                # Conditional edges: evaluate condition to pick target
                for ce in sched.out_cond_edges.get(nid, []):
                    cond_result = await self._eval_condition(ce.condition)
                    if cond_result:
                        target = ce.then_target
                        print(f"  [OASIS] 🔀 Condition '{ce.condition}' → TRUE → {target}")
                    else:
                        target = ce.else_target
                        print(f"  [OASIS] 🔀 Condition '{ce.condition}' → FALSE → {target or 'none'}")

                    if not target:
                        continue
                    if target == END:
                        reached_end = True
                        continue

                    self.forum.log_event("condition", detail=f"'{ce.condition}' → {target}")

                    # Conditional edge respects the same AND-trigger rule as fixed edges:
                    # the target is only activated when ALL its fixed-edge in_sources
                    # are satisfied.  (in_sources no longer contains conditional-edge
                    # sources, so this check won't be blocked by unresolved back-edges.)
                    target_in = sched.in_sources.get(target, set())
                    if target in completed_set:
                        # Back-edge / loop: re-activate the already-completed node
                        completed_set.discard(target)
                        next_activated.add(target)
                    elif target_in.issubset(completed_set):
                        next_activated.add(target)
                    else:
                        # Fixed-edge predecessors not yet done — defer activation.
                        # The target will be picked up later when its fixed-edge
                        # sources complete.
                        print(f"  [OASIS] ⏳ Conditional target '{target}' deferred: "
                              f"waiting for fixed-edge sources {target_in - completed_set}")

                # Selector edges: parse LLM output to pick target
                se = sched.out_selector_edges.get(nid)
                if se:
                    # Get the last post from this node's agent to find the choice
                    all_posts = await self.forum.browse()
                    node_step = sched.node_map.get(nid)
                    node_agents = self._resolve_experts(node_step.expert_names) if node_step else []
                    node_author_names = {a.name for a in node_agents}
                    # Find the last post from this node's agents
                    selector_output = ""
                    for p in reversed(all_posts):
                        if p.author in node_author_names:
                            selector_output = p.content
                            break
                    # Parse [oasis reply choose N]
                    match = _OASIS_REPLY_CHOOSE_RE.search(selector_output)
                    if match:
                        choice_num = int(match.group(1))
                        target = se.choices.get(choice_num, "")
                        print(f"  [OASIS] 🎯 Selector '{nid}' chose [{choice_num}] → {target or 'invalid'}")
                        self.forum.log_event("selector", detail=f"chose [{choice_num}] → {target}")
                        if target and target != END:
                            target_in = sched.in_sources.get(target, set())
                            if target in completed_set:
                                completed_set.discard(target)
                                next_activated.add(target)
                            elif target_in.issubset(completed_set):
                                next_activated.add(target)
                            else:
                                print(f"  [OASIS] ⏳ Selector target '{target}' deferred")
                        elif target == END:
                            reached_end = True
                    else:
                        # No valid choice found — default to first choice
                        if se.choices:
                            first_key = min(se.choices.keys())
                            target = se.choices[first_key]
                            print(f"  [OASIS] ⚠️ Selector '{nid}' no valid [oasis reply choose N] found in output, defaulting to [{first_key}] → {target}")
                            self.forum.log_event("selector_default", detail=f"default [{first_key}] → {target}")
                            if target and target != END:
                                target_in = sched.in_sources.get(target, set())
                                if target in completed_set:
                                    completed_set.discard(target)
                                    next_activated.add(target)
                                elif target_in.issubset(completed_set):
                                    next_activated.add(target)
                            elif target == END:
                                reached_end = True

            # If END was reached and no other nodes activated, stop
            if reached_end and not next_activated:
                print(f"  [OASIS] 🏁 Reached END at super-step {super_step}")
                break

            # Check: nodes with no outgoing edges that just completed = implicit END
            if not next_activated:
                # All activated nodes had no outgoing edges → implicit end
                all_terminal = all(
                    not sched.out_edges.get(nid) and not sched.out_cond_edges.get(nid) and not sched.out_selector_edges.get(nid)
                    for nid in activated_list
                )
                if all_terminal:
                    print(f"  [OASIS] 🏁 All terminal nodes completed at super-step {super_step}")
                    break

            activated = next_activated

        if super_step >= MAX_SUPER_STEPS:
            print(f"  [OASIS] ⚠️ Max super-steps ({MAX_SUPER_STEPS}) reached, stopping graph")
            self.forum.log_event("graph_max_steps", detail=f"stopped at {super_step}")

        self.forum.log_event("graph_end", detail=f"completed in {super_step} super-steps")
        print(f"  [OASIS] 🏁 Graph completed in {super_step} super-steps, {self._total_node_execs} node executions")

    def _build_visibility_filter_graph(self, node_id: str, completed_set: set[str]) -> dict:
        """Build visibility filter for a node based on its upstream nodes in the graph.

        In execute mode (non-discussion):
          Agent can only see posts from direct upstream (incoming edge source) nodes.
        In discussion mode: no filtering (returns empty dict).
        """
        if self._discussion:
            return {}

        sched = self.schedule
        # Find all nodes that have edges pointing TO this node
        upstream_ids = sched.in_sources.get(node_id, set())
        # Only include completed upstream nodes
        active_upstream = upstream_ids & completed_set

        if not active_upstream:
            return {"visible_authors": set()}

        upstream_authors: set[str] = set()
        for uid in active_upstream:
            up_node = sched.node_map.get(uid)
            if up_node:
                agents = self._resolve_experts(up_node.expert_names)
                for a in agents:
                    upstream_authors.add(a.name)
        return {"visible_authors": upstream_authors}

    async def _eval_condition(self, condition: str) -> bool:
        """Evaluate a condition expression against current forum state.

        Supported expressions:
          last_post_contains:<keyword>       — last post content contains keyword
          last_post_not_contains:<keyword>   — last post does NOT contain keyword
          post_count_gte:<N>                 — total post count >= N
          post_count_lt:<N>                  — total post count < N
          always                             — always true
          !<expr>                            — negate any expression
        """
        expr = condition.strip()

        # Handle negation prefix
        if expr.startswith("!"):
            inner = expr[1:].strip()
            return not await self._eval_condition(inner)

        if expr == "always":
            return True

        # Get last post for content-based conditions
        all_posts = await self.forum.browse()
        last_post_content = all_posts[-1].content if all_posts else ""

        if expr.startswith("last_post_contains:"):
            keyword = expr.split(":", 1)[1]
            return keyword in last_post_content

        if expr.startswith("last_post_not_contains:"):
            keyword = expr.split(":", 1)[1]
            return keyword not in last_post_content

        if expr.startswith("post_count_gte:"):
            n = int(expr.split(":", 1)[1])
            return len(all_posts) >= n

        if expr.startswith("post_count_lt:"):
            n = int(expr.split(":", 1)[1])
            return len(all_posts) < n

        print(f"  [OASIS] ⚠️ Unknown condition expression: '{expr}', treating as false")
        return False

    async def _execute_node(self, step: ScheduleStep, vis: dict | None = None):
        """Execute a single graph node."""
        disc = self._discussion
        if vis is None:
            vis = {}

        if step.step_type == StepType.MANUAL:
            print(f"  [OASIS] 📝 Manual post by {step.manual_author}")
            self.forum.log_event("manual_post", agent=step.manual_author)
            await self.forum.publish(
                author=step.manual_author,
                content=step.manual_content,
                reply_to=step.manual_reply_to,
            )

        elif step.step_type == StepType.ALL:
            print(f"  [OASIS] 👥 All experts speak")
            for expert in self.experts:
                self.forum.log_event("agent_call", agent=expert.name)

            async def _tracked_participate(expert):
                try:
                    await expert.participate(self.forum, discussion=disc, **vis)
                finally:
                    self.forum.log_event("agent_done", agent=expert.name)

            await asyncio.gather(
                *[_tracked_participate(e) for e in self.experts],
                return_exceptions=True,
            )

        elif step.step_type == StepType.EXPERT:
            agents = self._resolve_experts(step.expert_names)
            if agents:
                instr = step.instructions.get(step.expert_names[0], "")
                # For selector nodes: inject choice prompt
                selector_instr = ""
                if step.is_selector:
                    se = self.schedule.out_selector_edges.get(step.node_id)
                    if se and se.choices:
                        choices_desc = []
                        for num in sorted(se.choices.keys()):
                            target_id = se.choices[num]
                            target_node = self.schedule.node_map.get(target_id)
                            target_name = target_node.expert_names[0] if target_node and target_node.expert_names else target_id
                            choices_desc.append(f"  [oasis reply choose {num}] → {target_name} ({target_id})")
                        selector_instr = (
                            "\n\n⚠️ SELECTOR INSTRUCTION:\n"
                            "你需要根据上下文选择下一步操作。可选路径如下：\n"
                            + "\n".join(choices_desc) +
                            "\n请在你的回复中包含对应的选择标签，例如 [oasis reply choose 1]。\n"
                            "只选一个。"
                        )
                combined_instr = (instr + selector_instr) if instr else selector_instr
                print(f"  [OASIS] 🎤 {agents[0].name} speaks" + (f" (instruction: {combined_instr[:60]}...)" if combined_instr else "") + (" [SELECTOR]" if step.is_selector else ""))
                self.forum.log_event("agent_call", agent=agents[0].name, detail=combined_instr[:80] if combined_instr else "")
                await agents[0].participate(self.forum, instruction=combined_instr, discussion=disc, **vis)
                self.forum.log_event("agent_done", agent=agents[0].name)

        elif step.step_type == StepType.PARALLEL:
            agents = self._resolve_experts(step.expert_names)
            if agents:
                names = ", ".join(a.name for a in agents)
                print(f"  [OASIS] 🎤 Parallel: {names}")
                for agent, yaml_name in zip(agents, step.expert_names):
                    par_instr = step.instructions.get(yaml_name, "")
                    self.forum.log_event("agent_call", agent=agent.name, detail=par_instr[:80] if par_instr else "")

                async def _run_with_instr(agent, yaml_name):
                    instr = step.instructions.get(yaml_name, "")
                    try:
                        await agent.participate(self.forum, instruction=instr, discussion=disc, **vis)
                    finally:
                        self.forum.log_event("agent_done", agent=agent.name, detail=instr[:80] if instr else "")

                await asyncio.gather(
                    *[_run_with_instr(a, n) for a, n in zip(agents, step.expert_names)],
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
