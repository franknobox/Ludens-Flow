import logging
from typing import Tuple, Dict, Any, Optional

from ludens_flow.state import LudensState, save_state, write_trace_log
from ludens_flow.artifacts import write_artifact
from ludens_flow.prompt_templates import load_prompt_template
from ludens_flow.router import ludens_router_logic_with_action, Phase
from ludens_flow.agents.base import AgentResult

# 引入各个单体 Agent，避免重复实例化
from ludens_flow.agents.design_agent import DesignAgent
from ludens_flow.agents.pm_agent import PMAgent
from ludens_flow.agents.engineering_agent import EngineeringAgent
from ludens_flow.agents.review_agent import ReviewAgent

logger = logging.getLogger(__name__)

_ERROR_TIMEOUT = "TIMEOUT"
_ERROR_PARSE = "PARSE"
_ERROR_NODE = "NODE"

# Graph 编排层。
# 负责 phase 跳转、Agent 调用、状态合并、日志和落盘。

# 单例化全局使用的 Agent
_gdd_agent = DesignAgent()
_pm_agent = PMAgent()
_eng_agent = EngineeringAgent()
_review_agent = ReviewAgent()


def _phase_to_agent_name(phase: str) -> str:
    if not phase:
        return "System"
    if phase.startswith("GDD_"):
        return "DesignAgent"
    if phase.startswith("PM_"):
        return "PMAgent"
    if phase.startswith("ENG_") or phase == "DEV_COACHING":
        return "EngineeringAgent"
    if phase.startswith("REVIEW") or phase == "POST_REVIEW_DECISION":
        return "ReviewAgent"
    return "System"


def _user_input_to_text(user_input: Any) -> str:
    if isinstance(user_input, str):
        return user_input
    if isinstance(user_input, list):
        text_parts = []
        image_count = 0
        for item in user_input:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                text_val = item.get("text", "")
                if text_val:
                    text_parts.append(str(text_val))
            elif item.get("type") == "image_url":
                image_count += 1
        text = " ".join(text_parts).strip()
        if image_count > 0:
            return f"{text} [images:{image_count}]".strip()
        return text
    return str(user_input)


def _append_transcript(
    state: LudensState, role: str, content: str, phase: str, agent: str
) -> None:
    # 完整对话流水，主要用于复盘和排障。
    state.transcript_history.append(
        {
            "role": role,
            "content": content,
            "phase": phase,
            "agent": agent,
        }
    )
    if len(state.transcript_history) > 500:
        state.transcript_history = state.transcript_history[-500:]


def _merge_state_updates(state: LudensState, updates: Dict[str, Any]) -> None:
    """把 Agent 的增量更新合并回全局状态。"""
    if "drafts" in updates:
        for phase_key, items in updates["drafts"].items():
            if phase_key not in state.drafts:
                state.drafts[phase_key] = {}
            state.drafts[phase_key].update(items)

    if "change_requests" in updates:
        state.change_requests.extend(updates["change_requests"])

    if "decisions" in updates:
        state.decisions.extend(updates["decisions"])

    if "style_preset" in updates and updates["style_preset"]:
        state.style_preset = updates["style_preset"]

    if "review_gate" in updates:
        # review_gate 按整体覆盖处理。
        state.review_gate = updates["review_gate"]


def _classify_agent_error(exc: Exception) -> str:
    message = str(exc or "").lower()
    if isinstance(exc, TimeoutError) or "timeout" in message or "timed out" in message:
        return _ERROR_TIMEOUT
    if any(
        marker in message
        for marker in ["parse", "schema", "json", "invalid agent result"]
    ):
        return _ERROR_PARSE
    return _ERROR_NODE


def _build_recovery_reply(node_name: str, category: str) -> str:
    if category == _ERROR_TIMEOUT:
        return (
            f"{node_name} 响应超时，我已保留当前阶段与上下文。"
            "请稍后重试，或缩短输入后继续。"
        )
    if category == _ERROR_PARSE:
        return (
            f"{node_name} 本轮输出未通过结构化校验，系统已自动回退到安全态。"
            "请换一种表述重试。"
        )
    return f"{node_name} 本轮执行失败，系统已保留当前阶段，避免流程漂移。请稍后重试。"


