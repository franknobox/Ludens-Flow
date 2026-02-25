import logging
from typing import Optional, Dict, Any
import json

from ludens_flow.agents.base import BaseAgent, AgentResult, CommitSpec
from ludens_flow.state import LudensState
from ludens_flow.artifacts import read_artifact
from llm.provider import LLMConfig

logger = logging.getLogger(__name__)


class PMAgent(BaseAgent):
    name = "PMAgent"
    system_prompt = (
        "你是资深项目管理者(PM Agent)。基于 GDD 进行多轮对话补齐开发阶段、任务拆解、协作机制等信息；"
        "最终生成项目计划 Markdown 文档。"
    )

    def discuss(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        gdd_content = read_artifact("GDD")
        previous_draft = state.drafts.get("pm", {})
        
        prompt = (
            f"已有 GDD：\n{gdd_content}\n\n"
            f"目前项目计划讨论草案：\n{previous_draft}\n\n"
            f"用户意图：{user_input}\n"
            "请以专业 PM 视角，向用户补问关键 PM 信息：工期、团队人数/角色、每周投入、工具链（Unity版本、Git LFS、沟通工具）、协作方式等。\n"
            "在回复的最末尾，请提取当前讨论出的 PM 相关信息并用 ```json 代码块输出，例如包含 schedule, team_size, tools 等字段以供系统保存。"
        )
        reply = self._call(prompt, cfg)
        
        updates = {"drafts": {**state.drafts}}
        pm_draft = updates["drafts"].get("pm", {})
        
        try:
            start_idx = reply.rfind("```json")
            if start_idx != -1:
                end_idx = reply.find("```", start_idx + 7)
                if end_idx != -1:
                    json_str = reply[start_idx+7:end_idx].strip()
                    extracted_draft = json.loads(json_str)
                    pm_draft.update(extracted_draft)
                    updates["drafts"]["pm"] = pm_draft
                    reply = reply[:start_idx].strip() + reply[end_idx+3:]
        except Exception as e:
            logger.warning(f"Failed to parse PM JSON draft: {e}")
            pm_draft["current_discussion"] = reply
            updates["drafts"]["pm"] = pm_draft

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
            "1. 请输出一份详实的 PROJECT_PLAN.md。包含开发阶段与里程碑、任务拆解、协作方式与目录结构建议、风险项等。仅输出以 ```markdown 开始的代码块。\n"
            "2. 如果发现 GDD 存在描述不清或缺项可能影响项目排期，请在回复的最末尾附加一个 JSON，格式如下：\n"
            "```json\n"
            "{\"change_requests\": [{\"target\": \"GDD\", \"rationale\": \"缺少对核心循环结束条件的描述\"}]}\n"
            "```\n"
            "如果没有缺项，可以不输出 JSON。"
        )
        final_pm_output = self._call(prompt, cfg)
        
        final_pm = final_pm_output
        updates = {}
        
        # 尝试抠出纯净的 Markdown 正文
        md_start = final_pm_output.find("```markdown")
        if md_start != -1:
            md_end = final_pm_output.find("```", md_start + 11)
            if md_end != -1:
                final_pm = final_pm_output[md_start+11:md_end].strip()

        # 解析潜藏的 ChangeRequest 并挂载状态
        try:
            json_start = final_pm_output.rfind("```json")
            if json_start != -1:
                json_end = final_pm_output.find("```", json_start + 7)
                if json_end != -1:
                    cr_json = final_pm_output[json_start+7:json_end].strip()
                    cr_data = json.loads(cr_json)
                    if "change_requests" in cr_data:
                        updates["change_requests"] = getattr(state, "change_requests", []) + cr_data["change_requests"]
        except Exception as e:
            logger.warning(f"Failed to parse CR JSON in PM Agent: {e}")

        updates["decisions"] = getattr(state, "decisions", []) + ["PM committed"]

        logger.info("[PMAgent] Commit generated.")
        
        return AgentResult(
            assistant_message="项目管理规划书 (PROJECT_PLAN) 已定稿。\n\n**系统即将自动流转至技术(ENG)阶段。**",
            state_updates=updates,
            commit=CommitSpec(
                artifact_name="PROJECT_PLAN",
                content=final_pm,
                reason="PM Commit Sequence Initiated"
            ),
            events=["PM_COMMITTED"]
        )
