"""
文件功能：上下文能力模块（__init__.py），负责提示模板与用户画像能力。
核心内容：统一处理 prompt 模板加载、用户画像读写与格式化注入。
核心内容：为 Agent 调用提供可复用上下文拼装能力。
"""

from .prompt_templates import PromptTemplate, load_prompt_template
from .user_profile import (
    format_profile_for_prompt,
    load_profile,
    migrate_profile_file,
    migrate_profile_text_to_current_template,
    update_profile,
)

__all__ = [
    "PromptTemplate",
    "load_prompt_template",
    "format_profile_for_prompt",
    "load_profile",
    "migrate_profile_file",
    "migrate_profile_text_to_current_template",
    "update_profile",
]
