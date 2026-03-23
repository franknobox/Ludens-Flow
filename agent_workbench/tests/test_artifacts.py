import os
import shutil
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)

from ludens_flow.artifacts import (
    artifact_exists,
    read_artifact,
    write_artifact,
    write_dev_note,
    write_patch,
)
from ludens_flow.state import init_workspace, load_state, save_state


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        self.previous_project = os.environ.get("LUDENS_PROJECT_ID")
        self.workspace_root = (_ROOT / "workspace_test_artifacts").resolve()
        shutil.rmtree(self.workspace_root, ignore_errors=True)
        os.environ["LUDENS_WORKSPACE_DIR"] = str(self.workspace_root)
        os.environ.pop("LUDENS_PROJECT_ID", None)
        init_workspace()
        self.state = load_state()

    def tearDown(self):
        shutil.rmtree(self.workspace_root, ignore_errors=True)
        if self.previous_workspace is None:
            os.environ.pop("LUDENS_WORKSPACE_DIR", None)
        else:
            os.environ["LUDENS_WORKSPACE_DIR"] = self.previous_workspace

        if self.previous_project is None:
            os.environ.pop("LUDENS_PROJECT_ID", None)
        else:
            os.environ["LUDENS_PROJECT_ID"] = self.previous_project

    def test_write_artifact_updates_version_and_hash(self):
        write_artifact("GDD", "# Game Design Document\nThis is a test.", reason="Initial commit of GDD", actor="DesignAgent", state=self.state)
        write_artifact(
            "GDD",
            "# Game Design Document\nThis is a test.\n\nAdded new storylines.",
            reason="Update storyline",
            actor="DesignAgent",
            state=self.state,
        )

        self.assertEqual(self.state.artifacts["gdd"].version, 2)
        self.assertTrue(self.state.artifacts["gdd"].hash)

    def test_write_artifact_blocks_wrong_owner(self):
        with self.assertRaises(PermissionError):
            write_artifact("GDD", "Illegal inject", reason="Hack", actor="PMAgent", state=self.state)

    def test_write_artifact_rejects_unknown_name(self):
        with self.assertRaises(ValueError):
            write_artifact("INVALID_DOC", "...", reason="...", actor="DesignAgent", state=self.state)

    def test_read_artifact_recreates_missing_file(self):
        gdd_path = Path(self.state.artifacts["gdd"].path)
        gdd_path.unlink(missing_ok=True)

        lost_content = read_artifact("GDD", project_id=self.state.project_id)
        self.assertEqual(lost_content, "")
        self.assertTrue(artifact_exists("GDD", project_id=self.state.project_id))

    def test_freeze_blocks_canonical_artifacts_but_allows_side_channels(self):
        self.state.phase = "DEV_COACHING"
        self.state.artifact_frozen = True
        save_state(self.state)

        with self.assertRaises(PermissionError):
            write_artifact("GDD", "This should fail", reason="Try hack frozen state", actor="DesignAgent", state=self.state)

        note_path = write_dev_note("DECISIONS", "Decision 001: 缩减关卡数量。", project_id=self.state.project_id)
        patch_path = write_patch(
            "0001",
            "This patch proposes changes to the UI scheme without touching implementation_plan.md directly.",
            project_id=self.state.project_id,
        )

        self.assertTrue(note_path.exists())
        self.assertTrue(patch_path.exists())
        self.assertIn("Decision 001", note_path.read_text(encoding="utf-8"))
        self.assertIn("UI scheme", patch_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
