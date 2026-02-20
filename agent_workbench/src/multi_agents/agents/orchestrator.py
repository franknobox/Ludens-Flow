# orchestrator.py
# OrchestratorAgent：主控，不调用 LLM，只做流程调度
# 逻辑：while iteration < max_iterations:
#           依次运行 design → pm → engineering → review
#           若 verdict == "PASS" → break
#           否则 blocking_issues 已写入 ctx，下轮继续
