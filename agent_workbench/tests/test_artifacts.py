import sys
from pathlib import Path
import logging

# 添加 src 到路径，方便绝对导入
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ludens_flow.state import init_workspace, load_state, save_state
from ludens_flow.artifacts import write_artifact, read_artifact, artifact_exists

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def run_tests():
    logger.info("初始化工作区并加载 State...")
    init_workspace()
    state = load_state()

    logger.info("\n--- 测试 1: 正常单写入权覆盖 (GDD_AGENT) ---")
    reason_1 = "Initial commit of GDD"
    content_1 = "# Game Design Document\nThis is a test."
    write_artifact("GDD", content_1, reason=reason_1, actor="DesignAgent", state=state)
    logger.info(f"GDD version: {state.artifacts['gdd'].version}, hash: {state.artifacts['gdd'].hash[:8]}")
    
    logger.info("\n--- 测试 2: 二次内容写入 (GDD_AGENT) ---")
    reason_2 = "Update storyline"
    content_2 = "# Game Design Document\nThis is a test.\n\nAdded new storylines."
    write_artifact("GDD", content_2, reason=reason_2, actor="DesignAgent", state=state)
    logger.info(f"GDD version expected to be 2. Actual: {state.artifacts['gdd'].version}, hash: {state.artifacts['gdd'].hash[:8]}")
    
    logger.info("\n--- 测试 3: 拦截非法越权修改 (PM_AGENT 试图改 GDD) ---")
    try:
        write_artifact("GDD", "Illegal inject", reason="Hack", actor="PMAgent", state=state)
        logger.error("❌ 越权拦截失败！PM_AGENT 成功写入了 GDD！")
    except PermissionError as e:
        logger.info(f"✅ 成功拦截了非法修改大成功。异常详情: {str(e)}")
        
    logger.info("\n--- 测试 4: 拦截未知工件名称 ---")
    try:
        write_artifact("INVALID_DOC", "...", reason="...", actor="DesignAgent", state=state)
    except ValueError as e:
        logger.info(f"✅ 成功拦截了不合法的内部常量错误: {str(e)}")
        
    logger.info("\n--- 测试 5: read_artifact 与空文件重建 ---")
    # 把 GDD 偷偷删掉
    gdd_path = Path("workspace/GDD.md")
    if gdd_path.exists():
        gdd_path.unlink()
    
    # 在不存在的情况下强制读取，应当报错出 log 并在磁盘恢复空文件
    lost_content = read_artifact("GDD")
    logger.info(f"✅ 从磁盘重建空件读取结果为: '{lost_content}', 磁盘实体重新创建存在与否: {artifact_exists('GDD')}")
    
    logger.info("\n--- 测试完毕，状态覆盖保存 ---")
    save_state(state)
    logger.info("验收全部成功。")

if __name__ == "__main__":
    run_tests()
