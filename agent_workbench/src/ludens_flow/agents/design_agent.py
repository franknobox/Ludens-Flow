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
        "你的名字是 Dam (丹姆)，你是一名拥有 10 年以上经验的主设计师(游戏策划 Agent)。\n"
        "你的主要目标是像一位人类主策一样与用户平易近人地交流，厘清他们的设计思路、核心循环和团队规模目标。\n"
        "请绝对使用生动、自然、拟人化并且极其专业的自然语言对话，绝不要在聊天记录里输出任何刻板的 JSON 数据结构！"
    )

    def discuss(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        # 移除了所有槽位抽取的僵硬要求，放开手脚去聊天并借用 chat_history。
        prompt = (
            f"用户的需求/反馈: {user_input}\n\n"
            "请执行以下操作：\n"
            "1. 作为策划 Dam，与用户自然地交流本次的想法，提取或向用户探讨关键信息（核心玩法、范围、美术、队伍等）。\n"
            "2. 如果有模糊地带，用友好的反问来牵引对方思考；如果用户给出了确认，请热烈地发散您的脑洞并予以专业肯定。\n"
            "3. 保持自然、活泼。\n"
        )
        
        # 将带有连贯记忆的任务发送给大模型
        reply = self._call(prompt, cfg, history=state.chat_history)
        
        # 拼接引导动作选项
        reply += "\n\n**请选择接下来的操作：**\n[1] 继续讨论\n[2] 定稿并生成\n[3] 回退到上一步 (已是初始阶段)"
        
        # 纯自然语言回传给外界展示
        return AgentResult(
            assistant_message=reply.strip(),
            state_updates={}
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
            assistant_message="GDD 已定稿出炉，正交付总控归档。\n\n**系统即将自动流转至项目管理(PM)阶段。**\n\n*输入任意内容进入下一阶段*",
            state_updates={"decisions": decisions},
            commit=CommitSpec(
                artifact_name="GDD",
                content=final_gdd,
                reason="User confirmed commit via router"
            ),
            events=["GDD_COMMITTED"]
        )
