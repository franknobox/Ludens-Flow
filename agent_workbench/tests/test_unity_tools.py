import os
import shutil
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)

from ludens_flow.paths import set_project_unity_root
from ludens_flow.state import init_workspace
from ludens_flow.tools.unity_files import unity_list_dir, unity_read_file


class UnityToolsTests(unittest.TestCase):
    def setUp(self):
        self.previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        self.previous_project = os.environ.get("LUDENS_PROJECT_ID")
        self.workspace_root = (_ROOT / "workspace_test_unity_tools").resolve()
        self.unity_root = (_ROOT / "unity_test_tools_project").resolve()
        shutil.rmtree(self.workspace_root, ignore_errors=True)
        shutil.rmtree(self.unity_root, ignore_errors=True)

        os.environ["LUDENS_WORKSPACE_DIR"] = str(self.workspace_root)
        os.environ.pop("LUDENS_PROJECT_ID", None)

        init_workspace(project_id="alpha")
        (self.unity_root / "Assets" / "Scripts").mkdir(parents=True, exist_ok=True)
        (self.unity_root / "ProjectSettings").mkdir(parents=True, exist_ok=True)
        (self.unity_root / "Assets" / "Scripts" / "Player.cs").write_text(
            "public class Player {}\n",
            encoding="utf-8",
        )
        set_project_unity_root(str(self.unity_root), project_id="alpha")

    def tearDown(self):
        shutil.rmtree(self.workspace_root, ignore_errors=True)
        shutil.rmtree(self.unity_root, ignore_errors=True)
        if self.previous_workspace is None:
            os.environ.pop("LUDENS_WORKSPACE_DIR", None)
        else:
            os.environ["LUDENS_WORKSPACE_DIR"] = self.previous_workspace

        if self.previous_project is None:
            os.environ.pop("LUDENS_PROJECT_ID", None)
        else:
            os.environ["LUDENS_PROJECT_ID"] = self.previous_project

    def test_unity_list_dir_reads_bound_root(self):
        output = unity_list_dir(project_id="alpha")
        self.assertIn("Assets/", output)
        self.assertIn("ProjectSettings/", output)

    def test_unity_read_file_reads_text_file(self):
        output = unity_read_file("Assets/Scripts/Player.cs", project_id="alpha")
        self.assertIn("public class Player", output)

    def test_unity_read_file_blocks_path_escape(self):
        with self.assertRaises(RuntimeError):
            unity_read_file("../secret.txt", project_id="alpha")


if __name__ == "__main__":
    unittest.main()
