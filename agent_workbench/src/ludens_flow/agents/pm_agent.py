import logging
from typing import Optional, Dict, Any
import json

from ludens_flow.agents.base import BaseAgent, AgentResult, CommitSpec
from ludens_flow.state import LudensState
from ludens_flow.artifacts import read_artifact
from llm.provider import LLMConfig

logger = logging.getLogger(__name__)


import re

class PMAgent(BaseAgent):
    name = "PMAgent"
    system_prompt = (
        "你的名字是 Pax(帕克斯)，你是资深项目管理者 (PM Agent)。\n"
        "你需要基于 GDD 以及像一位经验丰富的人类合伙人一样，与用户沟通开发阶段、任务拆解、协作机制等信息；\n"
        "你必须用干练、拟人化且非常专业的自然语言回复，不要输出任何 JSON 数据结构。"
    )

    def discuss(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        gdd_content = read_artifact("GDD")
        previous_draft = state.drafts.get("pm", {})
        
        prompt = (
            f"已有 GDD：\n{gdd_content}\n\n"
            f"用户意图：{user_input}\n\n"
            "请执行以下操作：\n"
            "1. 以专业且亲和的 PM 视角，向用户确认或探讨关键信息：工期、团队人数、协作方式等。\n"
            "2. 以自然语言流畅地回复用户，不要带任何特殊格式标签。\n"
        )
        reply = self._call(prompt, cfg, history=state.chat_history)
        
        updates = {}

        reply += "\n\n**请选择接下来的操作：**\n[1] 继续讨论\n[2] 定稿并生成\n[3] 回退到上一步 (GDD_DISCUSS)"
        
        return AgentResult(
            assistant_message=reply.strip(),
            state_updates=updates
        )

    def commit(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        gdd_content = read_artifact("GDD")
        draft_context = state.drafts.get("pm", {})
        
        prompt = (
            f"已有 GDD：\n{gdd_content}\n\n"
            f"讨论共识：\n{draft_context}\n\n"
            "1. 请输出一份详实的 PROJECT_PLAN.md。要求包含：Milestones (M0/M1/M2) 及验收标准、Task breakdown (按模块或按角色拆解)、协作方式与目录结构建议、风险与缓解方案。\n"
            "2. 如果你发现 GDD 存在严重缺项导致无法顺利排期（例如完全没有提及核心战斗形式），请**务必**在回复正文的最后附加一节 ChangeRequest JSON 块。\n"
            "格式必须为：\n"
            "<<CHANGE_REQUEST_JSON>>\n"
            "{\n"
            "  \"change_requests\": [\n"
            "    {\"target\": \"GDD\", \"rationale\": \"缺少对核心循环结束条件的描述\", \"suggested_changes\": \"要求补充通关机制或无尽模式声明\", \"severity\": \"High\"}\n"
            "  ]\n"
            "}\n"
            "<<END_CHANGE_REQUEST_JSON>>\n"
            "如果没有缺项，可以不输出此 JSON。你的 Markdown 正文不应被代码块包裹，请直接以 Markdown 标题起手。"
        )
        final_pm_output = self._call(prompt, cfg, history=state.chat_history)
        
        updates = {}
        final_pm = final_pm_output
        
        cr_pattern = r"<<CHANGE_REQUEST_JSON>>\s*(\{.*?\})\s*<<END_CHANGE_REQUEST_JSON>>"
        cr_match = re.search(cr_pattern, final_pm_output, re.DOTALL)
        
        if cr_match:
            try:
                cr_data = json.loads(cr_match.group(1))
                if "change_requests" in cr_data:
                    updates["change_requests"] = getattr(state, "change_requests", []) + cr_data["change_requests"]
                    logger.info(f"[PMAgent] Detected and appended {len(cr_data['change_requests'])} ChangeRequest(s).")
                # 脱去 JSON，仅写入纯 Markdown 作为工件
                final_pm = final_pm_output[:cr_match.start()].strip() + final_pm_output[cr_match.end():].strip()
            except Exception as e:
                logger.warning(f"Failed to parse PM ChangeRequest JSON: {e}")

        updates["decisions"] = getattr(state, "decisions", []) + ["PM committed"]

        logger.info("[PMAgent] Commit generated.")
        
        return AgentResult(
            assistant_message="项目管理规划书 (PROJECT_PLAN) 已定稿。\n\n**系统即将自动流转至技术(ENG)阶段。**\n\n*输入任意内容进入下一阶段*",
            state_updates=updates,
            commit=CommitSpec(
                artifact_name="PROJECT_PLAN",
                content=final_pm,
                reason="PM Commit Sequence Initiated"
            ),
            events=["PM_COMMITTED"]
        )
