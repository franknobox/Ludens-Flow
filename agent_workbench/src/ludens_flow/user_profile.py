from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ludens_flow.paths import get_workspace_dir

logger = logging.getLogger(__name__)

# 用户画像文件的读写入口。
# 这里负责定位 USER_PROFILE.md、创建模板和合并追加条目。

def _find_workspace_dir(start_path: Optional[Path] = None) -> Path:
    """返回当前生效的工作区目录。"""
    _ = start_path
    return get_workspace_dir()


def _profile_path() -> Path:
    """返回 USER_PROFILE.md 路径，并确保工作区目录存在。"""
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
    """读取画像文件；缺失或空文件时自动补模板。"""
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
    """把新条目追加到 USER_PROFILE.md，跳过空值和重复内容。"""
    if not entries:
        return False

    # 先确保目标文件存在，再读取当前内容做去重。
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
    for entry in entries:
        value = entry.strip()
        if not value:
            continue
        if value in text:
            continue
        timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        appended_lines.append(f"- [{timestamp}] ({author}) {value}")
        changed = True

    if not changed:
        return False

    # 通过临时文件替换，避免半写入状态。
    new_text = text.rstrip() + "\n\n" + "\n".join(appended_lines) + "\n"
    try:
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
