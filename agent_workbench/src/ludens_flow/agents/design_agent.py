import logging
from typing import Optional, Dict, Any
import json

from ludens_flow.agents.base import BaseAgent, AgentResult, CommitSpec
from ludens_flow.state import LudensState
from llm.provider import LLMConfig

logger = logging.getLogger(__name__)

import re

class DesignAgent(BaseAgent):
    name = "DesignAgent"
    system_prompt = (
        "你是一名拥有10年以上经验的资深游戏策划，擅长将发散的灵感转化为逻辑严密的GDD。\n"
        "你的主要目标是厘清思路、为程序/美术提供可落盘的依据。\n"
    )

    def discuss(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        previous_draft = state.drafts.get("gdd", {})
        
        prompt = (
            f"用户的需求/反馈: {user_input}\n"
            f"当前策划思路草案: {previous_draft}\n\n"
            "请执行以下操作：\n"
            "1. 提取或向用户确认关键信息（核心循环、MVP范围、题材、预期反馈等）。若用户未明确，提出补问。\n"
            "2. 以自然语言流畅地回复用户，可以提供建议、扩展延伸或者询问细节。\n"
            "3. 【状态更新指令】在回复的最末尾，你**必须**输出一段更新总结的 JSON 块。系统将用此记录你此时的工作记忆。\n"
            "格式必须为：\n"
            "<<STATE_UPDATE_JSON>>\n"
            "{{\n"
            "  \"core_loop\": \"...\",\n"
            "  \"mvp_scope\": \"...\",\n"
            "  \"open_questions\": [\"...\"],\n"
            "  \"setting\": \"...\"\n"
            "}}\n"
            "<<END_STATE_UPDATE_JSON>>\n"
        )
        
        reply = self._call(prompt, cfg)
        
        updates = {"drafts": {**state.drafts}}
        gdd_draft = dict(updates["drafts"].get("gdd", {}))
        
        # 使用正则解析 JSON
        pattern = r"<<STATE_UPDATE_JSON>>\s*(\{.*?\})\s*<<END_STATE_UPDATE_JSON>>"
        match = re.search(pattern, reply, re.DOTALL)
        
        if match:
            try:
                extracted_draft = json.loads(match.group(1))
                gdd_draft.update(extracted_draft)
                updates["drafts"]["gdd"] = gdd_draft
                # 脱去 JSON 让用户看到的仅仅是自然对话
                reply = reply[:match.start()].strip() + reply[match.end():].strip()
            except Exception as e:
                logger.warning(f"Failed to parse Design <<STATE_UPDATE_JSON>> block: {e}")
                gdd_draft["current_discussion"] = reply
                updates["drafts"]["gdd"] = gdd_draft
        else:
            gdd_draft["current_discussion"] = reply
            updates["drafts"]["gdd"] = gdd_draft

        reply += "\n\n**请选择接下来的操作：**\n[1] 继续讨论\n[2] 定稿并生成\n[3] 回退到上一步 (已是初始阶段)"
        
        return AgentResult(
            assistant_message=reply.strip(),
            state_updates=updates
        )

    def commit(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        draft_context = state.drafts.get("gdd", {})
        
        prompt = (
            f"请基于以下我们在讨论中已经沉淀的草案信息：\n{draft_context}\n\n"
            "你需要输出一份直接给程序与美术过目的规范化 GDD(Game Design Document) Markdown 文档。\n"
            "要求：\n"
            "1. 包含以下版块：概述(背景/受众/题材)、核心循环、关键系统、关卡结构、美术风格与预期体验、MVP边界。\n"
            "2. **严禁擅自编造未确定内容**：未确定的部分必须严格留白，如：`[待定：补充说明...]`。\n"
            "3. 排版风格（默认保持适中）：仅在各章节主标题前加少量 Emoji 点缀，正文严谨冷峻。\n"
            "4. 尾部增设两部分：\n"
            "   - 【⚠️ 潜在风险】：基于你的经验，分析 2-3 个技术、实现或验证上的痛点风险。\n"
            "   - 【💡 提案变体】：为了拓展，用简洁的 1-2 句话提供 2 种玩法的衍生变体思路。\n"
            "重要：你的整篇输出将会被原封不动保存。所以除 Markdown 正文外，**不要**输出多余的解释首尾语。"
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
