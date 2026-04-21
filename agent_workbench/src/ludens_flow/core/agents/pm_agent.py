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
                "**Current PROJECT_PLAN content** "
                "(if this is a revision pass, continue from this version):\n"
                f"{existing_pm}\n\n"
            )

        base_prompt_text = (
            f"Existing GDD:\n{gdd_content}\n\n"
            f"{pm_context}"
            "Please do the following:\n"
            "1. As the project partner Pax, help the user confirm the most important schedule inputs, such as rough timeline and team size.\n"
            "2. Based on the GDD, identify which features are core to the experience and which ones should be cut for a jam or MVP scope.\n"
            "3. Assume Unity PC standalone is the main target. Do not drift into multiplayer or cross-platform planning unless the user asks for it.\n"
            "4. Reply in clear, natural language with practical scope guidance.\n"
        )

        if stream_handler:
            prompt = self._compose_user_prompt(
                base_prompt_text
                + "5. Reply in plain natural language only. Do not output JSON, code fences, or any structured protocol.\n",
                user_input,
                input_label="User intent",
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
            input_label="User intent",
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
            f"Existing GDD:\n{gdd_content}\n\n"
            "Produce a PROJECT_PLAN.md suitable for an indie game or game-jam project.\n"
            "Requirements:\n"
            "1. Milestones: split into M0 / M1 / M2, and make each milestone verifiable inside Unity Editor Play Mode.\n"
            "2. Task Breakdown: group work by Unity project modules, for example Scripts / Prefabs / SceneSetup / Animations / Audio.\n"
            "3. Unity folder structure suggestion: propose a practical Assets/ layout.\n"
            "4. Risks and mitigation: focus on technical and scope risks, not business release planning.\n"
            "5. If the GDD is still missing critical information, append a ChangeRequest JSON block in this exact format:\n"
            "<<CHANGE_REQUEST_JSON>>\n"
            "{\n"
            '  "change_requests": [\n'
            '    {"target": "GDD", "rationale": "missing ending condition", "suggested_changes": "clarify win or fail loop", "severity": "High"}\n'
            "  ]\n"
            "}\n"
            "<<END_CHANGE_REQUEST_JSON>>\n"
            "If there is no missing information, omit that JSON block. The main body should be plain Markdown."
        )
        prompt = self._compose_user_prompt(
            prompt_text,
            user_input,
            input_label="Current extra input",
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
                "**系统将自动进入工程阶段。**\n\n"
                "*发送任意消息即可继续。*"
            ),
            state_updates=updates,
            commit=CommitSpec(
                artifact_name="PROJECT_PLAN",
                content=final_pm,
                reason="PM Commit Sequence Initiated",
            ),
            events=["PM_COMMITTED"],
        )
