import json
import logging
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

from ludens_flow.paths import (
    create_project,
    get_artifact_paths,
    get_dev_notes_dir,
    get_images_dir,
    get_logs_dir,
    get_memory_dir,
    get_patches_dir,
    get_project_dir,
    get_state_file,
    get_workspace_root_dir,
    get_workspace_dir,
    resolve_project_id,
    touch_project,
)

logger = logging.getLogger(__name__)

LEGACY_ROOT_FILES = {
    "state.json": "state.json",
    "USER_PROFILE.md": "USER_PROFILE.md",
    "GDD.md": "GDD.md",
    "PROJECT_PLAN.md": "PROJECT_PLAN.md",
    "IMPLEMENTATION_PLAN.md": "IMPLEMENTATION_PLAN.md",
    "REVIEW_REPORT.md": "REVIEW_REPORT.md",
}

LEGACY_ROOT_DIRS = {
    "logs": "logs",
    "memory": "memory",
    "images": "images",
    "dev_notes": "dev_notes",
    "patches": "patches",
}

# --- 数据结构 ---


@dataclass
class ArtifactMeta:
    path: str
    owner: str  # 负责写入的 Agent 名称（保障单写入权）
    version: int = 0
    hash: str = ""  # 文件内容 hash
    updated_at: str = ""
    update_reason: str = ""


@dataclass
class LudensState:
    """系统全局运行状态"""

    project_id: Optional[str] = None
    revision: int = 0

    # 流程控制
    phase: str = "GDD_DISCUSS"
    iteration_count: int = 0
    max_iterations: int = 6
    artifact_frozen: bool = False  # 若 True，禁止修改 canonical 核心工件

    # 上下文参数
    style_preset: Optional[str] = None

    # 状态数据
    drafts: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {"gdd": {}, "pm": {}, "eng": {}}
    )
    change_requests: List[Dict[str, Any]] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)

    # 复杂网关：status, targets, issues
    review_gate: Optional[Dict[str, Any]] = None
    last_event: Optional[str] = None  # 用于 Router 处理自动跳转
    last_assistant_message: Optional[str] = None  # 用于向外部 CLI 抛出模型的自然语言
    last_error: Optional[str] = None

    # 对话记忆：记录跨模型的流转对话上下文，格式为 {"role": "user/assistant", "content": "..."}
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    transcript_history: List[Dict[str, str]] = field(default_factory=list)

    # 文件元数据
    artifacts: Dict[str, ArtifactMeta] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LudensState":
        """为了应对字段更新能够提供默认值，这里手动构建或利用 unpack"""
        # 特殊处理嵌套的 dataclass
        artifacts_raw = data.pop("artifacts", {})
        artifacts = {}
        for k, v in artifacts_raw.items():
            artifacts[k] = ArtifactMeta(**v)

        # 过滤掉无法识别的过时字段，兼容未来版本平滑升级
        valid_keys = cls.__dataclass_fields__.keys()
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}

        state = cls(**filtered_data)
        state.artifacts = artifacts
        return state


def _artifact_owner_map() -> Dict[str, str]:
    return {
        "gdd": "DesignAgent",
        "pm": "PMAgent",
        "eng": "EngineeringAgent",
        "review": "ReviewAgent",
        "devlog": "EngineeringAgent",
    }


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


def _preview_text(text: Optional[str], limit: int = 120) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _latest_assistant_preview(state: LudensState) -> str:
    preview = _preview_text(state.last_assistant_message)
    if preview:
        return preview

    for history in (state.transcript_history, state.chat_history):
        for item in reversed(history):
            if item.get("role") != "assistant":
                continue
            preview = _preview_text(item.get("content"))
            if preview:
                return preview

    return ""


