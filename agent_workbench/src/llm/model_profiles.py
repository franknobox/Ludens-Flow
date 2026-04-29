"""
文件功能：模型 Provider Profile 解析层，从环境变量读取可复用的供应商连接配置。
核心内容：解析 LUDENS_MODEL_PROFILES JSON，输出不含明文 key 的安全摘要与路由用配置。
关联文件：llm/modelrouter.py, ludens_flow/app/api.py
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

MODEL_PROFILES_ENV_VAR = "LUDENS_MODEL_PROFILES"


def _normalize_profile_id(value: Any) -> str:
    return str(value or "").strip()


def _normalize_profile_entry(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}

    entry: Dict[str, Any] = {}

    provider = str(raw.get("provider") or "").strip().lower()
    if provider:
        entry["provider"] = provider

    base_url = str(raw.get("base_url") or "").strip()
    if base_url:
        entry["base_url"] = base_url

    api_key_env = str(raw.get("api_key_env") or "").strip()
    if api_key_env:
        entry["api_key_env"] = api_key_env

    return entry


def load_model_profiles() -> Dict[str, Dict[str, Any]]:
    """Load provider profiles from LUDENS_MODEL_PROFILES.

    Expected format:
    {"openai_main":{"provider":"openai","base_url":"...","api_key_env":"OPENAI_API_KEY"}}
    """

    raw = str(os.getenv(MODEL_PROFILES_ENV_VAR) or "").strip()
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    if not isinstance(parsed, dict):
        return {}

    profiles: Dict[str, Dict[str, Any]] = {}
    for key, value in parsed.items():
        profile_id = _normalize_profile_id(key)
        if not profile_id:
            continue
        entry = _normalize_profile_entry(value)
        if entry:
            profiles[profile_id] = entry

    return profiles


def get_model_profile(profile_id: str) -> Optional[Dict[str, Any]]:
    normalized = _normalize_profile_id(profile_id)
    if not normalized:
        return None
    return load_model_profiles().get(normalized)


def list_model_profile_summaries() -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for profile_id, entry in load_model_profiles().items():
        api_key_env = str(entry.get("api_key_env") or "").strip()
        summaries.append(
            {
                "id": profile_id,
                "provider": entry.get("provider") or "",
                "base_url": entry.get("base_url") or "",
                "has_api_key": bool(api_key_env and os.getenv(api_key_env)),
            }
        )
    return summaries
