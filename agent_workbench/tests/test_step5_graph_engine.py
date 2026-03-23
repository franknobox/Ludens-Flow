import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)
os.environ.setdefault(
    "LUDENS_WORKSPACE_DIR",
    str((Path(tempfile.gettempdir()) / "ludens_flow_tests" / "test_step5_graph_engine").resolve()),
)

import ludens_flow.state as st
from ludens_flow.agents.base import AgentResult, CommitSpec
from ludens_flow.agents.design_agent import DesignAgent
from ludens_flow.agents.engineering_agent import EngineeringAgent
from ludens_flow.agents.pm_agent import PMAgent
from ludens_flow.agents.review_agent import ReviewAgent
from ludens_flow.graph import graph_step, run_agent_step
from ludens_flow.router import Phase

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def mock_design_discuss(self, state, user_input, cfg=None):
    return AgentResult(assistant_message="GDD Discuss Mock", state_updates={"drafts": {"gdd": {"core_loop": "kill-loot"}}})


def mock_design_commit(self, state, user_input, cfg=None):
    return AgentResult(
        assistant_message="",
        commit=CommitSpec(artifact_name="GDD", content="GDD Commit Mock!\n", reason="Test"),
        state_updates={},
    )


def mock_pm_discuss(self, state, user_input, cfg=None):
    return AgentResult(assistant_message="PM Discuss Mock", state_updates={"drafts": {"pm": {"team_size": 3}}})


def mock_pm_commit(self, state, user_input, cfg=None):
    return AgentResult(
        assistant_message="",
        commit=CommitSpec(artifact_name="PROJECT_PLAN", content="PM Commit Mock!\n", reason="Test"),
        state_updates={},
    )


def mock_eng_discuss(self, state, user_input, cfg=None):
    return AgentResult(assistant_message="Eng Discuss Mock", state_updates={"style_preset": "OOP"})


def mock_eng_commit(self, state, user_input, cfg=None):
    return AgentResult(
        assistant_message="",
        commit=CommitSpec(artifact_name="IMPLEMENTATION_PLAN", content="Eng Commit Mock!\n", reason="Test"),
        state_updates={},
    )


def mock_eng_coach(self, state, user_input, cfg=None):
    return AgentResult(assistant_message="Coach Mode Mocked Instruction", state_updates={})


def mock_review_commit(self, state, user_input, cfg=None):
    return AgentResult(
        assistant_message="",
        commit=CommitSpec(artifact_name="REVIEW_REPORT", content="Review Commit Mock\n", reason="Test"),
        state_updates={"review_gate": {"status": "PASS", "targets": [], "score": 95, "issues": []}},
    )


class Step5GraphEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._originals = {
            "design_discuss": DesignAgent.discuss,
            "design_commit": DesignAgent.commit,
            "pm_discuss": PMAgent.discuss,
            "pm_commit": PMAgent.commit,
            "eng_plan_discuss": EngineeringAgent.plan_discuss,
            "eng_plan_commit": EngineeringAgent.plan_commit,
            "eng_coach": EngineeringAgent.coach,
            "review_commit": ReviewAgent.commit,
        }

        DesignAgent.discuss = mock_design_discuss
        DesignAgent.commit = mock_design_commit
        PMAgent.discuss = mock_pm_discuss
        PMAgent.commit = mock_pm_commit
        EngineeringAgent.plan_discuss = mock_eng_discuss
        EngineeringAgent.plan_commit = mock_eng_commit
        EngineeringAgent.coach = mock_eng_coach
        ReviewAgent.commit = mock_review_commit

    @classmethod
    def tearDownClass(cls):
        DesignAgent.discuss = cls._originals["design_discuss"]
        DesignAgent.commit = cls._originals["design_commit"]
        PMAgent.discuss = cls._originals["pm_discuss"]
        PMAgent.commit = cls._originals["pm_commit"]
        EngineeringAgent.plan_discuss = cls._originals["eng_plan_discuss"]
        EngineeringAgent.plan_commit = cls._originals["eng_plan_commit"]
        EngineeringAgent.coach = cls._originals["eng_coach"]
        ReviewAgent.commit = cls._originals["review_commit"]

    def setUp(self):
        state_file = st.get_state_file()
        state_file.unlink(missing_ok=True)
        st.init_workspace()

    def test_step5_graph_e2e(self):
        logger.info("==========================================")
        logger.info("   Ludens Flow - Step5 Graph Acceptance   ")
        logger.info("==========================================\n")

        state = st.load_state()
        self.assertEqual(state.phase, Phase.GDD_DISCUSS.value)

        logger.info("[1] Graph: GDD 节点推演")
        state = graph_step(state, "我要做一个类似杀戮尖塔的游戏")
        state = graph_step(state, "2 定稿生成")
        state = graph_step(state, "")
        self.assertEqual(state.phase, Phase.PM_DISCUSS.value)

        logger.info("[2] Graph: PM 节点推演")
        state = graph_step(state, "3个人，开发2周")
        state = graph_step(state, "2 定稿生成")
        state = graph_step(state, "")
        self.assertEqual(state.phase, Phase.ENG_DISCUSS.value)

        logger.info("[3] Graph: ENG 节点推演")
        state = graph_step(state, "用 Unity 和 MVC")
        state = graph_step(state, "2 定稿并生成")
        state = graph_step(state, "")
        self.assertEqual(state.phase, Phase.REVIEW.value)

        logger.info("[4] Graph: REVIEW 全自动裁决节点")
        state = graph_step(state, "")
        state = graph_step(state, "")
        self.assertEqual(state.phase, Phase.DEV_COACHING.value)

        logger.info("[5] Graph: POST_REVIEW_DECISION => 用户选 C 进入 DEV_COACHING")
        state = graph_step(state, "c")
        self.assertEqual(state.phase, Phase.DEV_COACHING.value)
        self.assertIn("status", state.review_gate)
        self.assertTrue(getattr(state, "artifact_frozen", False))

        logger.info("\n✅ [测试 1 通过] 端到端图循环一站到底成功！")

    def test_step5_graph_frozen_guard(self):
        logger.info("\n--- 启动冰封守护测试 ---")
        state = st.load_state()
        state.phase = Phase.DEV_COACHING.value
        state.artifact_frozen = True

        agent_mock = EngineeringAgent()
        state = run_agent_step(agent_mock, "PLAN_COMMIT", state, "恶意覆盖主项目 commit")

        self.assertIsNotNone(state.last_error)
        self.assertIn("Cannot commit canonical artifact", state.last_error)
        logger.info("\n✅ [测试 2 通过] Write_artifact 中的结冰防护（ artifact_frozen=True ）生效并反馈给 Router！")


if __name__ == "__main__":
    unittest.main()
