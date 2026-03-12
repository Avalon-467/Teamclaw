"""
OASIS Forum - Discussion Engine

Manages the full lifecycle of a discussion:
  Round loop -> scheduled/parallel expert participation -> consensus check -> summarize

Three expert backends:
  1. ExpertAgent  — direct LLM (stateless, name="tag#temp#N")
  2. SessionExpert — internal session agent (stateful, name="tag#oasis#name" or "#oasis#name")
     - name is resolved to session_id via internal agent JSON (oasis_agents.json)
     - tag (if present) enables persona injection from presets
  3. ExternalExpert — external OpenAI-compatible API (name="tag#ext#id")
     - Directly calls external endpoints (DeepSeek, GPT-4, Ollama, etc)
     - Configured per-expert via YAML: api_url, api_key, model
     - OpenClaw CLI priority: model "agent:<name>" uses CLI first, HTTP fallback

Expert pool sourcing (YAML-only, schedule_file or schedule_yaml required):
  Pool is built entirely from YAML expert names (deduplicated).
  Priority: schedule_file > schedule_yaml (file takes precedence if both provided).
  Names MUST contain '#' to specify type:
    "tag#temp#N"              → ExpertAgent (tag looked up in presets for name/persona)
    "tag#oasis#<name>"       → SessionExpert (name→session lookup, tag→persona)
    "#oasis#<name>"          → SessionExpert (name→session lookup, no tag)
    "name#ext#<id>"          → ExternalExpert (requires api_url in YAML)
  Names without '#' are skipped with a warning.

  Session IDs are resolved from agent names via internal agent JSON.
  To explicitly ensure a fresh session, append "#new" to the name:
    "tag#oasis#name#new"  → "#new" is stripped, resolved session_id replaced with random UUID
  This guarantees no accidental reuse of an existing session.

  If YAML uses `all_experts: true`, all experts in the pool speak in parallel.
  Even for simple all-parallel scenarios, a minimal YAML suffices:
    version: 1
    repeat: true
    plan:
      - all_experts: true

No separate expert-session storage: session_ids are resolved from agent names
via internal agent JSON (oasis_agents.json), then used to access the
Agent checkpoint DB.

Execution modes:
  1. Default (repeat + all_experts): all experts participate in parallel each round
  2. Scheduled: follow a YAML schedule that defines speaking order per step
"""

import asyncio
import json
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

# Path to internal agent config directory (default, non-team)
_INTERNAL_AGENT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "user_files", "internalagent"
)
# Project root for team-scoped paths
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))


