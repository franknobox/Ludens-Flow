"""
文件功能：输入接入模块（__init__.py），处理文本/附件等输入预处理。
核心内容：解析多模态输入并转换为统一可消费的用户输入结构。
核心内容：在不改变业务语义前提下提升输入鲁棒性与兼容性。
"""

from .attachment_ingest import AttachmentPayload, build_attachment_user_input
from .input_parser import parse_user_input

__all__ = ["AttachmentPayload", "build_attachment_user_input", "parse_user_input"]
