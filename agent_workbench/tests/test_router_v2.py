import sys
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

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
        "issues": [
            {"target": "ENG", "severity": "MINOR", "desc": "Optimize loop"}
        ]
    }
    p, e, u = route(state, "A - 按建议修改")
    assert p == Phase.ENG_DISCUSS.value, f"Expected ENG_DISCUSS, got {p}"
    
    logger.info("--- 测试 3.3.2 ReviewGate B回流 (过滤 MAJOR/BLOCK) ---")
    # 如果只有MINOR，B选项直接放行
    p, e, u = route(state, "B - 只改重点")
    assert p == Phase.DEV_COACHING.value, f"Expected DEV_COACHING, got {p}"
    
    # 修改 issues 包含 MAJOR -> 应该回到靶向源头 PM (测试优先级 GDD>PM>ENG)
    state.review_gate["issues"] = [
        {"target": "ENG", "severity": "MINOR"},
        {"target": "PM", "severity": "MAJOR"}
    ]
    p, e, u = route(state, "B")
    assert p == Phase.PM_DISCUSS.value, f"Expected PM_DISCUSS, got {p}"

    logger.info("--- 测试 3.4 冻结拦截与跳脱 ---")
    state.phase = Phase.DEV_COACHING.value
    p, e, u = route(state, "我要定稿")
    # 冻结期间提交被无视
    assert p == Phase.DEV_COACHING.value
    # 申请解冻
    p, e, u = route(state, "好的，解冻工件吧")
    assert p == Phase.ENG_DISCUSS.value
    assert u.get("artifact_frozen") is False
    
    logger.info("--- 测试 死循环拦截 ---")
    state.iteration_count = 10
    state.phase = Phase.GDD_DISCUSS.value
    p, e, u = route(state, "随便说点啥")
    assert p == Phase.DEV_COACHING.value
    assert u.get("artifact_frozen") is True
    
    logger.info("✅ 测试通过: v2 拦截、默认跳转及 ReviewGate 靶向回流均符合预期")

if __name__ == "__main__":
    test_routes_v2()
