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
            dev_mode_context = f"\nCurrent effective implementation plan:\n{impl_plan}\n"

        base_prompt_text = (
            f"Existing GDD:\n{gdd}\n\n"
            f"Project plan:\n{pm}\n"
            f"{dev_mode_context}"
            f"Confirmed engineering preset so far: {style}\n\n"
            "Please do the following:\n"
            "1. Explain the A / B / C engineering preset options and recommend the best fit for the current project.\n"
            "2. If the user already chose a preset, continue the discussion inside that preset instead of restarting from scratch.\n"
            "3. Keep the conversation focused on engineering structure, implementation path, folder structure, module boundaries, risk, and debugging cost.\n"
            "4. In this discussion stage, do not give class-by-class implementation instructions, file skeletons, exact script breakdowns, or step-by-step Unity editor operations.\n"
            "5. Do not proactively suggest concrete file names, code scaffolds, or direct build instructions unless the user explicitly asks to enter a later execution-oriented stage.\n"
            "6. Keep the tone practical, clear, and supportive.\n"
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
            updates = {}
            if detected_style and detected_style != state.style_preset:
                updates["style_preset"] = detected_style
            return AgentResult(assistant_message=reply.strip(), state_updates=updates)

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
            f"Use the confirmed engineering preset: {style}\n\n"
            f"GDD:\n{gdd}\n\n"
            f"Project Plan:\n{pm}\n\n"
            "Produce an IMPLEMENTATION_PLAN.md for a Unity indie game developer.\n"
            "It must include:\n"
            "1. Unity project structure: a complete Assets directory suggestion.\n"
            "2. System-level task breakdown: scripts, mounted objects, key components, and implementation order.\n"
            "3. Key risks and fallback plans: list 2-3 realistic implementation risks and Plan B options.\n"
            "Output plain Markdown only, with no extra wrapper text."
        )
        prompt = self._compose_user_prompt(
            prompt_text,
            user_input,
            input_label="Current extra input",
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
                "**系统将自动进入内部评审阶段。**\n\n"
                "*发送任意消息即可继续。*"
            ),
            state_updates=updates,
            commit=CommitSpec(
                artifact_name="IMPLEMENTATION_PLAN",
                content=final_eng,
                reason="Engineering Architecture Finalized",
            ),
            events=["ENG_COMMITTED"],
        )

    def coach(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
        stream_handler: Optional[Callable[[str], None]] = None,
        tool_event_handler=None,
    ) -> AgentResult:
        impl_plan = read_artifact("IMPLEMENTATION_PLAN", project_id=state.project_id)
        resolved_style = self._resolve_style_preset(state, user_input)
        style = resolved_style or state.style_preset or "常规"

        prompt_text = (
            "You are in DEV_COACHING mode. Only guide implementation work; do not modify the canonical plan.\n"
            f"Engineering style: {style}\n"
            f"Implementation plan:\n{impl_plan}\n\n"
            "Reply using this structure:\n"
            "1. Confirm your understanding of the user's problem in 2-3 sentences.\n"
            "2. Give the most recommended implementation path.\n"
            "3. Provide a lightweight Unity execution guide.\n"
            "4. Warn about 1-2 likely pitfalls.\n"
            "5. End by asking whether the user wants a more detailed Unity step-by-step guide or a complete coding-agent prompt.\n"
        )
        prompt = self._compose_user_prompt(
            prompt_text,
            user_input,
            input_label="User's current problem",
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
        logger.info("[EngineeringAgent] Coach instruction issued.")

        updates = {}
        if resolved_style and resolved_style != state.style_preset:
            updates["style_preset"] = resolved_style

        return AgentResult(
            assistant_message=reply.strip(),
            state_updates=updates,
        )