def run_agent_step(
    agent, mode: str, state: LudensState, user_input: Any
) -> LudensState:
    """统一执行单个 Agent 节点，并处理状态、日志与落盘。"""
    node_name = agent.name
    current_phase = state.phase
    is_frozen = getattr(state, "artifact_frozen", False)

    # 节点入口日志。
    write_trace_log(
        "ENTER",
        node_name,
        current_phase,
        is_frozen,
        state.last_event or "NONE",
        project_id=state.project_id,
    )

    logger.debug("run_agent_step -> agent=%s mode=%s", node_name, mode)

    try:
        orig_prompt = getattr(agent, "system_prompt", "") or ""
        profile_text = ""
        profile_instruction = (
            "请从用户输入中提取人物信息，并按要求输出：\n"
            "提取信息包括但不限于：nickname（昵称/姓名），preferences（风格/喜好），project_goals（项目目标/需求/开发内容)\n"
            "输出格式：[PROFILE_UPDATE] key: value\n"
            "例如：[PROFILE_UPDATE] nickname: Alice"
        )
        try:
            # 加载用户画像
            from ludens_flow.user_profile import load_profile, format_profile_for_prompt

            raw_profile_text = (
                load_profile(max_chars=2000, project_id=state.project_id) or ""
            ).strip()
            profile_text = format_profile_for_prompt(raw_profile_text)
        except Exception as e:
            logger.warning(f"Failed to load user profile: {e}")

        # 加载prompts/文件夹
        import os

        filename_map = {
            "DesignAgent": "design_agent.md",
            "PMAgent": "pm_agent.md",
            "EngineeringAgent": "engineering_agent.md",
            "ReviewAgent": "review_agent.md",
        }

        template_system = None
        try:
            fname = filename_map.get(getattr(agent, "name", ""))
            if fname:
                prompt_template = load_prompt_template(fname)
                if prompt_template:
                    # 对.md文件进行分割，part[0]是system prompt，part[1]是profile_instruction
                    built_system_prompt = prompt_template.build_system_prompt()
                    if built_system_prompt:
                        template_system = built_system_prompt
                    if prompt_template.profile_instruction.strip():
                        profile_instruction = (
                            prompt_template.profile_instruction.strip()
                        )
        except Exception as e:
            logger.debug(f"Failed to load prompt template for {agent.name}: {e}")

        if profile_text:
            user_persona_block = profile_instruction + "\n\n" + profile_text
        else:
            user_persona_block = profile_instruction

        # 按 mode 分发到对应能力入口。
        result = None
        agent_state_snapshot = LudensState.from_dict(state.to_dict())
        try:
            if template_system:
                agent.system_prompt = template_system
            else:
                agent.system_prompt = orig_prompt

            if mode == "DISCUSS":
                result: AgentResult = agent.discuss(
                    agent_state_snapshot, user_input, user_persona=user_persona_block
                )
            elif mode == "COMMIT":
                result: AgentResult = agent.commit(
                    agent_state_snapshot, user_input, user_persona=user_persona_block
                )
            elif mode == "PLAN_DISCUSS":
                result: AgentResult = getattr(agent, "plan_discuss")(
                    agent_state_snapshot,
                    user_input,
                    None,
                    user_persona=user_persona_block,
                )
            elif mode == "PLAN_COMMIT":
                result: AgentResult = getattr(agent, "plan_commit")(
                    agent_state_snapshot,
                    user_input,
                    None,
                    user_persona=user_persona_block,
                )
            elif mode == "COACH":
                result: AgentResult = getattr(agent, "coach")(
                    agent_state_snapshot,
                    user_input,
                    None,
                    user_persona=user_persona_block,
                )
            else:
                raise ValueError(f"Unknown agent mode: {mode}")
        finally:
            agent.system_prompt = orig_prompt

        if not isinstance(result, AgentResult):
            raise TypeError("Invalid agent result type returned by node execution.")

        if (
            mode in {"DISCUSS", "PLAN_DISCUSS", "COACH"}
            and not (result.assistant_message or "").strip()
            and not result.commit
        ):
            raise ValueError("Parse failure: empty discuss/coaching reply.")

        # 统一提取画像更新。
        try:
            parsed_profile_updates = getattr(result, "profile_updates", None) or []
            if not parsed_profile_updates and hasattr(agent, "extract_profile_updates"):
                try:
                    parsed_profile_updates = agent.extract_profile_updates(
                        result.assistant_message or ""
                    )
                except Exception as e:
                    logger.debug(
                        f"Failed to extract profile updates from agent output: {e}"
                    )
                    parsed_profile_updates = []

            if parsed_profile_updates:
                # 回填后续写入流程使用的数据结构。
                result.profile_updates = parsed_profile_updates

        except Exception as e:
            logger.warning(f"Error while parsing profile updates: {e}")

        # 统一合并状态更新。
        if result.state_updates:
            _merge_state_updates(state, result.state_updates)

        # 前端展示文本，过滤内部协议行。
        def _strip_profile_update_lines(text: str) -> str:
            import re

            if not text:
                return text
            lines = text.splitlines()
            filtered = [
                line
                for line in lines
                if not re.match(r"^\s*\[PROFILE_UPDATE\]", line, re.IGNORECASE)
            ]
            return "\n".join(filtered).strip()

        state.last_assistant_message = _strip_profile_update_lines(
            result.assistant_message
        )

        # chat_history 保留短期上下文，transcript_history 保留完整流水。
        has_meaningful_input = False
        if isinstance(user_input, list):
            has_meaningful_input = bool(user_input)  # Not empty list
        else:
            has_meaningful_input = bool(user_input.strip())

        if has_meaningful_input and result.assistant_message.strip():
            user_text = _user_input_to_text(user_input)
            state.chat_history.append({"role": "user", "content": user_text})
            state.chat_history.append(
                {"role": "assistant", "content": result.assistant_message}
            )
            _append_transcript(state, "user", user_text, current_phase, node_name)
            _append_transcript(
                state, "assistant", result.assistant_message, current_phase, node_name
            )
            # 只保留最近 20 条短期对话。
            if len(state.chat_history) > 20:
                state.chat_history = state.chat_history[-20:]

        commit_flag = "N"
        # 工件写入统一由 Graph 把关。
        if result.commit and result.commit.artifact_name and result.commit.content:
            art_name = result.commit.artifact_name
            # 冻结期只允许旁路工件写入。
            if is_frozen and art_name not in ["DEVLOG"]:
                logger.warning(
                    f"BLOCKED: {node_name} tried to commit '{art_name}' during frozen DEV_COACHING phase."
                )
                state.last_error = f"Cannot commit canonical artifact {art_name} while artifact_frozen=True"
                commit_flag = "BLOCKED"
                save_state(state)
                write_trace_log(
                    "LEAVE",
                    node_name,
                    current_phase,
                    is_frozen,
                    commit_flag,
                    project_id=state.project_id,
                )
                return state
            else:
                commit_reason = result.commit.reason or "Agent initiated commit"
                if "review_gate" in result.state_updates:
                    # Review 自动门禁写入特殊原因。
                    commit_reason = f"Review Auto-Gate, decision: {result.state_updates['review_gate'].get('status', 'PND')}"

                logger.debug(f">>>>> WRITE ARTIFACT GUARD <<<<<")
                logger.debug(f"Type of content: {type(result.commit.content)}")
                logger.debug(f"Content preview: {repr(result.commit.content[:100])}...")

                # 写工件并记录 artifacts.log。
                write_artifact(
                    name=art_name,
                    content=result.commit.content,
                    reason=commit_reason,
                    actor=node_name,
                    state=state,
                    project_id=state.project_id,
                )
                commit_flag = "Y"

                # Router 下一轮据此推进 phase。
                commit_event = f"{art_name}_COMMITTED".upper()
                if art_name == "PROJECT_PLAN":
                    commit_event = "PM_COMMITTED"
                elif art_name == "IMPLEMENTATION_PLAN":
                    commit_event = "ENG_COMMITTED"
                elif art_name == "REVIEW_REPORT":
                    commit_event = "REVIEW_DONE"

                state.last_event = commit_event

        # 节点主流程结束后保存 state。
        state.last_error = None  # 正常执行后清理报错记录
        save_state(state)

        # 用户画像独立于主工件冻结规则。
        try:
            if getattr(result, "profile_updates", None):
                from ludens_flow.user_profile import update_profile

                if update_profile(
                    result.profile_updates,
                    author=node_name,
                    project_id=state.project_id,
                ):
                    logger.info(
                        f"Merged {len(result.profile_updates)} profile updates from {node_name} into USER_PROFILE.md"
                    )
        except Exception as e:
            logger.warning(f"Failed to merge profile updates: {e}")

        # 节点出口日志。
        write_trace_log(
            "LEAVE",
            node_name,
            current_phase,
            is_frozen,
            commit_flag,
            project_id=state.project_id,
        )

    except Exception as e:
        # 节点异常在这里收口，避免整条链路直接中断。
        err_msg = str(e)
        category = _classify_agent_error(e)
        logger.error(
            f"[Agent Error][{category}] {node_name} execution failed: {err_msg}"
        )
        state.last_error = f"[{category}] {err_msg}"
        state.last_assistant_message = _build_recovery_reply(node_name, category)
        _append_transcript(
            state,
            "assistant",
            state.last_assistant_message,
            current_phase,
            node_name,
        )
        save_state(state)
        write_trace_log(
            "LEAVE",
            node_name,
            current_phase,
            is_frozen,
            f"ERR_{category}",
            error=err_msg,
            project_id=state.project_id,
        )

    return state


