import logging
from typing import Optional

from ludens_flow.agents.base import AgentResult, BaseAgent, CommitSpec
from ludens_flow.schemas import DISCUSS_RESPONSE_SCHEMA_TEXT, parse_discuss_payload
from ludens_flow.state import LudensState
from llm.provider import LLMConfig

logger = logging.getLogger(__name__)


class DesignAgent(BaseAgent):
    """Handles GDD discussion and finalization."""

    name = "DesignAgent"

    def discuss(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
        stream_handler=None,
        tool_event_handler=None,
    ) -> AgentResult:
        from ludens_flow.app.artifacts import read_artifact

        existing_gdd = read_artifact("GDD", project_id=state.project_id)

        gdd_context = ""
        if existing_gdd.strip():
            gdd_context = (
                "**Current GDD content** "
                "(if this is a revision pass, continue from this draft instead of restarting):\n"
                f"{existing_gdd}\n\n"
            )

        base_prompt_text = (
            f"{gdd_context}"
            "Please do the following:\n"
            "1. As the design partner Dam, discuss the user's current game idea warmly and help surface the key points "
            "(core loop, player feeling, and likely development scope).\n"
            "2. From a Unity indie-dev perspective, comment on implementation feasibility where helpful, including smarter alternatives.\n"
            "3. Encourage creative exploration, but keep the discussion anchored to the smallest core experience that can actually ship.\n"
            "4. If parts are still vague, ask focused follow-up questions. If the direction is already clear, affirm it and expand it.\n"
            "5. Keep the tone lively, collaborative, and idea-forward.\n"
        )

        if stream_handler:
            prompt = self._compose_user_prompt(
                base_prompt_text
                + "6. Reply in plain natural language only. Do not output JSON, code fences, or any structured protocol.\n",
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
            "Based on the full discussion so far, produce a clean GDD (Game Design Document) in Markdown.\n"
            "It should be written for a Unity indie developer or a small game-jam team.\n\n"
            "Requirements:\n"
            "1. Include these sections: Overview (theme / core experience / target player), Core Loop, Key Systems, "
            "Level / Content Structure, Visual Style & Atmosphere, MVP Boundary.\n"
            "2. In the Key Systems section, each system should include a short Unity implementation note, for example using "
            "CharacterController, Tilemap, Rigidbody2D, NavMesh, Animator, and so on.\n"
            "3. In the MVP Boundary section, clearly separate must-have core experience from nice-to-have ideas that can wait.\n"
            "4. Do not invent unresolved details. If something truly was not decided in the discussion, mark it as "
            "[TODO: clarify ...]. But anything that was discussed should be carried through faithfully.\n"
            "5. Keep the Markdown clean and readable. A small amount of emphasis is fine, but avoid extra framing text.\n"
            "6. Add two short ending sections:\n"
            "   - Technical Risks: name 2-3 likely Unity implementation risks.\n"
            "   - Creative Variants: provide 2 concise gameplay variation directions.\n"
            "Important: this output will be saved directly. Do not add extra preface or closing remarks outside the Markdown body."
        )
        prompt = self._compose_user_prompt(
            prompt_text,
            user_input,
            input_label="Current extra input",
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
                "GDD finalized.\n\n"
                "**The system will now move into the PM phase automatically.**\n\n"
                "*Send any message to continue.*"
            ),
            state_updates={"decisions": ["GDD committed"]},
            commit=CommitSpec(
                artifact_name="GDD",
                content=final_gdd,
                reason="User confirmed commit via router",
            ),
            events=["GDD_COMMITTED"],
        )
