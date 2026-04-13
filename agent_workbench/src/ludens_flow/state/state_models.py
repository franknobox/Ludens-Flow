from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from ludens_flow.paths import get_artifact_paths, resolve_project_id


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
        artifacts_raw = data.pop("artifacts", {})
        artifacts = {}
        for key, value in artifacts_raw.items():
            artifacts[key] = ArtifactMeta(**value)

        valid_keys = cls.__dataclass_fields__.keys()
        filtered_data = {key: value for key, value in data.items() if key in valid_keys}

        state = cls(**filtered_data)
        state.artifacts = artifacts
        return state


# 工件写入责任映射：保证单一职责 Agent。
def _artifact_owner_map() -> Dict[str, str]:
    return {
        "gdd": "DesignAgent",
        "pm": "PMAgent",
        "eng": "EngineeringAgent",
        "review": "ReviewAgent",
        "devlog": "EngineeringAgent",
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
        },
    )
    return _sync_artifact_meta(state, resolved)
