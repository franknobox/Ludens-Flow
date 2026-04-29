"""
文件功能：工件能力模块（__init__.py），管理核心文档与开发附加工件。
核心内容：提供工件读取、写入、版本与冻结策略相关基础操作。
核心内容：保障流程阶段内工件更新可控、可审计、可回溯。
"""

from .artifacts import read_artifact, write_artifact, write_dev_note, write_patch

__all__ = ["read_artifact", "write_artifact", "write_dev_note", "write_patch"]
