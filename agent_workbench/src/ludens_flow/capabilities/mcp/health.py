"""Health checks for project-level external MCP servers.

The checker starts a configured MCP stdio process, performs a minimal
initialize + tools/list exchange, and returns a sanitized status payload.
It does not register or expose external tools to Ludens agents.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from copy import deepcopy
from typing import Any, Iterable, List


MCP_PROTOCOL_VERSION = "2024-11-05"
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_HEALTH_CACHE_TTL_SECONDS = 30
_TRANSPORT_CACHE: dict[str, str] = {}
_HEALTH_CACHE: dict[str, tuple[float, dict]] = {}
_HTTP_SESSIONS: dict[str, str] = {}


def _is_http_command(command: str) -> bool:
    cmd = str(command or "").strip().lower()
    return cmd.startswith(("http://", "https://"))


class McpClientError(RuntimeError):
    pass


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


def _frame_message(payload: dict) -> bytes:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


def _serialize_messages(messages: list[dict], *, transport: str) -> bytes:
    if transport == "line":
        return b"".join(
            json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n"
            for message in messages
        )
    return b"".join(_frame_message(message) for message in messages)


def _build_stdio_input(*, transport: str = "framed") -> bytes:
    initialize = _jsonrpc_request(
        1,
        "initialize",
        {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "Ludens-Flow", "version": "2.9.9"},
        },
    )
    initialized = _jsonrpc_notification("notifications/initialized")
    tools_list = _jsonrpc_request(2, "tools/list", {})
    return _serialize_messages([initialize, initialized, tools_list], transport=transport)


def _build_tool_call_input(
    tool_name: str,
    arguments: dict | None = None,
    *,
    transport: str = "framed",
) -> bytes:
    initialize = _jsonrpc_request(
        1,
        "initialize",
        {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "Ludens-Flow", "version": "2.9.9"},
        },
    )
    initialized = _jsonrpc_notification("notifications/initialized")
    tool_call = _jsonrpc_request(
        2,
        "tools/call",
        {
            "name": tool_name,
            "arguments": arguments or {},
        },
    )
    return _serialize_messages([initialize, initialized, tool_call], transport=transport)


def _to_bytes(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8", errors="replace")
    return str(value).encode("utf-8", errors="replace")


def _decode_output(value: Any) -> str:
    return _to_bytes(value).decode("utf-8", errors="replace")


def _combined_output(stdout: Any, stderr: Any) -> bytes:
    return _to_bytes(stdout) + b"\n" + _to_bytes(stderr)


def _parse_content_length_messages(output: bytes | str) -> List[dict]:
    raw = _to_bytes(output)
    messages: list[dict] = []
    index = 0
    lowered = raw.lower()
    while index < len(raw):
        header_start = lowered.find(b"content-length:", index)
        if header_start < 0:
            break

        header_end = raw.find(b"\r\n\r\n", header_start)
        separator_len = 4
        if header_end < 0:
            header_end = raw.find(b"\n\n", header_start)
            separator_len = 2
        if header_end < 0:
            break

        headers = raw[header_start:header_end].decode("ascii", errors="ignore")
        content_length = None
        for line in headers.splitlines():
            name, _, value = line.partition(":")
            if name.strip().lower() == "content-length":
                try:
                    content_length = int(value.strip())
                except ValueError:
                    content_length = None
                break

        if content_length is None or content_length < 0:
            index = header_end + separator_len
            continue

        body_start = header_end + separator_len
        body = raw[body_start : body_start + content_length]
        if len(body) < content_length:
            break
        try:
            messages.append(json.loads(body.decode("utf-8")))
        except json.JSONDecodeError:
            pass
        index = body_start + content_length
    return messages


def _parse_line_messages(output: bytes | str) -> List[dict]:
    raw = _to_bytes(output)
    messages: list[dict] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text.startswith(b"{"):
            continue
        try:
            messages.append(json.loads(text.decode("utf-8")))
        except json.JSONDecodeError:
            continue
    return messages


def _parse_mcp_messages(output: bytes | str) -> List[dict]:
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
        summary = {
            "name": name,
            "description": str(item.get("description") or "").strip(),
        }
        input_schema = item.get("inputSchema")
        if isinstance(input_schema, dict):
            summary["inputSchema"] = input_schema
        tools.append(summary)
    return tools


def _parse_sse(response_bytes: bytes) -> list[dict]:
    messages = []
    current_data = []
    for line in response_bytes.decode("utf-8").splitlines():
        if line.startswith("data: "):
            current_data.append(line[6:])
        elif line.strip() == "" and current_data:
            payload = json.loads("".join(current_data))
            messages.append(payload)
            current_data = []
    if current_data:
        payload = json.loads("".join(current_data))
        messages.append(payload)
    return messages


def _http_post_jsonrpc(
    base_url: str,
    payload: dict,
    *,
    timeout: int = 20,
    session_id: str = "",
) -> tuple[list[dict], str]:
    url = base_url.rstrip("/") + "/mcp"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream, */*",
    }
    if session_id:
        headers["mcp-session-id"] = session_id
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            new_session = resp.headers.get("mcp-session-id", session_id)
            return _parse_sse(resp.read()), str(new_session or session_id)
    except urllib.error.HTTPError as exc:
        try:
            error_body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            error_body = {}
        return [{
            "jsonrpc": "2.0",
            "id": payload.get("id"),
            "error": {
                "code": exc.code,
                "message": str(error_body.get("message") or error_body or exc.reason),
            },
        }], session_id
    except Exception as exc:
        return [{"jsonrpc": "2.0", "id": payload.get("id"), "error": {"message": str(exc)}}], session_id


def _result_for_config(
    config: dict,
    *,
    status: str,
    message: str = "",
    tools: list[dict] | None = None,
    transport: str = "",
) -> dict:
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
        "transport": transport,
    }


def _connection_cache_key(config: dict) -> str:
    relevant = {
        "id": config.get("id") or "",
        "engine": config.get("engine") or "",
        "enabled": bool(config.get("enabled", True)),
        "command": config.get("command") or "",
        "args": config.get("args") or [],
        "env": config.get("env") or {},
    }
    return json.dumps(relevant, ensure_ascii=False, sort_keys=True, default=str)


def _remember_transport(config: dict, transport: str) -> None:
    if transport in {"line", "framed", "http"}:
        _TRANSPORT_CACHE[_connection_cache_key(config)] = transport


def _transport_candidates(config: dict, preferred: str | None = None) -> list[str]:
    candidates: list[str] = []
    cached = _TRANSPORT_CACHE.get(_connection_cache_key(config))
    configured = str(config.get("transport") or "").strip()
    for item in (preferred, cached, configured):
        if item and item not in candidates:
            candidates.append(item)
    if _is_http_command(str(config.get("command") or "")) and "http" not in candidates:
        candidates.append("http")
    for item in ("line", "framed"):
        if item not in candidates:
            candidates.append(item)
    return candidates


def clear_mcp_connection_cache() -> None:
    _TRANSPORT_CACHE.clear()
    _HEALTH_CACHE.clear()


def _get_cached_health_result(config: dict, ttl_seconds: int) -> dict | None:
    cached = _HEALTH_CACHE.get(_connection_cache_key(config))
    if not cached:
        return None
    created_at, result = cached
    if time.monotonic() - created_at > ttl_seconds:
        _HEALTH_CACHE.pop(_connection_cache_key(config), None)
        return None
    return deepcopy(result)


def _remember_health_result(config: dict, result: dict) -> dict:
    if result.get("status") in {"tools_loaded", "reachable"}:
        _HEALTH_CACHE[_connection_cache_key(config)] = (time.monotonic(), deepcopy(result))
    return result


def check_mcp_connection(
    config: dict,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    use_cache: bool = True,
    cache_ttl_seconds: int = DEFAULT_HEALTH_CACHE_TTL_SECONDS,
) -> dict:
    command = str(config.get("command") or "").strip()
    if not bool(config.get("enabled", True)):
        return _result_for_config(config, status="configured", message="Connection is disabled.")
    if not command:
        return _result_for_config(config, status="not_configured", message="Command is empty.")

    if use_cache:
        cached = _get_cached_health_result(config, cache_ttl_seconds)
        if cached is not None:
            return cached

    if _is_http_command(command):
        try:
            cache_key = _connection_cache_key(config)
            session_id = _HTTP_SESSIONS.get(cache_key, "")
            init_messages, session_id = _http_post_jsonrpc(
                command,
                _jsonrpc_request(1, "initialize", {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "Ludens-Flow", "version": "3.0.0"},
                }),
                timeout=timeout_seconds,
                session_id=session_id,
            )
            init_result = next((m for m in init_messages if m.get("id") == 1), {})
            if "error" in init_result:
                return _result_for_config(
                    config,
                    status="failed",
                    message=str(init_result.get("error", {}).get("message", "HTTP MCP initialize failed.")),
                )

            _http_post_jsonrpc(
                command,
                _jsonrpc_notification("notifications/initialized"),
                timeout=timeout_seconds,
                session_id=session_id,
            )

            tools_messages, session_id = _http_post_jsonrpc(
                command,
                _jsonrpc_request(2, "tools/list", {}),
                timeout=timeout_seconds,
                session_id=session_id,
            )
            tools_result = next((m for m in tools_messages if m.get("id") == 2), {})
            if "error" in tools_result:
                return _result_for_config(
                    config,
                    status="reachable",
                    message=str(tools_result.get("error", {}).get("message", "HTTP MCP tools/list failed.")),
                    transport="http",
                )

            _HTTP_SESSIONS[cache_key] = session_id
            tools = _safe_tool_summary(tools_result.get("result", {}).get("tools"))
            if tools:
                _remember_transport(config, "http")
                return _remember_health_result(
                    config,
                    _result_for_config(config, status="tools_loaded", tools=tools, transport="http"),
                )
            _remember_transport(config, "http")
            return _remember_health_result(
                config,
                _result_for_config(
                    config,
                    status="reachable",
                    message="Initialized, but no tools were returned.",
                    transport="http",
                ),
            )
        except Exception as exc:
            return _result_for_config(config, status="failed", message=f"HTTP MCP error: {exc}")

    args = [str(item) for item in config.get("args", []) if str(item).strip()]
    env = os.environ.copy()
    raw_env = config.get("env", {})
    if isinstance(raw_env, dict):
        env.update({str(key): str(value) for key, value in raw_env.items()})

    last_error = ""
    initialized_without_tools = False
    for transport in _transport_candidates(config):
        if transport == "http":
            continue
        try:
            completed = subprocess.run(
                [command, *args],
                input=_build_stdio_input(transport=transport),
                capture_output=True,
                timeout=timeout_seconds,
                env=env,
                shell=False,
            )
        except FileNotFoundError:
            return _result_for_config(config, status="failed", message=f"Command not found: {command}")
        except subprocess.TimeoutExpired as exc:
            output = _combined_output(exc.stdout, exc.stderr)
            messages = _parse_mcp_messages(output)
            tools = _tools_from_messages(messages)
            if tools:
                _remember_transport(config, transport)
                return _remember_health_result(
                    config,
                    _result_for_config(config, status="tools_loaded", tools=tools, transport=transport),
                )
            last_error = "Health check timed out."
            continue
        except Exception as exc:
            last_error = str(exc)
            continue

        output = _combined_output(completed.stdout, completed.stderr)
        messages = _parse_mcp_messages(output)
        tools = _tools_from_messages(messages)
        if tools:
            _remember_transport(config, transport)
            return _remember_health_result(
                config,
                _result_for_config(config, status="tools_loaded", tools=tools, transport=transport),
            )

        if any(message.get("id") == 1 and "result" in message for message in messages):
            initialized_without_tools = True
            _remember_transport(config, transport)
            continue

        error_message = _first_error_message(messages)
        if not error_message:
            error_message = (_decode_output(completed.stderr) or _decode_output(completed.stdout) or "No MCP response.").strip()
        if completed.returncode == 0 and not error_message:
            error_message = "Process exited without listing tools."
        last_error = error_message[:500]

    if initialized_without_tools:
        transport = _TRANSPORT_CACHE.get(_connection_cache_key(config), "")
        return _remember_health_result(
            config,
            _result_for_config(
                config,
                status="reachable",
                message="Initialized, but no tools were returned.",
                transport=transport,
            ),
        )
    return _result_for_config(config, status="failed", message=last_error)


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


def call_mcp_tool(
    config: dict,
    tool_name: str,
    arguments: dict | None = None,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    transport: str | None = None,
) -> dict:
    command = str(config.get("command") or "").strip()
    if not bool(config.get("enabled", True)):
        raise McpClientError("MCP connection is disabled.")
    if not command:
        raise McpClientError("MCP command is empty.")

    if _is_http_command(command):
        try:
            cache_key = _connection_cache_key(config)
            session_id = _HTTP_SESSIONS.get(cache_key, "")
            messages, session_id = _http_post_jsonrpc(
                command,
                _jsonrpc_request(2, "tools/call", {"name": tool_name, "arguments": arguments or {}}),
                timeout=timeout_seconds,
                session_id=session_id,
            )
            _HTTP_SESSIONS[cache_key] = session_id
            result = next((m for m in messages if m.get("id") == 2), {})
            if "error" in result:
                error = result["error"]
                raise McpClientError(str(error.get("message") or error))
            return result.get("result", {})
        except McpClientError:
            raise
        except Exception as exc:
            raise McpClientError(f"HTTP MCP tool call failed: {exc}") from exc

    args = [str(item) for item in config.get("args", []) if str(item).strip()]
    env = os.environ.copy()
    raw_env = config.get("env", {})
    if isinstance(raw_env, dict):
        env.update({str(key): str(value) for key, value in raw_env.items()})

    last_error = ""
    for candidate_transport in _transport_candidates(config, preferred=transport):
        if candidate_transport == "http":
            continue
        try:
            completed = subprocess.run(
                [command, *args],
                input=_build_tool_call_input(tool_name, arguments, transport=candidate_transport),
                capture_output=True,
                timeout=timeout_seconds,
                env=env,
                shell=False,
            )
            output = _combined_output(completed.stdout, completed.stderr)
        except FileNotFoundError as exc:
            raise McpClientError(f"Command not found: {command}") from exc
        except subprocess.TimeoutExpired as exc:
            output = _combined_output(exc.stdout, exc.stderr)
            messages = _parse_mcp_messages(output)
            result, rpc_error = _result_from_messages(messages)
            if result is not None:
                _remember_transport(config, candidate_transport)
                return result
            if rpc_error:
                raise McpClientError(rpc_error)
            last_error = "MCP tool call timed out."
            continue

        messages = _parse_mcp_messages(output)
        result, rpc_error = _result_from_messages(messages)
        if result is not None:
            _remember_transport(config, candidate_transport)
            return result
        if rpc_error:
            raise McpClientError(rpc_error)

        error_message = _first_error_message(messages)
        if not error_message:
            error_message = (_decode_output(completed.stderr) or _decode_output(completed.stdout) or "No MCP response.").strip()
        last_error = error_message[:500]

    raise McpClientError(last_error)


def _result_from_messages(messages: Iterable[dict]) -> tuple[dict | None, str]:
    for message in messages:
        if message.get("id") != 2:
            continue
        if "result" in message and isinstance(message.get("result"), dict):
            return message["result"], ""
        error = message.get("error")
        if isinstance(error, dict):
            if "data" in error:
                return None, json.dumps(error, ensure_ascii=False)
            return None, str(error.get("message") or error)
    return None, ""
