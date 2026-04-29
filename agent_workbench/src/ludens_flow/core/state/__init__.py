"""
文件功能：状态子模块（__init__.py），服务项目级状态持久化与演进。
核心内容：围绕状态读写、迁移、日志与项目工作区操作提供基础能力。
核心内容：与 graph/router 协同，保证流程状态可追踪、可恢复、可扩展。
"""

from .state_logs import write_audit_log, write_router_log, write_trace_log
from .state_models import ArtifactMeta, LudensState, STATE_SCHEMA_VERSION, init_state
from .state_store import (
    StateConflictError,
    StateLockTimeoutError,
    StateStore,
    get_state_store,
    load_state,
    save_state,
)
from .state_workspace import (
    clear_images_dir,
    export_project_bundle,
    import_project_bundle,
    init_workspace,
    migrate_legacy_workspace_to_project,
    reset_current_project_state,
    reset_workspace_state,
)
from ludens_flow.core.paths import get_state_file

# 对外统一导出，供 `ludens_flow.core.state` 使用。
__all__ = [
    "ArtifactMeta",
    "LudensState",
    "STATE_SCHEMA_VERSION",
    "StateConflictError",
    "StateLockTimeoutError",
    "StateStore",
    "clear_images_dir",
    "export_project_bundle",
    "get_state_store",
    "get_state_file",
    "init_state",
    "import_project_bundle",
    "init_workspace",
    "load_state",
    "migrate_legacy_workspace_to_project",
    "reset_current_project_state",
    "reset_workspace_state",
    "save_state",
    "write_router_log",
    "write_trace_log",
    "write_audit_log",
]
