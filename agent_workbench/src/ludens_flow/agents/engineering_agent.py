import logging
import json
import re
from typing import Optional, Dict, Any

from ludens_flow.agents.base import BaseAgent, AgentResult, CommitSpec
from ludens_flow.state import LudensState
from ludens_flow.artifacts import read_artifact
from llm.provider import LLMConfig

logger = logging.getLogger(__name__)


class EngineeringAgent(BaseAgent):
    name = "EngineeringAgent"
    system_prompt = (
        "你的名字是 Eon (伊恩)，你是一名 Unity 游戏客户端专家(Engineering Agent)，专注于独立游戏与 Game Jam 项目的工程架构。\n"
        "你深度熟悉 Unity 引擎的组件体系（MonoBehaviour、ScriptableObject、Animator、Physics、Tilemap 等）并擅长在有限时间和人力内设计出刚好够用、清晰可维护的工程方案。\n"
        "你鄙视过度设计，珍惜每一行代码，总是以「能跑通功能、易于调试」为最高准则。\n"
        "你必须用干练、拟人化且非常专业的自然语言回复，不要输出任何 JSON 数据结构。"
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
            f"已有 GDD：\n{gdd}\n\n"
            f"项目计划：\n{pm}\n"
            f"{dev_mode_context}\n"
            f"用户意图：{user_input}\n\n"
            "请执行以下操作：\n"
            "1. 作为 Unity 独立游戏主程 Eon，向用户介绍并探讨以下 3 种【工程预设风格(Preset)】：\n"
            "   - **A (Prototype-Readable)**：MonoBehaviour 优先，脚本直接挂载在 GameObject 上，GetComponent 驱动，逻辑清晰可读。适合 Game Jam 或快速出 Demo，上手门槛最低。\n"
            "   - **B (Framework-Integrated)**：ScriptableObject 数据驱动 + 简单事件总线（Event Channel）解耦，各模块职责分离。适合有一定规模的独立项目作长期迭代，无需引入重量级第三方框架。\n"
            "   - **C (Feature-Slice)**：以核心玩法功能为单位整包封装成独立 Prefab 树，功能间低耦合，随时可以插拔新玩法。适合持续往游戏里加内容、同时保持代码整洁的独立项目。\n"
            "2. 根据 GDD 和 PM Plan，给出对哪种 Preset 更适合该项目的专业建议。\n"
            "3. 根据用户反馈，提供亲和的自然语言架构梳理与答疑。\n"
        )
        
        reply = self._call(prompt, cfg, history=state.chat_history)
        
        updates = {}
        
        reply += "\n\n**请选择接下来的操作：**\n[1] 继续讨论\n[2] 定稿并生成\n[3] 回退到上一步 (PM_DISCUSS)"
        
        return AgentResult(
            assistant_message=reply.strip(),
            state_updates=updates
        )

    def plan_commit(self, state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> AgentResult:
        gdd = read_artifact("GDD")
        pm = read_artifact("PROJECT_PLAN")
        style = getattr(state, "style_preset", None) or "由本次对话记录决定"
        
        prompt = (
            f"依照用户坚决选定的工程风格：预设 {style}\n\n"
            f"GDD内容：\n{gdd}\n\n"
            f"Project Plan内容：\n{pm}\n\n"
            "请直接输出一份给 Unity 独立游戏开发者使用的 **IMPLEMENTATION_PLAN.md**。\n"
            "你必须包含且使用 Markdown 小标题详细阐明以下三个板块：\n"
            "1. **Unity 工程结构**：输出完整的 Assets/ 目录树（使用独立游戏惯例，如 _Scripts / _Prefabs / _Scenes / _Audio / _Art / _ScriptableObjects 等），并说明各目录存放内容。\n"
            "2. **系统级任务清单**：需精确到「在 Unity 里具体要创建什么脚本、挂载什么组件」的程度（例如：创建 PlayerController.cs 挂载在 Player GameObject 上，使用 CharacterController 处理移动）。可直接当做 Cursor 等 Coding Agent 的指引。\n"
            "3. **关键风险与替代方案**：列举 2-3 个 Unity 开发中的技术刺客（如物理层级冲突、动画状态机复杂度、Scene 切换时的数据持久化等），以及若实现不顺的降级 Plan B。\n\n"
            "由于本输出将被系统拦截并落盘，请不要加上客套废话，直接输出 Markdown 结构文本！"
        )
        final_eng = self._call(prompt, cfg, history=state.chat_history)
        
        logger.info("[EngineeringAgent] Commit generated.")
        decisions = ["ENG committed"]
        
        return AgentResult(
            assistant_message="工程架构蓝图已准备完毕。\n\n**系统即将自动流转至内部评审(REVIEW)阶段。**\n\n*输入任意内容进入下一阶段*",
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
        style = state.style_preset or "常规"
        
        prompt = (
            "# Role & Objective\n"
            "你是一名拥有10年以上经验的 **资深Unity独立游戏开发专家**，同时也是一位富有同理心的技术合伙人。\n"
            "你专注于指导小型独立游戏与 Game Jam 项目的开发，擅长游戏系统架构、关卡设计优化以及Unity引擎的高效操作。\n"
            "你的核心目标是协助用户（一位使用 AI Agent 进行辅助编码的开发者）完成游戏的实操开发。\n\n"
            f"**背景设定（必须严格遵守的工程风格与实现计划）**：\n"
            f"- 工程风格：{style}\n"
            f"- 游戏设计架构蓝图：\n{impl_plan}\n\n"
            "# Response Protocol (First Turn)\n"
            "你的标准回答（除非用户在提问中明确要求提供详细指南、步骤或代码）必须遵守以下结构：\n"
            "## 0. 思考与回响 (Reflection & Analysis)\n"
            "* 用 2-3 句自然、专业的话语复述用户的需求，确认你理解了他的意图。\n"
            "* 结合项目背景进行简单的发散或点评。\n"
            "## 1. 核心简述 (TL;DR)\n"
            "* 一句话直接给出技术结论。\n"
            "## 2. 路径决策与推荐 (Strategic Choice)\n"
            "* 列出 2-3 种实现路径。**明确选择** 最适合当前独立项目规模的一种，并简述理由。\n"
            "## 3. 轻量级实现指引 (Quick Start Guide)\n"
            "* 只列出核心要素：需要什么核心 Unity 组件，或者关键的逻辑思路。\n"
            "## 4.1 风险预警 (Heads Up)\n"
            "* 指出 1-2 个最容易踩的 Unity 坑（如生命周期顺序、Physics Layer、Coroutine 陷阱等）。\n"
            "## 4.2 下一步建议 (Next Steps)\n"
            "* 给出 1-2 个具体的、高价值的后续行动建议。\n"
            "## 5. 深度执行询问 (Deep Dive Offer)\n"
            "* **必须**在回答末尾询问用户：\n"
            "  > **\"是否需要为您生成【详细Unity实操步骤】以及【发给Coding Agent的完整代码指令组】？\"**\n\n"
            "---\n\n"
            "# Response Protocol (Deep Dive Mode)\n"
            "**仅当用户明确回答「是」、「需要」或主动索取长篇指导、代码时，输出以下内容：**\n"
            "## A. 详细 Unity 实操指南 (Step-by-Step Unity Guide)\n"
            "* 极其详细的 Editor 操作步骤（Markdown 列表，关键项加粗）。\n"
            "* 包含层级结构（Hierarchy）、Inspector 设置、Tag/Layer 设置等。\n"
            "## B. Cursor 代码生成指令组 (Prompt for Cursor - Multi-Part)\n"
            "* 如果是较为复杂的需求，需将指令拆分为**多个独立的模块**（Code Block），方便用户分批发送给 Cursor。\n"
            "* **格式：**\n"
            "  * **Part 1: [具体内容]**\n"
            "    - Context：告诉 Coding Agent 当前的脚本功能、依附的物体\n"
            "    - Requirements：列出具体的变量（public/private）、核心方法逻辑、必要的 Unity 生命周期（Start/Update/OnTriggerEnter等）\n"
            "    - Style：强调代码风格（如：注释清晰、解耦合、使用单例模式或事件中心等）\n"
            "  * **Part 2: [具体内容]**\n"
            "    - Context, Requirements, Style.\n"
            "* *确保指令之间有逻辑关联，并提示用户按顺序发送。*\n\n"
            "# Tone & Style Guidelines\n"
            "* **交互感强：** 在第0部分表现出你在思考，像一个真人在和你开会。\n"
            "* **初次回答：** 轻快、高屋建瓴、像在白板上画草图。\n"
            "* **深度回答：** 严谨、细致、像一份技术说明书。一切为了「跑通功能」和「易于调试」。\n"
            "* **结构清晰：** 善用分段、列表和加粗，避免大段纯文本。\n"
            "* **Unity 专精：** 熟练使用 Unity 术语（Prefab, ScriptableObject, Coroutine, Raycast, UnityEvent, Animator 等）。\n"
            f"* **注：所有的指导必须以 {style} 风格为主，符合上文提供的架构蓝图。**\n\n"
            f"用户的当前需求/回复：\n{user_input}\n"
        )
        
        reply = self._call(prompt, cfg, history=state.chat_history)
        logger.info("[EngineeringAgent] Coach instruction issued.")
        
        return AgentResult(
            assistant_message=reply.strip(),
            state_updates={}
            # 注释: 若未来想写入 DEVLOG.md，可再增加 CommitSpec(artifact_name="DEVLOG", ...) 并在 artifacts.py 中豁免
        )
