"""Health checks for project-level external MCP servers.

The checker starts a configured MCP stdio process, performs a minimal
initialize + tools/list exchange, and returns a sanitized status payload.
It does not register or expose external tools to Ludens agents.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Iterable, List


MCP_PROTOCOL_VERSION = "2024-11-05"
DEFAULT_TIMEOUT_SECONDS = 8


def _jsonrpc_request(message_id: int, method: str, params: dict | None = None) -> dict:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": message_id,
        "method": method,
    }
    if params is not None:
        payload["params"] = params
    return payload


def _jsonrpc_notification(method: str, params: dict | None = None) -> dict:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": method,
    }
    if params is not None:
        payload["params"] = params
    return payload


def _frame_message(payload: dict) -> str:
    body = json.dumps(payload, ensure_ascii=False)
    body_bytes = body.encode("utf-8")
    return f"Content-Length: {len(body_bytes)}\r\n\r\n{body}"


def _build_stdio_input() -> str:
    initialize = _jsonrpc_request(
        1,
        "initialize",
        {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "Ludens-Flow", "version": "0.1.0"},
        },
    )
    initialized = _jsonrpc_notification("notifications/initialized")
    tools_list = _jsonrpc_request(2, "tools/list", {})
    return "".join(
        [_frame_message(initialize), _frame_message(initialized), _frame_message(tools_list)]
    )


def _parse_content_length_messages(output: str) -> List[dict]:
    messages: list[dict] = []
    index = 0
    while index < len(output):
        header_end = output.find("\r\n\r\n", index)
        separator_len = 4
        if header_end < 0:
            header_end = output.find("\n\n", index)
            separator_len = 2
        if header_end < 0:
            break

        headers = output[index:header_end]
        content_length = None
        for line in headers.splitlines():
            name, _, value = line.partition(":")
            if name.strip().lower() == "content-length":
                try:
                    content_length = int(value.strip())
                except ValueError:
                    content_length = None
                break

        if content_length is None:
            index = header_end + separator_len
            continue

        body_start = header_end + separator_len
        body = output[body_start : body_start + content_length]
        if len(body.encode("utf-8")) < content_length:
            break
        try:
            messages.append(json.loads(body))
        except json.JSONDecodeError:
            pass
        index = body_start + len(body)
    return messages


def _parse_line_messages(output: str) -> List[dict]:
    messages: list[dict] = []
    for line in output.splitlines():
        text = line.strip()
        if not text.startswith("{"):
            continue
        try:
            messages.append(json.loads(text))
        except json.JSONDecodeError:
            continue
    return messages


def _parse_mcp_messages(output: str) -> List[dict]:
    messages = _parse_content_length_messages(output)
    if messages:
        return messages
    return _parse_line_messages(output)


def _safe_tool_summary(raw_tools: Any) -> List[dict]:
    if not isinstance(raw_tools, list):
        return []
    tools: list[dict] = []
    for item in raw_tools:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        tools.append(
            {
                "name": name,
                "description": str(item.get("description") or "").strip(),
            }
        )
    return tools


def _result_for_config(config: dict, *, status: str, message: str = "", tools: list[dict] | None = None) -> dict:
    return {
        "id": str(config.get("id") or ""),
        "engine": str(config.get("engine") or ""),
        "label": str(config.get("label") or ""),
        "enabled": bool(config.get("enabled", True)),
        "configured": bool(str(config.get("command") or "").strip()),
        "status": status,
        "message": message,
        "tools": tools or [],
        "tool_count": len(tools or []),
    }


def check_mcp_connection(config: dict, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict:
    command = str(config.get("command") or "").strip()
    if not bool(config.get("enabled", True)):
        return _result_for_config(config, status="configured", message="Connection is disabled.")
    if not command:
        return _result_for_config(config, status="not_configured", message="Command is empty.")

    args = [str(item) for item in config.get("args", []) if str(item).strip()]
    env = os.environ.copy()
    raw_env = config.get("env", {})
    if isinstance(raw_env, dict):
        env.update({str(key): str(value) for key, value in raw_env.items()})

    try:
        completed = subprocess.run(
            [command, *args],
            input=_build_stdio_input(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env=env,
            shell=False,
        )
    except FileNotFoundError:
        return _result_for_config(config, status="failed", message=f"Command not found: {command}")
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + "\n" + (exc.stderr or "")
        messages = _parse_mcp_messages(output)
        tools = _tools_from_messages(messages)
        if tools:
            return _result_for_config(config, status="tools_loaded", tools=tools)
        return _result_for_config(config, status="failed", message="Health check timed out.")
    except Exception as exc:
        return _result_for_config(config, status="failed", message=str(exc))

    output = f"{completed.stdout or ''}\n{completed.stderr or ''}"
    messages = _parse_mcp_messages(output)
    tools = _tools_from_messages(messages)
    if tools:
        return _result_for_config(config, status="tools_loaded", tools=tools)

    if any(message.get("id") == 1 and "result" in message for message in messages):
        return _result_for_config(config, status="reachable", message="Initialized, but no tools were returned.")

    error_message = _first_error_message(messages)
    if not error_message:
        error_message = (completed.stderr or completed.stdout or "No MCP response.").strip()
    if completed.returncode == 0 and not error_message:
        error_message = "Process exited without listing tools."
    return _result_for_config(config, status="failed", message=error_message[:500])


def _tools_from_messages(messages: Iterable[dict]) -> List[dict]:
    for message in messages:
        if message.get("id") != 2:
            continue
        result = message.get("result")
        if isinstance(result, dict):
            tools = _safe_tool_summary(result.get("tools"))
            if tools:
                return tools
    return []


def _first_error_message(messages: Iterable[dict]) -> str:
    for message in messages:
        error = message.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error)
    return ""


def check_mcp_connections(configs: Iterable[dict]) -> List[dict]:
    return [check_mcp_connection(config) for config in configs]

