import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from ludens_flow.state import LudensState, ArtifactMeta, ARTIFACT_PATHS, LOGS_DIR, DEV_NOTES_DIR, PATCHES_DIR

logger = logging.getLogger(__name__)

ARTIFACTS_LOG_FILE = LOGS_DIR / "artifacts.log"

# --- 1. 统一工件注册表 (Registry) ---
# 定义每个核心工件的枚举名称、物理路径和唯一拥有的 Agent（单写入权）
ARTIFACT_REGISTRY = {
    "GDD": {
        "path": ARTIFACT_PATHS["gdd"],
        "owner": "DesignAgent"
    },
    "PROJECT_PLAN": {
        "path": ARTIFACT_PATHS["pm"],
        "owner": "PMAgent"
    },
    "IMPLEMENTATION_PLAN": {
        "path": ARTIFACT_PATHS["eng"],
        "owner": "EngineeringAgent"
    },
    "REVIEW_REPORT": {
        "path": ARTIFACT_PATHS["review"],
        "owner": "ReviewAgent"
    }
}


def _now_iso() -> str:
    """返回当前时间的 ISO 格式字符串"""
    return datetime.utcnow().isoformat() + "Z"


def compute_hash(content: str) -> str:
    """计算内容的 SHA-256 哈希值"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def artifact_exists(name: str) -> bool:
    """检查注册表中指定名字的工件实体文件是否存在"""
    if name not in ARTIFACT_REGISTRY:
        return False
    return ARTIFACT_REGISTRY[name]["path"].exists()


def read_artifact(name: str) -> str:
    """
    读取工件内容，若不存在则返回空字符串并尝试创建空文件。
    """
    if name not in ARTIFACT_REGISTRY:
        raise ValueError(f"Unknown artifact name: {name}")
    
    path = ARTIFACT_REGISTRY[name]["path"]
    
    if not path.exists():
        logger.warning(f"Artifact file {path} missing on read. Recreating empty file.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return ""
        
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_artifact(name: str, content: str, reason: str, actor: str, state: LudensState) -> LudensState:
    """
    执行带版本控制和原子覆盖写入的工件保存。
    1. 冻结校验：若 state.artifact_frozen 为 True，无情拒绝
    2. 强制鉴权: actor == owner
    3. 原子写入实际文件 (*.tmp -> rename)
    4. 更新传入的 state.artifacts 元数据 (version++, hash, timestamp)
    5. 记录追踪日志
    """
    if name not in ARTIFACT_REGISTRY:
        raise ValueError(f"Unknown artifact name: {name}")
    
    # --- 0. 结冰校验 (Freeze Guard) ---
    if getattr(state, "artifact_frozen", False):
         raise PermissionError(
             f"System is currently in DEV_COACHING (Artifact Frozen state). "
             f"Canonical artifact '{name}' is locked and cannot be modified. "
             f"Please use write_dev_note or write_patch instead."
         )
         
    registry_info = ARTIFACT_REGISTRY[name]
    expected_owner = registry_info["owner"]
    path: Path = registry_info["path"]
    
    # --- 1. 单写入权校验 ---
    if actor != expected_owner:
        raise PermissionError(
            f"Write denied for artifact '{name}'. "
            f"Expected owner: {expected_owner}, but got actor: {actor}. "
            f"Use ChangeRequest to modify this artifact instead."
        )

    # 规范化文本结尾（强制 \n 避免 diff 丑陋）
    if not content.endswith("\n"):
        content += "\n"

    # 根据状态机内部建构，确定在 state 里的 key (gdd, pm, eng, review)
    # 状态里对应的 key 是小写的： "gdd", "pm", "eng", "review"
    state_key_map = {
        "GDD": "gdd",
        "PROJECT_PLAN": "pm",
        "IMPLEMENTATION_PLAN": "eng",
        "REVIEW_REPORT": "review"
    }
    state_key = state_key_map[name]
    meta: ArtifactMeta = state.artifacts[state_key]

    # --- 2. 原子写文件 ---
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    except Exception as e:
        logger.error(f"Failed to write artifact {name} to {path}: {e}")
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise  # 写文件失败，中断，不更新 state

    # --- 3. 更新 state 内的元数据 ---
    new_hash = compute_hash(content)
    
    meta.version += 1
    meta.hash = new_hash
    meta.updated_at = _now_iso()
    meta.update_reason = reason
    
    # 写入 artifacts.log
    # 格式: ts | artifact | version | hash8 | actor | reason
    with open(ARTIFACTS_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{meta.updated_at}] | artifact={name} | v{meta.version} | hash={new_hash[:8]} | actor={actor} | reason={reason}\n")
    
    logger.info(f"Artifact {name} updated to v{meta.version} by {actor}.")
    return state

# --- 安全写入通道 (Dev Coaching 期间使用) ---

def write_dev_note(title: str, content: str) -> Path:
    """
    写入一封持续开发笔记 (Dev Notes)，例如 DECISIONS.md。
    这类文件位于 workspace/dev_notes/ 下，允许在冻结期间覆写或追加。
    """
    DEV_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    
    # 简单的清理处理，确保可用作文件名
    safe_title = "".join(c if c.isalnum() else "_" for c in title)
    filename = f"{safe_title}.md"
    path = DEV_NOTES_DIR / filename
    
    with open(path, "a", encoding="utf-8") as f: # 这里采追加模式，防盖掉历史
        f.write("\n\n" + f"# {_now_iso()}\n" + content + "\n")
        
    logger.info(f"Dev note saved to {path}.")
    return path


def write_patch(patch_id: str, content: str) -> Path:
    """
    写入一封变更补丁 (Patch)。
    位于 workspace/patches/ 下，记录改变建议，但不操作基线本身。
    """
    PATCHES_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"PATCH_{patch_id}.md"
    path = PATCHES_DIR / filename
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content + "\n")
        
    logger.info(f"Patch saved to {path}.")
    return path
