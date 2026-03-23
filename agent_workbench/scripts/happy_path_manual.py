"""
happy_path_manual.py — 全链路 Happy Path 手工集成脚本（可选真实 LLM）

用法：
  python agent_workbench/scripts/happy_path_manual.py
  python agent_workbench/scripts/happy_path_manual.py --skip-llm
"""
import sys
from pathlib import Path
import argparse

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

import os
import tempfile
os.chdir(_ROOT)
os.environ.setdefault(
    "LUDENS_WORKSPACE_DIR",
    str((Path(tempfile.gettempdir()) / "ludens_flow_tests" / "happy_path_manual").resolve()),
)

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--skip-llm", action="store_true", help="强制使用 Mock，跳过真实 LLM 调用")
args, _ = parser.parse_known_args()

from dotenv import load_dotenv
load_dotenv(_ROOT.parent / ".env")

_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("MOONSHOT_API_KEY") or os.getenv("LLM_API_KEY")
USE_MOCK = args.skip_llm or not bool(_api_key)

if USE_MOCK:
    print("⚠ 未检测到 API Key 或使用了 --skip-llm，将使用 Mock 模式运行。\n")
else:
    print("✓ 检测到 API Key，使用真实 LLM 模式运行。\n")

from ludens_flow.agents.base import AgentResult, CommitSpec
from ludens_flow.agents.design_agent import DesignAgent
from ludens_flow.agents.pm_agent import PMAgent
from ludens_flow.agents.engineering_agent import EngineeringAgent
from ludens_flow.agents.review_agent import ReviewAgent

if USE_MOCK:
    def _mock_gdd_discuss(self, state, user_input, cfg=None):
        return AgentResult(assistant_message="[Mock Dam] 好主意！做 Roguelike 战斗。", state_updates={})

    def _mock_gdd_commit(self, state, user_input, cfg=None):
        return AgentResult(
            assistant_message="GDD 定稿。",
            state_updates={},
            commit=CommitSpec(
                artifact_name="GDD",
                content="# GDD\n## 核心循环\n进房→战斗→掉落→下层\n## MVP\n移动/攻击/掉落",
                reason="mock",
            ),
            events=["GDD_COMMITTED"],
        )

    def _mock_pm_discuss(self, state, user_input, cfg=None):
        return AgentResult(assistant_message="[Mock Pax] 三周 M0/M1。", state_updates={})

    def _mock_pm_commit(self, state, user_input, cfg=None):
        return AgentResult(
            assistant_message="PM 定稿。",
            state_updates={},
            commit=CommitSpec(
                artifact_name="PROJECT_PLAN",
                content="# PROJECT_PLAN\n## M0\nPlay Mode 可跑通主循环",
                reason="mock",
            ),
            events=["PM_COMMITTED"],
        )

    def _mock_eng_discuss(self, state, user_input, cfg=None):
        return AgentResult(assistant_message="[Mock Eon] Preset A。", state_updates={"style_preset": "A"})

    def _mock_eng_commit(self, state, user_input, cfg=None):
        return AgentResult(
            assistant_message="ENG 定稿。",
            state_updates={},
            commit=CommitSpec(
                artifact_name="IMPLEMENTATION_PLAN",
                content="# IMPL\nPlayerController.cs (CharacterController)",
                reason="mock",
            ),
            events=["ENG_COMMITTED"],
        )

    def _mock_eng_coach(self, state, user_input, cfg=None):
        return AgentResult(assistant_message="[Mock Eon Coach] 这是思路……", state_updates={})

    def _mock_review_commit(self, state, user_input, cfg=None):
        return AgentResult(
            assistant_message="",
            state_updates={
                "review_gate": {"status": "PASS", "targets": [], "scores": {"design": 9, "engineering": 8}, "issues": []}
            },
            commit=CommitSpec(artifact_name="REVIEW_REPORT", content="# REVIEW\nPASS", reason="mock"),
            events=["REVIEW_DONE"],
        )

    DesignAgent.discuss = _mock_gdd_discuss
    DesignAgent.commit = _mock_gdd_commit
    PMAgent.discuss = _mock_pm_discuss
    PMAgent.commit = _mock_pm_commit
    EngineeringAgent.plan_discuss = _mock_eng_discuss
    EngineeringAgent.plan_commit = _mock_eng_commit
    EngineeringAgent.coach = _mock_eng_coach
    ReviewAgent.commit = _mock_review_commit

