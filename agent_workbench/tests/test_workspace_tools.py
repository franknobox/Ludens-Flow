import os
import shutil
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)

from ludens_flow.core.paths import add_project_workspace
from ludens_flow.core.state import init_workspace
from ludens_flow.capabilities.tools.registry import dispatch_tool_call
from ludens_flow.capabilities.tools.workspace_files import (
    workspace_read_files_batch,
    workspace_write_text_file,
)
from ludens_flow.capabilities.workspaces import (
    WorkspaceAccessError,
    resolve_workspace_binding,
)


class WorkspaceToolsTests(unittest.TestCase):
    def setUp(self):
        self.previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        self.previous_project = os.environ.get("LUDENS_PROJECT_ID")
        self.workspace_root = (_ROOT / "workspace_test_workspace_tools").resolve()
        self.generic_root = (_ROOT / "generic_test_workspace_tools").resolve()
        self.second_root = (_ROOT / "second_test_workspace_tools").resolve()

        shutil.rmtree(self.workspace_root, ignore_errors=True)
        shutil.rmtree(self.generic_root, ignore_errors=True)
        shutil.rmtree(self.second_root, ignore_errors=True)

        os.environ["LUDENS_WORKSPACE_DIR"] = str(self.workspace_root)
        os.environ.pop("LUDENS_PROJECT_ID", None)

        init_workspace(project_id="alpha")
        (self.generic_root / "Scripts").mkdir(parents=True, exist_ok=True)
        (self.generic_root / "Scripts" / "A.cs").write_text(
            "public class A {}\n", encoding="utf-8"
        )
        (self.generic_root / "Scripts" / "B.cs").write_text(
            "public class B {}\n", encoding="utf-8"
        )
        add_project_workspace(
            str(self.generic_root),
            project_id="alpha",
            kind="generic",
            workspace_id="generic-main",
            label="Main Generic",
            writable=True,
        )

    def tearDown(self):
        shutil.rmtree(self.workspace_root, ignore_errors=True)
        shutil.rmtree(self.generic_root, ignore_errors=True)
        shutil.rmtree(self.second_root, ignore_errors=True)
        if self.previous_workspace is None:
            os.environ.pop("LUDENS_WORKSPACE_DIR", None)
        else:
            os.environ["LUDENS_WORKSPACE_DIR"] = self.previous_workspace

        if self.previous_project is None:
            os.environ.pop("LUDENS_PROJECT_ID", None)
        else:
            os.environ["LUDENS_PROJECT_ID"] = self.previous_project

    def test_workspace_read_files_batch_reads_multiple_files(self):
        output = workspace_read_files_batch(
            ["Scripts/A.cs", "Scripts/B.cs"],
            project_id="alpha",
            workspace_id="generic-main",
        )
        self.assertIn("Files Read: 2", output)
        self.assertIn("[Attached Workspace File] Scripts/A.cs", output)
        self.assertIn("public class B", output)

    def test_workspace_binding_without_workspace_id_is_ambiguous_when_multiple_exist(self):
        (self.second_root / "Docs").mkdir(parents=True, exist_ok=True)
        add_project_workspace(
            str(self.second_root),
            project_id="alpha",
            kind="generic",
            workspace_id="generic-two",
            label="Second Generic",
            writable=False,
        )
        with self.assertRaises(WorkspaceAccessError) as ctx:
            resolve_workspace_binding("alpha")
        self.assertEqual(ctx.exception.code, "WORKSPACE_AMBIGUOUS")

    def test_workspace_write_text_file_requires_writable_workspace_and_emits_events(self):
        events: list[dict] = []
        output = dispatch_tool_call(
            "workspace_write_text_file",
            {
                "workspace_id": "generic-main",
                "path": "Scripts/Generated.cs",
                "content": "public class Generated {}\n",
            },
            project_id="alpha",
            tool_event_handler=events.append,
        )
        self.assertIn("Result: created", output)
        self.assertTrue((self.generic_root / "Scripts" / "Generated.cs").exists())
        self.assertEqual(
            [event["type"] for event in events],
            ["tool_progress", "file_changed"],
        )

    def test_workspace_write_text_file_rejects_disallowed_extensions(self):
        with self.assertRaises(WorkspaceAccessError) as ctx:
            workspace_write_text_file(
                "Scenes/Main.unity",
                "invalid",
                project_id="alpha",
                workspace_id="generic-main",
            )
        self.assertEqual(ctx.exception.code, "FILE_TYPE_NOT_ALLOWED")

    def test_workspace_read_files_batch_rejects_absolute_paths(self):
        with self.assertRaises(WorkspaceAccessError) as ctx:
            workspace_read_files_batch(
                [str((self.generic_root / "Scripts" / "A.cs").resolve())],
                project_id="alpha",
                workspace_id="generic-main",
            )
        self.assertEqual(ctx.exception.code, "ABSOLUTE_PATH_NOT_ALLOWED")


if __name__ == "__main__":
    unittest.main()
