import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

import logging
import os
import tempfile
os.chdir(_ROOT)
os.environ.setdefault(
    "LUDENS_WORKSPACE_DIR",
    str((Path(tempfile.gettempdir()) / "ludens_flow_tests" / "test_router_v2").resolve()),
)

from ludens_flow.state import init_state
from ludens_flow.router import route, Phase

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def test_routes_v2():
    state = init_state()
    
    logger.info("--- 测试 3.2 默认路由跳转 ---")
    state.phase = Phase.GDD_COMMIT.value
    p, e, u = route(state, "", last_event="GDD_COMMITTED")
    assert p == Phase.PM_DISCUSS.value, f"Expected PM_DISCUSS, got {p}"
    
    state.phase = Phase.PM_COMMIT.value
    p, e, u = route(state, "", last_event="PM_COMMITTED")
    assert p == Phase.ENG_DISCUSS.value, f"Expected ENG_DISCUSS, got {p}"

    logger.info("--- 测试 3.3.1 ReviewGate A回流 (全量) ---")
    state.phase = Phase.POST_REVIEW_DECISION.value
    state.review_gate = {
        "status": "REQUEST_CHANGES",
        "targets": ["ENG"],
        "issues": [{"target": "ENG", "severity": "MINOR", "desc": "Optimize loop"}]
    }
    # 使用单字母 "a" 触发 opt_a
    p, e, u = route(state, "a")
    assert p == Phase.ENG_DISCUSS.value, f"Expected ENG_DISCUSS, got {p}"
    
    logger.info("--- 测试 3.3.2 ReviewGate B回流 (过滤 MAJOR/BLOCK) ---")
    # 只有 MINOR -> B 选项直接放行到 DEV_COACHING
    state.phase = Phase.POST_REVIEW_DECISION.value
    state.review_gate["issues"] = [{"target": "ENG", "severity": "MINOR"}]
    p, e, u = route(state, "b")
    assert p == Phase.DEV_COACHING.value, f"Expected DEV_COACHING, got {p}"
    
    # 有 MAJOR -> 应该回到靶向源头 PM
    state.phase = Phase.POST_REVIEW_DECISION.value
    state.review_gate["issues"] = [
        {"target": "ENG", "severity": "MINOR"},
        {"target": "PM", "severity": "MAJOR"}
    ]
    p, e, u = route(state, "b")
    assert p == Phase.PM_DISCUSS.value, f"Expected PM_DISCUSS, got {p}"

    logger.info("--- 测试 3.4 冻结拦截与跳脱 ---")
    state.phase = Phase.DEV_COACHING.value
    state.artifact_frozen = True
    # 普通输入被拦截，保持在 DEV_COACHING
    p, e, u = route(state, "定稿")
    assert p == Phase.DEV_COACHING.value, f"Expected DEV_COACHING, got {p}"
    # 解冻关键词触发解冻
    p, e, u = route(state, "解冻")
    assert p == Phase.ENG_DISCUSS.value, f"Expected ENG_DISCUSS, got {p}"
    assert u.get("artifact_frozen") is False
    
    logger.info("--- 测试 死循环拦截 ---")
    state.iteration_count = 10
    state.phase = Phase.GDD_DISCUSS.value
    p, e, u = route(state, "随便")
    assert p == Phase.DEV_COACHING.value, f"Expected DEV_COACHING (iter limit), got {p}"
    assert u.get("artifact_frozen") is True
    
    logger.info("✅ 测试通过: v2 拦截、默认跳转及 ReviewGate 靶向回流均符合预期")

if __name__ == "__main__":
    test_routes_v2()