# --- Graph 阶段映射节点实体 ---


class RouterNode:
    """负责 phase 跳转，以及切换时的上下文整理。"""

    def execute(
        self,
        state: LudensState,
        user_input: str,
        explicit_action: Optional[str] = None,
    ) -> str:
        # 先由 router 决定下一阶段。
        result = ludens_router_logic_with_action(
            state,
            user_input,
            explicit_action=explicit_action,
        )

        from_phase = state.phase
        to_phase = result.next_phase

        # 跨 Agent 切换时，重置短期上下文并准备交接信息。
        from_prefix = from_phase.split("_")[0]
        to_prefix = to_phase.split("_")[0]

        if from_phase != to_phase:
            # 清空上一位 Agent 的短期记忆。
            if from_prefix != to_prefix or to_phase == "DEV_COACHING":
                state.chat_history = []
                logger.info(
                    f"Memory wiped for phase transition setting up next Context."
                )

                # 评审打回时，把 review_gate 摘要带回对应 DISCUSS 阶段。
                is_backflow = from_phase in (
                    "POST_REVIEW_DECISION",
                    "REVIEW",
                ) and to_phase.endswith("_DISCUSS")
                review_context = ""
                if is_backflow and state.review_gate:
                    issues = state.review_gate.get("issues", [])
                    if issues:
                        review_context = (
                            "\n\n📋 **评审反馈摘要（需要你本轮重点修正）**：\n"
                        )
                        for issue in issues:
                            tgt = issue.get("target", "?")
                            sev = issue.get("severity", "?")
                            summary = issue.get("summary", "")
                            hint = issue.get("fix_hint", "")
                            review_context += f"- [{sev}] ({tgt}) {summary}"
                            if hint:
                                review_context += f" → 建议：{hint}"
                            review_context += "\n"

                # 回流时补充当前工件内容，作为接手上下文。
                artifact_context = ""
                if is_backflow:
                    from ludens_flow.artifacts import read_artifact

                    if to_phase.startswith("GDD_"):
                        existing = read_artifact("GDD", project_id=state.project_id)
                        if existing.strip():
                            artifact_context = (
                                f"\n\n📄 **当前 GDD 版本内容**：\n{existing}"
                            )
                    elif to_phase.startswith("PM_"):
                        existing = read_artifact(
                            "PROJECT_PLAN", project_id=state.project_id
                        )
                        if existing.strip():
                            artifact_context = (
                                f"\n\n📄 **当前 PROJECT_PLAN 版本内容**：\n{existing}"
                            )
                    elif to_phase.startswith("ENG_"):
                        existing = read_artifact(
                            "IMPLEMENTATION_PLAN", project_id=state.project_id
                        )
                        if existing.strip():
                            artifact_context = f"\n\n📄 **当前 IMPLEMENTATION_PLAN 版本内容**：\n{existing}"

                # 为新 Agent 生成开场消息。
                greeting = ""
                if to_phase.startswith("GDD_"):
                    if is_backflow:
                        greeting = "我是 Dam (丹姆)，评审团 Revs 把你打回来找我了。我已经看过评审意见了，让我们一起把 GDD 打磨得更扎实！"
                    else:
                        greeting = "Hello，我是你的游戏主策划 Dam (丹姆)。很高兴接手这个项目的前期设计工作！你有什么天马行空的想法，直接砸过来吧！"
                elif to_phase.startswith("PM_"):
                    if is_backflow:
                        greeting = "Pax (帕克斯) 重新上线。评审反馈已收到，我们来调整一下排期和计划吧！"
                    else:
                        greeting = "你好！我是项目经理 Pax (帕克斯)。Dam 已经把需求同步过来了，我看过觉得很有意思。接下来我们来抓一抓排期和落地计划吧！"
                elif to_phase.startswith("ENG_") or to_phase == "DEV_COACHING":
                    if is_backflow:
                        greeting = "Eon (伊恩) 回来了。评审的技术问题我看到了，这次咱们把架构地基夯实！"
                    else:
                        greeting = "嗨！我是主程 Eon (伊恩)。前面的大饼我都看到了（笑）。接下来的技术选型和架构地基交给我，保证给你码踏实了。"
                elif to_phase == "REVIEW":
                    greeting = "各位好。我是终审节点 Revs (雷夫斯)。我这里的标准极其严格，不留情面，准备好接受全方位的查水表吧。"

                # 组合最终交接消息。
                full_greeting = greeting + review_context + artifact_context

                if full_greeting.strip():
                    state.last_assistant_message = full_greeting
                    state.chat_history.append(
                        {"role": "assistant", "content": full_greeting}
                    )
                    _append_transcript(
                        state,
                        "assistant",
                        full_greeting,
                        to_phase,
                        _phase_to_agent_name(to_phase),
                    )

        state.phase = to_phase
        save_state(state)

        logger.info(
            f"[RouterNode] Transition: {from_phase} -> {to_phase}. Reason: {result.explanation}"
        )
        return to_phase


