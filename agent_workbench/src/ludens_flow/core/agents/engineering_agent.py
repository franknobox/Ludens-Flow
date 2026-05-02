"""
文件功能：engineering_agent 角色 Agent 实现，负责对应阶段的讨论与提交逻辑。
核心内容：基于 BaseAgent 约定实现角色化提示词和工件产出规则。
核心内容：输出统一 AgentResult，供 graph 编排层合并状态与推进流程。
"""

import logging
import re
from typing import Callable, Optional

from ludens_flow.core.agents.base import AgentResult, BaseAgent, CommitSpec
from ludens_flow.capabilities.artifacts.artifacts import read_artifact
from ludens_flow.core.schemas import DISCUSS_RESPONSE_SCHEMA_TEXT, parse_discuss_payload
from ludens_flow.core.state import LudensState
from llm.provider import LLMConfig

logger = logging.getLogger(__name__)


class EngineeringAgent(BaseAgent):
    """Handles engineering preset discussion, implementation planning, and coaching."""

    name = "EngineeringAgent"
    agent_key = "engineering"

    def discuss(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
        stream_handler: Optional[Callable[[str], None]] = None,
        tool_event_handler=None,
    ) -> AgentResult:
        raise NotImplementedError(
            "EngineeringAgent uses plan_discuss and coach instead of discuss"
        )

    def commit(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
        tool_event_handler=None,
    ) -> AgentResult:
        raise NotImplementedError("EngineeringAgent uses plan_commit instead of commit")

    def _extract_style_preset(self, text: str) -> Optional[str]:
        if not text:
            return None

        raw = str(text).strip()
        if not raw:
            return None

        normalized = raw.lower()
        compact = re.sub(r"\s+", "", normalized)

        if normalized in {"a", "b", "c"}:
            return normalized.upper()

        explicit_patterns = {
            "A": [
                r"\bpreset\s*a\b",
                r"\boption\s*a\b",
                r"\bchoose\s*a\b",
                r"\bselect\s*a\b",
                r"\buse\s*a\b",
                r"\bgo with\s*a\b",
            ],
            "B": [
                r"\bpreset\s*b\b",
                r"\boption\s*b\b",
                r"\bchoose\s*b\b",
                r"\bselect\s*b\b",
                r"\buse\s*b\b",
                r"\bgo with\s*b\b",
            ],
            "C": [
                r"\bpreset\s*c\b",
                r"\boption\s*c\b",
                r"\bchoose\s*c\b",
                r"\bselect\s*c\b",
                r"\buse\s*c\b",
                r"\bgo with\s*c\b",
            ],
        }
        for preset, patterns in explicit_patterns.items():
            if any(re.search(pattern, normalized) for pattern in patterns):
                return preset

        chinese_patterns = {
            "A": ["预设a", "方案a", "选a", "选择a", "用a", "a方案"],
            "B": ["预设b", "方案b", "选b", "选择b", "用b", "b方案"],
            "C": ["预设c", "方案c", "选c", "选择c", "用c", "c方案"],
        }
        for preset, patterns in chinese_patterns.items():
            if any(pattern in compact for pattern in patterns):
                return preset

        return None

    def _resolve_style_preset(
        self, state: LudensState, user_input: str = ""
    ) -> Optional[str]:
        detected = self._extract_style_preset(user_input)
        if detected:
            return detected

        if getattr(state, "style_preset", None):
            return state.style_preset

        for item in reversed(getattr(state, "chat_history", [])):
            if item.get("role") != "user":
                continue
            detected = self._extract_style_preset(item.get("content", ""))
            if detected:
                return detected

        return None

    def plan_discuss(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
        stream_handler: Optional[Callable[[str], None]] = None,
        tool_event_handler=None,
    ) -> AgentResult:
        gdd = read_artifact("GDD", project_id=state.project_id)
        pm = read_artifact("PROJECT_PLAN", project_id=state.project_id)
        impl_plan = read_artifact("IMPLEMENTATION_PLAN", project_id=state.project_id)

        detected_style = self._extract_style_preset(user_input)
        style = detected_style or state.style_preset or "None"
        dev_mode_context = ""
        if getattr(state, "artifact_frozen", False) and impl_plan.strip():
            dev_mode_context = f"\n当前生效的实现计划：\n{impl_plan}\n"

        base_prompt_text = (
            f"现有 GDD：\n{gdd}\n\n"
            f"项目计划：\n{pm}\n"
            f"{dev_mode_context}"
            f"目前已确认的工程方案预设：{style}\n\n"
            "请完成以下任务，默认使用简体中文回复，除非用户明确要求英文：\n"
            "1. 解释 A / B / C 三种工程方案选项，并推荐最适合当前项目的一种。\n"
            "2. 如果用户已经选择了方案，就在该方案内部继续讨论，不要从零开始。\n"
            "3. 讨论重点放在工程结构、实现路径、文件夹结构、模块边界、风险和调试成本上。\n"
            "4. 在工程讨论阶段，不要给出逐类实现指令、文件骨架、精确脚本拆分或 Unity 编辑器逐步操作。\n"
            "5. 除非用户明确要求进入后续执行阶段，否则不要主动建议具体文件名、代码脚手架或直接构建指令。\n"
            "6. 语气保持务实、清晰。\n"
        )

        if stream_handler:
            prompt = self._compose_user_prompt(
                base_prompt_text
                + "7. 只输出自然语言正文，不要输出 JSON、代码块或结构化协议。\n",
                user_input,
                input_label="用户意图",
            )
            reply = self._call(
                prompt,
                cfg,
                history=state.chat_history,
                user_persona=user_persona,
                project_id=state.project_id,
                stream_handler=stream_handler,
                tool_event_handler=tool_event_handler,
            )
            updates = {}
            if detected_style and detected_style != state.style_preset:
                updates["style_preset"] = detected_style
            return AgentResult(assistant_message=reply.strip(), state_updates=updates)

        prompt = self._compose_user_prompt(
            f"{base_prompt_text}\n{DISCUSS_RESPONSE_SCHEMA_TEXT}",
            user_input,
            input_label="用户意图",
        )

        raw = self._call(
            prompt,
            cfg,
            history=state.chat_history,
            user_persona=user_persona,
            project_id=state.project_id,
            tool_event_handler=tool_event_handler,
        )
        payload, _ = parse_discuss_payload(raw)
        if payload:
            state_updates = dict(payload.state_updates)
            if detected_style and detected_style != state.style_preset:
                state_updates["style_preset"] = detected_style
            return AgentResult(
                assistant_message=payload.reply,
                state_updates=state_updates,
                events=payload.events,
                profile_updates=payload.profile_updates,
            )

        updates = {}
        if detected_style and detected_style != state.style_preset:
            updates["style_preset"] = detected_style
        return AgentResult(assistant_message=(raw or "").strip(), state_updates=updates)

    def plan_commit(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
        tool_event_handler=None,
    ) -> AgentResult:
        gdd = read_artifact("GDD", project_id=state.project_id)
        pm = read_artifact("PROJECT_PLAN", project_id=state.project_id)
        resolved_style = self._resolve_style_preset(state, user_input)
        style = resolved_style or getattr(state, "style_preset", None) or "Use the current discussion context"

        prompt_text = (
            f"使用已确认的工程方案预设：{style}\n\n"
            f"GDD:\n{gdd}\n\n"
            f"项目计划：\n{pm}\n\n"
            "请为 Unity 独立游戏开发者生成一份 IMPLEMENTATION_PLAN.md。\n"
            "默认使用简体中文撰写，除非用户明确要求英文。\n"
            "必须包含：\n"
            "1. Unity 项目结构：给出完整、实用的 Assets 目录建议。\n"
            "2. 系统级任务拆解：覆盖脚本、挂载对象、关键组件和实现顺序。\n"
            "3. 关键风险与兜底方案：列出 2-3 个现实的实现风险和 Plan B。\n"
            "只输出纯 Markdown，不要添加额外包装话术。"
        )
        prompt = self._compose_user_prompt(
            prompt_text,
            user_input,
            input_label="当前补充输入",
        )
        final_eng = self._call(
            prompt,
            cfg,
            history=state.chat_history,
            user_persona=user_persona,
            project_id=state.project_id,
            tool_event_handler=tool_event_handler,
        )

        logger.info("[EngineeringAgent] Commit generated.")
        updates = {"decisions": ["ENG committed"]}
        if resolved_style and resolved_style != state.style_preset:
            updates["style_preset"] = resolved_style

        return AgentResult(
            assistant_message=(
                "实施方案已定稿。\n\n"
                "**系统正在自动进入内部评审阶段。**"
            ),
            state_updates=updates,
            commit=CommitSpec(
                artifact_name="IMPLEMENTATION_PLAN",
                content=final_eng,
                reason="Engineering Architecture Finalized",
            ),
            events=["ENG_COMMITTED"],
        )

    @staticmethod
    def _make_devlog_filter(real_handler):
        """Wraps a stream_handler to silently suppress [DEVLOG]...[/DEVLOG] blocks."""
        buf = [""]
        inside = [False]

        def _handle(chunk: str):
            buf[0] += chunk
            out = ""
            rest = buf[0]
            buf[0] = ""

            while rest:
                if not inside[0]:
                    start = rest.find("[DEVLOG]")
                    if start == -1:
                        # No full marker; protect against a partial tail
                        marker = "[DEVLOG]"
                        for n in range(len(marker) - 1, 0, -1):
                            if rest.endswith(marker[:n]):
                                out += rest[:-n]
                                buf[0] = rest[-n:]
                                rest = ""
                                break
                        else:
                            out += rest
                            rest = ""
                    else:
                        out += rest[:start]
                        rest = rest[start + len("[DEVLOG]"):]
                        inside[0] = True
                else:
                    end = rest.find("[/DEVLOG]")
                    if end == -1:
                        rest = ""  # still inside block, discard
                    else:
                        rest = rest[end + len("[/DEVLOG]"):]
                        inside[0] = False

            if out and real_handler:
                real_handler(out)

        return _handle

    def coach(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
        stream_handler: Optional[Callable[[str], None]] = None,
        tool_event_handler=None,
    ) -> AgentResult:
        from datetime import datetime, timezone

        impl_plan = read_artifact("IMPLEMENTATION_PLAN", project_id=state.project_id)
        resolved_style = self._resolve_style_preset(state, user_input)
        style = resolved_style or state.style_preset or "\u5e38\u89c4"

        prompt_text = (
            "你现在处于 DEV_COACHING 模式。只指导实现工作，不修改正式方案。\n"
            "默认使用简体中文回复，除非用户明确要求英文。\n"
            f"工程风格：{style}\n"
            f"实现计划：\n{impl_plan}\n\n"
            "请使用以下结构回复：\n"
            "1. 用 2-3 句话确认你对用户问题的理解。\n"
            "2. 给出最推荐的实现路径。\n"
            "3. 提供轻量级 Unity 执行指引。\n"
            "4. 提醒 1-2 个最可能踩坑的点。\n"
            "5. 结尾询问用户是否需要更详细的 Unity 实操步骤，或一份可发给 coding agent 的完整指令。\n"
            "\n"
            "DEVLOG（可选）：\n"
            "如果这轮交流包含有价值的技术决策、架构取舍、关键问题，或值得写入项目记录的内容，"
            "请在回复末尾追加一个简短 DEVLOG，严格使用以下格式：\n"
            "[DEVLOG]\n"
            "<2-4 行中文记录。以「决策」、「问题」或「笔记」开头。>\n"
            "[/DEVLOG]\n"
            "如果只是普通问答、快速澄清或没有新决策，请完全省略该块。\n"
        )
        prompt = self._compose_user_prompt(
            prompt_text,
            user_input,
            input_label="User\u2019s current problem",
        )

        # Wrap stream_handler so [DEVLOG] blocks are silently filtered from the UI
        filtered_handler = (
            self._make_devlog_filter(stream_handler) if stream_handler else None
        )

        reply = self._call(
            prompt,
            cfg,
            history=state.chat_history,
            user_persona=user_persona,
            project_id=state.project_id,
            stream_handler=filtered_handler,
            tool_event_handler=tool_event_handler,
        )
        logger.info("[EngineeringAgent] Coach instruction issued.")

        # Parse DEVLOG block and strip it from the stored assistant message
        devlog_match = re.search(r"\[DEVLOG\](.*?)\[/DEVLOG\]", reply, re.DOTALL)
        devlog_entry = devlog_match.group(1).strip() if devlog_match else None
        clean_reply = re.sub(
            r"\s*\[DEVLOG\].*?\[/DEVLOG\]", "", reply, flags=re.DOTALL
        ).strip()

        updates: dict = {}
        if resolved_style and resolved_style != state.style_preset:
            updates["style_preset"] = resolved_style

        commit = None
        if devlog_entry:
            existing = read_artifact("DEVLOG", project_id=state.project_id)
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            if not existing.strip():
                preamble = "# Dev Coaching Log\n\n"
                separator = ""
            else:
                preamble = ""
                separator = "\n\n---\n\n"
            new_content = (
                preamble
                + existing.rstrip()
                + separator
                + f"### {ts}\n\n{devlog_entry}\n"
            )
            commit = CommitSpec(
                artifact_name="DEVLOG",
                content=new_content,
                reason="Coach session DEVLOG entry",
            )
            logger.info(
                "[EngineeringAgent] DEVLOG entry queued: %s...",
                devlog_entry[:60],
            )

        return AgentResult(
            assistant_message=clean_reply,
            state_updates=updates,
            commit=commit,
        )
