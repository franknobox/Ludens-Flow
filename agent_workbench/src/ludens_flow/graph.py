import logging
from typing import Tuple, Dict, Any, Optional

from ludens_flow.state import LudensState, save_state, write_trace_log, write_router_log
from ludens_flow.artifacts import write_artifact
from ludens_flow.router import ludens_router_logic, Phase
from ludens_flow.agents.base import AgentResult

# 引入各个单体 Agent，避免重复实例化
from ludens_flow.agents.design_agent import DesignAgent
from ludens_flow.agents.pm_agent import PMAgent
from ludens_flow.agents.engineering_agent import EngineeringAgent
from ludens_flow.agents.review_agent import ReviewAgent

logger = logging.getLogger(__name__)

# 单例化全局使用的 Agent
_gdd_agent = DesignAgent()
_pm_agent = PMAgent()
_eng_agent = EngineeringAgent()
_review_agent = ReviewAgent()


def _merge_state_updates(state: LudensState, updates: Dict[str, Any]) -> None:
    """处理并合并 Agent 返回的数据到 global state"""
    if "drafts" in updates:
        for phase_key, items in updates["drafts"].items():
            if phase_key not in state.drafts:
                state.drafts[phase_key] = {}
            state.drafts[phase_key].update(items)
            
    if "change_requests" in updates:
        state.change_requests.extend(updates["change_requests"])
        
    if "decisions" in updates:
        state.decisions.extend(updates["decisions"])
        
    if "style_preset" in updates and updates["style_preset"]:
        state.style_preset = updates["style_preset"]

    if "review_gate" in updates:
        # 整体覆盖更新这道大门
        state.review_gate = updates["review_gate"]


