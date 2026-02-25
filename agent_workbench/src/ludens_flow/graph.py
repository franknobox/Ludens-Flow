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
                
                logger.error(f">>>>> WRITE ARTIFACT CRITICAL GUARD <<<<<")
                logger.error(f"Type of content: {type(result.commit.content)}")
                logger.error(f"Val of content: {repr(result.commit.content)}")

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
    # 1. 向调度器请求下一个状态
    router_node = RouterNode()
    router_node.execute(state, user_input)
    
    print(f"\n[DEBUG] Graph Step - Router Output Phase: {state.phase}")
    
    # 若扭转后是用户打断人工选择节点（ POST_REVIEW_DECISION），则不进入任何 Agent 去无头调用。
    if state.phase == Phase.POST_REVIEW_DECISION.value:
         logger.info("Graph Paused at POST_REVIEW_DECISION for User selection.")
         return state
         
    # 2. 将路由指向具体的 Agent Node 交班
    active_node = PHASE_NODE_MAP.get(state.phase)
    print(f"[DEBUG] Graph Step - Active Node mapped: {active_node}")
    if active_node:
        state = active_node.execute(state, user_input)
    else:
        logger.warning(f"Unhandled phase in Graph: {state.phase}")
        
    return state
