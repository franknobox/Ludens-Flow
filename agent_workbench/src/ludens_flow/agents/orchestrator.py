import logging
from typing import Tuple, Optional, Any

from ludens_flow.state import LudensState, save_state
from ludens_flow.router import route, Phase
from ludens_flow.artifacts import write_artifact
from llm.provider import LLMConfig

from ludens_flow.agents.design_agent import DesignAgent
from ludens_flow.agents.pm_agent import PMAgent
from ludens_flow.agents.engineering_agent import EngineeringAgent
from ludens_flow.agents.review_agent import ReviewAgent

from ludens_flow.state import LudensState, save_state, LOGS_DIR

logger = logging.getLogger(__name__)

TRACE_LOG_FILE = LOGS_DIR / "trace.log"

def _append_trace(event_type: str, state: LudensState, commit_spec: Optional[Any] = None):
    # event_type: "ENTER" or "LEAVE"
    now_iso = __import__('datetime').datetime.utcnow().isoformat() + "Z"
    phase = state.phase or "NONE"
    last_event = state.last_event or "NONE"
    frozen = getattr(state, "artifact_frozen", False)
    has_commit = "YES" if commit_spec else "NO"
    
    line = f"[{now_iso}] {event_type:<5} | Phase: {phase:<20} | Last Event: {last_event:<15} | Frozen: {frozen:<5} | Commit: {has_commit}\n"
    with open(TRACE_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)

# 全局单例的实例化 Agent 集合
_agents = {
    "Design": DesignAgent(),
    "PM": PMAgent(),
    "Eng": EngineeringAgent(),
    "Review": ReviewAgent()
}

def execute_step(state: LudensState, user_input: str, cfg: Optional[LLMConfig] = None) -> Tuple[str, LudensState]:
    """
    Step 4.5 Orchestrator 核心接线管线:
    执行单次交互步进，调用相应 Agent 节点 -> 落盘 Artifacts -> 发送给 Router 判断后续相位。
    
    返回 (assistant_message, state)
    """
    phase = state.phase or Phase.GDD_DISCUSS.value
    _append_trace("ENTER", state)
    
    assistant_message = ""
    agent_result = None
    actor_name = "System"
    
    # --- 1. 定位并调用具体 Agent 节点 ---
    try:
        if phase == Phase.GDD_DISCUSS.value:
            actor_name = _agents["Design"].name
            agent_result = _agents["Design"].discuss(state, user_input, cfg)
        elif phase == Phase.GDD_COMMIT.value:
            actor_name = _agents["Design"].name
            agent_result = _agents["Design"].commit(state, user_input, cfg)
            
        elif phase == Phase.PM_DISCUSS.value:
            actor_name = _agents["PM"].name
            agent_result = _agents["PM"].discuss(state, user_input, cfg)
        elif phase == Phase.PM_COMMIT.value:
            actor_name = _agents["PM"].name
            agent_result = _agents["PM"].commit(state, user_input, cfg)
            
        elif phase == Phase.ENG_DISCUSS.value:
            actor_name = _agents["Eng"].name
            agent_result = _agents["Eng"].discuss(state, user_input, cfg)
        elif phase == Phase.ENG_COMMIT.value:
            actor_name = _agents["Eng"].name
            agent_result = _agents["Eng"].commit(state, user_input, cfg)
            
        elif phase == Phase.REVIEW.value:
            actor_name = _agents["Review"].name
            agent_result = _agents["Review"].commit(state, user_input, cfg)
            
        elif phase == Phase.DEV_COACHING.value:
            actor_name = _agents["Eng"].name
            agent_result = _agents["Eng"].discuss(state, user_input, cfg)
            
        elif phase == Phase.POST_REVIEW_DECISION.value:
            # 这是一个纯由 Router 接管的空节点，Agent 不做事实回复
            assistant_message = "系统已接收决策指令，流转中..."
            
    except Exception as e:
        logger.error(f"Agent execution failed in phase {phase}: {e}")
        return f"Agent {actor_name} 节点执行发生异常: {e}", state

    # --- 2. 状态增量合并与写文件接防机制 ---
    last_event = None
    
    if agent_result:
        assistant_message = agent_result.assistant_message
        
        # Merge state updates 字典合入深层拷贝 （如 drafts）
        for dict_key, value in agent_result.state_updates.items():
            if isinstance(value, dict) and hasattr(state, dict_key) and isinstance(getattr(state, dict_key), dict):
                getattr(state, dict_key).update(value)
            else:
                setattr(state, dict_key, value)
        
        # 拦截凭条执行 Artifacts 落盘动作
        commit_spec = agent_result.commit
        if commit_spec:
            logger.info(f"[{actor_name}] is writing artifact: {commit_spec.artifact_name}")
            # 统一由 Artifacts 模块写盘，并校验权限 (若遇 frozen 会抛出 PermissionError)
            write_artifact(
                name=commit_spec.artifact_name,
                content=commit_spec.content,
                reason=commit_spec.reason,
                actor=actor_name,
                state=state
            )
            
            # 在没有被覆写 event 时，追加系统保底事件钩子
            if not agent_result.events:
                last_event = f"{commit_spec.artifact_name}_COMMITTED"
        
        # 事件提取与广播给系统状态
        # (重要: Router 将依赖 state.last_event 判定跳转，必须确保下发)
        if agent_result.events:
            last_event = agent_result.events[-1] 
            
        state.last_event = last_event
            
    # --- 3. 让 Router 决定下一步方向并存储全阶段 ---
    if phase != Phase.POST_REVIEW_DECISION.value and not agent_result:
         # Agent 没匹配上，保持等待原位
         pass
    else:
         # 将用户的回答传递给路由，由路由引擎接管后续方向
         next_phase, explanation, route_updates = route(state, user_input, last_event=last_event)
         for dict_key, dict_value in route_updates.items():
             setattr(state, dict_key, dict_value)
             
         if next_phase != phase:
             assistant_message += f"\n\n**(系统动作: {explanation})**"
             
    # --- 4. 固化持久化最新时刻 ---
    save_state(state)
    _append_trace("LEAVE", state, agent_result.commit if agent_result else None)
    return assistant_message, state
