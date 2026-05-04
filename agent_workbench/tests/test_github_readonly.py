import os
import shutil
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)

from ludens_flow.capabilities.github import parse_github_repo_ref
from ludens_flow.core.paths import (
    add_project_workspace,
    create_project,
    get_project_github_repo,
    list_project_workspaces,
    set_active_project_id,
    set_project_github_repo,
)


class GitHubReadonlyTests(unittest.TestCase):
    def test_parse_github_repo_ref_accepts_common_forms(self):
        self.assertEqual(
            parse_github_repo_ref("franknobox/Ludens-Flow")["repo"],
            "Ludens-Flow",
        )
        self.assertEqual(
            parse_github_repo_ref("https://github.com/franknobox/Ludens-Flow.git")["owner"],
            "franknobox",
        )
        self.assertEqual(
            parse_github_repo_ref("git@github.com:franknobox/Ludens-Flow.git")["url"],
            "https://github.com/franknobox/Ludens-Flow",
        )

    def test_project_github_repo_does_not_clear_workspaces(self):
        previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        previous_project = os.environ.get("LUDENS_PROJECT_ID")
        workspace_root = (_ROOT / "workspace_test_github").resolve()
        project_root = (workspace_root / "external_project").resolve()
        shutil.rmtree(workspace_root, ignore_errors=True)

        try:
            os.environ["LUDENS_WORKSPACE_DIR"] = str(workspace_root)
            os.environ.pop("LUDENS_PROJECT_ID", None)
            project_root.mkdir(parents=True)

            create_project("alpha", set_active=True)
            set_active_project_id("alpha")
            add_project_workspace(
                str(project_root),
                project_id="alpha",
                kind="generic",
                workspace_id="generic-main",
                label="External Project",
                writable=True,
                enabled=True,
            )
            set_project_github_repo(
                {"owner": "franknobox", "repo": "Ludens-Flow"},
                project_id="alpha",
            )

            self.assertEqual(
                get_project_github_repo(project_id="alpha")["repo"],
                "Ludens-Flow",
            )
            self.assertEqual(
                len(list_project_workspaces(project_id="alpha", include_disabled=True)),
                1,
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


if __name__ == "__main__":
    unittest.main()