def run_agent_step(agent, mode: str, state: LudensState, user_input: str) -> LudensState:
    """
    Graph 中“执行一个节点”的标准工具函数
    内部按顺序：记录 trace-进入 -> 调用 agent -> 合并状态 -> 写物料 -> 盖状态 -> 记录 trace-退出 -> 抛错收拢
    """
    node_name = agent.name
    current_phase = state.phase
    is_frozen = getattr(state, "artifact_frozen", False)
    
    # 1. 记录 trace: ENTER
    write_trace_log("ENTER", node_name, current_phase, is_frozen, state.last_event or "NONE")
    
    print(f"[DEBUG] run_agent_step - Calling agent: {node_name} Mode: {mode}")    
    try:
        # 2. 调用 agent 的指定方法
        if mode == "DISCUSS":
            result: AgentResult = agent.discuss(state, user_input)
        elif mode == "COMMIT":
            result: AgentResult = agent.commit(state, user_input)
        elif mode == "PLAN_DISCUSS":
            result: AgentResult = getattr(agent, "plan_discuss")(state, user_input)
        elif mode == "PLAN_COMMIT":
            result: AgentResult = getattr(agent, "plan_commit")(state, user_input)
        elif mode == "COACH":
            result: AgentResult = getattr(agent, "coach")(state, user_input)
        else:
            raise ValueError(f"Unknown agent mode: {mode}")

        # 3. 合并状态的更新字段 (drafts, change_requests, review_gate 等)
        if result.state_updates:
            _merge_state_updates(state, result.state_updates)
            
        # 同步记录供终端回显的话术
        state.last_assistant_message = result.assistant_message
        
        # 将本轮回话打包送进短期记忆体 (过滤空语句)
        has_meaningful_input = False
        if isinstance(user_input, list):
            has_meaningful_input = bool(user_input)  # Not empty list
        else:
            has_meaningful_input = bool(user_input.strip())
            
        if has_meaningful_input and result.assistant_message.strip():
            state.chat_history.append({"role": "user", "content": user_input})
            state.chat_history.append({"role": "assistant", "content": result.assistant_message})
            # 设置阶段隔离/记忆断层：只保留最近 10 次对话(20条数据)，避免 token 在无限对练里被撑爆
            if len(state.chat_history) > 20:
                state.chat_history = state.chat_history[-20:]

        commit_flag = "N"
        # 4. 如果包含实质性写盘行为 (Commit)
        if result.commit and result.commit.artifact_name and result.commit.content:
            art_name = result.commit.artifact_name
            # 双向守护拦截: 如果在结冰期且写入的不是日志/笔记类豁免工件，则强硬切断写入，防止 Agent 违规撰写主线档案
            if is_frozen and art_name not in ["DEVLOG"]:
                logger.warning(f"BLOCKED: {node_name} tried to commit '{art_name}' during frozen DEV_COACHING phase.")
                state.last_error = f"Cannot commit canonical artifact {art_name} while artifact_frozen=True"
                commit_flag = "BLOCKED"
                save_state(state)
                write_trace_log("LEAVE", node_name, current_phase, is_frozen, commit_flag)
                return state
            else:
                commit_reason = result.commit.reason or "Agent initiated commit"
                if "review_gate" in result.state_updates:
                    # 针对 Review 特殊说明原因
                    commit_reason = f"Review Auto-Gate, decision: {result.state_updates['review_gate'].get('status', 'PND')}"
                
                logger.debug(f">>>>> WRITE ARTIFACT GUARD <<<<<")
                logger.debug(f"Type of content: {type(result.commit.content)}")
                logger.debug(f"Content preview: {repr(result.commit.content[:100])}...")

                # 写盘并计入 artifacts.log
                write_artifact(
                    name=art_name, 
                    content=result.commit.content, 
                    reason=commit_reason, 
                    actor=node_name, 
                    state=state
                )
                commit_flag = "Y"
                
                # 生成对应的流转动作事件
                commit_event = f"{art_name}_COMMITTED".upper()
                if art_name == "PROJECT_PLAN":
                    commit_event = "PM_COMMITTED"
                elif art_name == "IMPLEMENTATION_PLAN":
                    commit_event = "ENG_COMMITTED"
                elif art_name == "REVIEW_REPORT":
                    commit_event = "REVIEW_DONE"
                    
                state.last_event = commit_event

        # 5. 持久化数据
        state.last_error = None  # 正常执行后清理报错记录
        save_state(state)
        
        # 6. 记录 trace: LEAVE
        write_trace_log("LEAVE", node_name, current_phase, is_frozen, commit_flag)

    except Exception as e:
        # 错误抓取，避免炸服退出，让 Router 根据 last_error 将选择权返回给用户
        err_msg = str(e)
        logger.error(f"[Agent Error] {node_name} execution failed: {err_msg}")
        state.last_error = err_msg
        save_state(state)
        write_trace_log("LEAVE", node_name, current_phase, is_frozen, "N", error=err_msg)

    return state


# --- Graph 阶段映射节点实体 ---

