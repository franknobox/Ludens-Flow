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
        "你的名字是 Pax (帕克斯)，你是一位擅长独立游戏项目的 PM Agent。\n"
        "你深度理解小团队或个人开发者的节奏，了解 Unity 项目的工程目录结构与 Editor 工作流。\n"
        "你的核心哲学是：控制 scope，快速验证，砍掉一切不必要的功能，让核心体验尽快跑起来。\n"
        "你必须用干练、亲切且务实的自然语言回复，不要输出任何 JSON 数据结构。"
    )

    def discuss(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        gdd_content = read_artifact("GDD")
        existing_pm = read_artifact("PROJECT_PLAN")
        
        pm_context = ""
        if existing_pm.strip():
            pm_context = f"**当前已有的 PROJECT_PLAN 文档内容**（如果是回流修改阶段，请在此基础上修订）：\n{existing_pm}\n\n"
        
        prompt = (
            f"已有 GDD：\n{gdd_content}\n\n"
            f"{pm_context}"
            f"用户意图：{user_input}\n\n"
            "请执行以下操作：\n"
            "1. 以独立游戏 PM 的视角，向用户确认或探讨关键排期信息：大致工期（以天/周为单位）、参与人数（默认 1-3 人小团队）。\n"
            "2. 结合 GDD 中的功能，主动帮用户识别哪些功能是核心体验不可缺少的，哪些可以在 Game Jam 或 MVP 阶段果断砍掉。\n"
            "3. 所有建议以 Unity PC Standalone（Editor 可以 Play Mode 验收）为默认交付目标，不主动引入跨平台或多人联网议题。\n"
            "4. 以自然语言流畅地回复用户，不带任何特殊格式标签。\n"
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
        
        prompt = (
            f"已有 GDD：\n{gdd_content}\n\n"
            "请基于我们之前的完整讨论记录，输出一份适合独立游戏或 Game Jam 项目的 PROJECT_PLAN.md，要求：\n"
            "1. **Milestones**：以 M0/M1/M2 划分，每个 Milestone 的验收标准必须是 Unity Editor Play Mode 可测试的具体状态（例如：M0 = 可在 Play Mode 中进入主场景并完成一次完整的游戏主循环）。\n"
            "2. **Task Breakdown**：按 Unity 工程模块拆分任务，例如 Scripts / Prefabs / SceneSetup / Animations / Audio。每项任务应细化到「在 Unity 里要做什么」的程度，方便单人或小团队直接上手。\n"
            "3. **Unity 目录结构建议**：输出一份适合本项目的 Assets/ 目录树，遵循 Unity 独立游戏项目惯例（如 _Scripts / _Prefabs / _Scenes / _Audio / _Art 等）。\n"
            "4. **风险与缓解**：聚焦技术风险和 scope 蔓延风险，给出务实的应对建议。不涉及多人协作流程或商业发布计划。\n"
            "5. 如果你发现 GDD 存在严重缺项导致无法顺利排期，请在回复正文最后附加 ChangeRequest JSON 块：\n"
            "格式：\n"
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
                final_pm = final_pm_output[:cr_match.start()].strip() + final_pm_output[cr_match.end():].strip()
            except Exception as e:
                logger.warning(f"Failed to parse PM ChangeRequest JSON: {e}")

        updates["decisions"] = ["PM committed"]

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
