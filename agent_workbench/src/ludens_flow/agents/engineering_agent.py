import logging
import json
from typing import Optional, Dict, Any

from ludens_flow.agents.base import BaseAgent, AgentResult, CommitSpec
from ludens_flow.state import LudensState
from ludens_flow.artifacts import read_artifact
from llm.provider import LLMConfig

logger = logging.getLogger(__name__)


class EngineeringAgent(BaseAgent):
    name = "EngineeringAgent"
    system_prompt = (
        "你是资深游戏程序(Engineering Agent)。基于 GDD 与 Project Plan，提供工程实现路径指导。"
        "包含代码架构、引擎选型、数据模型、模块划分等内容，支持预设风格与长期开发教练指导。"
    )

    def discuss(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        raise NotImplementedError("EngineeringAgent uses plan_discuss and coach instead of discuss")

    def commit(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        raise NotImplementedError("EngineeringAgent uses plan_commit instead of commit")

    def plan_discuss(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        gdd = read_artifact("GDD")
        pm = read_artifact("PROJECT_PLAN")
        impl_plan = read_artifact("IMPLEMENTATION_PLAN")  
        
        style = state.style_preset or "None"
        eng_draft = state.drafts.get("eng", {})
        
        dev_mode_context = f"\n当前实际生效的实施计划：\n{impl_plan}" if getattr(state, "artifact_frozen", False) else ""

        prompt = (
            f"目标工程风格预设(当前：{style})\n"
            f"已有 GDD：\n{gdd}\n\n"
            f"项目计划：\n{pm}\n"
            f"{dev_mode_context}\n"
            f"过往工程路线草稿与共识：\n{eng_draft}\n\n"
            f"新用户需求/提问：{user_input}\n"
            "请以资深主程视角回答：\n"
            "1. 给出具体的技术架构指导。\n"
            "2. 必须要求用户选择/确认工程风格预设（如：OOP、ECS、轻量级原型）。\n"
            "3. 在回复的最末尾提供一个 ```json 代码块，务必包含 style_preset 字段（根据对话确认），以及新讨论出的 architecture_notes 等信息。\n"
        )
        
        reply = self._call(prompt, cfg)
        
        updates = {"drafts": {**state.drafts}}
        draft_updates = updates["drafts"].get("eng", {})
        
        try:
            start_idx = reply.rfind("```json")
            if start_idx != -1:
                end_idx = reply.find("```", start_idx + 7)
                if end_idx != -1:
                    json_str = reply[start_idx+7:end_idx].strip()
                    extracted_data = json.loads(json_str)
                    
                    if "style_preset" in extracted_data and extracted_data["style_preset"]:
                        updates["style_preset"] = extracted_data.pop("style_preset")
                        
                    draft_updates.update(extracted_data)
                    updates["drafts"]["eng"] = draft_updates
                    
                    reply = reply[:start_idx].strip() + reply[end_idx+3:]
        except Exception as e:
            logger.warning(f"Failed to parse ENG JSON draft: {e}")
            draft_updates["current_discussion"] = reply
            updates["drafts"]["eng"] = draft_updates

        # Step 4.4 Append options
        reply += "\n\n**请选择接下来的操作：**\n[1] 继续讨论\n[2] 定稿并生成\n[3] 回退到上一步 (PM_DISCUSS)"
        
        return AgentResult(
            assistant_message=reply.strip(),
            state_updates=updates
        )

    def plan_commit(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        gdd = read_artifact("GDD")
        pm = read_artifact("PROJECT_PLAN")
        draft = state.drafts.get("eng", {})
        style = state.style_preset or "常规"
        
        prompt = (
            f"依照确定的工程风格：{style}\n"
            f"GDD内容：{gdd}\n\nProject Plan内容：{pm}\n\n工程讨论共识结晶：{draft}\n\n"
            "输出一份直接指导开发者落地的 IMPLEMENTATION_PLAN.md。"
            "需涵盖：架构拆解 / 核心系统数据流 / 技术栈建议 / 首个迭代任务点。"
            "由于由另一端抓取，请务必仅输出纯 Markdown 正文。"
        )
        final_eng = self._call(prompt, cfg)
        
        logger.info("[EngineeringAgent] Commit generated.")
        decisions = getattr(state, "decisions", []) + ["ENG committed"]
        
        return AgentResult(
            assistant_message="工程架构蓝图已准备完毕。\n\n**系统即将自动流转至内部评审(REVIEW)阶段。**",
            state_updates={"decisions": decisions},
            commit=CommitSpec(
                artifact_name="IMPLEMENTATION_PLAN",
                content=final_eng,
                reason="Engineering Architecture Finalized"
            ),
            events=["ENG_COMMITTED"]
        )

    def coach(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        """
        专职进行引擎保姆级实操指导，不包含任何大架构文件的强行覆写
        输出记录将只向外发到 DEVLOG.md（可选），系统主工件被全数冻结
        """
        impl_plan = read_artifact("IMPLEMENTATION_PLAN")
        
        prompt = (
            f"基于已定稿的实行计划:\n{impl_plan}\n\n"
            f"用户在引擎操作/开发中遇到了问题或需要指导: {user_input}\n"
            "请作为一线老将给予直接的具体引擎操作指导（如在Unity里怎么挂组件、命名文件等，或者给出代码段）。\n"
            "请提供手把手的步骤和验收点。"
        )
        
        # 为了演示和留档，直接生成纯文本指导
        reply = self._call(prompt, cfg)
        logger.info("[EngineeringAgent] Coach instruction issued.")
        
        return AgentResult(
            assistant_message=reply.strip(),
            state_updates={}
            # 注释: 若未来想写入 DEVLOG.md，可再增加 CommitSpec(artifact_name="DEVLOG", ...) 并在 artifacts.py 中豁免
        )
