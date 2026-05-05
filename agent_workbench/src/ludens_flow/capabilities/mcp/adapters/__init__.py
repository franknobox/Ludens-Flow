"""Engine-specific MCP adapter registry."""

from __future__ import annotations

from ludens_flow.capabilities.mcp.adapters.base import BaseEngineAdapter
from ludens_flow.capabilities.mcp.adapters.blender import BlenderEngineAdapter
from ludens_flow.capabilities.mcp.adapters.godot import GodotEngineAdapter
from ludens_flow.capabilities.mcp.adapters.unity import UnityEngineAdapter
from ludens_flow.capabilities.mcp.adapters.unreal import UnrealEngineAdapter


_ADAPTERS: dict[str, BaseEngineAdapter] = {
    "unity": UnityEngineAdapter(),
    "godot": GodotEngineAdapter(),
    "blender": BlenderEngineAdapter(),
    "unreal": UnrealEngineAdapter(),
}


def get_engine_adapter(engine: str) -> BaseEngineAdapter:
    return _ADAPTERS[engine]
