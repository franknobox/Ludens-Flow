import logging
import json
from typing import Optional, Dict, Any

from ludens_flow.agents.base import BaseAgent, AgentResult, CommitSpec
from ludens_flow.state import LudensState
from ludens_flow.artifacts import read_artifact
from llm.provider import LLMConfig

logger = logging.getLogger(__name__)


class ReviewAgent(BaseAgent):
    name = "ReviewAgent"
    system_prompt = (
        "你是综合评审团队(Review Agent)。结合玩家体验与资深开发双维度视角评审前三份工件。"
        "必须严谨：在末尾用 JSON 附带门神结果块。"
    )

    def discuss(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        """REVIEW 主要走 commit，此处可用作人工干预测试的过场"""
        return AgentResult(assistant_message="Review Agent is in DISCUSS mode. Usually we jump direct to COMMIT.")

    def commit(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        gdd = read_artifact("GDD")
        pm = read_artifact("PROJECT_PLAN")
        impl = read_artifact("IMPLEMENTATION_PLAN")
        
        prompt = (
            "请审视以下三份核心文档的一致性、scope控制、乐趣自洽度与工程风险：\n\n"
            f"【GDD】\n{gdd}\n\n【PM】\n{pm}\n\n【ENG】\n{impl}\n\n"
            "1. 输出一份专业的 Markdown 评审报告（包含打分、分析与优缺点总结）\n"
            "2. 结尾必须由一个 ```json 代码块提供机器可读的大闸门结论，需精准包含：\n"
            "   - status: (PASS/REQUEST_CHANGES/BLOCK)\n"
            "   - targets: 字符串数组, 受影响且需要回流重做的上游，例如 ['GDD', 'PM', 'ENG']\n"
            "   - issues: 对象数组, 每项如 {\"target\": \"GDD\", \"severity\": \"MAJOR\", \"desc\": \"逻辑漏洞\"}\n"
            "   - score: 0-100 的综合数字分数\n"
            "如果完美无瑕无硬伤，status 即写 PASS。"
        )
        
        final_report = self._call(prompt, cfg)
        gate_dict = self._parse_json_gate(final_report)
        status = gate_dict.get('status', 'PASS')
        
        logger.info(f"[ReviewAgent] Commit generated, Gate status resolved to: {status}")
        
        decisions = getattr(state, "decisions", []) + [f"Review concluded with {status}"]
        updates = {
            "review_gate": gate_dict,
            "decisions": decisions
        }
        
        # Step 4.4 针对 Review 阶段特有的打回/开火车提示菜单
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
                content=final_report,
                reason="Official Multi-Dimensional Review"
            ),
            events=["REVIEW_DONE"]
        )

    def _parse_json_gate(self, report_text: str) -> Dict[str, Any]:
        try:
            start_idx = report_text.rfind("```json")
            if start_idx != -1:
                end_idx = report_text.find("```", start_idx + 7)
                if end_idx != -1:
                    json_str = report_text[start_idx+7:end_idx].strip()
                    return json.loads(json_str)
        except Exception as e:
            logger.warning(f"Failed to parse JSON gate from Review Agent: {e}")
            
        status = "PASS" if "PASS" in report_text.upper() else "REQUEST_CHANGES"
        targets = []
        if "ENG" in report_text.upper() or "IMPLEMENTATION" in report_text.upper():
            targets.append("ENG")
        if "PM" in report_text.upper() or "PROJECT" in report_text.upper():
            targets.append("PM")
        if "GDD" in report_text.upper() or "DESIGN" in report_text.upper():
            targets.append("GDD")
            
        return {
            "status": status,
            "targets": list(set(targets)),
            "issues": [
                {"target": t, "severity": "MAJOR", "desc": "Inferring issue from full text due to JSON parse slip."}
                for t in list(set(targets))
            ] if status != "PASS" else [],
            "score": 80
        }
