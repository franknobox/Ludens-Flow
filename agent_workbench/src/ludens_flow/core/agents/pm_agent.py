"""
文件功能：pm_agent 角色 Agent 实现，负责对应阶段的讨论与提交逻辑。
核心内容：基于 BaseAgent 约定实现角色化提示词和工件产出规则。
核心内容：输出统一 AgentResult，供 graph 编排层合并状态与推进流程。
"""

import json
import logging
import re
from typing import Optional

from ludens_flow.core.agents.base import AgentResult, BaseAgent, CommitSpec
from ludens_flow.capabilities.artifacts.artifacts import read_artifact
from ludens_flow.core.schemas import DISCUSS_RESPONSE_SCHEMA_TEXT, parse_discuss_payload
from ludens_flow.core.state import LudensState
from llm.provider import LLMConfig

logger = logging.getLogger(__name__)


class PMAgent(BaseAgent):
    """Handles project planning discussion, scope shaping, and PM commits."""

    name = "PMAgent"
    agent_key = "pm"

    def discuss(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
        stream_handler=None,
        tool_event_handler=None,
    ) -> AgentResult:
        gdd_content = read_artifact("GDD", project_id=state.project_id)
        existing_pm = read_artifact("PROJECT_PLAN", project_id=state.project_id)

        pm_context = ""
        if existing_pm.strip():
            pm_context = (
                "**当前 PROJECT_PLAN 内容**"
                "（如果这是一次修订，请基于这版继续，而不是从零开始）：\n"
                f"{existing_pm}\n\n"
            )

        base_prompt_text = (
            f"现有 GDD：\n{gdd_content}\n\n"
            f"{pm_context}"
            "请完成以下任务，默认使用简体中文回复，除非用户明确要求英文：\n"
            "1. 作为项目伙伴 Pax，帮助用户确认最重要的排期输入，例如大致周期和团队规模。\n"
            "2. 基于 GDD，判断哪些功能是核心体验，哪些功能应该在 game jam 或 MVP 范围内暂时砍掉。\n"
            "3. 默认假设 Unity PC 单机版本是主要目标。除非用户主动提出，不要扩展到多人或跨平台规划。\n"
            "4. 用清晰、自然的语言回复，重点给出可执行的范围控制建议。\n"
        )

        if stream_handler:
            prompt = self._compose_user_prompt(
                base_prompt_text
                + "5. 只输出自然语言正文，不要输出 JSON、代码块或结构化协议。\n",
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
            return AgentResult(assistant_message=reply.strip(), state_updates={})

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
        gdd_content = read_artifact("GDD", project_id=state.project_id)

        prompt_text = (
            f"现有 GDD：\n{gdd_content}\n\n"
            "请生成一份适合独立游戏或 game jam 项目的 PROJECT_PLAN.md。\n"
            "默认使用简体中文撰写，除非用户明确要求英文。\n"
            "要求：\n"
            "1. 里程碑：拆分为 M0 / M1 / M2，并让每个里程碑都能在 Unity Editor Play Mode 中验证。\n"
            "2. 任务拆解：按 Unity 项目模块组织，例如 Scripts / Prefabs / SceneSetup / Animations / Audio。\n"
            "3. Unity 文件夹结构建议：给出实用的 Assets/ 目录规划。\n"
            "4. 风险与缓解：聚焦技术风险和范围风险，不做商业发行规划。\n"
            "5. 如果 GDD 仍缺少关键信息，请在文末追加一个 ChangeRequest JSON 块，严格使用以下格式：\n"
            "<<CHANGE_REQUEST_JSON>>\n"
            "{\n"
            '  "change_requests": [\n'
            '    {"target": "GDD", "rationale": "缺少结束条件", "suggested_changes": "明确胜利或失败循环", "severity": "High"}\n'
            "  ]\n"
            "}\n"
            "<<END_CHANGE_REQUEST_JSON>>\n"
            "如果没有缺失信息，请省略该 JSON 块。主体内容应为纯 Markdown。"
        )
        prompt = self._compose_user_prompt(
            prompt_text,
            user_input,
            input_label="当前补充输入",
        )
        final_pm_output = self._call(
            prompt,
            cfg,
            history=state.chat_history,
            user_persona=user_persona,
            project_id=state.project_id,
            tool_event_handler=tool_event_handler,
        )

        updates = {}
        final_pm = final_pm_output

        cr_pattern = (
            r"<<CHANGE_REQUEST_JSON>>\s*(\{.*?\})\s*<<END_CHANGE_REQUEST_JSON>>"
        )
        cr_match = re.search(cr_pattern, final_pm_output, re.DOTALL)

        if cr_match:
            try:
                cr_data = json.loads(cr_match.group(1))
                if "change_requests" in cr_data:
                    updates["change_requests"] = cr_data["change_requests"]
                    logger.info(
                        "[PMAgent] Detected and appended %s ChangeRequest(s).",
                        len(cr_data["change_requests"]),
                    )
                final_pm = (
                    final_pm_output[: cr_match.start()].strip()
                    + final_pm_output[cr_match.end() :].strip()
                )
            except Exception as exc:
                logger.warning("Failed to parse PM ChangeRequest JSON: %s", exc)

        updates["decisions"] = ["PM committed"]
        logger.info("[PMAgent] Commit generated.")

        return AgentResult(
            assistant_message=(
                "项目计划已定稿。\n\n"
                "**系统正在自动进入工程阶段。**"
            ),
            state_updates=updates,
            commit=CommitSpec(
                artifact_name="PROJECT_PLAN",
                content=final_pm,
                reason="PM Commit Sequence Initiated",
            ),
            events=["PM_COMMITTED"],
        )