class GDDNode:
    def execute(self, state: LudensState, user_input: str) -> LudensState:
        mode = "COMMIT" if state.phase == Phase.GDD_COMMIT.value else "DISCUSS"
        return run_agent_step(_gdd_agent, mode, state, user_input)


class PMNode:
    def execute(self, state: LudensState, user_input: str) -> LudensState:
        mode = "COMMIT" if state.phase == Phase.PM_COMMIT.value else "DISCUSS"
        return run_agent_step(_pm_agent, mode, state, user_input)


class ENGNode:
    def execute(self, state: LudensState, user_input: str) -> LudensState:
        # 工程节点根据 phase 切到讨论、定稿或辅导模式。
        if state.phase == Phase.DEV_COACHING.value:
            mode = "COACH"
        elif state.phase == Phase.ENG_COMMIT.value:
            mode = "PLAN_COMMIT"
        else:
            mode = "PLAN_DISCUSS"
        return run_agent_step(_eng_agent, mode, state, user_input)


class REVIEWNode:
    def execute(self, state: LudensState, user_input: str) -> LudensState:
        # Review 直接走正式评审输出。
        return run_agent_step(_review_agent, "COMMIT", state, user_input)


# 全局节点表映射机制
PHASE_NODE_MAP = {
    Phase.GDD_DISCUSS.value: GDDNode(),
    Phase.GDD_COMMIT.value: GDDNode(),
    Phase.PM_DISCUSS.value: PMNode(),
    Phase.PM_COMMIT.value: PMNode(),
    Phase.ENG_DISCUSS.value: ENGNode(),
    Phase.ENG_COMMIT.value: ENGNode(),
    Phase.DEV_COACHING.value: ENGNode(),
    Phase.REVIEW.value: REVIEWNode(),
}


