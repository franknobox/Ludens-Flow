# design_agent.py
# DesignAgent：策划 Agent
# 输入：ctx.user_request + ctx.blocking_issues（上轮阻塞问题，若有）
# 输出：ctx.gdd
# system_prompt："你是游戏策划(Design Agent)。产出可落盘的GDD Markdown。"
