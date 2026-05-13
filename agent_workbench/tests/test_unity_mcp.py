"""Unity MCP stdio health check test (requires Unity Editor running)."""
import json
import unittest

from ludens_flow.capabilities.mcp import health as mcp_health


class UnityMcpStdioTests(unittest.TestCase):
    def setUp(self):
        mcp_health.clear_mcp_connection_cache()

    def tearDown(self):
        mcp_health.clear_mcp_connection_cache()

    def test_unity_stdio_health_check(self):
        """Verify Unity MCP responds over stdio with initialize + tools/list."""
        config = {
            "id": "unity-stdio-test",
            "engine": "unity",
            "command": "uvx",
            "args": ["--from", "mcpforunityserver", "mcp-for-unity"],
            "enabled": True,
        }

        result = mcp_health.check_mcp_connection(
            config, use_cache=False, timeout_seconds=90
        )

        status = result.get("status", "")
        transport = result.get("transport", "")
        tools = result.get("tools", [])
        tool_count = result.get("tool_count", 0)
        message = result.get("message", "")

        print(f"\nStatus: {status}")
        print(f"Transport: {transport}")
        print(f"Tools: {tool_count}")
        print(f"Message: {message}")
        if tools:
            for t in tools[:5]:
                print(f"  - {t['name']}")

        self.assertIn(status, ("tools_loaded", "reachable"),
                      f"Expected tools_loaded or reachable, got {status}: {message}")
        if status == "tools_loaded":
            self.assertGreater(tool_count, 0, "Should have tools when tools_loaded")
            self.assertEqual(transport, "line")


if __name__ == "__main__":
    unittest.main()
