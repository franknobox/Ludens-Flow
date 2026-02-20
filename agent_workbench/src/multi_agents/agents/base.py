# base.py
# BaseAgent：所有子 Agent 的抽象基类
# 接口：run(ctx: SharedContext, cfg: LLMConfig) -> None
# 工具方法：_call(user_prompt, cfg) -> str  （统一 LLM 调用入口，便于后续换框架）
