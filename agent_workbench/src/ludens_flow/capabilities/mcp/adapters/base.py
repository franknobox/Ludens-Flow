"""Base classes for engine-specific MCP adapters."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class EngineMcpCall:
    tool_name: str
    arguments: Dict[str, Any]
    operation_name: str


class BaseEngineAdapter:
    engine: str = ""
    operation_names: Dict[str, str] = {}
    tool_candidates: Dict[str, List[str]] = {}

    def map_call(
        self,
        capability: str,
        args: Dict[str, Any],
        available_tools: List[dict],
        *,
        project_id: str | None = None,
    ) -> Optional[EngineMcpCall]:
        tool_name = self.select_underlying_tool(capability, available_tools)
        if not tool_name:
            return None
        tool_schema = next(
            (tool for tool in available_tools if str(tool.get("name") or "") == tool_name),
            {},
        )
        return EngineMcpCall(
            tool_name=tool_name,
            arguments=self.to_underlying_arguments(
                capability,
                args,
                tool_name,
                tool_schema=tool_schema,
                project_id=project_id,
            ),
            operation_name=self.operation_name(capability),
        )

    def operation_name(self, capability: str) -> str:
        return self.operation_names.get(capability, capability.replace("engine_", "engine."))

    def select_underlying_tool(self, capability: str, available_tools: List[dict]) -> str:
        names = [str(tool.get("name") or "") for tool in available_tools]
        candidates = self.tool_candidates.get(capability, [])
        normalized_names = {_normalize_tool_name(name): name for name in names}

        for candidate in candidates:
            if candidate in names:
                return candidate
            normalized = _normalize_tool_name(candidate)
            if normalized in normalized_names:
                return normalized_names[normalized]

        capability_hint = capability.removeprefix("engine_")
        for name in names:
            normalized = _normalize_tool_name(name)
            if _normalize_tool_name(capability_hint) in normalized:
                return name
        return ""

    def to_underlying_arguments(
        self,
        capability: str,
        args: Dict[str, Any],
        tool_name: str,
        *,
        tool_schema: dict | None = None,
        project_id: str | None = None,
    ) -> Dict[str, Any]:
        return {
            key: value
            for key, value in args.items()
            if key not in {"engine", "connection_id"} and value is not None
        }

    def fallback_arguments(
        self,
        capability: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        return []


def _normalize_tool_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())
