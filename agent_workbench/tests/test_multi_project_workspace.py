import os
import shutil
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)

from ludens_flow.app.artifacts import read_artifact, write_artifact
from ludens_flow.paths import (
    clear_project_unity_root,
    create_project,
    get_active_project_id,
    get_project_dir,
    get_project_unity_root,
    get_workspace_root_dir,
    list_projects,
    set_project_unity_root,
    set_active_project_id,
)
from ludens_flow.state import init_workspace, load_state, save_state
from ludens_flow.context.user_profile import _profile_path, load_profile, update_profile


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
            self.assertEqual(
                profile_path, get_project_dir("project-1") / "USER_PROFILE.md"
            )

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
            write_artifact(
                "GDD",
                "alpha gdd",
                reason="test",
                actor="DesignAgent",
                state=alpha_state,
                project_id=alpha["id"],
            )
            update_profile(["nickname: Alpha"], author="test", project_id=alpha["id"])

            init_workspace(project_id=beta["id"])
            beta_state = load_state(project_id=beta["id"])
            beta_state.phase = "ENG_DISCUSS"
            save_state(beta_state, project_id=beta["id"])
            write_artifact(
                "GDD",
                "beta gdd",
                reason="test",
                actor="DesignAgent",
                state=beta_state,
                project_id=beta["id"],
            )
            update_profile(["nickname: Beta"], author="test", project_id=beta["id"])

            self.assertEqual(read_artifact("GDD", project_id="alpha"), "alpha gdd\n")
            self.assertEqual(read_artifact("GDD", project_id="beta"), "beta gdd\n")
            self.assertIn("Alpha", load_profile(project_id="alpha"))
            self.assertIn("Beta", load_profile(project_id="beta"))
            self.assertNotEqual(
                load_state(project_id="alpha").phase,
                load_state(project_id="beta").phase,
            )

            self.assertEqual(
                get_project_dir("alpha"),
                get_workspace_root_dir() / "projects" / "alpha",
            )
            self.assertEqual(
                get_project_dir("beta"), get_workspace_root_dir() / "projects" / "beta"
            )
            self.assertEqual(
                {item["id"] for item in list_projects()}, {"alpha", "beta"}
            )
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

    def test_project_metadata_tracks_phase_and_last_message(self):
        previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        previous_project = os.environ.get("LUDENS_PROJECT_ID")
        workspace_root = (_ROOT / "workspace_test_project_meta").resolve()
        shutil.rmtree(workspace_root, ignore_errors=True)

        try:
            os.environ["LUDENS_WORKSPACE_DIR"] = str(workspace_root)
            os.environ.pop("LUDENS_PROJECT_ID", None)

            meta = create_project("alpha", display_name="Alpha Board", set_active=True)
            self.assertEqual(meta["display_name"], "Alpha Board")

            init_workspace(project_id="alpha")
            state = load_state(project_id="alpha")
            state.phase = "ENG_COMMIT"
            state.last_assistant_message = (
                "Need one more pass on movement tuning and hit feedback."
            )
            save_state(state, project_id="alpha")

            listed = {item["id"]: item for item in list_projects()}
            self.assertEqual(listed["alpha"]["display_name"], "Alpha Board")
            self.assertEqual(listed["alpha"]["last_phase"], "ENG_COMMIT")
            self.assertIn("movement tuning", listed["alpha"]["last_message_preview"])
            self.assertFalse(listed["alpha"]["archived"])
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

    def test_project_can_bind_and_unbind_unity_root(self):
        previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        previous_project = os.environ.get("LUDENS_PROJECT_ID")
        workspace_root = (_ROOT / "workspace_test_unity_binding").resolve()
        unity_root = (_ROOT / "unity_test_project").resolve()
        shutil.rmtree(workspace_root, ignore_errors=True)
        shutil.rmtree(unity_root, ignore_errors=True)

        try:
            os.environ["LUDENS_WORKSPACE_DIR"] = str(workspace_root)
            os.environ.pop("LUDENS_PROJECT_ID", None)

            (unity_root / "Assets").mkdir(parents=True, exist_ok=True)
            (unity_root / "ProjectSettings").mkdir(parents=True, exist_ok=True)

            create_project("alpha", set_active=True)
            bound_meta = set_project_unity_root(str(unity_root), project_id="alpha")

            self.assertEqual(bound_meta["unity_root"], str(unity_root))
            self.assertEqual(
                get_project_unity_root(project_id="alpha"), str(unity_root)
            )
            self.assertEqual(list_projects()[0]["unity_root"], str(unity_root))

            cleared_meta = clear_project_unity_root(project_id="alpha")
            self.assertEqual(cleared_meta["unity_root"], "")
            self.assertIsNone(get_project_unity_root(project_id="alpha"))
        finally:
            shutil.rmtree(workspace_root, ignore_errors=True)
            shutil.rmtree(unity_root, ignore_errors=True)
            if previous_workspace is None:
                os.environ.pop("LUDENS_WORKSPACE_DIR", None)
            else:
                os.environ["LUDENS_WORKSPACE_DIR"] = previous_workspace
            if previous_project is None:
                os.environ.pop("LUDENS_PROJECT_ID", None)
            else:
                os.environ["LUDENS_PROJECT_ID"] = previous_project

    def test_init_workspace_migrates_legacy_root_files_into_project_one(self):
        previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        previous_project = os.environ.get("LUDENS_PROJECT_ID")
        workspace_root = (_ROOT / "workspace_test_legacy_migration").resolve()
        shutil.rmtree(workspace_root, ignore_errors=True)

        try:
            os.environ["LUDENS_WORKSPACE_DIR"] = str(workspace_root)
            os.environ.pop("LUDENS_PROJECT_ID", None)

            workspace_root.mkdir(parents=True, exist_ok=True)
            (workspace_root / "state.json").write_text(
                '{"phase": "PM_DISCUSS"}', encoding="utf-8"
            )
            (workspace_root / "GDD.md").write_text("legacy gdd", encoding="utf-8")
            (workspace_root / "USER_PROFILE.md").write_text(
                "legacy profile", encoding="utf-8"
            )
            (workspace_root / "images").mkdir(parents=True, exist_ok=True)
            (workspace_root / "images" / "legacy.png").write_bytes(b"legacy-image")

            init_workspace()

            project_one = get_project_dir("project-1")
            self.assertFalse((workspace_root / "state.json").exists())
            self.assertFalse((workspace_root / "GDD.md").exists())
            self.assertFalse((workspace_root / "USER_PROFILE.md").exists())
            self.assertFalse((workspace_root / "images" / "legacy.png").exists())

            self.assertTrue((project_one / "state.json").exists())
            self.assertEqual(
                (project_one / "GDD.md").read_text(encoding="utf-8"), "legacy gdd"
            )
            self.assertEqual(
                (project_one / "USER_PROFILE.md").read_text(encoding="utf-8"),
                "legacy profile",
            )
            self.assertTrue((project_one / "images" / "legacy.png").exists())
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
