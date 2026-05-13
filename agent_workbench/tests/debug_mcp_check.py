import json
import sys
sys.path.insert(0, "agent_workbench/src")

from ludens_flow.capabilities.mcp.health import check_mcp_connection

# 模拟用户保存的 HTTP 配置
config = {
    "id": "unity-mcp",
    "engine": "unity",
    "label": "Unity MCP",
    "command": "http://127.0.0.1:8080",
    "args": [],
    "env": {},
    "enabled": True,
}

print(f"Command: {config['command']}")
print(f"Is HTTP: {config['command'].startswith(('http://', 'https://'))}")
print()

result = check_mcp_connection(config, use_cache=False)
print(f"Status: {result.get('status')}")
print(f"Message: {result.get('message')}")
print(f"Tool count: {result.get('tool_count')}")
print(f"Transport: {result.get('transport')}")
print(f"Tools: {[t.get('name') for t in result.get('tools', [])][:10]}")
