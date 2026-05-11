"""
Extract compact game content tags from finalized design artifacts.
"""

from __future__ import annotations

import re
from typing import Iterable


_TAG_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("类 PVZ", ("pvz", "植物大战僵尸", "类pvz")),
    ("塔防", ("塔防", "tower defense")),
    ("校园题材", ("校园", "学校", "大学", "深圳大学", "深大", "选课", "社团")),
    ("选课系统", ("选课", "课程")),
    ("社团 Buff", ("社团", "buff")),
    ("Roguelike", ("roguelike", "肉鸽")),
    ("卡牌", ("卡牌", "牌组", "deck")),
    ("解谜", ("解谜", "谜题", "puzzle")),
    ("平台跳跃", ("平台跳跃", "横版平台", "platformer")),
    ("动作", ("动作", "action")),
    ("射击", ("射击", "shooter", "弹幕")),
    ("冒险", ("冒险", "adventure")),
    ("叙事", ("叙事", "剧情", "故事", "文本冒险")),
    ("经营模拟", ("经营", "模拟经营", "management")),
    ("策略", ("策略", "战略", "战术", "strategy")),
    ("生存", ("生存", "survival")),
    ("恐怖", ("恐怖", "惊悚", "horror")),
    ("开放世界", ("开放世界", "open world")),
    ("2D", ("2d", "二维", "俯视角", "横版")),
    ("3D", ("3d", "三维")),
    ("像素风", ("像素", "pixel")),
    ("手绘风", ("手绘", "插画")),
)

_FIELD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:游戏类型|类型|题材|玩法类型|核心玩法)\s*[:：]\s*([^\n\r。；;]{2,40})", re.I),
    re.compile(r"(?:核心体验|卖点|关键词)\s*[:：]\s*([^\n\r。；;]{2,48})", re.I),
)


def _append_unique(tags: list[str], tag: str, *, limit: int = 4) -> None:
    cleaned = re.sub(r"\s+", " ", str(tag or "")).strip(" -#/，,。；;:：")
    if not cleaned or len(cleaned) > 16 or cleaned in tags:
        return
    tags.append(cleaned)
    if len(tags) > limit:
        del tags[limit:]


def _field_candidates(text: str) -> Iterable[str]:
    for pattern in _FIELD_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(1)
            for part in re.split(r"[/、,，|+＋]", raw):
                cleaned = part.strip(" -#/（）()[]【】")
                if 2 <= len(cleaned) <= 10:
                    yield cleaned


def extract_game_tags_from_gdd(content: str, *, limit: int = 4) -> list[str]:
    """Return 2-4 compact tags describing game content and genre.

    The extractor is deterministic on purpose: GDD finalization should not trigger
    another LLM request or make project metadata depend on a fragile response.
    """

    text = str(content or "").strip()
    if not text:
        return []

    lower = text.lower()
    tags: list[str] = []

    for tag, keywords in _TAG_RULES:
        if any(keyword.lower() in lower for keyword in keywords):
            _append_unique(tags, tag, limit=limit)

    for candidate in _field_candidates(text):
        if len(tags) >= limit:
            break
        if candidate.lower() in {"游戏", "项目", "demo", "mvp", "核心玩法"}:
            continue
        _append_unique(tags, candidate, limit=limit)

    if len(tags) == 1:
        _append_unique(tags, "玩法原型", limit=limit)

    return tags[:limit]
