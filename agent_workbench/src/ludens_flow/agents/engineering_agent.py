import logging
import re
from typing import Optional

from ludens_flow.agents.base import BaseAgent, AgentResult, CommitSpec
from ludens_flow.artifacts import read_artifact
from ludens_flow.schemas import DISCUSS_RESPONSE_SCHEMA_TEXT, parse_discuss_payload
from ludens_flow.state import LudensState
from llm.provider import LLMConfig

logger = logging.getLogger(__name__)


class EngineeringAgent(BaseAgent):
    """负责工程预设讨论、实施计划定稿和冻结后的开发辅导。"""

    name = "EngineeringAgent"

    def discuss(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
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
    ) -> AgentResult:
        raise NotImplementedError("EngineeringAgent uses plan_commit instead of commit")

    def _extract_style_preset(self, text: str) -> Optional[str]:
        """从用户表达里识别 A / B / C 工程预设。"""
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
        """优先读本轮输入，其次读持久化状态，最后回看最近用户对话。"""
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
    ) -> AgentResult:
        # 工程讨论依赖前置的 GDD / PROJECT_PLAN，必要时也带上当前 IMPLEMENTATION_PLAN。
        gdd = read_artifact("GDD", project_id=state.project_id)
        pm = read_artifact("PROJECT_PLAN", project_id=state.project_id)
        impl_plan = read_artifact("IMPLEMENTATION_PLAN", project_id=state.project_id)

        detected_style = self._extract_style_preset(user_input)
        style = detected_style or state.style_preset or "None"
        dev_mode_context = ""
        if getattr(state, "artifact_frozen", False) and impl_plan.strip():
            dev_mode_context = f"\n当前实际生效的实施计划：\n{impl_plan}\n"

        # 讨论态负责解释预设、收敛方案，并在用户明确选择时持久化 preset。
        prompt = (
            f"已有 GDD：\n{gdd}\n\n"
            f"项目计划：\n{pm}\n"
            f"{dev_mode_context}"
            f"用户意图：{user_input}\n\n"
            f"当前已确认的工程预设：{style}\n\n"
            "请完成以下任务：\n"
            "1. 向用户解释 A/B/C 三种工程预设风格，并结合当前项目给出建议。\n"
            "2. 如果用户已经明确选择了某个预设，请围绕该预设继续讨论，不要重新发散。\n"
            "3. 讨论应聚焦 Unity 项目的可执行性、目录结构、模块边界和调试成本。\n"
            "4. 语气专业、清晰、友好，用自然语言回答。\n"
            f"\n\n{DISCUSS_RESPONSE_SCHEMA_TEXT}"
        )

        updates = {}

        raw = self._call(
            prompt,
            cfg,
            history=state.chat_history,
            user_persona=user_persona,
            project_id=state.project_id,
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

        reply = raw or ""
        if detected_style and detected_style != state.style_preset:
            updates["style_preset"] = detected_style
        return AgentResult(assistant_message=reply.strip(), state_updates=updates)

    def plan_commit(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
    ) -> AgentResult:
        # 定稿态把已确认 preset 固化到 IMPLEMENTATION_PLAN。
        gdd = read_artifact("GDD", project_id=state.project_id)
        pm = read_artifact("PROJECT_PLAN", project_id=state.project_id)
        resolved_style = self._resolve_style_preset(state, user_input)
        style = (
            resolved_style
            or getattr(state, "style_preset", None)
            or "由本次对话记录决定"
        )

        prompt = (
            f"依照用户最终确认的工程预设：{style}\n\n"
            f"GDD 内容：\n{gdd}\n\n"
            f"Project Plan 内容：\n{pm}\n\n"
            "请直接输出一份给 Unity 独立游戏开发者使用的 IMPLEMENTATION_PLAN.md。\n"
            "必须包含以下部分：\n"
            "1. Unity 工程结构：给出完整的 Assets 目录建议。\n"
            "2. 系统级任务清单：明确脚本、挂载对象、关键组件和实现顺序。\n"
            "3. 关键风险与替代方案：列出 2-3 个实现风险及 Plan B。\n"
            "请直接输出 Markdown 正文，不要加额外前后缀。\n"
        )
        final_eng = self._call(
            prompt,
            cfg,
            history=state.chat_history,
            user_persona=user_persona,
            project_id=state.project_id,
        )

        logger.info("[EngineeringAgent] Commit generated.")
        updates = {"decisions": ["ENG committed"]}
        if resolved_style and resolved_style != state.style_preset:
            updates["style_preset"] = resolved_style

        return AgentResult(
            assistant_message="工程架构蓝图已准备完毕。\n\n**系统即将自动流转至内部评审(REVIEW)阶段。**\n\n*输入任意内容进入下一阶段*",
            state_updates=updates,
            commit=CommitSpec(
                artifact_name="IMPLEMENTATION_PLAN",
                content=final_eng,
                reason="Engineering Architecture Finalized",
            ),
            events=["ENG_COMMITTED"],
        )

    def coach(
        self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None
    ) -> AgentResult:
        # DEV_COACHING 只做辅导，不改主工件。
        impl_plan = read_artifact("IMPLEMENTATION_PLAN", project_id=state.project_id)
        resolved_style = self._resolve_style_preset(state, user_input)
        style = resolved_style or state.style_preset or "常规"

        prompt = (
            "你现在处于 DEV_COACHING 阶段，只做开发辅导，不修改主工件。\n"
            f"工程风格：{style}\n"
            f"实施计划：\n{impl_plan}\n\n"
            f"用户当前问题：\n{user_input}\n\n"
            "请按下面结构回答：\n"
            "1. 用 2-3 句确认你对问题的理解。\n"
            "2. 给出最推荐的实现路径。\n"
            "3. 提供轻量级 Unity 实施步骤。\n"
            "4. 提醒 1-2 个最容易踩的坑。\n"
            "5. 最后询问用户是否需要更详细的 Unity 操作步骤或发给 Coding Agent 的完整代码指令。\n"
        )

        reply = self._call(
            prompt,
            cfg,
            history=state.chat_history,
            project_id=state.project_id,
        )
        logger.info("[EngineeringAgent] Coach instruction issued.")

        updates = {}
        if resolved_style and resolved_style != state.style_preset:
            updates["style_preset"] = resolved_style

        return AgentResult(
            assistant_message=reply.strip(),
            state_updates=updates,
        )
