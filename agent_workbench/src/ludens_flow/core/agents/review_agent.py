import logging
from typing import Any, Dict, Optional

from ludens_flow.core.agents.base import AgentResult, BaseAgent, CommitSpec
from ludens_flow.capabilities.artifacts.artifacts import read_artifact
from ludens_flow.core.schemas import (
    REVIEW_GATE_SCHEMA_TEXT,
    ReviewGatePayload,
    parse_review_gate_payload,
)
from ludens_flow.core.state import LudensState
from llm.provider import LLMConfig

logger = logging.getLogger(__name__)


class ReviewAgent(BaseAgent):
    name = "ReviewAgent"

    def discuss(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
        tool_event_handler=None,
    ) -> AgentResult:
        """Review mostly runs in commit mode; discuss is only a lightweight fallback."""
        return AgentResult(
            assistant_message=(
                "Review Agent is in DISCUSS mode. Usually we jump direct to COMMIT."
            )
        )

    def commit(
        self,
        state: LudensState,
        user_input: str,
        cfg: Optional[LLMConfig] = None,
        user_persona: Optional[str] = None,
        tool_event_handler=None,
    ) -> AgentResult:
        gdd = read_artifact("GDD", project_id=state.project_id)
        pm = read_artifact("PROJECT_PLAN", project_id=state.project_id)
        impl = read_artifact("IMPLEMENTATION_PLAN", project_id=state.project_id)

        prompt = (
            "请严格审视以下三份核心文档，从 Unity 独立游戏开发的角度评估一致性、可行性和 scope 健康度：\n\n"
            f"【GDD】\n{gdd}\n\n【PROJECT PLAN】\n{pm}\n\n【IMPLEMENTATION PLAN】\n{impl}\n\n"
            "1. 请在正文区域输出一份专业的 Markdown 评审报告，包含以下维度：\n"
            "   - 创意与设计评审：核心玩法是否清晰，游戏体验是否自洽，有何亮点与潜在问题。\n"
            "   - Unity 工程可执行性审视：IMPLEMENTATION_PLAN 中描述的架构在 Unity 里是否有真实可用的实现手段；对于当前规模是否过度设计或遗漏关键技术点。\n"
            "   - Scope 健康度检查：GDD 和 PM Plan 中是否存在 Feature Creep；哪些功能在 Game Jam 或 MVP 阶段应该果断砍掉。\n"
            "   - 风险综合分析：列出 2-3 个最可能导致项目卡壳的技术或设计风险，并给出针对性建议。\n"
            f"2. {REVIEW_GATE_SCHEMA_TEXT}\n\n"
            "判断标准：存在致命的逻辑或技术死结时使用 BLOCK；存在影响开发的重要瑕疵时使用 REQUEST_CHANGES；整体健康时使用 PASS。"
        )
        prompt = self._compose_user_prompt(prompt, user_input, input_label="本轮补充输入")

        final_report = self._call(
            prompt,
            cfg,
            history=state.chat_history,
            user_persona=user_persona,
            project_id=state.project_id,
            tool_event_handler=tool_event_handler,
        )
        gate_payload, final_report_md = self._parse_review_gate(final_report)
        gate_dict = gate_payload.to_dict()
        status = gate_payload.status

        logger.info(
            "[ReviewAgent] Commit generated, Gate status resolved to: %s",
            status,
        )

        decisions = [f"Review concluded with {status}"]
        updates = {"review_gate": gate_dict, "decisions": decisions}

        scores = gate_payload.scores
        design_score = scores.get("design")
        engineering_score = scores.get("engineering")
        legacy_score = gate_dict.get("score")

        if isinstance(design_score, (int, float)) and isinstance(
            engineering_score, (int, float)
        ):
            score_text = f"design={design_score}, engineering={engineering_score}"
        elif isinstance(legacy_score, (int, float)):
            score_text = str(legacy_score)
        else:
            score_text = "N/A"

        msg = f"终极评审揭晓，裁决判定：**{status}** (系统评定分: {score_text})\n\n"
        msg += "请在下方流程选项中选择下一步操作。"

        return AgentResult(
            assistant_message=msg,
            state_updates=updates,
            commit=CommitSpec(
                artifact_name="REVIEW_REPORT",
                content=final_report_md,
                reason="Official Multi-Dimensional Review",
            ),
            events=["REVIEW_DONE"],
        )

    def _parse_review_gate(self, report_text: str) -> tuple[ReviewGatePayload, str]:
        """Parse ReviewGate JSON and apply hard-stop validation rules."""
        gate_payload, clean_md = parse_review_gate_payload(report_text)

        if gate_payload is None:
            logger.error(
                "[ReviewAgent] Could not parse <<REVIEW_GATE_JSON>> payload from output."
            )
            fallback = ReviewGatePayload(
                status="REQUEST_CHANGES",
                targets=["ENG"],
                scores={"design": 0.0, "engineering": 0.0},
                issues=[],
            )
            return fallback, report_text

        gate_payload = self._apply_gate_rules(gate_payload)
        return gate_payload, clean_md

    def _apply_gate_rules(self, gate_payload: ReviewGatePayload) -> ReviewGatePayload:
        has_block_issue = any(
            issue.severity.upper() == "BLOCK" for issue in gate_payload.issues
        )
        if has_block_issue:
            gate_payload.status = "BLOCK"
            return gate_payload

        design_score = gate_payload.scores.get("design", 10.0)
        engineering_score = gate_payload.scores.get("engineering", 10.0)

        if design_score < 6 or engineering_score < 6:
            gate_payload.status = "REQUEST_CHANGES"
            if not gate_payload.targets:
                gate_payload.targets = ["GDD"] if design_score < 6 else ["ENG"]
            return gate_payload

        if gate_payload.status not in {"BLOCK", "REQUEST_CHANGES"}:
            gate_payload.status = "PASS"

        return gate_payload
