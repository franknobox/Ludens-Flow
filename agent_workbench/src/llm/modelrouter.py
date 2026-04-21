"""
文件功能：模型路由解析器，按项目配置为不同 Agent/能力解析最终模型参数。
核心内容：按 global -> agents -> capabilities -> agent_capabilities 的优先级合并路由。
核心内容：结合环境默认值和项目 settings，输出可直接执行的 LLMConfig。
关联文件：ludens_flow/core/graph.py, ludens_flow/core/paths.py, llm/provider.py
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from llm.provider import LLMConfig, build_config
from ludens_flow.core.paths import get_project_settings


def _normalize_route_entry(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}

    entry: Dict[str, Any] = {}
    for key in ("provider", "model", "base_url", "api_key_env"):
        value = str(raw.get(key) or "").strip()
        if value:
            entry[key] = value

    if "provider" in entry:
        entry["provider"] = entry["provider"].lower()

    if "temperature" in raw and raw.get("temperature") is not None:
        try:
            entry["temperature"] = float(raw.get("temperature"))
        except (TypeError, ValueError):
            pass

    return entry


def _merge_route(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key in ("provider", "model", "base_url", "temperature", "api_key_env"):
        if key in override and override[key] not in (None, ""):
            merged[key] = override[key]
    return merged


def _resolved_route_from_settings(
    settings: Dict[str, Any], agent_key: str, capability: str
) -> Dict[str, Any]:
    routing = settings.get("model_routing")
    if not isinstance(routing, dict):
        return {}

    normalized_agent = str(agent_key or "").strip().lower()
    normalized_capability = str(capability or "").strip().lower()

    route: Dict[str, Any] = {}
    route = _merge_route(route, _normalize_route_entry(routing.get("global")))

    agents = routing.get("agents")
    if isinstance(agents, dict):
        route = _merge_route(
            route, _normalize_route_entry(agents.get(normalized_agent))
        )

    capabilities = routing.get("capabilities")
    if isinstance(capabilities, dict):
        route = _merge_route(
            route, _normalize_route_entry(capabilities.get(normalized_capability))
        )

    agent_capabilities = routing.get("agent_capabilities")
    if isinstance(agent_capabilities, dict):
        capability_map = agent_capabilities.get(normalized_agent)
        if isinstance(capability_map, dict):
            route = _merge_route(
                route,
                _normalize_route_entry(capability_map.get(normalized_capability)),
            )

    return route


def resolve_model_config(
    *,
    project_id: Optional[str],
    agent_key: str,
    capability: str,
    default_route: Optional[Dict[str, Any]] = None,
    capability_defaults: Optional[Dict[str, Dict[str, Any]]] = None,
) -> LLMConfig:
    """Resolve provider/model with priority: default -> project global -> agent -> capability -> agent+capability."""

    base_cfg = build_config(strict=False)
    route: Dict[str, Any] = {
        "provider": base_cfg.provider,
        "model": base_cfg.model,
        "base_url": base_cfg.base_url,
        "temperature": base_cfg.temperature,
    }

    route = _merge_route(route, _normalize_route_entry(default_route))

    if isinstance(capability_defaults, dict):
        route = _merge_route(
            route,
            _normalize_route_entry(capability_defaults.get(str(capability or "").strip().lower())),
        )

    settings: Dict[str, Any] = {}
    try:
        settings = get_project_settings(project_id=project_id)
    except Exception:
        settings = {}

    route = _merge_route(
        route,
        _resolved_route_from_settings(settings, agent_key=agent_key, capability=capability),
    )

    explicit_api_key = None
    api_key_env = str(route.get("api_key_env") or "").strip()
    if api_key_env:
        explicit_api_key = (os.getenv(api_key_env) or "").strip() or None

    return build_config(
        provider=route.get("provider") or base_cfg.provider,
        model=route.get("model") or base_cfg.model,
        base_url=route.get("base_url"),
        temperature=route.get("temperature"),
        api_key=explicit_api_key,
        strict=False,
    )
