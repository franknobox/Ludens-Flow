"""
文件功能：能力工具模块（__init__.py），对外提供可控工具调用能力。
核心内容：封装工具参数处理、错误返回与结果摘要的统一行为。
核心内容：作为 Agent 工具层能力入口，服务文件/搜索/工作区相关任务。
"""

from .registry import dispatch_tool_call, merge_tool_schemas

__all__ = ["dispatch_tool_call", "merge_tool_schemas"]
