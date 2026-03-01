import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

import logging
import os
os.chdir(_ROOT)

import ludens_flow.state as st
from ludens_flow.graph import graph_step, run_agent_step
from ludens_flow.agents.base import BaseAgent, AgentResult, CommitSpec
from ludens_flow.router import Phase

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# --- Mock 机制：直接接管 Agent 的具体 discuss/commit 方法 ---
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

    # 强制清理（绝对路径）
    state_file = _ROOT / "workspace" / "state.json"
    if state_file.exists():
        state_file.unlink()

    st.WORKSPACE_DIR = _ROOT / "workspace"
    st.init_workspace()
    state = st.load_state()

    assert state.phase == Phase.GDD_DISCUSS.value, f"Init should be GDD_DISCUSS, got {state.phase}"

    logger.info("[1] Graph: GDD 节点推演")
    state = graph_step(state, "我要做一个类似杀戮尖塔的游戏")
    state = graph_step(state, "2 定稿生成")
    state = graph_step(state, "")
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
    # step4a: router 在 REVIEW 阶段停留，REVIEWNode.commit 执行，设置 last_event=REVIEW_DONE
    state = graph_step(state, "")
    # step4b: router 消耗 last_event=REVIEW_DONE，转至 POST_REVIEW_DECISION（跨 Agent 暂停发问候语）
    state = graph_step(state, "")
    assert state.phase == Phase.POST_REVIEW_DECISION.value, f"Router Failed, got {state.phase}"
    
    logger.info("[5] Graph: POST_REVIEW_DECISION => 用户选 C 进入 DEV_COACHING")
    # POST_REVIEW_DECISION → DEV_COACHING 跳过暂停（已在 graph.py 中豁免），直接执行 coach
    state = graph_step(state, "c")
    assert state.phase == Phase.DEV_COACHING.value, f"Router Failed, got {state.phase}"
    assert "status" in state.review_gate, "Review Gate result missing"
    assert getattr(state, "artifact_frozen", False) == True, "Artifact Should be frozen"
    
    logger.info("\n✅ [测试 1 通过] 端到端图循环一站到底成功！")



def test_step5_graph_frozen_guard():
    """ 验收场景 2: POST_REVIEW 选 C 后的冰封期防御测试 """
    logger.info("\n--- 启动冰封守护测试 ---")
    st.WORKSPACE_DIR = _ROOT / "workspace"
    state = st.load_state()
    
    state.phase = Phase.DEV_COACHING.value
    state.artifact_frozen = True
    
    agent_mock = EngineeringAgent()
    
    try:
        state = run_agent_step(agent_mock, "PLAN_COMMIT", state, "恶意覆盖主项目 commit")
        
        assert state.last_error is not None, "Frozen Guard failed to report error msg!"
        assert "Cannot commit canonical artifact" in state.last_error, f"Unexpected error: {state.last_error}"
        logger.info("\n✅ [测试 2 通过] Write_artifact 中的结冰防护（ artifact_frozen=True ）生效并反馈给 Router！")
    except Exception as e:
        logger.error(f"Test crash during frozen guard: {e}")
        raise

if __name__ == "__main__":
    test_step5_graph_e2e()
    test_step5_graph_frozen_guard()