import ludens_flow.state as st
from ludens_flow.artifacts import write_artifact
from ludens_flow.graph import graph_step
from ludens_flow.router import Phase


def go(state, user_input: str, label: str = ""):
    prev = state.phase
    state = graph_step(state, user_input)
    print(f"  [{label:22s}] {prev} -> {state.phase}")
    return state


def assert_reply_quality(state, keyword: str, phase_name: str):
    if USE_MOCK:
        return
    msg = state.last_assistant_message or ""
    assert len(msg) > 20, f"[{phase_name}] LLM 回复过短（{len(msg)} 字），可能调用失败"
    assert keyword in msg or len(msg) > 100, f"[{phase_name}] 回复未包含期待关键词 '{keyword}'，内容：{msg[:120]}…"


def run_happy_path():
    mode_label = "Mock 模式" if USE_MOCK else "真实 LLM 模式"
    print("=" * 56)
    print(f"  Happy Path — {mode_label}")
    print("=" * 56)

    st.get_state_file().unlink(missing_ok=True)
    st.init_workspace()
    state = st.load_state()
    assert state.phase == Phase.GDD_DISCUSS.value

    print("\n[Phase 1] GDD 策划")
    state = go(state, "我想做一个类 Roguelike 的 Unity 游戏，2D 战斗为核心", "discuss")
    assert state.phase == Phase.GDD_DISCUSS.value
    assert_reply_quality(state, "Unity", "GDD_DISCUSS")

    state = go(state, "定稿", "commit trigger")
    state = go(state, "", "agent execute")
    state = go(state, "", "cross-agent greet")
    assert state.phase == Phase.PM_DISCUSS.value

    print("\n[Phase 2] PM 规划")
    state = go(state, "我一个人开发，目标两周完成 Game Jam 版本", "discuss")
    assert state.phase == Phase.PM_DISCUSS.value
    assert_reply_quality(state, "Milestone", "PM_DISCUSS")

    state = go(state, "定稿", "commit trigger")
    state = go(state, "", "agent execute")
    state = go(state, "", "cross-agent greet")
    assert state.phase == Phase.ENG_DISCUSS.value

    print("\n[Phase 3] 工程架构")
    state = go(state, "Preset A", "discuss")
    assert state.phase == Phase.ENG_DISCUSS.value
    assert_reply_quality(state, "MonoBehaviour", "ENG_DISCUSS")

    state = go(state, "定稿", "commit trigger")
    state = go(state, "", "ENG 自动执行")
    state = go(state, "", "ENG→REVIEW")
    assert state.phase == Phase.REVIEW.value

    print("\n[Phase 4] 自动评审")
    state = go(state, "", "REVIEW→POST transition")
    assert state.phase == Phase.POST_REVIEW_DECISION.value
    assert state.review_gate is not None

    print("\n[Phase 5] 用户决策")
    state = go(state, "c", "option C → DEV_COACHING")
    assert state.phase == Phase.DEV_COACHING.value
    assert getattr(state, "artifact_frozen", False) is True

    print("\n[Phase 6] 冻结期写入保护")
    try:
        write_artifact("GDD", "hack", reason="test", actor="DesignAgent", state=state)
        raise AssertionError("冻结期写入应被拦截")
    except PermissionError:
        print("  ✓ 冻结期写入被正常拦截")

    print("\n" + "=" * 56)
    print(f"  ✅ Happy Path ({mode_label}) 全部通过！")
    print("=" * 56 + "\n")


if __name__ == "__main__":
    run_happy_path()