class RouterNode:
    """
    所有调度的总枢纽。根据 state.phase 和用户指令决定下一个 Agent 何去何从。
    写 router.log 并执行 phase 扭转。
    """
    def execute(self, state: LudensState, user_input: str) -> str:
        # 调用 Router 分发逻辑
        result = ludens_router_logic(state, user_input)
        
        from_phase = state.phase
        to_phase = result.next_phase
        
        # 状态推进与记录
        gate_status = "N/A"
        if state.review_gate:
             gate_status = state.review_gate.get("status", "N/A")
             
        write_router_log(
            iteration=state.iteration_count,
            from_phase=from_phase,
            to_phase=to_phase,
            choice=user_input,
            gate=gate_status,
            frozen=getattr(state, "artifact_frozen", False),
            reason=result.explanation
        )
        
        # 大阶段跃迁时自动清空历史语境并触发接力自我介绍
        # 避免同部门间距跳转（如 GDD_DISCUSS 到 GDD_COMMIT）重复介绍
        from_prefix = from_phase.split('_')[0]
        to_prefix = to_phase.split('_')[0]
        
        if from_phase != to_phase:
            # 清理旧时代记忆
            if from_prefix != to_prefix or to_phase == "DEV_COACHING":
                state.chat_history = []
                logger.info(f"Memory wiped for phase transition setting up next Context.")
                
                # 检测是否为评审回流场景
                is_backflow = from_phase in ("POST_REVIEW_DECISION", "REVIEW") and to_phase.endswith("_DISCUSS")
                review_context = ""
                if is_backflow and state.review_gate:
                    issues = state.review_gate.get("issues", [])
                    if issues:
                        review_context = "\n\n📋 **评审反馈摘要（需要你本轮重点修正）**：\n"
                        for issue in issues:
                            tgt = issue.get("target", "?")
                            sev = issue.get("severity", "?")
                            summary = issue.get("summary", "")
                            hint = issue.get("fix_hint", "")
                            review_context += f"- [{sev}] ({tgt}) {summary}"
                            if hint:
                                review_context += f" → 建议：{hint}"
                            review_context += "\n"
                
                # 回流时注入已有工件内容作为上下文
                artifact_context = ""
                if is_backflow:
                    from ludens_flow.artifacts import read_artifact
                    if to_phase.startswith("GDD_"):
                        existing = read_artifact("GDD")
                        if existing.strip():
                            artifact_context = f"\n\n📄 **当前 GDD 版本内容**：\n{existing}"
                    elif to_phase.startswith("PM_"):
                        existing = read_artifact("PROJECT_PLAN")
                        if existing.strip():
                            artifact_context = f"\n\n📄 **当前 PROJECT_PLAN 版本内容**：\n{existing}"
                    elif to_phase.startswith("ENG_"):
                        existing = read_artifact("IMPLEMENTATION_PLAN")
                        if existing.strip():
                            artifact_context = f"\n\n📄 **当前 IMPLEMENTATION_PLAN 版本内容**：\n{existing}"
                
                # 为新登场的 Agent 强插一条虚拟开场白！
                greeting = ""
                if to_phase.startswith("GDD_"):
                    if is_backflow:
                        greeting = "我是 Dam (丹姆)，评审团 Revs 把你打回来找我了。我已经看过评审意见了，让我们一起把 GDD 打磨得更扎实！"
                    else:
                        greeting = "Hello，我是你的游戏主策划 Dam (丹姆)。很高兴接手这个项目的前期设计工作！你有什么天马行空的想法，直接砸过来吧！"
                elif to_phase.startswith("PM_"):
                    if is_backflow:
                        greeting = "Pax (帕克斯) 重新上线。评审反馈已收到，我们来调整一下排期和计划吧！"
                    else:
                        greeting = "你好！我是项目经理 Pax (帕克斯)。Dam 已经把需求同步过来了，我看过觉得很有意思。接下来我们来抓一抓排期和落地计划吧！"
                elif to_phase.startswith("ENG_") or to_phase == "DEV_COACHING":
                    if is_backflow:
                        greeting = "Eon (伊恩) 回来了。评审的技术问题我看到了，这次咱们把架构地基夯实！"
                    else:
                        greeting = "嗨！我是主程 Eon (伊恩)。前面的大饼我都看到了（笑）。接下来的技术选型和架构地基交给我，保证给你码踏实了。"
                elif to_phase == "REVIEW":
                    greeting = "各位好。我是终审节点 Revs (雷夫斯)。我这里的标准极其严格，不留情面，准备好接受全方位的查水表吧。"
                
                # 拼接完整的开场消息
                full_greeting = greeting + review_context + artifact_context
                    
                if full_greeting.strip():
                    state.last_assistant_message = full_greeting
                    state.chat_history.append({"role": "assistant", "content": full_greeting})

        state.phase = to_phase
        save_state(state)
        
        logger.info(f"[RouterNode] Transition: {from_phase} -> {to_phase}. Reason: {result.explanation}")
        return to_phase


