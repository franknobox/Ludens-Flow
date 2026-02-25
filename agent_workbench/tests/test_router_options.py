import sys
from pathlib import Path
import logging

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ludens_flow.state import init_state
from ludens_flow.router import route, Phase

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def test_routes():
    state = init_state()
    
    logger.info("--- 测试 Discuss 动作项 ---")
    state.phase = Phase.PM_DISCUSS.value
    # 选项 1：停留
    p, e, _ = route(state, "1 还需要讨论一下预算")
    assert p == Phase.PM_DISCUSS.value
    # 选项 2：前进
    p, e, _ = route(state, "定稿吧")
    assert p == Phase.PM_COMMIT.value
    # 选项 3：回退
    p, e, _ = route(state, "3")
    assert p == Phase.GDD_DISCUSS.value

    logger.info("--- 测试 POST_REVIEW_DECISION 动作项 ---")
    state.phase = Phase.POST_REVIEW_DECISION.value
    p, e, u = route(state, "我选A，按建议修改")
    assert p == Phase.GDD_DISCUSS.value
    assert u.get("iteration_count") == 1
    
    p, e, u = route(state, "直接进入开发")
    assert p == Phase.DEV_COACHING.value
    assert u.get("artifact_frozen") is True

    logger.info("--- 测试 DEV_COACHING 解冻机制 ---")
    state.phase = Phase.DEV_COACHING.value
    state.artifact_frozen = True
    
    # 正常聊天应保持冻结
    p, e, u = route(state, "这段代码怎么写？")
    assert p == Phase.DEV_COACHING.value
    assert u.get("artifact_frozen") is True
    
    # 触发解冻关键词
    p, e, u = route(state, "重新评审一下新的改动吧，我要开启新迭代")
    assert p == Phase.ENG_DISCUSS.value # default unfreeze back target
    assert u.get("artifact_frozen") is False
    assert u.get("iteration_count") == 1
    
    logger.info("✅ 测试通过: 用户选项轻量解析完全符合预期")

if __name__ == "__main__":
    test_routes()
