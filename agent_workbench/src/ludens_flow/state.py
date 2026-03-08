import json
import logging
import os
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ludens_flow.paths import (
    get_artifact_paths,
    get_dev_notes_dir,
    get_images_dir,
    get_logs_dir,
    get_memory_dir,
    get_patches_dir,
    get_state_file,
    get_workspace_dir,
)

logger = logging.getLogger(__name__)

# --- 常量定义 ---
WORKSPACE_DIR = get_workspace_dir()
LOGS_DIR = get_logs_dir()
MEMORY_DIR = get_memory_dir()
DEV_NOTES_DIR = get_dev_notes_dir()
PATCHES_DIR = get_patches_dir()
STATE_FILE = get_state_file()
ARTIFACT_PATHS = get_artifact_paths()


# --- 数据结构 ---

@dataclass
class ArtifactMeta:
    path: str
    owner: str            # 负责写入的 Agent 名称（保障单写入权）
    version: int = 0
    hash: str = ""        # 文件内容 hash
    updated_at: str = ""
    update_reason: str = ""


@dataclass
class LudensState:
    """系统全局运行状态"""
    # 流程控制
    phase: str = "GDD_DISCUSS"
    iteration_count: int = 0
    max_iterations: int = 6
    artifact_frozen: bool = False  # 若 True，禁止修改 canonical 核心工件

    # 上下文参数
    style_preset: Optional[str] = None
    
    # 状态数据
    drafts: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {"gdd": {}, "pm": {}, "eng": {}})
    change_requests: List[Dict[str, Any]] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    
    # 复杂网关：status, targets, issues
    review_gate: Optional[Dict[str, Any]] = None  
    last_event: Optional[str] = None  # 用于 Router 处理自动跳转
    last_assistant_message: Optional[str] = None  # 用于向外部 CLI 抛出模型的自然语言
    last_error: Optional[str] = None
    
    # 对话记忆：记录跨模型的流转对话上下文，格式为 {"role": "user/assistant", "content": "..."}
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    
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


# --- 核心函数 ---

def init_workspace() -> None:
    """初始化运行工作区，确保必备目录与空文件存在"""
    workspace_dir = get_workspace_dir()
    logs_dir = get_logs_dir()
    memory_dir = get_memory_dir()
    images_dir = get_images_dir()
    dev_notes_dir = get_dev_notes_dir()
    patches_dir = get_patches_dir()
    artifact_paths = get_artifact_paths()

    for d in [workspace_dir, logs_dir, memory_dir, images_dir, dev_notes_dir, patches_dir]:
        d.mkdir(parents=True, exist_ok=True)
        
    for path in artifact_paths.values():
        if not path.exists():
            path.touch()


def clear_images_dir() -> Path:
    """Delete all files/subdirectories under workspace/images and keep the folder."""
    images_dir = get_images_dir()
    images_dir.mkdir(parents=True, exist_ok=True)

    for entry in images_dir.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)
    return images_dir


def reset_workspace_state(clear_images: bool = True) -> LudensState:
    """
    Reset persisted runtime state for a fresh session.
    - Remove state.json if present.
    - Optionally clear workspace/images.
    """
    get_state_file().unlink(missing_ok=True)
    if clear_images:
        clear_images_dir()
    return load_state()


def init_state() -> LudensState:
    """构建初始默认状态"""
    artifact_paths = get_artifact_paths()
    return LudensState(
        phase="GDD_DISCUSS",
        iteration_count=0,
        max_iterations=6,
        artifacts={
            "gdd": ArtifactMeta(path=str(artifact_paths["gdd"]), owner="DesignAgent"),
            "pm": ArtifactMeta(path=str(artifact_paths["pm"]), owner="PMAgent"),
            "eng": ArtifactMeta(path=str(artifact_paths["eng"]), owner="EngineeringAgent"),
            "review": ArtifactMeta(path=str(artifact_paths["review"]), owner="ReviewAgent"),
        }
    )


def load_state(path: Optional[Union[str, Path]] = None) -> LudensState:
    """
    加载持久化状态。
    若文件不存在：返回全新初始状态。
    若文件解析失败：备份坏档，并返回初始状态，防止死锁。
    """
    path = Path(path) if path is not None else get_state_file()
    if not path.exists():
        logger.info(f"State file {path} not found. Creating a new state.")
        return init_state()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Successfully loaded state from {path}.")
        return LudensState.from_dict(data)
    except Exception as e:
        # 文件损坏或格式错误
        timestamp = int(time.time())
        backup_path = path.with_name(f"state.broken.{timestamp}.json")
        try:
            shutil.move(str(path), str(backup_path))
            logger.error(f"Failed to load state: {e}. Bad file moved to {backup_path}. Returning new state.")
        except Exception as mv_err:
            logger.error(f"Failed to load state and failed to backup bad file: {mv_err}. Returning new state.")
            
        return init_state()


def save_state(state: LudensState, path: Optional[Union[str, Path]] = None) -> None:
    """
    原子写入状态文件。
    先写到同目录的 tmp 文件，再重命名覆盖，防止中途断电损坏文件。
    """
    path = Path(path) if path is not None else get_state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # 将 state 转换为 dict，处理可能的特殊类型
    data_dict = state.to_dict()
    
    # 建立临时文件描述符
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data_dict, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno()) # 确保内容刷新到磁盘
        
        # Windows 和 Unix 行为一致的覆盖方案
        os.replace(tmp_path, str(path))
        logger.debug(f"State successfully saved to {path}.")
    except Exception as e:
        logger.error(f"Failed to save state to {path}: {e}")
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise

# --- 日志三件套写入工具 ---
def _now_iso() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"

def write_trace_log(action: str, node: str, phase: str, frozen: bool, event_or_commit: str, error: str = "") -> None:
    """
    trace.log: 每个节点进入/退出
    entering: ts | node | phase | frozen | last_event
    leaving: ts | node | commit=Y/N | error=...
    """
    logs_dir = get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    trace_file = logs_dir / "trace.log"
    ts = _now_iso()
    with open(trace_file, "a", encoding="utf-8") as f:
        if action.upper() == "ENTER":
            f.write(f"[{ts}] ENTER | {node} | phase={phase} | frozen={frozen} | last_event={event_or_commit}\n")
        elif action.upper() == "LEAVE":
            f.write(f"[{ts}] LEAVE | {node} | commit={event_or_commit} | error={error}\n")

def write_router_log(iteration: int, from_phase: str, to_phase: str, choice: str, gate: str, frozen: bool, reason: str) -> None:
    """
    router.log: 每次 Router 决策
    ts | iter | from_phase -> to_phase | choice | gate | frozen | reason
    """
    logs_dir = get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    router_file = logs_dir / "router.log"
    ts = _now_iso()
    with open(router_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] | iter={iteration} | {from_phase} -> {to_phase} | choice={choice} | gate={gate} | frozen={frozen} | reason={reason}\n")
