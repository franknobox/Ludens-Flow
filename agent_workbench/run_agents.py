# run.py — 多Agent版入口（替换 run_baseline.py）
# 用法：
#   python run.py "你的游戏需求"
#   python run.py           ← 交互式输入
#
# 流程：
#   1. 读取用户需求（命令行参数 or input()）
#   2. 初始化 SharedContext
#   3. 实例化四个子 Agent 和 OrchestratorAgent
#   4. orchestrator.run(ctx, cfg)
#   5. atomic_write 将 ctx 中的产物写入 artifacts/ 目录
