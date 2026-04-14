import json
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
    PROJECT_META_SCHEMA_VERSION,
    create_project,
    get_logs_dir,
    get_project_dir,
    get_project_meta_file,
    list_projects,
)
from ludens_flow.state import (
    STATE_SCHEMA_VERSION,
    export_project_bundle,
    import_project_bundle,
    init_workspace,
    load_state,
    migrate_legacy_workspace_to_project,
    save_state,
)


class ProjectLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        self.previous_project = os.environ.get("LUDENS_PROJECT_ID")
        self.workspace_root = (_ROOT / "workspace_test_project_lifecycle").resolve()
        shutil.rmtree(self.workspace_root, ignore_errors=True)
        os.environ["LUDENS_WORKSPACE_DIR"] = str(self.workspace_root)
        os.environ.pop("LUDENS_PROJECT_ID", None)
        init_workspace()

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

    def test_state_schema_migrates_legacy_payload(self):
        create_project("legacy")
        state_file = get_project_dir("legacy") / "state.json"
        state_file.write_text(
            json.dumps({"project_id": "legacy", "phase": "PM_DISCUSS"}),
            encoding="utf-8",
        )

        state = load_state(project_id="legacy")
        self.assertEqual(state.schema_version, STATE_SCHEMA_VERSION)
        self.assertEqual(state.phase, "PM_DISCUSS")

        persisted = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertEqual(persisted.get("schema_version"), STATE_SCHEMA_VERSION)

        audit_log = (get_logs_dir("legacy") / "audit.log").read_text(encoding="utf-8")
        self.assertIn("event=STATE_SCHEMA_MIGRATION", audit_log)

    def test_project_meta_schema_migrates_legacy_file(self):
        create_project("alpha")
        meta_file = get_project_meta_file("alpha")
        meta_file.write_text(
            json.dumps({"id": "alpha", "title": "Alpha Legacy"}),
            encoding="utf-8",
        )

        items = {item["id"]: item for item in list_projects()}
        self.assertEqual(
            items["alpha"].get("schema_version"), PROJECT_META_SCHEMA_VERSION
        )

        persisted = json.loads(meta_file.read_text(encoding="utf-8"))
        self.assertEqual(persisted.get("schema_version"), PROJECT_META_SCHEMA_VERSION)
        self.assertEqual(persisted.get("display_name"), "Alpha Legacy")

        audit_log = (get_logs_dir("alpha") / "audit.log").read_text(encoding="utf-8")
        self.assertIn("event=PROJECT_META_SCHEMA_MIGRATION", audit_log)

    def test_workspace_legacy_migration_writes_audit_log(self):
        legacy_gdd = self.workspace_root / "GDD.md"
        legacy_gdd.write_text("legacy gdd", encoding="utf-8")

        moved = migrate_legacy_workspace_to_project("project-1")
        self.assertIn("GDD.md", moved)

        migrated_gdd = get_project_dir("project-1") / "GDD.md"
        self.assertEqual(migrated_gdd.read_text(encoding="utf-8"), "legacy gdd")

        audit_log = (get_logs_dir("project-1") / "audit.log").read_text(
            encoding="utf-8"
        )
        self.assertIn("event=WORKSPACE_MIGRATION", audit_log)

    def test_project_export_import_roundtrip(self):
        create_project("alpha", set_active=True)
        init_workspace(project_id="alpha")
        alpha_state = load_state(project_id="alpha")
        alpha_state.phase = "ENG_DISCUSS"
        save_state(alpha_state, project_id="alpha")

        write_artifact(
            "GDD",
            "alpha gdd",
            reason="test",
            actor="DesignAgent",
            state=alpha_state,
            project_id="alpha",
        )

        bundle_path = self.workspace_root / "exports"
        bundle = export_project_bundle(bundle_path, project_id="alpha")
        self.assertTrue(bundle.exists())

        imported = import_project_bundle(
            bundle,
            project_id="beta",
            set_active=False,
            overwrite=True,
        )
        self.assertEqual(imported, "beta")

        beta_state = load_state(project_id="beta")
        self.assertEqual(beta_state.phase, "ENG_DISCUSS")
        self.assertEqual(read_artifact("GDD", project_id="beta"), "alpha gdd\n")

        alpha_audit = (get_logs_dir("alpha") / "audit.log").read_text(encoding="utf-8")
        beta_audit = (get_logs_dir("beta") / "audit.log").read_text(encoding="utf-8")
        self.assertIn("event=PROJECT_EXPORT", alpha_audit)
        self.assertIn("event=PROJECT_IMPORT", beta_audit)


if __name__ == "__main__":
    unittest.main()
