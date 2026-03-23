import os
import shutil
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)

from ludens_flow.artifacts import read_artifact, write_artifact
from ludens_flow.paths import (
    create_project,
    get_active_project_id,
    get_project_dir,
    get_workspace_root_dir,
    list_projects,
    set_active_project_id,
)
from ludens_flow.state import init_workspace, load_state, save_state
from ludens_flow.user_profile import _profile_path, load_profile, update_profile


class MultiProjectWorkspaceTests(unittest.TestCase):
    def test_profile_path_defaults_into_first_project(self):
        previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        previous_project = os.environ.get("LUDENS_PROJECT_ID")
        workspace_root = (_ROOT / "workspace_test_user_profile").resolve()
        shutil.rmtree(workspace_root, ignore_errors=True)

        try:
            os.environ["LUDENS_WORKSPACE_DIR"] = str(workspace_root)
            os.environ.pop("LUDENS_PROJECT_ID", None)

            profile_path = _profile_path()
            self.assertEqual(profile_path, get_project_dir("project-1") / "USER_PROFILE.md")

            text = load_profile()
            self.assertTrue(text.strip())
            self.assertTrue(profile_path.exists())

            changed = update_profile(["nickname: OverrideTester"], author="test")
            self.assertTrue(changed)
            self.assertIn("OverrideTester", profile_path.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(workspace_root, ignore_errors=True)
            if previous_workspace is None:
                os.environ.pop("LUDENS_WORKSPACE_DIR", None)
            else:
                os.environ["LUDENS_WORKSPACE_DIR"] = previous_workspace
            if previous_project is None:
                os.environ.pop("LUDENS_PROJECT_ID", None)
            else:
                os.environ["LUDENS_PROJECT_ID"] = previous_project

    def test_init_workspace_auto_creates_first_project(self):
        previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        previous_project = os.environ.get("LUDENS_PROJECT_ID")
        workspace_root = (_ROOT / "workspace_test_auto_project").resolve()
        shutil.rmtree(workspace_root, ignore_errors=True)

        try:
            os.environ["LUDENS_WORKSPACE_DIR"] = str(workspace_root)
            os.environ.pop("LUDENS_PROJECT_ID", None)

            init_workspace()
            state = load_state()

            self.assertEqual(state.project_id, "project-1")
            self.assertEqual(get_active_project_id(), "project-1")
            self.assertTrue((workspace_root / "projects" / "project-1").exists())
            self.assertEqual([item["id"] for item in list_projects()], ["project-1"])
        finally:
            shutil.rmtree(workspace_root, ignore_errors=True)
            if previous_workspace is None:
                os.environ.pop("LUDENS_WORKSPACE_DIR", None)
            else:
                os.environ["LUDENS_WORKSPACE_DIR"] = previous_workspace
            if previous_project is None:
                os.environ.pop("LUDENS_PROJECT_ID", None)
            else:
                os.environ["LUDENS_PROJECT_ID"] = previous_project

    def test_named_projects_use_isolated_directories_and_files(self):
        previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        previous_project = os.environ.get("LUDENS_PROJECT_ID")
        workspace_root = (_ROOT / "workspace_test_multi_project").resolve()
        shutil.rmtree(workspace_root, ignore_errors=True)

        try:
            os.environ["LUDENS_WORKSPACE_DIR"] = str(workspace_root)
            os.environ.pop("LUDENS_PROJECT_ID", None)

            alpha = create_project("alpha")
            beta = create_project("beta")

            init_workspace(project_id=alpha["id"])
            alpha_state = load_state(project_id=alpha["id"])
            alpha_state.phase = "PM_DISCUSS"
            save_state(alpha_state, project_id=alpha["id"])
            write_artifact("GDD", "alpha gdd", reason="test", actor="DesignAgent", state=alpha_state, project_id=alpha["id"])
            update_profile(["nickname: Alpha"], author="test", project_id=alpha["id"])

            init_workspace(project_id=beta["id"])
            beta_state = load_state(project_id=beta["id"])
            beta_state.phase = "ENG_DISCUSS"
            save_state(beta_state, project_id=beta["id"])
            write_artifact("GDD", "beta gdd", reason="test", actor="DesignAgent", state=beta_state, project_id=beta["id"])
            update_profile(["nickname: Beta"], author="test", project_id=beta["id"])

            self.assertEqual(read_artifact("GDD", project_id="alpha"), "alpha gdd\n")
            self.assertEqual(read_artifact("GDD", project_id="beta"), "beta gdd\n")
            self.assertIn("Alpha", load_profile(project_id="alpha"))
            self.assertIn("Beta", load_profile(project_id="beta"))
            self.assertNotEqual(load_state(project_id="alpha").phase, load_state(project_id="beta").phase)

            self.assertEqual(get_project_dir("alpha"), get_workspace_root_dir() / "projects" / "alpha")
            self.assertEqual(get_project_dir("beta"), get_workspace_root_dir() / "projects" / "beta")
            self.assertEqual({item["id"] for item in list_projects()}, {"alpha", "beta"})
        finally:
            shutil.rmtree(workspace_root, ignore_errors=True)

        if previous_workspace is None:
            os.environ.pop("LUDENS_WORKSPACE_DIR", None)
        else:
            os.environ["LUDENS_WORKSPACE_DIR"] = previous_workspace

        if previous_project is None:
            os.environ.pop("LUDENS_PROJECT_ID", None)
        else:
            os.environ["LUDENS_PROJECT_ID"] = previous_project

    def test_active_project_switches_default_state_scope(self):
        previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        previous_project = os.environ.get("LUDENS_PROJECT_ID")
        workspace_root = (_ROOT / "workspace_test_multi_project_active").resolve()
        shutil.rmtree(workspace_root, ignore_errors=True)

        try:
            os.environ["LUDENS_WORKSPACE_DIR"] = str(workspace_root)
            os.environ.pop("LUDENS_PROJECT_ID", None)

            create_project("alpha")
            create_project("beta")

            set_active_project_id("alpha")
            init_workspace()
            alpha_state = load_state()
            alpha_state.phase = "PM_DISCUSS"
            save_state(alpha_state)

            set_active_project_id("beta")
            init_workspace()
            beta_state = load_state()
            self.assertEqual(beta_state.project_id, "beta")
            self.assertEqual(beta_state.phase, "GDD_DISCUSS")

            set_active_project_id("alpha")
            self.assertEqual(load_state().phase, "PM_DISCUSS")
        finally:
            shutil.rmtree(workspace_root, ignore_errors=True)

        if previous_workspace is None:
            os.environ.pop("LUDENS_WORKSPACE_DIR", None)
        else:
            os.environ["LUDENS_WORKSPACE_DIR"] = previous_workspace

        if previous_project is None:
            os.environ.pop("LUDENS_PROJECT_ID", None)
        else:
            os.environ["LUDENS_PROJECT_ID"] = previous_project


if __name__ == "__main__":
    unittest.main()
