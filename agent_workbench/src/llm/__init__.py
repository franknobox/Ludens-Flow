"""
文件功能：llm 包导出入口，统一暴露模型调用与路由解析能力。
核心内容：导出 provider 层配置与文本生成函数。
核心内容：导出模型路由解析函数，供 core 编排层按策略调用。
"""

from .provider import LLMConfig, generate, load_config
from .modelrouter import resolve_model_config

__all__ = ["LLMConfig", "load_config", "generate", "resolve_model_config"]
