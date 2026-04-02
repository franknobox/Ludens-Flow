import os
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)

import ludens_flow.state as st
from ludens_flow.paths import get_images_dir


class WorkspaceResetTests(unittest.TestCase):
    def test_reset_current_project_state_clears_images_and_state(self):
        previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        try:
            with tempfile.TemporaryDirectory() as td:
                os.environ["LUDENS_WORKSPACE_DIR"] = str((Path(td) / "workspace_reset_test").resolve())

                st.init_workspace()
                images_dir = get_images_dir()
                self.assertTrue(images_dir.exists())

                (images_dir / "test.png").write_bytes(b"mock-image-bytes")
                nested_dir = images_dir / "nested"
                nested_dir.mkdir(parents=True, exist_ok=True)
                (nested_dir / "keep.txt").write_text("to-be-removed", encoding="utf-8")

                state = st.load_state()
                state.phase = "PM_DISCUSS"
                st.save_state(state)
                self.assertTrue(st.get_state_file().exists())

                reset_state = st.reset_current_project_state(clear_images=True)

                self.assertEqual(reset_state.phase, "GDD_DISCUSS")
                self.assertFalse(st.get_state_file().exists())
                self.assertTrue(images_dir.exists())
                self.assertEqual(list(images_dir.iterdir()), [])
        finally:
            if previous_workspace is None:
                os.environ.pop("LUDENS_WORKSPACE_DIR", None)
            else:
                os.environ["LUDENS_WORKSPACE_DIR"] = previous_workspace


if __name__ == "__main__":
    unittest.main()