def graph_step(
    state: LudensState,
    user_input: str,
    explicit_action: Optional[str] = None,
) -> LudensState:
    """执行一次最小图推进：先路由，再决定是否调用目标节点。"""
    old_phase = state.phase

    # 每一步都先经过 Router。
    router_node = RouterNode()
    router_node.execute(state, user_input, explicit_action=explicit_action)

    new_phase = state.phase

    logger.debug("graph_step -> router output phase=%s", new_phase)

    # REVIEW 后若进入人工决策点，立即暂停。
    if new_phase == Phase.POST_REVIEW_DECISION.value:
        logger.info("Graph Paused at POST_REVIEW_DECISION for User selection.")
        return state

    # 跨 Agent 切换时，先把 greeting 交给前端，再进入下一轮执行。
    old_prefix = old_phase.split("_")[0] if old_phase else ""
    new_prefix = new_phase.split("_")[0]

    if old_phase != new_phase and (
        old_prefix != new_prefix or new_phase == "DEV_COACHING"
    ):
        # POST_REVIEW_DECISION -> DEV_COACHING 不额外停一轮。
        is_post_review_to_dev = (
            old_phase == Phase.POST_REVIEW_DECISION.value
            and new_phase == Phase.DEV_COACHING.value
        )
        if not is_post_review_to_dev:
            logger.info(
                f"Cross-Agent transition detected ({old_phase} -> {new_phase}). Suspending graph to emit greeting."
            )
            return state

    # 其余情况交给目标节点执行。
    active_node = PHASE_NODE_MAP.get(new_phase)
    logger.debug("graph_step -> active node=%s", active_node)
    if active_node:
        state = active_node.execute(state, user_input)
    else:
        logger.warning(f"Unhandled phase in Graph: {new_phase}")

    return state
