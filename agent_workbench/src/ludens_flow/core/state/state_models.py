"""
文件功能：状态子模块（state_models.py），服务项目级状态持久化与演进。
核心内容：围绕状态读写、迁移、日志与项目工作区操作提供基础能力。
核心内容：与 graph/router 协同，保证流程状态可追踪、可恢复、可扩展。
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from ludens_flow.core.paths import get_artifact_paths, resolve_project_id

STATE_SCHEMA_VERSION = 2


# 工件元数据：用于追踪每个主工件的版本与归属。
@dataclass
class ArtifactMeta:
    path: str
    owner: str
    version: int = 0
    hash: str = ""
    updated_at: str = ""
    update_reason: str = ""


# 运行时状态：统一承载流程、上下文、历史与工件映射。
@dataclass
class LudensState:
    """系统全局运行状态"""

    project_id: Optional[str] = None
    schema_version: int = STATE_SCHEMA_VERSION
    revision: int = 0

    phase: str = "GDD_DISCUSS"
    iteration_count: int = 0
    max_iterations: int = 6
    artifact_frozen: bool = False

    style_preset: Optional[str] = None

    drafts: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {"gdd": {}, "pm": {}, "eng": {}}
    )
    change_requests: List[Dict[str, Any]] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)

    review_gate: Optional[Dict[str, Any]] = None
    last_event: Optional[str] = None
    last_assistant_message: Optional[str] = None
    last_error: Optional[str] = None

    chat_history: List[Dict[str, str]] = field(default_factory=list)
    transcript_history: List[Dict[str, str]] = field(default_factory=list)

    artifacts: Dict[str, ArtifactMeta] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    # 反序列化：兼容未知旧字段并恢复嵌套的 ArtifactMeta。
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LudensState":
        normalized, _, _ = migrate_state_payload(data)

        artifacts_raw = normalized.pop("artifacts", {})
        artifacts = {}
        for key, value in artifacts_raw.items():
            artifacts[key] = ArtifactMeta(**value)

        valid_keys = cls.__dataclass_fields__.keys()
        filtered_data = {
            key: value for key, value in normalized.items() if key in valid_keys
        }

        state = cls(**filtered_data)
        state.artifacts = artifacts
        return state


def migrate_state_payload(data: Dict[str, Any]) -> tuple[Dict[str, Any], bool, int]:
    """Normalize and migrate a persisted state payload to current schema."""
    payload = dict(data or {})

    raw_version = payload.get("schema_version", 1)
    try:
        source_version = int(raw_version)
    except (TypeError, ValueError):
        source_version = 1

    migrated = False

    if source_version < 2:
        payload.setdefault("revision", 0)
        migrated = True

    payload["schema_version"] = STATE_SCHEMA_VERSION
    migrated = migrated or source_version != STATE_SCHEMA_VERSION

    return payload, migrated, source_version


# 工件写入责任映射：保证单一职责 Agent。
def _artifact_owner_map() -> Dict[str, str]:
    return {
        "gdd": "DesignAgent",
        "pm": "PMAgent",
        "eng": "EngineeringAgent",
        "review": "ReviewAgent",
        "devlog": "EngineeringAgent",
        "notes": "User",
    }


# 同步工件路径与 owner：用于多项目场景的路径漂移修正。
def _sync_artifact_meta(
    state: LudensState, project_id: Optional[str] = None
) -> LudensState:
    resolved = resolve_project_id(
        project_id if project_id is not None else state.project_id
    )
    artifact_paths = get_artifact_paths(resolved)
    owners = _artifact_owner_map()

    state.project_id = resolved
    for key, path in artifact_paths.items():
        meta = state.artifacts.get(key)
        if meta is None:
            state.artifacts[key] = ArtifactMeta(path=str(path), owner=owners[key])
            continue
        meta.path = str(path)
        meta.owner = owners[key]

    return state


# 构建初始状态：为新项目注入默认 phase 与工件路径。
def init_state(project_id: Optional[str] = None) -> LudensState:
    """构建初始默认状态"""
    resolved = resolve_project_id(project_id)
    artifact_paths = get_artifact_paths(resolved)
    state = LudensState(
        project_id=resolved,
        phase="GDD_DISCUSS",
        iteration_count=0,
        max_iterations=6,
        artifacts={
            "gdd": ArtifactMeta(path=str(artifact_paths["gdd"]), owner="DesignAgent"),
            "pm": ArtifactMeta(path=str(artifact_paths["pm"]), owner="PMAgent"),
            "eng": ArtifactMeta(
                path=str(artifact_paths["eng"]), owner="EngineeringAgent"
            ),
            "review": ArtifactMeta(
                path=str(artifact_paths["review"]), owner="ReviewAgent"
            ),
            "devlog": ArtifactMeta(
                path=str(artifact_paths["devlog"]), owner="EngineeringAgent"
            ),
            "notes": ArtifactMeta(path=str(artifact_paths["notes"]), owner="User"),
        },
    )
    return _sync_artifact_meta(state, resolved)