def _load_internal_agents(user_id: str, team: str = "") -> list[dict]:
    """Load the internal-agent JSON list for a user.

    Reads two files and merges them:
      - oasis_agents.json: {"agents": [{"name": ..., "tag": ...}]}
      - oasis_sessions.json: {"agent_name": "session_id", ...}

    If team is specified, load from the team-scoped path:
      data/user_files/{user_id}/teams/{team}/oasis_*.json
    Otherwise load from:
      data/user_files/internalagent/oasis_*.json

    Returns list of {"session": "<id>", "meta": {"name": ..., "tag": ...}} entries.
    Returns [] if file missing or unreadable.
    """
    if team:
        base_dir = os.path.join(_PROJECT_ROOT, "data", "user_files", user_id, "teams", team)
    else:
        base_dir = _INTERNAL_AGENT_DIR

    agents_path = os.path.join(base_dir, "oasis_agents.json")
    sessions_path = os.path.join(base_dir, "oasis_sessions.json")

    # Load agent metadata from oasis_agents.json
    agents_list: list[dict] = []
    if os.path.isfile(agents_path):
        try:
            with open(agents_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "agents" in data and isinstance(data["agents"], list):
                agents_list = data["agents"]
            elif isinstance(data, list):
                agents_list = data
        except Exception:
            pass

    # Build name -> meta mapping
    name_to_meta: dict[str, dict] = {}
    for a in agents_list:
        if isinstance(a, dict) and "name" in a:
            name_to_meta[a["name"]] = a

    # Load name -> session_id mapping from oasis_sessions.json
    name_to_session: dict[str, str] = {}
    if os.path.isfile(sessions_path):
        try:
            with open(sessions_path, "r", encoding="utf-8") as f:
                name_to_session = json.load(f)
        except Exception:
            pass

    # Merge: build [{"session": "sid", "meta": {"name": ..., "tag": ...}}, ...]
    result: list[dict] = []
    for name, sid in name_to_session.items():
        meta = name_to_meta.get(name, {})
        if "name" not in meta:
            meta = dict(meta)
            meta["name"] = name
        result.append({"session": sid, "meta": meta})

    return result


def _resolve_session_by_name(agents: list[dict], name: str) -> str | None:
    """Find session_id by matching agent meta.name (case-insensitive).

    Returns the session_id string, or None if not found.
    """
    name_lower = name.lower()
    for a in agents:
        meta = a.get("meta", {})
        if meta.get("name", "").lower() == name_lower:
            return a.get("session", "")
    return None


def _find_tag_in_internal_agents(agents: list[dict], session_id: str) -> str:
    """Find the tag from internal agent JSON by session_id.

    Returns the tag string, or "" if not found.
    """
    for a in agents:
        if a.get("session") == session_id:
            return a.get("meta", {}).get("tag", "")
    return ""

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
      "tag#oasis#name"      → SessionExpert (name→session lookup, tag→persona)
      "#oasis#name"         → SessionExpert (name→session lookup, no tag)
      "name#ext#id"         → ExternalExpert (api_url/api_key/model from YAML)
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
        team: str = "",
    ):
        self.forum = forum
        self._cancelled = False
        self._early_stop = early_stop
        self._discussion_override = discussion  # API-level override (None = use YAML)
        self._team = team  # Team name for scoped agent storage

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
        internal_agents = _load_internal_agents(user_id, self._team)  # for name→session lookup
        seen: set[str] = set()
        # Map YAML original names → expert (built during pool construction)
        yaml_to_expert: dict[str, ExpertAgent | SessionExpert | ExternalExpert] = {}
        for full_name in yaml_names:
            if full_name in seen:
                continue
            seen.add(full_name)

            if "#" not in full_name:
                print(f"  [OASIS] ⚠️ YAML expert name '{full_name}' has no '#', skipping. "
                      f"Use 'tag#temp#N' or 'tag#oasis#name' or '#oasis#name' or 'name#ext#id'.")
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
                config = self._lookup_by_tag(first, user_id, self._team)
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
                    team=self._team,
                )
                if is_openclaw and not api_url:
                    print(f"  [OASIS] 🦞 OpenClaw agent: {expert.name} (CLI only, no api_url)")
                else:
                    print(f"  [OASIS] 🌐 External expert: {expert.name} → {api_url}")
            elif sid.startswith("temp#"):
                # e.g. "creative#temp#1" → ExpertAgent with explicit temp_id
                config = self._lookup_by_tag(first, user_id, self._team)
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
                # Session agent by name:
                #   "tag#oasis#<name>"      → name lookup for session_id (tag→persona)
                #   "oasis#<name>"          → name lookup (no tag, first is empty from '#oasis#name' split)
                # Also handles leading '#': '#oasis#name' splits as first='', sid='oasis#name'

                # Extract the part after 'oasis#'
                oasis_rest = sid.split("oasis#", 1)[1] if "oasis#" in sid else ""

                # Resolve oasis_rest as an agent name
                resolved_sid = _resolve_session_by_name(internal_agents, oasis_rest) if oasis_rest else None

                if not resolved_sid:
                    print(f"  [OASIS] ⚠️ Cannot resolve agent name '{oasis_rest}' from internal agents JSON, skipping '{full_name}'.")
                    continue

                agent_name = oasis_rest
                tag_for_lookup = first  # may be empty for '#oasis#name'

                if force_new:
                    actual_sid = uuid.uuid4().hex[:8]
                    print(f"  [OASIS] 🆕 #new: '{full_name}' → new session '{actual_sid}'")
                else:
                    actual_sid = resolved_sid

                # Tag lookup for persona (like ExternalExpert): found → use it, not found → skip
                persona = ""
                expert_name = agent_name
                ia_tag = ""
                if tag_for_lookup:
                    config = self._lookup_by_tag(tag_for_lookup, user_id, self._team)
                    if config:
                        expert_name = config.get("name", agent_name)
                        persona = config.get("persona", "")
                        print(f"  [OASIS] 🏷️ Tag '{tag_for_lookup}' → persona for '{expert_name}'")
                else:
                    # No explicit tag in YAML, try to find tag from internal agent JSON
                    ia_tag = _find_tag_in_internal_agents(internal_agents, resolved_sid)
                    if ia_tag:
                        config = self._lookup_by_tag(ia_tag, user_id, self._team)
                        if config:
                            persona = config.get("persona", "")
                            print(f"  [OASIS] 🏷️ Auto-detected tag '{ia_tag}' → persona for '{expert_name}'")

                cfg = ext_configs.get(full_name, {})
                expert = SessionExpert(
                    name=expert_name,
                    session_id=actual_sid,
                    user_id=user_id,
                    persona=persona,
                    bot_base_url=bot_base_url,
                    enabled_tools=bot_enabled_tools,
                    timeout=bot_timeout,
                    tag=tag_for_lookup or ia_tag,
                    extra_headers=cfg.get("headers"),
                )
                print(f"  [OASIS] 💬 Session agent (name): '{agent_name}' → session '{actual_sid}'")
            else:
                # Unknown format — skip with warning
                print(f"  [OASIS] ⚠️ Unrecognized expert name format '{full_name}', skipping. "
                      f"Use 'tag#temp#N' or 'tag#oasis#name' or '#oasis#name' or 'name#ext#id'.")
                continue

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
            self._expert_map.setdefault(e.name, e)       # expert display name
            self._expert_map.setdefault(e.title, e)      # "创意专家" (first-come wins)
            if e.tag:
                self._expert_map.setdefault(e.tag, e)    # "creative" (first-come wins)
            if hasattr(e, "session_id"):
                self._expert_map.setdefault(e.session_id, e)  # session_id shortcut
            if hasattr(e, "ext_id"):
                self._expert_map.setdefault(e.ext_id, e)  # ext_id shortcut

        self.summarizer = _get_summarizer()

    @staticmethod
    def _lookup_by_tag(tag: str, user_id: str, team: str = "") -> dict | None:
        """Find expert config by tag. Returns {"name", "persona", ...} or None.

        When *team* is provided, team-specific experts take priority (they
        appear first in the list returned by get_all_experts).
        """
        for c in get_all_experts(user_id, team=team):
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
                    print(f"  [OASIS] 🔍 Selector '{nid}' raw output (first 200 chars): {selector_output[:200]!r}")
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
                            "\n\n🔴 关键格式要求（必须严格遵守）：\n"
                            "你的回复**第一行**必须是以下格式之一（完全匹配，包含方括号）：\n"
                            "[oasis reply choose 1]\n"
                            "[oasis reply choose 2]\n"
                            "... 等等（仅选一个）。\n"
                            "选择标记必须放在回复的最开头第一行！后面可以跟你的分析理由。\n"
                            "这是系统识别你选择的唯一方式，不输出此格式将导致默认选择第一项。"
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
