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
from ludens_flow import api
from ludens_flow.artifacts import read_artifact, write_artifact
from ludens_flow.paths import create_project
from ludens_flow.state import STATE_SCHEMA_VERSION


class ApiProjectLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        self.previous_project = os.environ.get("LUDENS_PROJECT_ID")
        self.workspace_root = (_ROOT / "workspace_test_api_project_lifecycle").resolve()
        shutil.rmtree(self.workspace_root, ignore_errors=True)
        os.environ["LUDENS_WORKSPACE_DIR"] = str(self.workspace_root)
        os.environ.pop("LUDENS_PROJECT_ID", None)
        st.init_workspace()

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

    def test_state_endpoint_contains_schema_version(self):
        payload = api.get_state()
        self.assertEqual(payload.get("schema_version"), STATE_SCHEMA_VERSION)
        self.assertTrue(payload.get("project_id"))

    def test_export_import_endpoints_roundtrip(self):
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

    def test_import_endpoint_requires_overwrite_for_nonempty_target(self):
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


if __name__ == "__main__":
    unittest.main()
