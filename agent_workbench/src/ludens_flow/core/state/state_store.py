import json
import logging
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Union

from ludens_flow.core.paths import get_state_file, resolve_project_id, touch_project

from .state_logs import write_audit_log
from .state_models import (
    LudensState,
    _sync_artifact_meta,
    init_state,
    migrate_state_payload,
)
from .state_workspace import (
    _clear_artifact_files,
    clear_images_dir,
    migrate_legacy_workspace_to_project,
)

logger = logging.getLogger(__name__)


# 版本冲突异常：防止旧状态覆盖新状态。
class StateConflictError(RuntimeError):
    """Raised when state persistence detects stale in-memory revisions."""


# 文件锁超时异常：用于提示并发等待过久。
class StateLockTimeoutError(TimeoutError):
    """Raised when waiting for project state file lock timed out."""


# 文本预览裁剪：用于项目列表摘要展示。
def _preview_text(text: Optional[str], limit: int = 120) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


# 优先取最近 assistant 回复，作为项目元信息预览。
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


# 状态存储核心：文件锁 + 原子写 + revision 控制。
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

    # 解析目标状态文件路径，并触发历史目录迁移。
    def _resolve_state_path(
        self, path: Optional[Union[str, Path]] = None, project_id: Optional[str] = None
    ) -> tuple[str, Path]:
        resolved = resolve_project_id(project_id)
        migrate_legacy_workspace_to_project(resolved)
        state_path = Path(path) if path is not None else get_state_file(resolved)
        return resolved, state_path

    def _lock_path(self, state_path: Path) -> Path:
        return state_path.with_name(state_path.name + ".lock")

    def _atomic_write_json(self, state_path: Path, payload: dict) -> None:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(state_path.parent),
            prefix=state_path.name + ".",
            suffix=".tmp",
            text=True,
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(tmp_path, str(state_path))
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise

    # 过期锁判定：用于崩溃后的锁文件回收。
    def _is_stale_lock(self, lock_path: Path) -> bool:
        try:
            age = time.time() - lock_path.stat().st_mtime
        except FileNotFoundError:
            return False
        return age > self.stale_lock_seconds

    @contextmanager
    # 文件互斥锁：确保同一项目同一时刻只有一个写入者。
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

    # 无锁读取：仅在持锁上下文里调用。
    def _load_state_unlocked(self, state_path: Path, project_id: str) -> LudensState:
        if not state_path.exists():
            logger.info(f"State file {state_path} not found. Creating a new state.")
            return init_state(project_id=project_id)

        try:
            with open(state_path, "r", encoding="utf-8") as handle:
                raw_data = json.load(handle)
            data, migrated, source_version = migrate_state_payload(raw_data)
            if migrated:
                self._atomic_write_json(state_path, data)
                write_audit_log(
                    event="STATE_SCHEMA_MIGRATION",
                    detail=f"from={source_version} to={data.get('schema_version')}",
                    project_id=project_id,
                )
            logger.info(f"Successfully loaded state from {state_path}.")
            return _sync_artifact_meta(LudensState.from_dict(data), project_id)
        except Exception as exc:
            timestamp = int(time.time())
            backup_path = state_path.with_name(f"state.broken.{timestamp}.json")
            try:
                shutil.move(str(state_path), str(backup_path))
                logger.error(
                    f"Failed to load state: {exc}. Bad file moved to {backup_path}. Returning new state."
                )
            except Exception as move_exc:
                logger.error(
                    f"Failed to load state and failed to backup bad file: {move_exc}. Returning new state."
                )

            return init_state(project_id=project_id)

    # 无锁读取 revision：用于 optimistic lock 校验。
    def _read_revision_unlocked(self, state_path: Path) -> int:
        if not state_path.exists():
            return 0

        try:
            with open(state_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return 0

        raw_revision = data.get("revision", 0)
        try:
            revision = int(raw_revision)
        except (TypeError, ValueError):
            revision = 0
        return max(revision, 0)

    # 无锁保存：执行 revision 对比与原子替换写入。
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

        data_dict = state.to_dict()
        data_dict["revision"] = new_revision

        try:
            self._atomic_write_json(state_path, data_dict)

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
        except Exception as exc:
            logger.error(f"Failed to save state to {state_path}: {exc}")
            raise

    # 对外读取入口：持锁并加载状态。
    def load(
        self, path: Optional[Union[str, Path]] = None, project_id: Optional[str] = None
    ) -> LudensState:
        resolved, state_path = self._resolve_state_path(
            path=path, project_id=project_id
        )
        with self._acquire_file_lock(state_path):
            return self._load_state_unlocked(state_path, resolved)

    # 对外保存入口：持锁并执行 revision 校验。
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

    # 对外重置入口：清理状态/工件/图片并返回新状态。
    def reset(
        self, clear_images: bool = True, project_id: Optional[str] = None
    ) -> LudensState:
        resolved, state_path = self._resolve_state_path(project_id=project_id)
        with self._acquire_file_lock(state_path):
            state_path.unlink(missing_ok=True)
            _clear_artifact_files(resolved)
            if clear_images:
                clear_images_dir(resolved)
            write_audit_log(
                event="PROJECT_RESET",
                detail=f"clear_images={clear_images}",
                project_id=resolved,
            )
            return self._load_state_unlocked(state_path, resolved)


# 进程级共享 Store 单例。
_STATE_STORE = StateStore()


# 统一获取 Store 的入口函数。
def get_state_store() -> StateStore:
    return _STATE_STORE


# 兼容函数：转发到 StateStore.load。
def load_state(
    path: Optional[Union[str, Path]] = None, project_id: Optional[str] = None
) -> LudensState:
    return get_state_store().load(path=path, project_id=project_id)


# 兼容函数：转发到 StateStore.save。
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
