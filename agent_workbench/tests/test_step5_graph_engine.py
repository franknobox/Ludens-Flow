import sys
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).resolve().parents[1])) 
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import ludens_flow.state as st
from ludens_flow.graph import graph_step
from ludens_flow.agents.base import BaseAgent
from ludens_flow.router import Phase

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from ludens_flow.agents.base import AgentResult, CommitSpec

# --- Mock 机制：直接接管 Agent 的高层抽象而不是底层 call ---
from ludens_flow.agents.design_agent import DesignAgent
from ludens_flow.agents.pm_agent import PMAgent
from ludens_flow.agents.engineering_agent import EngineeringAgent
from ludens_flow.agents.review_agent import ReviewAgent

def mock_design_discuss(self, state, user_input, cfg=None):
    return AgentResult(assistant_message="GDD Discuss Mock", state_updates={"drafts": {"gdd": {"core_loop": "kill-loot"}}})

def mock_design_commit(self, state, user_input, cfg=None):
    return AgentResult(assistant_message="", commit=CommitSpec(artifact_name="GDD", content="GDD Commit Mock!\n", reason="Test"), state_updates={})

def mock_pm_discuss(self, state, user_input, cfg=None):
    return AgentResult(assistant_message="PM Discuss Mock", state_updates={"drafts": {"pm": {"team_size": 3}}})

def mock_pm_commit(self, state, user_input, cfg=None):
    return AgentResult(assistant_message="", commit=CommitSpec(artifact_name="PROJECT_PLAN", content="PM Commit Mock!\n", reason="Test"), state_updates={})

def mock_eng_discuss(self, state, user_input, cfg=None):
    return AgentResult(assistant_message="Eng Discuss Mock", state_updates={"style_preset": "OOP"})

def mock_eng_commit(self, state, user_input, cfg=None):
    return AgentResult(assistant_message="", commit=CommitSpec(artifact_name="IMPLEMENTATION_PLAN", content="Eng Commit Mock!\n", reason="Test"), state_updates={})

def mock_eng_coach(self, state, user_input, cfg=None):
    return AgentResult(assistant_message="Coach Mode Mocked Instruction", state_updates={})

def mock_review_commit(self, state, user_input, cfg=None):
    return AgentResult(
         assistant_message="",
         commit=CommitSpec(artifact_name="REVIEW_REPORT", content="Review Commit Mock\n", reason="Test"),
         state_updates={"review_gate": {"status": "PASS", "targets": [], "score": 95, "issues": []}}
    )

DesignAgent.discuss = mock_design_discuss
DesignAgent.commit = mock_design_commit
PMAgent.discuss = mock_pm_discuss
PMAgent.commit = mock_pm_commit
EngineeringAgent.plan_discuss = mock_eng_discuss
EngineeringAgent.plan_commit = mock_eng_commit
EngineeringAgent.coach = mock_eng_coach
ReviewAgent.commit = mock_review_commit

def test_step5_graph_e2e():
    """ 验收场景 1: 完美通路端到端 """
    logger.info("==========================================")
    logger.info("   Ludens Flow - Step5 Graph Acceptance   ")
    logger.info("==========================================\n")

    import os
    if os.path.exists("workspace/state.json"):
        os.remove("workspace/state.json")

    st.WORKSPACE_DIR = Path("workspace")
    st.init_workspace()
    state = st.load_state()

    assert state.phase == Phase.GDD_DISCUSS.value, f"Init should be GDD_DISCUSS, got {state.phase}"

    logger.info("[1] Graph: GDD 节点推演")
    state = graph_step(state, "我要做一个类似杀戮尖塔的游戏")
    state = graph_step(state, "2 定稿生成") # Router 推入 GDD_COMMIT，AgentNode 写入并抛出事件
    state = graph_step(state, "") # Router 承接事件自动推入 PM_DISCUSS
    assert state.phase == Phase.PM_DISCUSS.value, f"Router Failed, got {state.phase}"

    logger.info("[2] Graph: PM 节点推演")
    state = graph_step(state, "3个人，开发2周")
    state = graph_step(state, "2 定稿生成") 
    state = graph_step(state, "") 
    assert state.phase == Phase.ENG_DISCUSS.value, f"Router Failed, got {state.phase}"

    logger.info("[3] Graph: ENG 节点推演")
    state = graph_step(state, "用 Unity 和 MVC")
    state = graph_step(state, "2 定稿并生成")
    state = graph_step(state, "") 
    assert state.phase == Phase.REVIEW.value, f"Router Failed, got {state.phase}"

    logger.info("[4] Graph: REVIEW 全自动裁决节点")
    # ReviewAgent 当前设定为一被传唤就直接走 COMMIT (见 graph.py 的 REVIEWNode)
    state = graph_step(state, "") # Router 把阶段锁在 REVIEW，并触发 Agent 打分发事件
    
    logger.info("[5] Graph: POST_REVIEW_DECISION 判定 (内部打分为 PASS 时自动推入 DEV_COACHING)")
    state = graph_step(state, "") # Router 承接打分事件并根据 PASS 直接推入 DEV_COACHING 冻结
    assert state.phase == Phase.DEV_COACHING.value, f"Router Failed, got {state.phase}"
    assert "status" in state.review_gate, "Review Gate result missing"
    assert getattr(state, "artifact_frozen", False) == True, "Artifact Should be frozen"
    
    logger.info("\n✅ [测试 1 通过] 端到端图循环一站到底成功！")


def test_step5_graph_frozen_guard():
    """ 验收场景 2: POST_REVIEW 选 C 后的冰封期防御测试 """
    logger.info("\n--- 启动冰封守护测试 ---")
    st.WORKSPACE_DIR = Path("workspace")
    state = st.load_state()
    
    # 强制将状态转至 DEV_COACHING 且启用冻结
    state.phase = Phase.DEV_COACHING.value
    state.artifact_frozen = True
    
    # 因为 ENGNode 在 DEV_COACHING 只响应 DISCUSS，要强行验证结冰守护
    # 需要绕过 ENGNode 正常的降级保护，直接模拟一次 Agent 强制 commit (比如恶意的返回)
    agent_mock = EngineeringAgent()
    
    try:
        from ludens_flow.graph import run_agent_step
        # 强行下发 COMMIT 命令（在 Graph 业务中已经被 ENGNode 封死在接口层了，此处直接调底层函数突破防波堤）
        state = run_agent_step(agent_mock, "PLAN_COMMIT", state, "恶意覆盖主项目 commit")
        
        # 验证防御机制是否成功拦下并产生了报错记录
        assert state.last_error is not None, "Frozen Guard failed to report error msg!"
        assert "Cannot commit canonical artifact" in state.last_error, f"Unexpected error: {state.last_error}"
        logger.info("\n✅ [测试 2 通过] Write_artifact 中的结冰防护（ artifact_frozen=True ）生效并反馈给 Router！")
    except Exception as e:
        logger.error(f"Test crash during frozen guard: {e}")
        raise

if __name__ == "__main__":
    test_step5_graph_e2e()
    test_step5_graph_frozen_guard()
