"""
文件功能：design_agent 角色 Agent 实现，负责对应阶段的讨论与提交逻辑。
核心内容：基于 BaseAgent 约定实现角色化提示词和工件产出规则。
核心内容：输出统一 AgentResult，供 graph 编排层合并状态与推进流程。
"""

import logging
from typing import Optional

from ludens_flow.core.agents.base import AgentResult, BaseAgent, CommitSpec
from ludens_flow.core.schemas import DISCUSS_RESPONSE_SCHEMA_TEXT, parse_discuss_payload
from ludens_flow.core.state import LudensState
from llm.provider import LLMConfig

logger = logging.getLogger(__name__)


class DesignAgent(BaseAgent):
    """Handles GDD discussion and finalization."""

    name = "DesignAgent"
    agent_key = "design"

    def discuss(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
        stream_handler=None,
        tool_event_handler=None,
    ) -> AgentResult:
        from ludens_flow.capabilities.artifacts.artifacts import read_artifact

        existing_gdd = read_artifact("GDD", project_id=state.project_id)

        gdd_context = ""
        if existing_gdd.strip():
            gdd_context = (
                "**当前 GDD 内容**"
                "（如果这是一次修订，请基于这版草稿继续，而不是从零开始）：\n"
                f"{existing_gdd}\n\n"
            )

        base_prompt_text = (
            f"{gdd_context}"
            "请完成以下任务，默认使用简体中文回复，除非用户明确要求英文：\n"
            "1. 作为策划伙伴 Dam，围绕用户当前的游戏想法展开讨论，帮助提炼关键点"
            "（核心循环、玩家感受、可能的开发范围）。\n"
            "2. 从 Unity 独立开发视角，在有帮助时评价实现可行性，并给出更聪明的替代方案。\n"
            "3. 鼓励创意发散，但始终把讨论锚定在真正能做出来的最小核心体验上。\n"
            "4. 如果仍有模糊部分，提出聚焦的追问；如果方向已经清楚，就确认方向并适度展开。\n"
            "5. 语气保持有想法、有协作感，但不要空泛。\n"
        )

        if stream_handler:
            prompt = self._compose_user_prompt(
                base_prompt_text
                + "6. 只输出自然语言正文，不要输出 JSON、代码块或结构化协议。\n",
                user_input,
                input_label="用户的需求/反馈",
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
            return AgentResult(assistant_message=reply.strip(), state_updates={})

        prompt = self._compose_user_prompt(
            f"{base_prompt_text}\n{DISCUSS_RESPONSE_SCHEMA_TEXT}",
            user_input,
            input_label="用户的需求/反馈",
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
            return AgentResult(
                assistant_message=payload.reply,
                state_updates=payload.state_updates,
                events=payload.events,
                profile_updates=payload.profile_updates,
            )

        return AgentResult(assistant_message=(raw or "").strip(), state_updates={})

    def commit(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
        tool_event_handler=None,
    ) -> AgentResult:
        prompt_text = (
            "请基于目前完整讨论，生成一份干净、可直接保存的 GDD（游戏设计文档），格式为 Markdown。\n"
            "默认使用简体中文撰写，除非用户明确要求英文。文档应面向 Unity 独立游戏开发者或小型 game jam 团队。\n\n"
            "要求：\n"
            "1. 至少包含这些部分：概述（题材 / 核心体验 / 目标玩家）、核心循环、关键系统、"
            "关卡 / 内容结构、视觉风格与氛围、MVP 边界。\n"
            "2. 在关键系统部分，每个系统都要补充简短的 Unity 实现提示，例如 CharacterController、"
            "Tilemap、Rigidbody2D、NavMesh、Animator 等。\n"
            "3. 在 MVP 边界部分，明确区分必须完成的核心体验和可以后置的想法。\n"
            "4. 不要编造尚未确定的细节。如果讨论中确实没有决定，请标记为“【待确认：...】”。"
            "但已经讨论过的内容必须如实保留。\n"
            "5. 保持 Markdown 清晰可读，可以少量使用强调，但不要加入额外包装话术。\n"
            "6. 末尾增加两个简短部分：\n"
            "   - 技术风险：列出 2-3 个可能出现的 Unity 实现风险。\n"
            "   - 创意变体：给出 2 个简洁的玩法变化方向。\n"
            "重要：这份内容会被直接保存。不要在 Markdown 正文之外添加开场白或结束语。"
        )
        prompt = self._compose_user_prompt(
            prompt_text,
            user_input,
            input_label="当前补充输入",
        )
        final_gdd = self._call(
            prompt,
            cfg,
            history=state.chat_history,
            user_persona=user_persona,
            project_id=state.project_id,
            tool_event_handler=tool_event_handler,
        )
        logger.info("[DesignAgent] Commit generated.")

        return AgentResult(
            assistant_message=(
                "GDD 已定稿。\n\n"
                "**系统正在自动进入 PM 阶段。**"
            ),
            state_updates={"decisions": ["GDD 已提交"]},
            commit=CommitSpec(
                artifact_name="GDD",
                content=final_gdd,
                reason="User confirmed commit via router",
            ),
            events=["GDD_COMMITTED"],
        )
