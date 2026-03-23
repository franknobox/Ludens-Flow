import logging
import json
import re
from typing import Optional, Dict, Any

from ludens_flow.agents.base import BaseAgent, AgentResult, CommitSpec
from ludens_flow.state import LudensState
from ludens_flow.artifacts import read_artifact
from llm.provider import LLMConfig

logger = logging.getLogger(__name__)


class ReviewAgent(BaseAgent):
    name = "ReviewAgent"
    system_prompt = (
        "你的名字是 Revs（雷夫斯），你是资深综合评审(Review Agent)，有丰富的 Unity 独立游戏开发与 Game Jam 经验。\n"
        "你以「这个方案靠一两个人在有限时间内真的能做出来吗」的务实角度评审整套立项产物。\n"
        "你同时具备策划视角与 Unity 技术视角，特别关注 scope 蔓延（Feature Creep）与技术过度设计问题。\n"
        "你必须严谨、挑剔，并总是输出包含准确分数的 REVIEW 报告，并在结尾附加机器鉴权大门 (ReviewGate)。"
    )

    def discuss(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        """REVIEW 主要走 commit，此处可用作人工干预测试的过场"""
        return AgentResult(assistant_message="Review Agent is in DISCUSS mode. Usually we jump direct to COMMIT.")

    def commit(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        gdd = read_artifact("GDD", project_id=state.project_id)
        pm = read_artifact("PROJECT_PLAN", project_id=state.project_id)
        impl = read_artifact("IMPLEMENTATION_PLAN", project_id=state.project_id)
        
        prompt = (
            "请严格审视以下三份核心文档，从 Unity 独立游戏开发的角度评估一致性、可行性和 scope 健康度：\n\n"
            f"【GDD】\n{gdd}\n\n【PROJECT PLAN】\n{pm}\n\n【IMPLEMENTATION PLAN】\n{impl}\n\n"
            "1. 请在正文区域输出一份专业的 Markdown 评审报告，包含以下维度：\n"
            "   - **创意与设计评审**：核心玩法是否清晰，游戏体验是否自洽，有何亮点与潜在问题。\n"
            "   - **Unity 工程可执行性审计**：IMPLEMENTATION_PLAN 中描述的架构在 Unity 里是否有真实可用的实现手段？对于当前规模（默认小团队/个人）是否过度设计或遗漏关键技术点？\n"
            "   - **Scope 健康度检查**：GDD 和 PM Plan 中是否存在 Feature Creep？有哪些功能在 Game Jam 或独立项目 MVP 阶段应该果断砍掉？\n"
            "   - **风险综合分析**：列出 2-3 个最可能导致项目卡壳的技术或设计风险，并给出针对性建议。\n"
            "2. 在整个回复的末尾，**必须**输出一段 JSON 数据驱动的 ReviewGate，格式如下：\n"
            "<<REVIEW_GATE_JSON>>\n"
            "{\n"
            "  \"status\": \"PASS\" 或 \"REQUEST_CHANGES\" 或 \"BLOCK\",\n"
            "  \"targets\": [\"GDD\", \"PM\", \"ENG\"], // 指示退回修改的阶段，可以为空数组\n"
            "  \"scores\": {\"design\": 8, \"engineering\": 7}, // 必须在 0-10 之间\n"
            "  \"issues\": [\n"
            "    {\"target\": \"ENG\", \"severity\": \"MAJOR\", \"summary\": \"架构不支持需求\", \"fix_hint\": \"建议改用事件总线解耦\"}\n"
            "  ] // 可以为空数组\n"
            "}\n"
            "<<END_REVIEW_GATE_JSON>>\n\n"
            "判断标准：存在致命的逻辑/技术死胡同时使用 BLOCK；存在影响开发的重要瑕疵使用 REQUEST_CHANGES；整体健康使用 PASS。"
        )
        
        final_report = self._call(prompt, cfg, history=state.chat_history)
        gate_dict, final_report_md = self._parse_json_gate(final_report)
        status = gate_dict.get('status', 'REQUEST_CHANGES')
        
        logger.info(f"[ReviewAgent] Commit generated, Gate status resolved to: {status}")
        
        decisions = [f"Review concluded with {status}"]
        updates = {
            "review_gate": gate_dict,
            "decisions": decisions
        }
        
        msg = f"终极评审揭晓！裁决判定：**{status}** (系统评定分: {gate_dict.get('score', 'N/A')})\n\n"
        msg += "**请对本次评审做出指示：**\n"
        msg += "[A] 接受建议（携带问题报告回流对应阶段）\n"
        msg += "[B] 仅重做重点（剔除小瑕疵，仅为 BLOCK/MAJOR 缺陷打回）\n"
        msg += "[C] 全盘忽略（不管不顾，强制定权封包，进入开发模式）\n"
        
        return AgentResult(
            assistant_message=msg,
            state_updates=updates,
            commit=CommitSpec(
                artifact_name="REVIEW_REPORT",
                content=final_report_md,
                reason="Official Multi-Dimensional Review"
            ),
            events=["REVIEW_DONE"]
        )

    def _parse_json_gate(self, report_text: str) -> tuple[Dict[str, Any], str]:
        """ 解析 ReviewGate JSON 并执行硬规则熔断校验，返回 (鉴权字典, 纯净的 markdown 报告) """
        gate_data = None
        clean_md = report_text
        
        pattern = r"<<REVIEW_GATE_JSON>>\s*(\{.*?\})\s*<<END_REVIEW_GATE_JSON>>"
        match = re.search(pattern, report_text, re.DOTALL)
        
        if match:
            try:
                gate_data = json.loads(match.group(1))
                clean_md = report_text[:match.start()].strip() + "\n\n" + report_text[match.end():].strip()
            except Exception as e:
                logger.error(f"[ReviewAgent] JSON blocks captured but failed to parse: {e}")
                gate_data = None
        else:
            logger.error("[ReviewAgent] Could not find <<REVIEW_GATE_JSON>> markers in output.")
            
        # 兜底：如果没解析出来，触发绝对熔断，全部打回 ENG
        if not gate_data:
            fallback = {
                "status": "REQUEST_CHANGES",
                "targets": ["ENG"],
                "scores": {"design": 0, "engineering": 0},
                "issues": [{"target": "ENG", "severity": "BLOCK", "summary": "评审结构解析失败", "fix_hint": "建议人工查看报告"}]
            }
            return fallback, clean_md

        # --- 规则校验层 ---
        # 1. 自动熔断：如有任何 severity=BLOCK，则强制 BLOCK
        has_block_issue = any(issue.get("severity", "").upper() == "BLOCK" for issue in gate_data.get("issues", []))
        if has_block_issue:
            gate_data["status"] = "BLOCK"
            return gate_data, clean_md
            
        # 2. 自动熔断：评分低于6，强制 REQUEST_CHANGES (如果没被 BLOCK)
        scores = gate_data.get("scores", {})
        design_score = scores.get("design", 10)
        eng_score = scores.get("engineering", 10)
        
        if design_score < 6 or eng_score < 6:
            gate_data["status"] = "REQUEST_CHANGES"
            if "targets" not in gate_data or not gate_data["targets"]:
                gate_data["targets"] = ["GDD"] if design_score < 6 else ["ENG"]
                
        # 分数和 BLOCK 均绿通，若模型本意是退回，则尊重其决定；否则兜底为 PASS (防乱写)
        if gate_data.get("status") not in ["BLOCK", "REQUEST_CHANGES"]:
            gate_data["status"] = "PASS"

        return gate_data, clean_md
