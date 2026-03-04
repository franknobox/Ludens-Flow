"""
test_happy_path.py — 全链路 Happy Path 集成测试（真实 LLM）

用法：
  python tests/test_happy_path.py              # 使用项目根目录的 .env
  python tests/test_happy_path.py --skip-llm  # 跳过 LLM 调用，用 Mock 快速验证流程

行为：
  - 自动加载 .env 中的 LLM 配置（OPENAI_API_KEY 或 MOONSHOT_API_KEY）
  - 若未找到有效的 API Key，自动降级为 Mock 模式并提示
  - 真实 LLM 模式下验证：每个阶段的 Agent 回复是否包含实质内容
  - 两种模式都验证：状态机流转、工件写入、DEV_COACHING 冻结保护
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
    str((Path(tempfile.gettempdir()) / "ludens_flow_tests" / "test_happy_path").resolve()),
)

# ── 解析参数 ──────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--skip-llm", action="store_true", help="强制使用 Mock，跳过真实 LLM 调用")
args, _ = parser.parse_known_args()

# ── 检测 LLM 配置 ─────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(_ROOT.parent / ".env")

_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("MOONSHOT_API_KEY") or os.getenv("LLM_API_KEY")
USE_MOCK = args.skip_llm or not bool(_api_key)

if USE_MOCK:
    print("⚠  未检测到 API Key 或使用了 --skip-llm，将使用 Mock 模式运行。")
    print("   如需真实 LLM 测试，请在项目根目录 .env 中配置 OPENAI_API_KEY。\n")
else:
    print(f"✓  检测到 API Key，使用真实 LLM 模式运行。\n")

# ── Mock 定义（仅 Mock 模式时注入）────────────────────────────────────────────
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
            assistant_message="GDD 定稿。", state_updates={},
            commit=CommitSpec(artifact_name="GDD",
                              content="# GDD\n## 核心循环\n进房→战斗→掉落→下层\n## MVP\n移动/攻击/掉落",
                              reason="mock"),
            events=["GDD_COMMITTED"]
        )

    def _mock_pm_discuss(self, state, user_input, cfg=None):
        return AgentResult(assistant_message="[Mock Pax] 三周 M0/M1。", state_updates={})

    def _mock_pm_commit(self, state, user_input, cfg=None):
        return AgentResult(
            assistant_message="PM 定稿。", state_updates={},
            commit=CommitSpec(artifact_name="PROJECT_PLAN",
                              content="# PROJECT_PLAN\n## M0\nPlay Mode 可跑通主循环",
                              reason="mock"),
            events=["PM_COMMITTED"]
        )

    def _mock_eng_discuss(self, state, user_input, cfg=None):
        return AgentResult(assistant_message="[Mock Eon] Preset A。", state_updates={"style_preset": "A"})

    def _mock_eng_commit(self, state, user_input, cfg=None):
        return AgentResult(
            assistant_message="ENG 定稿。", state_updates={},
            commit=CommitSpec(artifact_name="IMPLEMENTATION_PLAN",
                              content="# IMPL\nPlayerController.cs (CharacterController)",
                              reason="mock"),
            events=["ENG_COMMITTED"]
        )

    def _mock_eng_coach(self, state, user_input, cfg=None):
        return AgentResult(assistant_message="[Mock Eon Coach] 这是思路……", state_updates={})

    def _mock_review_commit(self, state, user_input, cfg=None):
        return AgentResult(
            assistant_message="", state_updates={
                "review_gate": {"status": "PASS", "targets": [], "scores": {"design": 9, "engineering": 8}, "issues": []}
            },
            commit=CommitSpec(artifact_name="REVIEW_REPORT", content="# REVIEW\nPASS", reason="mock"),
            events=["REVIEW_DONE"]
        )

    DesignAgent.discuss   = _mock_gdd_discuss
    DesignAgent.commit    = _mock_gdd_commit
    PMAgent.discuss       = _mock_pm_discuss
    PMAgent.commit        = _mock_pm_commit
    EngineeringAgent.plan_discuss = _mock_eng_discuss
    EngineeringAgent.plan_commit  = _mock_eng_commit
    EngineeringAgent.coach        = _mock_eng_coach
    ReviewAgent.commit    = _mock_review_commit

# ── 测试主体 ──────────────────────────────────────────────────────────────────
import ludens_flow.state as st
from ludens_flow.graph import graph_step
from ludens_flow.router import Phase


def go(state, user_input: str, label: str = ""):
    prev = state.phase
    state = graph_step(state, user_input)
    print(f"  [{label:22s}] {prev} -> {state.phase}")
    return state


def assert_reply_quality(state, keyword: str, phase_name: str):
    """真实 LLM 模式下验证回复内容不为空且包含关键词"""
    if USE_MOCK:
        return
    msg = state.last_assistant_message or ""
    assert len(msg) > 20, f"[{phase_name}] LLM 回复过短（{len(msg)} 字），可能调用失败"
    assert keyword in msg or len(msg) > 100, (
        f"[{phase_name}] 回复未包含期待关键词 '{keyword}'，内容：{msg[:120]}…"
    )


def run_happy_path():
    mode_label = "Mock 模式" if USE_MOCK else "真实 LLM 模式"
    print("=" * 56)
    print(f"  Happy Path — {mode_label}")
    print("=" * 56)

    # ── 清理并初始化 ──
    st.get_state_file().unlink(missing_ok=True)
    st.init_workspace()
    state = st.load_state()
    assert state.phase == Phase.GDD_DISCUSS.value

    # ── Phase 1: GDD ─────────────────────────────────────────
    print("\n[Phase 1] GDD 策划")
    state = go(state, "我想做一个类 Roguelike 的 Unity 游戏，2D 战斗为核心", "discuss")
    assert state.phase == Phase.GDD_DISCUSS.value
    assert_reply_quality(state, "Unity", "GDD_DISCUSS")

    state = go(state, "定稿",  "commit trigger")
    state = go(state, "",      "agent execute")
    state = go(state, "",      "cross-agent greet")
    assert state.phase == Phase.PM_DISCUSS.value, f"Got {state.phase}"
    assert "gdd" in state.artifacts, "GDD 工件未写入"
    print(f"  ✓ GDD v{state.artifacts['gdd'].version}")

    # ── Phase 2: PM ──────────────────────────────────────────
    print("\n[Phase 2] PM 规划")
    state = go(state, "我一个人开发，目标两周完成 Game Jam 版本", "discuss")
    assert state.phase == Phase.PM_DISCUSS.value
    assert_reply_quality(state, "Milestone", "PM_DISCUSS")

    state = go(state, "定稿", "commit trigger")
    state = go(state, "",     "agent execute")
    state = go(state, "",     "cross-agent greet")
    assert state.phase == Phase.ENG_DISCUSS.value, f"Got {state.phase}"
    assert "pm" in state.artifacts
    print(f"  ✓ PROJECT_PLAN v{state.artifacts['pm'].version}")

    # ── Phase 3: ENG ─────────────────────────────────────────
    print("\n[Phase 3] 工程架构")
    state = go(state, "Preset A", "discuss")
    assert state.phase == Phase.ENG_DISCUSS.value
    assert_reply_quality(state, "MonoBehaviour", "ENG_DISCUSS")

    state = go(state, "定稿", "commit trigger")
    state = go(state, "",     "ENG 自动执行")
    state = go(state, "",     "ENG→REVIEW")       # 识别到 last_event 跨阶段自动过渡
    assert state.phase == Phase.REVIEW.value, f"Got {state.phase}"
    assert "eng" in state.artifacts
    print(f"  ✓ IMPLEMENTATION_PLAN v{state.artifacts['eng'].version}")

    # ── Phase 4: REVIEW ──────────────────────────────────────
    print("\n[Phase 4] 自动评审")
    state = go(state, "",  "REVIEW→POST transition") # 上一步到达REVIEW时已执行完毕，此处仅流转
    assert state.phase == Phase.POST_REVIEW_DECISION.value, f"Got {state.phase}"
    assert "review" in state.artifacts
    assert state.review_gate is not None
    gate_status = state.review_gate.get("status", "?")
    print(f"  ✓ REVIEW_REPORT 写入，裁决：{gate_status}")

    # 真实 LLM 模式下验证 ReviewGate 结构合法
    if not USE_MOCK:
        assert gate_status in ("PASS", "REQUEST_CHANGES", "BLOCK"), f"非法 Gate 状态：{gate_status}"
        scores = state.review_gate.get("scores", {})
        assert "design" in scores or "engineering" in scores, "scores 字段缺失"

    # ── Phase 5: 用户决策 → DEV_COACHING ─────────────────────
    print("\n[Phase 5] 用户决策")
    state = go(state, "c", "option C → DEV_COACHING")
    assert state.phase == Phase.DEV_COACHING.value, f"Got {state.phase}"
    assert getattr(state, "artifact_frozen", False) is True
    print(f"  ✓ 进入 DEV_COACHING，工件已冻结")

    # ── Phase 6: 冻结保护验证 ────────────────────────────────
    print("\n[Phase 6] 冻结期写入保护")
    from ludens_flow.artifacts import write_artifact
    try:
        write_artifact("GDD", "hack", reason="test", actor="DesignAgent", state=state)
        assert False, "冻结期写入应被拦截！"
    except PermissionError:
        print("  ✓ 冻结期写入被正常拦截")

    print("\n" + "=" * 56)
    print(f"  ✅ Happy Path ({mode_label}) 全部通过！")
    print("=" * 56 + "\n")


if __name__ == "__main__":
    run_happy_path()
