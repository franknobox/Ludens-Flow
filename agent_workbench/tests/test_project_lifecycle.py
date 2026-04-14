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

import ludens_flow.state as st
import ludens_flow.app.api as api
from ludens_flow.app.artifacts import read_artifact, write_artifact
from ludens_flow.paths import (
    PROJECT_META_SCHEMA_VERSION,
    archive_project,
    create_project,
    delete_project,
    get_active_project_id,
    get_logs_dir,
    get_project_dir,
    get_project_meta_file,
    list_active_projects,
    list_archived_projects,
    list_projects,
    rename_project,
    restore_project,
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

    def test_state_endpoint_contains_schema_version(self):
        payload = api.get_state()
        self.assertEqual(payload.get("schema_version"), STATE_SCHEMA_VERSION)
        self.assertTrue(payload.get("project_id"))

    def test_api_export_import_endpoints_roundtrip(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        alpha_state = st.load_state(project_id="alpha")
        alpha_state.phase = "ENG_DISCUSS"
        st.save_state(alpha_state, project_id="alpha")

        write_artifact(
            "GDD",
            "alpha gdd",
            reason="test",
            actor="DesignAgent",
            state=alpha_state,
            project_id="alpha",
        )

        export_resp = api.post_export_current_project(
            api.ProjectExportRequest(output_path=str(self.workspace_root / "exports"))
        )
        bundle_path = Path(export_resp["bundle_path"])
        self.assertTrue(bundle_path.exists())

        import_resp = api.post_import_project_bundle(
            api.ProjectImportRequest(
                bundle_path=str(bundle_path),
                project_id="beta",
                set_active=False,
                overwrite=True,
            )
        )
        self.assertEqual(import_resp["project_id"], "beta")
        self.assertEqual(import_resp["state"]["phase"], "ENG_DISCUSS")
        self.assertEqual(import_resp["state"]["schema_version"], STATE_SCHEMA_VERSION)
        self.assertEqual(read_artifact("GDD", project_id="beta"), "alpha gdd\n")

    def test_api_import_requires_overwrite_for_nonempty_target(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        alpha_state = st.load_state(project_id="alpha")
        write_artifact(
            "GDD",
            "alpha gdd",
            reason="test",
            actor="DesignAgent",
            state=alpha_state,
            project_id="alpha",
        )
        export_resp = api.post_export_current_project(
            api.ProjectExportRequest(output_path=str(self.workspace_root / "exports"))
        )

        create_project("beta", set_active=False)
        beta_state = st.load_state(project_id="beta")
        write_artifact(
            "GDD",
            "beta existing",
            reason="test",
            actor="DesignAgent",
            state=beta_state,
            project_id="beta",
        )

        with self.assertRaises(RuntimeError):
            api.post_import_project_bundle(
                api.ProjectImportRequest(
                    bundle_path=export_resp["bundle_path"],
                    project_id="beta",
                    set_active=False,
                    overwrite=False,
                )
            )

    def test_archiving_active_project_moves_it_to_history_and_switches_active(self):
        create_project("alpha", set_active=True)
        archived = archive_project("alpha")

        self.assertTrue(archived["archived"])
        self.assertEqual([item["id"] for item in list_archived_projects()], ["alpha"])
        self.assertNotEqual(get_active_project_id(), "alpha")
        self.assertTrue(list_active_projects())

    def test_restore_project_removes_it_from_history(self):
        create_project("alpha", set_active=True)
        archive_project("alpha")

        restored = restore_project("alpha", set_active=False)

        self.assertFalse(restored["archived"])
        self.assertEqual([item["id"] for item in list_archived_projects()], [])
        self.assertIn("alpha", {item["id"] for item in list_active_projects()})

    def test_rename_project_updates_display_name(self):
        create_project("alpha", display_name="Alpha", set_active=False)

        renamed = rename_project("alpha", "Alpha Renamed")

        self.assertEqual(renamed["display_name"], "Alpha Renamed")
        listed = {item["id"]: item for item in list_projects()}
        self.assertEqual(listed["alpha"]["display_name"], "Alpha Renamed")

    def test_delete_project_requires_archived_status(self):
        create_project("alpha", set_active=False)
        with self.assertRaises(RuntimeError):
            delete_project("alpha")

        archive_project("alpha")
        deleted = delete_project("alpha")
        self.assertEqual(deleted, "alpha")
        self.assertFalse(get_project_dir("alpha").exists())

    def test_api_project_lists_split_active_and_archived(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        api.post_project(api.ProjectRequest(project_id="beta"))
        api.post_archive_project("alpha")

        payload = api.get_projects()

        self.assertEqual(payload["active_project"], get_active_project_id())
        self.assertIn("beta", {item["id"] for item in payload["active_projects"]})
        self.assertIn("alpha", {item["id"] for item in payload["archived_projects"]})

    def test_api_restore_and_delete_archived_project(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        api.post_project(api.ProjectRequest(project_id="beta"))
        api.post_archive_project("alpha")

        restored = api.post_restore_project(
            "alpha", api.ProjectRestoreRequest(set_active=False)
        )
        self.assertIn("alpha", {item["id"] for item in restored["active_projects"]})
        self.assertEqual(restored["archived_projects"], [])

        api.post_archive_project("alpha")
        deleted = api.delete_archived_project("alpha")
        self.assertEqual(deleted["deleted_project"], "alpha")
        self.assertNotIn("alpha", {item["id"] for item in deleted["archived_projects"]})

    def test_api_rename_project_updates_project_lists(self):
        api.post_project(api.ProjectRequest(project_id="alpha", display_name="Alpha"))

        renamed = api.post_rename_project(
            "alpha", api.ProjectRenameRequest(display_name="Alpha Prime")
        )

        project_lookup = {item["id"]: item for item in renamed["projects"]}
        self.assertEqual(project_lookup["alpha"]["display_name"], "Alpha Prime")


if __name__ == "__main__":
    unittest.main()
