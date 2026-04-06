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
    """负责项目计划阶段的讨论、范围收敛和定稿。"""
    name = "PMAgent"

    def discuss(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None, user_persona: Optional[str] = None) -> AgentResult:
        # 回流修改时，把现有 PROJECT_PLAN 一起带入讨论。
        gdd_content = read_artifact("GDD", project_id=state.project_id)
        existing_pm = read_artifact("PROJECT_PLAN", project_id=state.project_id)
        
        pm_context = ""
        if existing_pm.strip():
            pm_context = f"**当前已有的 PROJECT_PLAN 文档内容**（如果是回流修改阶段，请在此基础上修订）：\n{existing_pm}\n\n"
        
        # discuss 负责排期、范围和 MVP 收敛，不直接落盘正式计划。
        prompt = (
            f"已有 GDD：\n{gdd_content}\n\n"
            f"{pm_context}"
            f"用户意图：{user_input}\n\n"
            "请执行以下操作：\n"
            "1. 以独立游戏 PM 的视角，向用户确认或探讨关键排期信息：大致工期（以天/周为单位）、参与人数（默认 1-3 人小团队）。\n"
            "2. 结合 GDD 中的功能，主动帮用户识别哪些功能是核心体验不可缺少的，哪些可以在 Game Jam 或 MVP 阶段果断砍掉。\n"
            "3. 所有建议以 Unity PC Standalone（Editor 可以 Play Mode 验收）为默认交付目标，不主动引入跨平台或多人联网议题。\n"
            "4. 以自然语言流畅地回复用户，不带任何特殊格式标签。\n"
            "\n\n请严格仅输出一个合法的 JSON 对象，且不要包含任何多余的解释文字或注释。JSON schema（必须遵守）：\n"
            "{\n"
            "  \"reply\": \"要直接显示给用户的自然语言回答（string）\",\n"
            "  \"state_updates\": { /* 可选：要合并到 state 的字典 */ },\n"
            "  \"profile_updates\": [\"[PROFILE_UPDATE] key: value\", ...],\n"
            "  \"events\": [\"EVENT_NAME\", ...],\n"
            "  \"commit\": { \"artifact_name\": \"PROJECT_PLAN\", \"content\": \"可选：当需要写盘时提供的文本\", \"reason\": \"写入原因\" } /* 可选 */\n"
            "}\n"
            "重要：如果某字段无值，请使用 null、{} 或 [] 表示；不要输出多余文本。\n"
        )
        raw = self._call(prompt, cfg, history=state.chat_history, user_persona=user_persona)
        parsed, remaining = self.parse_structured_response(raw)
        if parsed:
            assistant_text = parsed.get("reply", remaining or "")
            menu = "\n\n**请选择接下来的操作：**\n[1] 继续讨论\n[2] 定稿并生成\n[3] 回退到上一步 (GDD_DISCUSS)"
            assistant_text = (assistant_text or "") + menu
            state_updates = parsed.get("state_updates", {}) or {}
            profile_updates = parsed.get("profile_updates", []) or []
            events = parsed.get("events", []) or []
            return AgentResult(
                assistant_message=(assistant_text or "").strip(),
                state_updates=state_updates,
                events=events,
                profile_updates=profile_updates
            )

        reply = (raw or "")
        updates = {}
        reply += "\n\n**请选择接下来的操作：**\n[1] 继续讨论\n[2] 定稿并生成\n[3] 回退到上一步 (GDD_DISCUSS)"
        return AgentResult(
            assistant_message=reply.strip(),
            state_updates=updates
        )

    def commit(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None, user_persona: Optional[str] = None) -> AgentResult:
        # commit 输出最终 PROJECT_PLAN，并解析附带的变更请求。
        gdd_content = read_artifact("GDD", project_id=state.project_id)
        
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
        final_pm_output = self._call(prompt, cfg, history=state.chat_history, user_persona=user_persona)
        
        updates = {}
        final_pm = final_pm_output
        
        cr_pattern = r"<<CHANGE_REQUEST_JSON>>\s*(\{.*?\})\s*<<END_CHANGE_REQUEST_JSON>>"
        cr_match = re.search(cr_pattern, final_pm_output, re.DOTALL)
        
        if cr_match:
            try:
                cr_data = json.loads(cr_match.group(1))
                if "change_requests" in cr_data:
                    # 这里只回传本轮新请求，具体合并由 Graph 统一处理。
                    updates["change_requests"] = cr_data["change_requests"]
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
