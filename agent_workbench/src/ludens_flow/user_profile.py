from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


# 该函数尝试向上查找包含 "workspace" 子目录的路径，作为仓库根路径的可靠标志。如果找不到，则回退到当前工作目录下的 "workspace"。
def _find_workspace_dir(start_path: Optional[Path] = None) -> Path:
    """向上查找包含 'workspace' 子目录的仓库根路径，失败则使用 cwd."""
    p = start_path or Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        candidate = parent / "workspace"
        if candidate.exists() and candidate.is_dir():
            return candidate
    # fallback: repo root guess (two levels up) or cwd
    guess = Path(__file__).resolve().parents[3] / "workspace"
    if guess.exists():
        return guess
    return Path.cwd() / "workspace"


def _profile_path() -> Path:
    ws = _find_workspace_dir()
    ws.mkdir(parents=True, exist_ok=True)
    return ws / "USER_PROFILE.md"


_TEMPLATE = """
这是自动维护的用户画像文件。由各 Agent 提议变更，最终写入由系统合并。

## 基本信息
- 昵称：
- 偏好：
- 项目上下文：

## Agent 观察笔记
""".lstrip()


def load_profile(max_chars: int = 2000) -> str:
    """读取 USER_PROFILE.md 的文本，若不存在则创建骨架并返回模板。
    返回文本会被截断到 max_chars 以控制注入长度。
    """
    path = _profile_path()
    if not path.exists():
        try:
            path.write_text(_TEMPLATE, encoding="utf-8")
            logger.info(f"Created new USER_PROFILE at {path}")
        except Exception as e:
            logger.error(f"Failed to create profile template: {e}")
            return _TEMPLATE[:max_chars]

    try:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            path.write_text(_TEMPLATE, encoding="utf-8")
            return _TEMPLATE[:max_chars]
        return text[:max_chars]
    except Exception as e:
        logger.error(f"Failed to read profile: {e}")
        return _TEMPLATE[:max_chars]


def update_profile(entries: List[str], author: str = "agent") -> bool:
    """将一组条目合并写入 USER_PROFILE.md，避免重复。

    每个 entry 为一行文本（例如 'nickname: Alice'），函数会检查条目是否已经存在（简单 substring 检测），
    如果不存在则追加到文件末尾的“自动更新记录”区块，并写入时间戳与作者标识。
    返回 True 表示发生了写入，False 表示没有变化。
    """
    if not entries:
        return False

    path = _profile_path()
    try:
        if not path.exists():
            path.write_text(_TEMPLATE, encoding="utf-8")
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to prepare profile for update: {e}")
        return False

    changed = False
    appended_lines: List[str] = []
    for e in entries:
        s = e.strip()
        if not s:
            continue
        # 简单去重：若文本已存在于文件中（包含），则视为重复
        if s in text:
            continue
        timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        line = f"- [{timestamp}] ({author}) {s}"
        appended_lines.append(line)
        changed = True

    if not changed:
        return False

    # 找到自动更新区块的插入点（在末尾添加）
    new_text = text.rstrip() + "\n\n" + "\n".join(appended_lines) + "\n"
    try:
        # 原子写入
        tmp = path.with_suffix(".tmp")
        tmp.write_text(new_text, encoding="utf-8")
        tmp.replace(path)
        logger.info(f"USER_PROFILE updated with {len(appended_lines)} entries")
        return True
    except Exception as e:
        logger.error(f"Failed to write USER_PROFILE: {e}")
        return False


if __name__ == "__main__":
    print(load_profile(500))
    print(update_profile(["nickname: Tester", "likes: short replies"]))