def _has_content(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        return any(path.iterdir())
    return path.stat().st_size > 0


def _move_legacy_entry(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    if _has_content(target):
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)

    shutil.move(str(source), str(target))
    return True


def migrate_legacy_workspace_to_project(project_id: Optional[str] = None) -> list[str]:
    """Move legacy single-project workspace files into project-1 once."""
    resolved = resolve_project_id(project_id)
    if resolved != "project-1":
        return []

    workspace_root = get_workspace_root_dir()
    project_dir = get_project_dir(resolved)
    moved: list[str] = []

    for legacy_name, target_name in LEGACY_ROOT_FILES.items():
        if _move_legacy_entry(workspace_root / legacy_name, project_dir / target_name):
            moved.append(legacy_name)

    for legacy_name, target_name in LEGACY_ROOT_DIRS.items():
        if _move_legacy_entry(workspace_root / legacy_name, project_dir / target_name):
            moved.append(legacy_name)

    return moved


class StateConflictError(RuntimeError):
    """Raised when state persistence detects stale in-memory revisions."""


class StateLockTimeoutError(TimeoutError):
    """Raised when waiting for project state file lock timed out."""


class StateStore:
    """Project-scoped state persistence with file lock, atomic writes and revisions."""

    def __init__(
        self,
        *,
        lock_timeout_seconds: float = 10.0,
        lock_poll_interval_seconds: float = 0.05,
        stale_lock_seconds: float = 120.0,
    ) -> None:
        self.lock_timeout_seconds = lock_timeout_seconds
        self.lock_poll_interval_seconds = lock_poll_interval_seconds
        self.stale_lock_seconds = stale_lock_seconds

    def _resolve_state_path(
        self, path: Optional[Union[str, Path]] = None, project_id: Optional[str] = None
    ) -> tuple[str, Path]:
        resolved = resolve_project_id(project_id)
        migrate_legacy_workspace_to_project(resolved)
        state_path = Path(path) if path is not None else get_state_file(resolved)
        return resolved, state_path

    def _lock_path(self, state_path: Path) -> Path:
        return state_path.with_name(state_path.name + ".lock")

    def _is_stale_lock(self, lock_path: Path) -> bool:
        try:
            age = time.time() - lock_path.stat().st_mtime
        except FileNotFoundError:
            return False
        return age > self.stale_lock_seconds

    @contextmanager
    def _acquire_file_lock(self, state_path: Path) -> Iterator[None]:
        lock_path = self._lock_path(state_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        started_at = time.time()
        acquired = False

        while not acquired:
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    payload = json.dumps(
                        {
                            "pid": os.getpid(),
                            "acquired_at": started_at,
                        }
                    )
                    os.write(fd, payload.encode("utf-8"))
                finally:
                    os.close(fd)
                acquired = True
            except FileExistsError:
                if self._is_stale_lock(lock_path):
                    try:
                        lock_path.unlink(missing_ok=True)
                    except OSError:
                        pass

                if time.time() - started_at >= self.lock_timeout_seconds:
                    raise StateLockTimeoutError(
                        f"Timed out acquiring state lock: {lock_path}"
                    )
                time.sleep(self.lock_poll_interval_seconds)

        try:
            yield
        finally:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _load_state_unlocked(self, state_path: Path, project_id: str) -> LudensState:
        if not state_path.exists():
            logger.info(f"State file {state_path} not found. Creating a new state.")
            return init_state(project_id=project_id)

        try:
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Successfully loaded state from {state_path}.")
            return _sync_artifact_meta(LudensState.from_dict(data), project_id)
        except Exception as e:
            timestamp = int(time.time())
            backup_path = state_path.with_name(f"state.broken.{timestamp}.json")
            try:
                shutil.move(str(state_path), str(backup_path))
                logger.error(
                    f"Failed to load state: {e}. Bad file moved to {backup_path}. Returning new state."
                )
            except Exception as mv_err:
                logger.error(
                    f"Failed to load state and failed to backup bad file: {mv_err}. Returning new state."
                )

            return init_state(project_id=project_id)

    def _read_revision_unlocked(self, state_path: Path) -> int:
        if not state_path.exists():
            return 0

        try:
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return 0

        raw_revision = data.get("revision", 0)
        try:
            revision = int(raw_revision)
        except (TypeError, ValueError):
            revision = 0
        return max(revision, 0)

    def _save_state_unlocked(
        self,
        state: LudensState,
        state_path: Path,
        project_id: str,
        expected_revision: Optional[int] = None,
    ) -> int:
        state = _sync_artifact_meta(state, project_id)

        base_revision = getattr(state, "revision", 0)
        try:
            base_revision = int(base_revision)
        except (TypeError, ValueError):
            base_revision = 0
        base_revision = max(base_revision, 0)

        if expected_revision is None:
            expected_revision = base_revision

        current_revision = self._read_revision_unlocked(state_path)
        if current_revision != expected_revision:
            raise StateConflictError(
                f"State revision conflict for project '{project_id}': "
                f"expected {expected_revision}, current {current_revision}."
            )

        new_revision = expected_revision + 1
        state_path.parent.mkdir(parents=True, exist_ok=True)

        data_dict = state.to_dict()
        data_dict["revision"] = new_revision

        fd, tmp_path = tempfile.mkstemp(
            dir=str(state_path.parent),
            prefix=state_path.name + ".",
            suffix=".tmp",
            text=True,
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data_dict, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, str(state_path))

            if project_id:
                touch_project(
                    project_id,
                    last_phase=state.phase,
                    last_message_preview=_latest_assistant_preview(state),
                )

            state.revision = new_revision
            logger.debug(
                f"State successfully saved to {state_path} @ rev {new_revision}."
            )
            return new_revision
        except Exception as e:
            logger.error(f"Failed to save state to {state_path}: {e}")
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise

    def load(
        self, path: Optional[Union[str, Path]] = None, project_id: Optional[str] = None
    ) -> LudensState:
        resolved, state_path = self._resolve_state_path(
            path=path, project_id=project_id
        )
        with self._acquire_file_lock(state_path):
            return self._load_state_unlocked(state_path, resolved)

    def save(
        self,
        state: LudensState,
        path: Optional[Union[str, Path]] = None,
        project_id: Optional[str] = None,
        expected_revision: Optional[int] = None,
    ) -> int:
        target_project = project_id if project_id is not None else state.project_id
        resolved, state_path = self._resolve_state_path(
            path=path, project_id=target_project
        )
        with self._acquire_file_lock(state_path):
            return self._save_state_unlocked(
                state,
                state_path,
                resolved,
                expected_revision=expected_revision,
            )

    def reset(
        self, clear_images: bool = True, project_id: Optional[str] = None
    ) -> LudensState:
        resolved, state_path = self._resolve_state_path(project_id=project_id)
        with self._acquire_file_lock(state_path):
            state_path.unlink(missing_ok=True)
            _clear_artifact_files(resolved)
            if clear_images:
                clear_images_dir(resolved)
            return self._load_state_unlocked(state_path, resolved)


_STATE_STORE = StateStore()


def get_state_store() -> StateStore:
    return _STATE_STORE


# --- 核心函数 ---


def init_workspace(project_id: Optional[str] = None) -> None:
    """初始化运行工作区，确保必备目录与空文件存在"""
    resolved = resolve_project_id(project_id)
    if resolved:
        create_project(resolved)
        migrate_legacy_workspace_to_project(resolved)
        touch_project(resolved)

    workspace_dir = get_workspace_dir(resolved)
    logs_dir = get_logs_dir(resolved)
    memory_dir = get_memory_dir(resolved)
    images_dir = get_images_dir(resolved)
    dev_notes_dir = get_dev_notes_dir(resolved)
    patches_dir = get_patches_dir(resolved)
    artifact_paths = get_artifact_paths(resolved)

    for d in [
        workspace_dir,
        logs_dir,
        memory_dir,
        images_dir,
        dev_notes_dir,
        patches_dir,
    ]:
        d.mkdir(parents=True, exist_ok=True)

    for path in artifact_paths.values():
        if not path.exists():
            path.touch()


def clear_images_dir(project_id: Optional[str] = None) -> Path:
    """Delete all files/subdirectories under workspace/images and keep the folder."""
    images_dir = get_images_dir(resolve_project_id(project_id))
    images_dir.mkdir(parents=True, exist_ok=True)

    for entry in images_dir.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)
    return images_dir


def _clear_artifact_files(project_id: Optional[str] = None) -> None:
    """将所有工件文件清空（重置为空文件），并清理 dev_notes 和 patches 目录。"""
    resolved = resolve_project_id(project_id)
    artifact_paths = get_artifact_paths(resolved)
    for path in artifact_paths.values():
        if path.exists():
            path.write_text("", encoding="utf-8")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

    # 清理 dev_notes 和 patches 下的内容
    for d in [get_dev_notes_dir(resolved), get_patches_dir(resolved)]:
        if d.exists():
            for entry in d.iterdir():
                if entry.is_dir():
                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    entry.unlink(missing_ok=True)


def reset_current_project_state(
    clear_images: bool = True, project_id: Optional[str] = None
) -> LudensState:
    """Reset one project's persisted state, artifacts and optional image cache."""
    return get_state_store().reset(clear_images=clear_images, project_id=project_id)


def reset_workspace_state(
    clear_images: bool = True, project_id: Optional[str] = None
) -> LudensState:
    """Compatibility alias for older callers."""
    return reset_current_project_state(clear_images=clear_images, project_id=project_id)


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


def load_state(
    path: Optional[Union[str, Path]] = None, project_id: Optional[str] = None
) -> LudensState:
    return get_state_store().load(path=path, project_id=project_id)


def save_state(
    state: LudensState,
    path: Optional[Union[str, Path]] = None,
    project_id: Optional[str] = None,
    expected_revision: Optional[int] = None,
) -> None:
    get_state_store().save(
        state,
        path=path,
        project_id=project_id,
        expected_revision=expected_revision,
    )


# --- 日志三件套写入工具 ---
def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_trace_log(
    action: str,
    node: str,
    phase: str,
    frozen: bool,
    event_or_commit: str,
    error: str = "",
    project_id: Optional[str] = None,
) -> None:
    """
    trace.log: 每个节点进入/退出
    entering: ts | node | phase | frozen | last_event
    leaving: ts | node | commit=Y/N | error=...
    """
    logs_dir = get_logs_dir(resolve_project_id(project_id))
    logs_dir.mkdir(parents=True, exist_ok=True)
    trace_file = logs_dir / "trace.log"
    ts = _now_iso()
    with open(trace_file, "a", encoding="utf-8") as f:
        if action.upper() == "ENTER":
            f.write(
                f"[{ts}] ENTER | {node} | phase={phase} | frozen={frozen} | last_event={event_or_commit}\n"
            )
        elif action.upper() == "LEAVE":
            f.write(
                f"[{ts}] LEAVE | {node} | commit={event_or_commit} | error={error}\n"
            )


def write_router_log(
    iteration: int,
    from_phase: str,
    to_phase: str,
    choice: str,
    gate: str,
    frozen: bool,
    reason: str,
    project_id: Optional[str] = None,
) -> None:
    """
    router.log: 每次 Router 决策
    ts | iter | from_phase -> to_phase | choice | gate | frozen | reason
    """
    logs_dir = get_logs_dir(resolve_project_id(project_id))
    logs_dir.mkdir(parents=True, exist_ok=True)
    router_file = logs_dir / "router.log"
    ts = _now_iso()
    with open(router_file, "a", encoding="utf-8") as f:
        f.write(
            f"[{ts}] | iter={iteration} | {from_phase} -> {to_phase} | choice={choice} | gate={gate} | frozen={frozen} | reason={reason}\n"
        )
