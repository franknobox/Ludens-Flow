import logging
from typing import Optional, Dict, Any
import json

from ludens_flow.agents.base import BaseAgent, AgentResult, CommitSpec
from ludens_flow.state import LudensState
from llm.provider import LLMConfig

logger = logging.getLogger(__name__)

class DesignAgent(BaseAgent):
    name = "DesignAgent"
    system_prompt = (
        "你是资深游戏策划(Design Agent)。支持多轮对话商讨方案；"
        "仅当用户确认“开始执行/定稿”后，你的同僚会被触发生成最终的 GDD.md。"
    )

    def discuss(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        previous_draft = state.drafts.get("gdd", {})
        
        prompt = (
            f"用户的需求/反馈: {user_input}\n"
            f"当前策划思路草案: {previous_draft}\n\n"
            "请以专业游戏策划的视角：\n"
            "1. 简短总结当前已知的游戏设定\n"
            "2. 列出 5-8 个关键补问（受众、平台、核心循环、MVP范围、一个关卡示例等）以推进讨论\n"
            "3. 提取当前讨论的核心信息（如 core_loop, mvp_scope, open_questions），在你的回复最末尾用 ```json 代码块输出这些字段，以供系统保存。\n"
        )
        
        reply = self._call(prompt, cfg)
        
        updates = {"drafts": {**state.drafts}}
        gdd_draft = updates["drafts"].get("gdd", {})
        
        try:
            start_idx = reply.rfind("```json")
            if start_idx != -1:
                end_idx = reply.find("```", start_idx + 7)
                if end_idx != -1:
                    json_str = reply[start_idx+7:end_idx].strip()
                    extracted_draft = json.loads(json_str)
                    gdd_draft.update(extracted_draft)
                    updates["drafts"]["gdd"] = gdd_draft
                    reply = reply[:start_idx].strip() + reply[end_idx+3:]
        except Exception as e:
            logger.warning(f"Failed to parse Design JSON draft: {e}")
            gdd_draft["current_discussion"] = reply
            updates["drafts"]["gdd"] = gdd_draft

        reply += "\n\n**请选择接下来的操作：**\n[1] 继续讨论\n[2] 定稿并生成\n[3] 回退到上一步 (GDD_DISCUSS 已经是起点)"
        
        return AgentResult(
            assistant_message=reply.strip(),
            state_updates=updates
        )

    def commit(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        draft_context = state.drafts.get("gdd", {})
        
        prompt = (
            f"请基于以下讨论共识与草案信息：\n{draft_context}\n\n"
            "输出一份专业、结构化、可落盘的 GDD(Game Design Document) Markdown 文档。"
            "需包含：概述、核心循环、关键系统、关卡结构、美术风格、MVP边界。不要输出多余解释。"
        )
        final_gdd = self._call(prompt, cfg)
        logger.info("[DesignAgent] Commit generated.")
        
        decisions = getattr(state, "decisions", []) + ["GDD committed"]
        
        return AgentResult(
            assistant_message="GDD 已定稿出炉，正交付总控归档。\n\n**系统即将自动流转至项目管理(PM)阶段。**",
            state_updates={"decisions": decisions},
            commit=CommitSpec(
                artifact_name="GDD",
                content=final_gdd,
                reason="User confirmed commit via router"
            ),
            events=["GDD_COMMITTED"]
        )
