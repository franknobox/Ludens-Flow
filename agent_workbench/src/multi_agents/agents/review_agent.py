# review_agent.py
# ReviewAgent：评审 Agent
# 输入：ctx.gdd + ctx.project_plan + ctx.impl_plan
# 输出：ctx.review_report + ctx.verdict("PASS"/"FAIL") + ctx.blocking_issues
# system_prompt："你是验收审查(Review Agent)。必须明确写出 PASS 或 FAIL，列出阻塞问题。"
# 需实现：_parse_verdict(report) -> str
#         _parse_blocking_issues(report) -> list[str]
