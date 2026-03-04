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
    str((Path(tempfile.gettempdir()) / "ludens_flow_tests" / "test_router_options").resolve()),
)

from ludens_flow.state import init_state
from ludens_flow.router import route, Phase

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def test_routes():
    # 使用 init_state() 创建全新干净的内存状态，不依赖磁盘文件
    state = init_state()
    
    logger.info("--- 测试 Discuss 动作项 ---")
    # Router 的 is_short_cmd 规则：len <= 8 才触发关键词匹配，否则只匹配纯数字/字母
    state.phase = Phase.PM_DISCUSS.value
    # 选项 1：停留 (纯数字 "1")
    p, e, _ = route(state, "1")
    assert p == Phase.PM_DISCUSS.value, f"Expected PM_DISCUSS, got {p}"
    # 选项 2：前进 (短关键词 "定稿")
    state.phase = Phase.PM_DISCUSS.value
    p, e, _ = route(state, "定稿")
    assert p == Phase.PM_COMMIT.value, f"Expected PM_COMMIT, got {p}"
    # 选项 3：回退 (纯数字 "3")
    state.phase = Phase.PM_DISCUSS.value
    p, e, _ = route(state, "3")
    assert p == Phase.GDD_DISCUSS.value, f"Expected GDD_DISCUSS, got {p}"

    logger.info("--- 测试 POST_REVIEW_DECISION 动作项 ---")
    # 必须先设置 review_gate，router 根据 targets 决定回流到哪
    state.review_gate = {"status": "REQUEST_CHANGES", "targets": ["GDD"], "issues": []}
    
    # 选项 A：单字母 "a" 精确匹配
    state.phase = Phase.POST_REVIEW_DECISION.value
    p, e, u = route(state, "a")
    assert p == Phase.GDD_DISCUSS.value, f"Expected GDD_DISCUSS, got {p}"
    assert u.get("iteration_count") == 1
    
    # 选项 C：单字母 "c" 直接进入开发
    state.phase = Phase.POST_REVIEW_DECISION.value
    p, e, u = route(state, "c")
    assert p == Phase.DEV_COACHING.value, f"Expected DEV_COACHING, got {p}"
    assert u.get("artifact_frozen") is True

    logger.info("--- 测试 DEV_COACHING 解冻机制 ---")
    state.phase = Phase.DEV_COACHING.value
    state.artifact_frozen = True
    
    # 正常聊天应保持冻结
    p, e, u = route(state, "这段代码怎么写？")
    assert p == Phase.DEV_COACHING.value, f"Expected DEV_COACHING, got {p}"
    assert u.get("artifact_frozen") is True
    
    # 触发解冻关键词（短语，<=8字符）
    p, e, u = route(state, "解冻")
    assert p == Phase.ENG_DISCUSS.value, f"Expected ENG_DISCUSS, got {p}"
    assert u.get("artifact_frozen") is False
    
    logger.info("✅ 测试通过: 用户选项轻量解析完全符合预期")

if __name__ == "__main__":
    test_routes()