class GDDNode:
    def execute(self, state: LudensState, user_input: str) -> LudensState:
        mode = "COMMIT" if state.phase == Phase.GDD_COMMIT.value else "DISCUSS"
        return run_agent_step(_gdd_agent, mode, state, user_input)

class PMNode:
    def execute(self, state: LudensState, user_input: str) -> LudensState:
        mode = "COMMIT" if state.phase == Phase.PM_COMMIT.value else "DISCUSS"
        return run_agent_step(_pm_agent, mode, state, user_input)

class ENGNode:
    def execute(self, state: LudensState, user_input: str) -> LudensState:
        # 三路完全解耦：不同阶段导向不同接口
        if state.phase == Phase.DEV_COACHING.value:
            mode = "COACH"
        elif state.phase == Phase.ENG_COMMIT.value:
            mode = "PLAN_COMMIT"
        else:
            mode = "PLAN_DISCUSS"
        return run_agent_step(_eng_agent, mode, state, user_input)

class REVIEWNode:
    def execute(self, state: LudensState, user_input: str) -> LudensState:
        # ReviewAgent 通常一锤定音发出 COMMIT
        return run_agent_step(_review_agent, "COMMIT", state, user_input)


# 全局节点表映射机制
PHASE_NODE_MAP = {
    Phase.GDD_DISCUSS.value: GDDNode(),
    Phase.GDD_COMMIT.value: GDDNode(),
    Phase.PM_DISCUSS.value: PMNode(),
    Phase.PM_COMMIT.value: PMNode(),
    Phase.ENG_DISCUSS.value: ENGNode(),
    Phase.ENG_COMMIT.value: ENGNode(),
    Phase.DEV_COACHING.value: ENGNode(),
    Phase.REVIEW.value: REVIEWNode()
}

def graph_step(state: LudensState, user_input: str) -> LudensState:
    """
    单次大循环入口：
    由 Router 找门 -> 如果是需裁判节点直接弹开 -> 如果有对应的 Agent Node，则入内执行并返回
    """
    old_phase = state.phase
    
    # 1. 向调度器请求下一个状态
    router_node = RouterNode()
    router_node.execute(state, user_input)
    
    new_phase = state.phase
    
    print(f"\n[DEBUG] Graph Step - Router Output Phase: {new_phase}")
    
    # 若扭转后是用户打断人工选择节点（ POST_REVIEW_DECISION），则不进入任何 Agent 去无头调用。
    if new_phase == Phase.POST_REVIEW_DECISION.value:
         logger.info("Graph Paused at POST_REVIEW_DECISION for User selection.")
         return state
         
    # 若存在跨 Agent 的流转，系统已注入新角色的寒暄 (last_assistant_message), 直接暂停挂起引擎将舞台交还给终端
    old_prefix = old_phase.split('_')[0] if old_phase else ""
    new_prefix = new_phase.split('_')[0]
    
    if old_phase != new_phase and (old_prefix != new_prefix or new_phase == "DEV_COACHING"):
        # POSt_REVIEW_DECISION → DEV_COACHING 不需要暂停发送 Greeting，因为用户已经在决策界面，
        # 无需再介绍 Eon，直接进入 DEV_COACHING 执行第一轮 coach 即可
        is_post_review_to_dev = (old_phase == Phase.POST_REVIEW_DECISION.value and new_phase == Phase.DEV_COACHING.value)
        if not is_post_review_to_dev:
            logger.info(f"Cross-Agent transition detected ({old_phase} -> {new_phase}). Suspending graph to emit greeting.")
            return state

         
    # 2. 将路由指向具体的 Agent Node 交班
    active_node = PHASE_NODE_MAP.get(new_phase)
    print(f"[DEBUG] Graph Step - Active Node mapped: {active_node}")
    if active_node:
        state = active_node.execute(state, user_input)
    else:
        logger.warning(f"Unhandled phase in Graph: {new_phase}")
        
    return state
