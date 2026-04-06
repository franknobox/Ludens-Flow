import logging
from typing import Optional, Dict, Any
import json

from ludens_flow.agents.base import BaseAgent, AgentResult, CommitSpec
from ludens_flow.state import LudensState
from llm.provider import LLMConfig

logger = logging.getLogger(__name__)


class DesignAgent(BaseAgent):
    """负责 GDD 阶段的讨论和定稿。"""
    name = "DesignAgent"

    def discuss(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None, user_persona: Optional[str] = None) -> AgentResult:
        # 回流修改时，把当前 GDD 一并带入讨论上下文。
        from ludens_flow.artifacts import read_artifact
        existing_gdd = read_artifact("GDD", project_id=state.project_id)
        
        gdd_context = ""
        if existing_gdd.strip():
            gdd_context = f"**当前已有的 GDD 文档内容**（如果是回流修改阶段，请在此基础上修订而非从零开始）：\n{existing_gdd}\n\n"
        
        # discuss 只收敛需求和玩法方向，不直接生成最终工件。
        prompt = (
            f"{gdd_context}"
            f"用户的需求/反馈: {user_input}\n\n"
            "请执行以下操作：\n"
            "1. 作为策划 Dam，与用户热情地交流本次的想法，探讨和提炼关键信息（核心玩法机制、游戏感受、大致开发规模）。\n"
            "2. 从 Unity 独立开发的视角出发，适时评估玩法机制的实现可行性——例如某个机制在 Unity 里是否容易实现，或者有没有更聪明的替代方案。\n"
            "3. 鼓励创意冒险，聚焦于能在有限时间内跑通的最小核心体验（类似 Game Jam 思维）。\n"
            "4. 如果有模糊地带，用友好的反问牵引思考；如果用户给的方向清晰，热烈肯定并发散脑洞。\n"
            "5. 保持轻松、活泼、富有创造力的对话节奏。\n"
            "\n\n请严格仅输出一个合法的 JSON 对象，且不要包含任何多余的解释文字或注释。JSON schema（必须遵守）：\n"
            "{\n"
            "  \"reply\": \"要直接显示给用户的自然语言回答（string）\",\n"
            "  \"state_updates\": { /* 可选：要合并到 state 的字典 */ },\n"
            "  \"profile_updates\": [\"[PROFILE_UPDATE] key: value\", ...],\n"
            "  \"events\": [\"EVENT_NAME\", ...],\n"
            "  \"commit\": { \"artifact_name\": \"GDD\", \"content\": \"要写入的完整文本\", \"reason\": \"写入原因\" } /* 可选 */\n"
            "}\n"
            "重要：如果某字段无值，请使用 null、{} 或 [] 表示；不要输出多余文本。"
        )
        
        raw = self._call(prompt, cfg, history=state.chat_history, user_persona=user_persona)

        # 尝试解析结构化 JSON 响应。
        parsed, remaining = self.parse_structured_response(raw)
        if parsed:
            assistant_text = parsed.get("reply", remaining or "")
            menu = "\n\n**请选择接下来的操作：**\n[1] 继续讨论\n[2] 定稿并生成\n[3] 回退到上一步 (已是初始阶段)"
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

        # 无JSON
        reply = (raw or "")
        reply += "\n\n**请选择接下来的操作：**\n[1] 继续讨论\n[2] 定稿并生成\n[3] 回退到上一步 (已是初始阶段)"
        return AgentResult(
            assistant_message=reply.strip(),
            state_updates={}
        )

    def commit(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None, user_persona: Optional[str] = None) -> AgentResult:
        # commit 直接输出可落盘的最终版 GDD。
        prompt = (
            "请基于我们之前的完整讨论记录，将其中已经明确的信息整合为一份规范化 GDD (Game Design Document) Markdown 文档。\n"
            "面向使用 Unity 引擎的独立开发者或小型 Game Jam 团队。\n\n"
            "要求：\n"
            "1. 包含以下版块：概述（题材/核心体验/目标玩家）、核心循环、关键系统、关卡/内容结构、美术风格与氛围、MVP 边界。\n"
            "2. **关键系统** 版块中，每个系统必须附注 Unity 实现可行性备注，例如使用 CharacterController / Tilemap / Rigidbody2D / NavMesh / Animator 等具体手段。\n"
            "3. **MVP 边界** 版块需明确「哪些功能是核心体验必须有」「哪些是 nice-to-have 可以留到后续」，以 Game Jam 标准控制范围。\n"
            "4. **严禁擅自编造未确定内容**：如果讨论中确实没有提及某个版块的细节，该部分必须严格留白标注为 `[待定：补充说明...]`。但凡讨论中提到过的内容，必须如实填入。\n"
            "5. 排版风格：仅在各章节主标题前加少量 Emoji 点缀，正文严谨冷峻。\n"
            "6. 尾部增设两部分：\n"
            "   - 【⚠️ 技术风险】：基于 Unity 开发经验，分析 2-3 个实现上的技术痛点（如物理碰撞、动画状态机、场景管理等）。\n"
            "   - 【💡 创意变体】：用简洁的 1-2 句话提供 2 种玩法衍生变体方向，激发后续迭代灵感。\n"
            "重要：你的整篇输出将会被原封不动保存。除 Markdown 正文外，**不要**输出多余的解释首尾语。"
        )
        final_gdd = self._call(prompt, cfg, history=state.chat_history, user_persona=user_persona)
        logger.info("[DesignAgent] Commit generated.")
        
        decisions = ["GDD committed"]
        
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
