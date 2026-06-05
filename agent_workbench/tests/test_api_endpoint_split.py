import os
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.environ.setdefault(
    "LUDENS_WORKSPACE_DIR",
    str((Path(tempfile.gettempdir()) / "ludens_flow_tests" / "test_api_endpoint_split").resolve()),
)

from ludens_flow.app.api import app


class ApiEndpointSplitTests(unittest.TestCase):
    def test_api_route_endpoints_are_registered_from_feature_modules(self):
        expected_modules = {
            "/api/state": "ludens_flow.app.api.chat",
            "/api/chat": "ludens_flow.app.api.chat",
            "/api/actions": "ludens_flow.app.api.chat",
            "/api/reset": "ludens_flow.app.api.chat",
            "/api/projects": "ludens_flow.app.api.projects",
            "/api/projects/{project_id}/select": "ludens_flow.app.api.projects",
            "/api/projects/current/settings": "ludens_flow.app.api.settings",
            "/api/projects/current/workspaces": "ludens_flow.app.api.workspaces",
            "/api/workspace/files": "ludens_flow.app.api.workspaces",
            "/api/projects/current/copywriting/generate": "ludens_flow.app.api.copywriting",
            "/api/projects/{project_id}/events": "ludens_flow.app.api.events",
        }

        routes_by_path = {getattr(route, "path", ""): route for route in app.routes}
        for path, module_name in expected_modules.items():
            with self.subTest(path=path):
                self.assertIn(path, routes_by_path)
                endpoint = getattr(routes_by_path[path], "endpoint", None)
                self.assertIsNotNone(endpoint)
                self.assertEqual(endpoint.__module__, module_name)


if __name__ == "__main__":
    unittest.main()
