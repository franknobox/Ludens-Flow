import os
import shutil
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)

from ludens_flow.user_profile import _profile_path, load_profile, update_profile


class UserProfileWorkspaceTests(unittest.TestCase):
    def test_profile_path_uses_workspace_override(self):
        previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        override_workspace = (_ROOT / "workspace_test_user_profile").resolve()

        try:
            shutil.rmtree(override_workspace, ignore_errors=True)
            os.environ["LUDENS_WORKSPACE_DIR"] = str(override_workspace)

            profile_path = _profile_path()
            self.assertEqual(profile_path, override_workspace / "USER_PROFILE.md")

            text = load_profile()
            self.assertTrue(text.strip())
            self.assertTrue(profile_path.exists())

            changed = update_profile(["nickname: OverrideTester"], author="test")
            self.assertTrue(changed)
            self.assertIn("OverrideTester", profile_path.read_text(encoding="utf-8"))
        finally:
            if previous_workspace is None:
                os.environ.pop("LUDENS_WORKSPACE_DIR", None)
            else:
                os.environ["LUDENS_WORKSPACE_DIR"] = previous_workspace
            shutil.rmtree(override_workspace, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
