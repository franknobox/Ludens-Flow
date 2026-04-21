"""
文件功能：工作区访问模块（__init__.py），统一管理路径边界与访问策略。
核心内容：提供工作区绑定解析、沙箱校验和读写权限判断能力。
核心内容：为工具层提供稳定工作区访问契约，减少业务分支复杂度。
"""

from .access import (
    DEFAULT_TEXT_FILE_EXTENSIONS,
    WorkspaceAccessError,
    WorkspaceBinding,
    WorkspaceTarget,
    check_workspace_write_permission,
    ensure_text_file_target,
    resolve_workspace_binding,
    resolve_workspace_target,
)

__all__ = [
    "DEFAULT_TEXT_FILE_EXTENSIONS",
    "WorkspaceAccessError",
    "WorkspaceBinding",
    "WorkspaceTarget",
    "check_workspace_write_permission",
    "ensure_text_file_target",
    "resolve_workspace_binding",
    "resolve_workspace_target",
]
