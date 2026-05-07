"""
文件功能：项目生命周期测试集合，覆盖 API 与状态存储的关键路径。
核心内容：验证创建/切换/归档/导入导出/设置更新等项目级行为。
核心内容：确保 schema 迁移、审计日志与 workspace 管理逻辑稳定可回归。
"""

import json
import os
import shutil
import subprocess
import sys
import unittest
import base64
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)

import ludens_flow.core.state as st
import ludens_flow.app.api as api
import ludens_flow.core.agents.base as base_mod
import ludens_flow.capabilities.mcp.adapter as mcp_adapter
from ludens_flow.capabilities.mcp import health as mcp_health
from ludens_flow.core import paths as path_mod
from fastapi import HTTPException
from ludens_flow.capabilities.artifacts.artifacts import read_artifact, write_artifact
from ludens_flow.capabilities.mcp.adapter import ENGINE_TOOL_SCHEMAS
from ludens_flow.capabilities.mcp.adapters import get_engine_adapter
from ludens_flow.capabilities.mcp.health import McpClientError
from ludens_flow.capabilities.tools.registry import dispatch_tool_call, list_common_tools
from ludens_flow.core.agents.base import AgentResult, BaseAgent
from ludens_flow.core.paths import (
    PROJECT_META_SCHEMA_VERSION,
    add_project_workspace,
    archive_project,
    create_project,
    delete_project,
    get_active_project_id,
    get_dev_notes_assets_dir,
    get_logs_dir,
    get_project_dir,
    get_project_meta_file,
    list_active_projects,
    list_archived_projects,
    list_projects,
    list_project_workspaces,
    rename_project,
    restore_project,
    touch_project,
)
from ludens_flow.core.state import (
    STATE_SCHEMA_VERSION,
    export_project_bundle,
    import_project_bundle,
    init_workspace,
    load_state,
    migrate_legacy_workspace_to_project,
    save_state,
)
from llm.provider import LLMConfig


class _ToolPolicyTestAgent(BaseAgent):
    name = "ToolPolicyTestAgent"
    system_prompt = "test"

    def discuss(self, *args, **kwargs):
        return AgentResult(assistant_message="")

    def commit(self, *args, **kwargs):
        return AgentResult(assistant_message="")


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
            json.dumps(
                {
                    "id": "alpha",
                    "title": "Alpha Legacy",
                    "unity_root": str((_ROOT / "legacy_unity_project").resolve()),
                }
            ),
            encoding="utf-8",
        )

        items = {item["id"]: item for item in list_projects()}
        self.assertEqual(
            items["alpha"].get("schema_version"), PROJECT_META_SCHEMA_VERSION
        )
        self.assertEqual(
            items["alpha"]["workspaces"][0]["kind"],
            "unity",
        )

        persisted = json.loads(meta_file.read_text(encoding="utf-8"))
        self.assertEqual(persisted.get("schema_version"), PROJECT_META_SCHEMA_VERSION)
        self.assertEqual(persisted.get("display_name"), "Alpha Legacy")
        self.assertTrue(persisted.get("workspaces"))

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

    def test_api_can_update_workspace_artifact_content(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))

        response = api.put_workspace_file_content(
            "gdd",
            api.WorkspaceFileUpdateRequest(content="# GDD\nEdited by user"),
        )

        self.assertEqual(response["id"], "gdd")
        self.assertIn("Edited by user", response["content"])
        self.assertEqual(
            read_artifact("GDD", project_id="alpha"),
            "# GDD\nEdited by user\n",
        )

    def test_api_exposes_notes_artifact_and_uploads_note_assets(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))

        files = api.list_workspace_files()["files"]
        self.assertTrue(any(item["id"] == "notes" for item in files))

        response = api.put_workspace_file_content(
            "notes",
            api.WorkspaceFileUpdateRequest(content="free note"),
        )
        self.assertEqual(response["id"], "notes")
        self.assertEqual(read_artifact("NOTES", project_id="alpha"), "free note\n")

        data_url = "data:image/png;base64," + base64.b64encode(b"png-bytes").decode("ascii")
        upload = api.upload_workspace_file_asset(
            "notes",
            api.WorkspaceFileAssetUploadRequest(
                name="sketch.png",
                data_url=data_url,
            ),
        )

        self.assertEqual(get_dev_notes_assets_dir("alpha").name, "assets")
        self.assertEqual(get_dev_notes_assets_dir("alpha").parent.name, "dev_notes")
        self.assertIn("/api/workspace/files/notes/assets/", upload["markdown"])
        self.assertTrue((get_dev_notes_assets_dir("alpha") / upload["name"]).exists())

    def test_api_saves_mcp_connections_and_checks_status(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))

        settings = api.post_current_project_settings(
            api.ProjectSettingsRequest(
                mcp_connections=[
                    {
                        "id": "unity-mcp",
                        "engine": "unity",
                        "label": "Unity MCP",
                        "command": "",
                        "args": [],
                        "enabled": True,
                    }
                ]
            )
        )

        self.assertEqual(settings["mcp_connections"][0]["id"], "unity-mcp")
        self.assertEqual(settings["mcp_connections"][0]["engine"], "unity")

        health = api.post_check_current_project_mcp_connections(
            api.McpConnectionCheckRequest(connection_id="unity-mcp")
        )

        self.assertEqual(health["connections"][0]["status"], "not_configured")
        self.assertEqual(health["connections"][0]["tool_count"], 0)

    def test_api_refuses_accidental_mcp_connection_clear(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        api.post_current_project_settings(
            api.ProjectSettingsRequest(
                mcp_connections=[
                    {
                        "id": "blender-mcp",
                        "engine": "blender",
                        "label": "Blender MCP",
                        "command": "cmd",
                        "args": ["/c", "uvx", "blender-mcp"],
                        "enabled": True,
                    }
                ]
            )
        )

        with self.assertRaises(HTTPException) as ctx:
            api.post_current_project_settings(
                api.ProjectSettingsRequest(mcp_connections=[])
            )
        self.assertEqual(ctx.exception.status_code, 409)

        with self.assertRaises(HTTPException) as ctx:
            api.post_current_project_settings(
                api.ProjectSettingsRequest(
                    mcp_connections=[
                        {
                            "id": "unity-mcp",
                            "engine": "unity",
                            "label": "Unity MCP",
                            "command": "",
                            "args": [],
                            "enabled": True,
                        }
                    ]
                )
            )
        self.assertEqual(ctx.exception.status_code, 409)

        after_failed_save = api.get_current_project_settings()
        self.assertEqual(after_failed_save["mcp_connections"][0]["id"], "blender-mcp")

        deleted = api.delete_current_project_mcp_connection("blender-mcp")
        self.assertEqual(deleted["mcp_connections"], [])

    def test_project_touch_preserves_workspace_after_stale_meta_read(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        external_root = self.workspace_root / "external-root"
        external_root.mkdir(parents=True)
        add_project_workspace(
            str(external_root),
            project_id="alpha",
            kind="generic",
            writable=True,
        )

        original_read = path_mod._read_project_meta
        calls = {"count": 0}

        def stale_first_read(project_id):
            if project_id == "alpha" and calls["count"] == 0:
                calls["count"] += 1
                stale = dict(original_read(project_id))
                stale["workspaces"] = []
                stale["unity_root"] = ""
                return stale
            return original_read(project_id)

        path_mod._read_project_meta = stale_first_read
        try:
            path_mod.touch_project("alpha", last_phase="PM_DISCUSS")
        finally:
            path_mod._read_project_meta = original_read

        workspaces = list_project_workspaces(project_id="alpha", include_disabled=True)
        self.assertEqual([item["id"] for item in workspaces], ["generic-workspace"])
        self.assertEqual(workspaces[0]["root"], str(external_root.resolve()))

    def test_project_touch_preserves_mcp_connections_after_stale_meta_read(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        api.post_current_project_settings(
            api.ProjectSettingsRequest(
                mcp_connections=[
                    {
                        "id": "blender-mcp",
                        "engine": "blender",
                        "label": "Blender MCP",
                        "command": "cmd",
                        "args": ["/c", "uvx", "blender-mcp"],
                        "enabled": True,
                    }
                ]
            )
        )

        original_read = path_mod._read_project_meta
        calls = {"count": 0}

        def stale_first_read(project_id):
            if project_id == "alpha" and calls["count"] == 0:
                calls["count"] += 1
                stale = dict(original_read(project_id))
                stale["mcp_connections"] = []
                return stale
            return original_read(project_id)

        path_mod._read_project_meta = stale_first_read
        try:
            path_mod.touch_project("alpha", last_phase="PM_DISCUSS")
        finally:
            path_mod._read_project_meta = original_read

        settings = api.get_current_project_settings()
        self.assertEqual(settings["mcp_connections"][0]["id"], "blender-mcp")

    def test_project_touch_does_not_resurrect_deleted_workspace_from_stale_read(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        external_root = self.workspace_root / "external-root"
        external_root.mkdir(parents=True)
        add_project_workspace(
            str(external_root),
            project_id="alpha",
            kind="generic",
            workspace_id="external-main",
            writable=True,
        )
        stale_meta = path_mod._read_project_meta("alpha")

        api.delete_current_project_workspace("external-main")
        self.assertEqual(list_project_workspaces(project_id="alpha"), [])

        original_read = path_mod._read_project_meta
        calls = {"count": 0}

        def stale_first_read(project_id):
            if project_id == "alpha" and calls["count"] == 0:
                calls["count"] += 1
                return dict(stale_meta)
            return original_read(project_id)

        path_mod._read_project_meta = stale_first_read
        try:
            path_mod.touch_project("alpha", last_phase="PM_DISCUSS")
        finally:
            path_mod._read_project_meta = original_read

        self.assertEqual(list_project_workspaces(project_id="alpha"), [])

    def test_project_touch_does_not_resurrect_deleted_mcp_from_stale_read(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        api.post_current_project_settings(
            api.ProjectSettingsRequest(
                mcp_connections=[
                    {
                        "id": "blender-mcp",
                        "engine": "blender",
                        "label": "Blender MCP",
                        "command": "cmd",
                        "args": ["/c", "uvx", "blender-mcp"],
                        "enabled": True,
                    }
                ]
            )
        )
        stale_meta = path_mod._read_project_meta("alpha")

        api.delete_current_project_mcp_connection("blender-mcp")
        self.assertEqual(api.get_current_project_settings()["mcp_connections"], [])

        original_read = path_mod._read_project_meta
        calls = {"count": 0}

        def stale_first_read(project_id):
            if project_id == "alpha" and calls["count"] == 0:
                calls["count"] += 1
                return dict(stale_meta)
            return original_read(project_id)

        path_mod._read_project_meta = stale_first_read
        try:
            path_mod.touch_project("alpha", last_phase="PM_DISCUSS")
        finally:
            path_mod._read_project_meta = original_read

        self.assertEqual(api.get_current_project_settings()["mcp_connections"], [])

    def test_list_projects_isolates_broken_project_metadata(self):
        create_project("alpha")
        create_project("broken")
        get_project_meta_file("broken").write_text("{broken-json", encoding="utf-8")

        projects = {item["id"]: item for item in list_projects()}

        self.assertIn("alpha", projects)
        self.assertIn("broken", projects)
        self.assertIn("metadata_error", projects["broken"])

    def test_mcp_write_confirmation_requires_explicit_approval_handler(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        api.post_current_project_settings(
            api.ProjectSettingsRequest(
                agent_file_write_confirm_required=True,
                mcp_connections=[
                    {
                        "id": "blender-mcp",
                        "engine": "blender",
                        "label": "Blender MCP",
                        "command": "cmd",
                        "args": ["/c", "uvx", "blender-mcp"],
                        "enabled": True,
                    }
                ],
            )
        )

        with self.assertRaisesRegex(McpClientError, "no permission handler"):
            dispatch_tool_call(
                "engine_create_object",
                {"engine": "blender", "name": "Denied Cube"},
                project_id="alpha",
            )

    def test_api_can_import_enable_and_delete_external_skill(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        self.assertEqual(api.get_skill_catalog()["skills"], [])

        imported = api.post_import_skill(
            api.SkillImportRequest(
                manifest={
                    "id": "external-unity-helper",
                    "name": "External Unity Helper",
                    "description": "External skill for Unity workflows.",
                    "version": "0.2.0",
                    "agents": ["engineering"],
                    "tags": ["Unity", "External"],
                },
                prompt="Use this helper for Unity tasks.",
            )
        )

        self.assertIn(
            "external-unity-helper",
            {item["id"] for item in imported["skills"]},
        )
        skill_dir = self.workspace_root / "skills" / "installed" / "external-unity-helper"
        self.assertTrue((skill_dir / "skill.json").exists())
        self.assertTrue((skill_dir / "prompt.md").exists())

        project_skills = api.post_current_project_skill_toggle(
            "external-unity-helper",
            api.ProjectSkillToggleRequest(enabled=True),
        )
        self.assertIn("external-unity-helper", project_skills["enabled_skill_ids"])

        deleted = api.delete_installed_skill("external-unity-helper")
        self.assertEqual(deleted["deleted_skill"], "external-unity-helper")
        self.assertFalse(skill_dir.exists())
        self.assertNotIn(
            "external-unity-helper",
            api.get_current_project_skills()["enabled_skill_ids"],
        )

    def test_api_returns_404_when_deleting_missing_skill(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))

        with self.assertRaises(HTTPException) as ctx:
            api.delete_installed_skill("missing-skill")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_api_can_read_and_update_user_profile(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))

        profile = api.get_current_user_profile()
        self.assertEqual(profile["project_id"], "alpha")
        self.assertTrue(profile["path"].endswith("USER_PROFILE.md"))
        self.assertEqual(profile["display_path"], "workspace/projects/alpha/USER_PROFILE.md")
        self.assertIn("# USER_PROFILE", profile["content"])

        updated = api.post_current_user_profile(
            api.UserProfileUpdateRequest(
                content="# USER_PROFILE\n\n## Core Identity\n- nickname: Tester\n"
            )
        )

        self.assertIn("- nickname: Tester", updated["content"])
        self.assertEqual(updated["display_path"], "workspace/projects/alpha/USER_PROFILE.md")
        profile_path = self.workspace_root / "projects" / "alpha" / "USER_PROFILE.md"
        self.assertIn("- nickname: Tester", profile_path.read_text(encoding="utf-8"))

    def test_engine_mcp_tools_are_whitelisted_not_raw_tools(self):
        tool_names = {item["name"] for item in list_common_tools()}

        self.assertIn("engine_list_scene", tool_names)
        self.assertIn("engine_create_script", tool_names)
        self.assertNotIn("create_script", tool_names)
        self.assertNotIn("add_node", tool_names)

    def test_base_agent_uses_explicit_tool_policy(self):
        captured = []
        original_generate = base_mod.generate

        def fake_generate(**kwargs):
            captured.append(kwargs.get("tools"))
            return "ok"

        base_mod.generate = fake_generate
        try:
            agent = _ToolPolicyTestAgent()
            cfg = LLMConfig(provider="openai", model="test", api_key="test")

            agent._call("hello", cfg=cfg, tools=None)
            self.assertEqual(captured[-1], [])

            agent._call("hello", cfg=cfg, tools=ENGINE_TOOL_SCHEMAS)
            exposed_names = {
                item["function"]["name"] for item in captured[-1]
            }
            self.assertTrue(exposed_names)
            self.assertTrue(all(name.startswith("engine_") for name in exposed_names))
            self.assertNotIn("web_search", exposed_names)
            self.assertNotIn("workspace_write_text_file", exposed_names)
            self.assertNotIn("unity_read_file", exposed_names)

            agent._call("hello", cfg=cfg, tools="common")
            common_names = {item["function"]["name"] for item in captured[-1]}
            self.assertIn("web_search", common_names)
            self.assertIn("engine_list_scene", common_names)
        finally:
            base_mod.generate = original_generate

    def test_engine_mcp_adapter_requires_configured_connection(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))

        with self.assertRaisesRegex(Exception, "No enabled unity MCP connection"):
            dispatch_tool_call(
                "engine_list_scene",
                {"engine": "unity"},
                project_id="alpha",
            )

    def test_blender_adapter_translates_ludens_capabilities_to_blender_operations(self):
        adapter = get_engine_adapter("blender")
        available_tools = [{"name": "execute_blender_code"}]

        list_call = adapter.map_call(
            "engine_list_scene",
            {"engine": "blender"},
            [
                {
                    "name": "get_scene_info",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"user_prompt": {"type": "string"}},
                        "required": ["user_prompt"],
                    },
                }
            ],
        )
        self.assertIsNotNone(list_call)
        self.assertEqual(list_call.tool_name, "get_scene_info")
        self.assertEqual(
            list_call.arguments["user_prompt"],
            "Ludens-Flow blender.scene.inspect",
        )

        create_call = adapter.map_call(
            "engine_create_object",
            {
                "engine": "blender",
                "name": "Test Cube",
                "object_type": "cube",
                "position": {"x": 1, "y": 2, "z": 3},
            },
            available_tools,
        )
        self.assertIsNotNone(create_call)
        self.assertEqual(create_call.tool_name, "execute_blender_code")
        self.assertEqual(create_call.operation_name, "blender.object.create")
        self.assertIn("primitive_cube_add", create_call.arguments["code"])
        self.assertIn("Test Cube", create_call.arguments["code"])
        self.assertIn("user_prompt", create_call.arguments)

        save_call = adapter.map_call(
            "engine_save_scene",
            {"engine": "blender", "scene_path": "E:/tmp/test.blend"},
            available_tools,
        )
        self.assertIsNotNone(save_call)
        self.assertEqual(save_call.operation_name, "blender.file.save")
        self.assertIn("save_as_mainfile", save_call.arguments["code"])

    def test_blender_adapter_passes_scene_max_items_when_supported(self):
        adapter = get_engine_adapter("blender")

        list_call = adapter.map_call(
            "engine_list_scene",
            {"engine": "blender", "max_items": 12},
            [
                {
                    "name": "get_scene_info",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "user_prompt": {"type": "string"},
                            "max_items": {"type": "integer"},
                        },
                    },
                }
            ],
        )

        self.assertIsNotNone(list_call)
        self.assertEqual(list_call.arguments["max_items"], 12)

    def test_blender_scene_fallback_is_limited_to_known_legacy_schema(self):
        adapter = get_engine_adapter("blender")

        self.assertEqual(
            adapter.fallback_arguments(
                "engine_list_scene",
                "get_scene_info",
                {"user_prompt": "Ludens-Flow blender.scene.inspect"},
            ),
            [{}],
        )
        self.assertEqual(
            adapter.fallback_arguments(
                "engine_list_scene",
                "get_scene_info",
                {"random_string": "ludens-flow"},
            ),
            [],
        )
        self.assertEqual(
            adapter.fallback_arguments(
                "engine_list_scene",
                "get_scene_info",
                {"dummy": "ludens-flow"},
            ),
            [],
        )

    def test_mcp_health_check_uses_ttl_cache(self):
        mcp_health.clear_mcp_connection_cache()
        config = {
            "id": "cached-blender",
            "engine": "blender",
            "command": "cmd",
            "args": ["/c", "uvx", "blender-mcp"],
            "enabled": True,
        }
        calls = []

        def fake_run(command, *, input, **kwargs):
            calls.append(input)
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    b'{"jsonrpc":"2.0","id":1,"result":{}}\n'
                    b'{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"get_scene_info"}]}}\n'
                ),
                stderr=b"",
            )

        with patch("ludens_flow.capabilities.mcp.health.subprocess.run", side_effect=fake_run):
            first = mcp_health.check_mcp_connection(config)
            second = mcp_health.check_mcp_connection(config)

        self.assertEqual(first["status"], "tools_loaded")
        self.assertEqual(second["tools"][0]["name"], "get_scene_info")
        self.assertEqual(len(calls), 1)
        mcp_health.clear_mcp_connection_cache()

    def test_engine_list_scene_result_is_limited_by_max_items(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        api.post_current_project_settings(
            api.ProjectSettingsRequest(
                mcp_connections=[
                    {
                        "id": "blender-mcp",
                        "engine": "blender",
                        "label": "Blender MCP",
                        "command": "cmd",
                        "args": ["/c", "uvx", "blender-mcp"],
                        "enabled": True,
                    }
                ]
            )
        )

        def fake_check(connection):
            return {
                "status": "tools_loaded",
                "transport": "line",
                "tools": [{"name": "get_scene_info"}],
            }

        def fake_call(connection, tool_name, arguments, *, transport=None):
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"objects": [{"name": f"Obj{i}"} for i in range(5)]}),
                    }
                ]
            }

        with patch.object(mcp_adapter, "check_mcp_connection", side_effect=fake_check), patch.object(
            mcp_adapter,
            "call_mcp_tool",
            side_effect=fake_call,
        ):
            output = dispatch_tool_call(
                "engine_list_scene",
                {"engine": "blender", "max_items": 2},
                project_id="alpha",
            )

        payload = json.loads(output)
        self.assertEqual([item["name"] for item in payload["objects"]], ["Obj0", "Obj1"])
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["omitted_items"], 3)

    def test_engine_mcp_adapter_does_not_emit_progress_events(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        api.post_current_project_settings(
            api.ProjectSettingsRequest(
                mcp_connections=[
                    {
                        "id": "blender-mcp",
                        "engine": "blender",
                        "label": "Blender MCP",
                        "command": "cmd",
                        "args": ["/c", "uvx", "blender-mcp"],
                        "enabled": True,
                    }
                ]
            )
        )
        events = []

        def fake_check(connection):
            return {
                "status": "tools_loaded",
                "transport": "line",
                "tools": [{"name": "get_scene_info"}],
            }

        def fake_call(connection, tool_name, arguments, *, transport=None):
            return {"content": [{"type": "text", "text": "{}"}]}

        with patch.object(mcp_adapter, "check_mcp_connection", side_effect=fake_check), patch.object(
            mcp_adapter,
            "call_mcp_tool",
            side_effect=fake_call,
        ):
            dispatch_tool_call(
                "engine_list_scene",
                {"engine": "blender"},
                project_id="alpha",
                tool_event_handler=events.append,
            )

        self.assertEqual(events, [])

    def test_engine_mcp_write_only_emits_permission_events_from_adapter(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        api.post_current_project_settings(
            api.ProjectSettingsRequest(
                mcp_connections=[
                    {
                        "id": "blender-mcp",
                        "engine": "blender",
                        "label": "Blender MCP",
                        "command": "cmd",
                        "args": ["/c", "uvx", "blender-mcp"],
                        "enabled": True,
                    }
                ]
            )
        )
        events = []

        def fake_check(connection):
            return {
                "status": "tools_loaded",
                "transport": "line",
                "tools": [{"name": "execute_blender_code"}],
            }

        def fake_call(connection, tool_name, arguments, *, transport=None):
            return {"content": [{"type": "text", "text": "created"}]}

        def event_handler(event):
            events.append(event)
            return event.get("type") == "permission_required"

        with patch.object(mcp_adapter, "check_mcp_connection", side_effect=fake_check), patch.object(
            mcp_adapter,
            "call_mcp_tool",
            side_effect=fake_call,
        ):
            dispatch_tool_call(
                "engine_create_object",
                {"engine": "blender", "name": "Cube"},
                project_id="alpha",
                tool_event_handler=event_handler,
            )

        self.assertEqual(
            [event["type"] for event in events],
            ["permission_required", "permission_granted"],
        )

    def test_engine_mcp_fallback_error_reports_attempted_arguments(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        api.post_current_project_settings(
            api.ProjectSettingsRequest(
                mcp_connections=[
                    {
                        "id": "blender-mcp",
                        "engine": "blender",
                        "label": "Blender MCP",
                        "command": "cmd",
                        "args": ["/c", "uvx", "blender-mcp"],
                        "enabled": True,
                    }
                ]
            )
        )

        def fake_check(connection):
            return {
                "status": "tools_loaded",
                "transport": "line",
                "tools": [
                    {
                        "name": "get_scene_info",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"user_prompt": {"type": "string"}},
                        },
                    }
                ],
            }

        def fake_call(connection, tool_name, arguments, *, transport=None):
            raise McpClientError("Invalid request parameters")

        with patch.object(mcp_adapter, "check_mcp_connection", side_effect=fake_check), patch.object(
            mcp_adapter,
            "call_mcp_tool",
            side_effect=fake_call,
        ):
            with self.assertRaisesRegex(McpClientError, "Tried arguments") as ctx:
                dispatch_tool_call("engine_list_scene", {"engine": "blender"}, project_id="alpha")

        message = str(ctx.exception)
        self.assertIn("user_prompt", message)
        self.assertNotIn("random_string", message)
        self.assertNotIn("dummy", message)

    def test_blender_adapter_enforces_safe_scene_save_workspace(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        blender_root = self.workspace_root / "blender_project"
        blender_root.mkdir(parents=True)
        add_project_workspace(
            str(blender_root),
            project_id="alpha",
            kind="blender",
            workspace_id="main-blender",
            writable=True,
        )

        adapter = get_engine_adapter("blender")
        save_call = adapter.map_call(
            "engine_save_scene",
            {
                "engine": "blender",
                "workspace_id": "main-blender",
                "scene_path": "scenes/demo.blend",
            },
            [{"name": "execute_blender_code"}],
            project_id="alpha",
        )

        self.assertIsNotNone(save_call)
        self.assertIn("demo.blend", save_call.arguments["code"])
        self.assertIn("save_as_mainfile", save_call.arguments["code"])

        with self.assertRaisesRegex(McpClientError, "approved writable"):
            adapter.map_call(
                "engine_save_scene",
                {"engine": "blender", "scene_path": str(self.workspace_root / "outside.blend")},
                [{"name": "execute_blender_code"}],
                project_id="alpha",
            )

    def test_unity_adapter_sandboxes_script_creation_to_writable_workspace(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        unity_root = self.workspace_root / "unity_project"
        (unity_root / "Assets" / "Scripts").mkdir(parents=True)
        (unity_root / "ProjectSettings").mkdir(parents=True)
        add_project_workspace(
            str(unity_root),
            project_id="alpha",
            kind="unity",
            workspace_id="unity-main",
            writable=True,
        )

        adapter = get_engine_adapter("unity")
        script_call = adapter.map_call(
            "engine_create_script",
            {
                "engine": "unity",
                "workspace_id": "unity-main",
                "path": "Assets/Scripts/Foo.cs",
                "class_name": "Foo",
                "content": "public class Foo {}",
            },
            [{"name": "create_script"}],
            project_id="alpha",
        )

        self.assertIsNotNone(script_call)
        self.assertEqual(script_call.tool_name, "create_script")
        self.assertEqual(script_call.arguments["path"], "Assets/Scripts/Foo.cs")
        self.assertEqual(script_call.arguments["contents"], "public class Foo {}")
        self.assertNotIn("workspace_id", script_call.arguments)

        with self.assertRaisesRegex(McpClientError, "PATH_ESCAPE"):
            adapter.map_call(
                "engine_create_script",
                {
                    "engine": "unity",
                    "workspace_id": "unity-main",
                    "path": "../Outside.cs",
                    "content": "public class Outside {}",
                },
                [{"name": "create_script"}],
                project_id="alpha",
            )

        with self.assertRaisesRegex(McpClientError, r"\.cs"):
            adapter.map_call(
                "engine_create_script",
                {
                    "engine": "unity",
                    "workspace_id": "unity-main",
                    "path": "Assets/Scripts/Foo.txt",
                    "content": "bad",
                },
                [{"name": "create_script"}],
                project_id="alpha",
            )

    def test_godot_and_unreal_adapters_require_workspace_sandbox_for_writes(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        godot_root = self.workspace_root / "godot_project"
        (godot_root / "scenes").mkdir(parents=True)
        (godot_root / "project.godot").write_text('[application]\nconfig/name="Test"\n', encoding="utf-8")
        generic_root = self.workspace_root / "generic_engine_project"
        (generic_root / "Content" / "Maps").mkdir(parents=True)
        add_project_workspace(
            str(godot_root),
            project_id="alpha",
            kind="godot",
            workspace_id="godot-main",
            writable=True,
        )
        add_project_workspace(
            str(generic_root),
            project_id="alpha",
            kind="generic",
            workspace_id="engine-main",
            writable=True,
        )

        godot = get_engine_adapter("godot")
        godot_call = godot.map_call(
            "engine_save_scene",
            {
                "engine": "godot",
                "workspace_id": "godot-main",
                "scene_path": "scenes/main.tscn",
            },
            [{"name": "save_scene"}],
            project_id="alpha",
        )
        self.assertIsNotNone(godot_call)
        self.assertEqual(godot_call.tool_name, "save_scene")
        self.assertEqual(godot_call.arguments["projectPath"], str(godot_root))
        self.assertEqual(godot_call.arguments["scenePath"], "scenes/main.tscn")

        unreal = get_engine_adapter("unreal")
        save_call = unreal.map_call(
            "engine_save_scene",
            {
                "engine": "unreal",
                "workspace_id": "engine-main",
                "scene_path": "Content/Maps/Demo.umap",
            },
            [{"name": "save_level"}],
            project_id="alpha",
        )
        self.assertIsNotNone(save_call)
        self.assertEqual(save_call.arguments["scene_path"], str(generic_root / "Content" / "Maps" / "Demo.umap"))

        with self.assertRaisesRegex(McpClientError, "Project id is required"):
            godot.map_call(
                "engine_save_scene",
                {
                    "engine": "godot",
                    "workspace_id": "godot-main",
                    "scene_path": "scenes/main.tscn",
                },
                [{"name": "save_scene"}],
                project_id=None,
            )

    def test_godot_adapter_maps_ludens_capabilities_to_coding_solo_tools(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        godot_root = self.workspace_root / "godot_project"
        (godot_root / "scenes").mkdir(parents=True)
        (godot_root / "scripts").mkdir(parents=True)
        (godot_root / "project.godot").write_text('[application]\nconfig/name="Godot Test"\n', encoding="utf-8")
        add_project_workspace(
            str(godot_root),
            project_id="alpha",
            kind="godot",
            workspace_id="godot-main",
            writable=True,
        )
        adapter = get_engine_adapter("godot")
        available = [
            {"name": "get_project_info"},
            {"name": "get_debug_output"},
            {"name": "create_scene"},
            {"name": "add_node"},
            {"name": "save_scene"},
            {"name": "run_project"},
            {"name": "launch_editor"},
            {"name": "stop_project"},
        ]

        info_call = adapter.map_call(
            "engine_list_scene",
            {"engine": "godot", "workspace_id": "godot-main"},
            available,
            project_id="alpha",
        )
        self.assertEqual(info_call.tool_name, "get_project_info")
        self.assertEqual(info_call.arguments["projectPath"], str(godot_root))

        console_call = adapter.map_call(
            "engine_read_console",
            {"engine": "godot"},
            available,
            project_id="alpha",
        )
        self.assertEqual(console_call.tool_name, "get_debug_output")
        self.assertEqual(console_call.arguments, {})

        scene_call = adapter.map_call(
            "engine_create_object",
            {
                "engine": "godot",
                "workspace_id": "godot-main",
                "name": "Root",
                "object_type": "Node2D",
                "scene_path": "scenes/main.tscn",
                "create_scene": True,
            },
            available,
            project_id="alpha",
        )
        self.assertEqual(scene_call.tool_name, "create_scene")
        self.assertEqual(scene_call.arguments["scenePath"], "scenes/main.tscn")
        self.assertEqual(scene_call.arguments["rootNodeType"], "Node2D")

        node_call = adapter.map_call(
            "engine_create_object",
            {
                "engine": "godot",
                "workspace_id": "godot-main",
                "name": "Player",
                "object_type": "CharacterBody2D",
                "scene_path": "res://scenes/main.tscn",
                "parent": "root",
            },
            available,
            project_id="alpha",
        )
        self.assertEqual(node_call.tool_name, "add_node")
        self.assertEqual(node_call.arguments["nodeName"], "Player")
        self.assertEqual(node_call.arguments["nodeType"], "CharacterBody2D")
        self.assertEqual(node_call.arguments["scenePath"], "scenes/main.tscn")

        run_call = adapter.map_call(
            "engine_run_project",
            {
                "engine": "godot",
                "workspace_id": "godot-main",
                "mode": "run",
                "scene_path": "scenes/main.tscn",
            },
            available,
            project_id="alpha",
        )
        self.assertEqual(run_call.tool_name, "run_project")
        self.assertEqual(run_call.arguments["scene"], "scenes/main.tscn")

        editor_call = adapter.map_call(
            "engine_run_project",
            {"engine": "godot", "workspace_id": "godot-main", "mode": "editor"},
            available,
            project_id="alpha",
        )
        self.assertEqual(editor_call.tool_name, "launch_editor")

        stop_call = adapter.map_call(
            "engine_run_project",
            {"engine": "godot", "workspace_id": "godot-main", "mode": "stop"},
            available,
            project_id="alpha",
        )
        self.assertEqual(stop_call.tool_name, "stop_project")
        self.assertEqual(stop_call.arguments, {})

        script_call = adapter.map_call(
            "engine_create_script",
            {
                "engine": "godot",
                "workspace_id": "godot-main",
                "path": "scripts/player.gd",
                "content": "extends Node",
            },
            available,
            project_id="alpha",
        )
        self.assertIsNone(script_call)

    def test_safe_engine_adapters_validate_run_mode_and_scene_extension(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        unity_root = self.workspace_root / "unity_project"
        (unity_root / "Assets" / "Scenes").mkdir(parents=True)
        (unity_root / "ProjectSettings").mkdir(parents=True)
        add_project_workspace(
            str(unity_root),
            project_id="alpha",
            kind="unity",
            workspace_id="unity-main",
            writable=True,
        )

        adapter = get_engine_adapter("unity")
        run_call = adapter.map_call(
            "engine_run_project",
            {
                "engine": "unity",
                "workspace_id": "unity-main",
                "mode": "play",
                "scene_path": "Assets/Scenes/Main.unity",
            },
            [{"name": "manage_editor"}],
            project_id="alpha",
        )
        self.assertIsNotNone(run_call)
        self.assertEqual(run_call.tool_name, "manage_editor")
        self.assertEqual(run_call.arguments["action"], "play")

        with self.assertRaisesRegex(McpClientError, "Unsupported Unity run mode"):
            adapter.map_call(
                "engine_run_project",
                {
                    "engine": "unity",
                    "workspace_id": "unity-main",
                    "mode": "shell",
                },
                [{"name": "manage_editor"}],
                project_id="alpha",
            )

        with self.assertRaisesRegex(McpClientError, r"\.unity"):
            adapter.map_call(
                "engine_save_scene",
                {
                    "engine": "unity",
                    "workspace_id": "unity-main",
                    "scene_path": "Assets/Scenes/Main.txt",
                },
                [{"name": "manage_scene"}],
                project_id="alpha",
            )

    def test_unity_adapter_maps_ludens_capabilities_to_coplay_tools(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        unity_root = self.workspace_root / "unity_project"
        (unity_root / "Assets" / "Scripts").mkdir(parents=True)
        (unity_root / "Assets" / "Scenes").mkdir(parents=True)
        (unity_root / "ProjectSettings").mkdir(parents=True)
        add_project_workspace(
            str(unity_root),
            project_id="alpha",
            kind="unity",
            workspace_id="unity-main",
            writable=True,
        )
        adapter = get_engine_adapter("unity")

        available = [
            {"name": "manage_scene"},
            {"name": "read_console"},
            {"name": "manage_gameobject"},
            {"name": "manage_editor"},
            {"name": "create_script"},
            {"name": "run_tests"},
        ]

        list_call = adapter.map_call(
            "engine_list_scene",
            {"engine": "unity", "max_items": 25},
            available,
            project_id="alpha",
        )
        self.assertEqual(list_call.tool_name, "manage_scene")
        self.assertEqual(list_call.arguments["action"], "get_hierarchy")
        self.assertEqual(list_call.arguments["page_size"], 25)

        console_call = adapter.map_call(
            "engine_read_console",
            {"engine": "unity", "max_entries": 10, "filter": "NullReference"},
            available,
            project_id="alpha",
        )
        self.assertEqual(console_call.tool_name, "read_console")
        self.assertEqual(console_call.arguments["action"], "get")
        self.assertEqual(console_call.arguments["count"], 10)
        self.assertEqual(console_call.arguments["filter_text"], "NullReference")

        create_call = adapter.map_call(
            "engine_create_object",
            {
                "engine": "unity",
                "name": "Player",
                "object_type": "cube",
                "position": {"x": 1, "y": 2, "z": 3},
            },
            available,
            project_id="alpha",
        )
        self.assertEqual(create_call.tool_name, "manage_gameobject")
        self.assertEqual(create_call.arguments["action"], "create")
        self.assertEqual(create_call.arguments["primitive_type"], "Cube")
        self.assertEqual(create_call.arguments["position"], [1.0, 2.0, 3.0])

        move_call = adapter.map_call(
            "engine_move_object",
            {
                "engine": "unity",
                "target": "Player",
                "rotation": [0, 90, 0],
            },
            available,
            project_id="alpha",
        )
        self.assertEqual(move_call.tool_name, "manage_gameobject")
        self.assertEqual(move_call.arguments["action"], "modify")
        self.assertEqual(move_call.arguments["rotation"], [0.0, 90.0, 0.0])

        save_call = adapter.map_call(
            "engine_save_scene",
            {
                "engine": "unity",
                "workspace_id": "unity-main",
                "scene_path": "Assets/Scenes/Main.unity",
            },
            available,
            project_id="alpha",
        )
        self.assertEqual(save_call.tool_name, "manage_scene")
        self.assertEqual(save_call.arguments["action"], "save")
        self.assertEqual(save_call.arguments["name"], "Main")
        self.assertEqual(save_call.arguments["path"], "Assets/Scenes")

        tests_call = adapter.map_call(
            "engine_run_project",
            {"engine": "unity", "mode": "playmode_tests"},
            available,
            project_id="alpha",
        )
        self.assertEqual(tests_call.tool_name, "run_tests")
        self.assertEqual(tests_call.arguments["mode"], "PlayMode")

    def test_blender_adapter_rejects_unsafe_python(self):
        adapter = get_engine_adapter("blender")

        with self.assertRaisesRegex(McpClientError, "forbidden"):
            adapter.map_call(
                "engine_create_script",
                {
                    "engine": "blender",
                    "content": "import os\nos.remove('bad')",
                },
                [{"name": "execute_blender_code"}],
            )

    def test_api_allows_manual_workspace_edit_when_artifacts_are_frozen(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        state = st.load_state(project_id="alpha")
        state.phase = "DEV_COACHING"
        state.artifact_frozen = True
        st.save_state(state, project_id="alpha")

        response = api.put_workspace_file_content(
            "gdd",
            api.WorkspaceFileUpdateRequest(content="manual change in frozen phase"),
        )

        self.assertEqual(response["id"], "gdd")
        self.assertIn("manual change in frozen phase", response["content"])
        persisted_state = st.load_state(project_id="alpha")
        self.assertTrue(persisted_state.artifact_frozen)

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

    def test_rename_project_moves_directory_and_updates_project_id(self):
        create_project("alpha", display_name="Alpha", set_active=True)

        renamed = rename_project("alpha", "Alpha Renamed")

        self.assertEqual(renamed["id"], "alpha-renamed")
        self.assertEqual(renamed["display_name"], "Alpha Renamed")
        self.assertTrue(get_project_dir("alpha-renamed").exists())
        self.assertFalse((self.workspace_root / "projects" / "alpha").exists())
        self.assertEqual(get_active_project_id(), "alpha-renamed")

        listed = {item["id"]: item for item in list_projects()}
        self.assertEqual(listed["alpha-renamed"]["display_name"], "Alpha Renamed")

    def test_rename_project_rejects_existing_target_id(self):
        create_project("alpha", display_name="Alpha", set_active=False)
        create_project("beta", display_name="Beta", set_active=False)

        with self.assertRaises(FileExistsError):
            rename_project("alpha", "Beta")

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

    def test_api_can_create_project_without_explicit_id(self):
        created = api.post_project(api.ProjectRequest(display_name="测试项目"))

        self.assertTrue(created["project"]["id"].startswith("project-"))
        self.assertEqual(created["project"]["display_name"], "测试项目")
        self.assertEqual(created["state"]["project_id"], created["project"]["id"])

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
        self.assertEqual(renamed["active_project"], "alpha-prime")
        self.assertEqual(project_lookup["alpha-prime"]["display_name"], "Alpha Prime")
        self.assertNotIn("alpha", project_lookup)

    def test_api_can_manage_project_workspace_list(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        unity_root = (self.workspace_root / "unity_api_project").resolve()
        (unity_root / "Assets").mkdir(parents=True, exist_ok=True)
        (unity_root / "ProjectSettings").mkdir(parents=True, exist_ok=True)

        created = api.post_current_project_workspace(
            api.ProjectWorkspaceRequest(
                root=str(unity_root),
                kind="unity",
                workspace_id="unity-alpha",
                label="Unity Alpha",
            )
        )
        self.assertEqual(created["workspace"]["id"], "unity-alpha")
        listing = api.get_current_project_workspaces()
        self.assertEqual(listing["workspaces"][0]["id"], "unity-alpha")

        deleted = api.delete_current_project_workspace("unity-alpha")
        self.assertEqual(deleted["workspaces"], [])

    def test_project_workspace_list_refuses_accidental_clear(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        workspace_root = (self.workspace_root / "game_workspace").resolve()
        workspace_root.mkdir(parents=True, exist_ok=True)

        add_project_workspace(
            str(workspace_root),
            project_id="alpha",
            kind="generic",
            workspace_id="game-main",
            writable=True,
        )

        with self.assertRaisesRegex(ValueError, "Refusing to remove"):
            touch_project("alpha", workspaces=[])

        workspaces = list_project_workspaces(project_id="alpha")
        self.assertEqual(len(workspaces), 1)
        self.assertEqual(workspaces[0]["id"], "game-main")

        deleted = api.delete_current_project_workspace("game-main")
        self.assertEqual(deleted["workspaces"], [])

    def test_api_can_read_and_update_current_project_settings(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))

        current = api.get_current_project_settings()
        self.assertEqual(current["project_id"], "alpha")
        self.assertTrue(current["agent_file_write_enabled"])
        self.assertEqual(current.get("model_routing"), {})

        updated = api.post_current_project_settings(
            api.ProjectSettingsRequest(agent_file_write_enabled=False)
        )
        self.assertEqual(updated["project_id"], "alpha")
        self.assertFalse(updated["agent_file_write_enabled"])

        reloaded = api.get_current_project_settings()
        self.assertFalse(reloaded["agent_file_write_enabled"])

    def test_api_can_update_project_model_routing(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))

        updated = api.post_current_project_settings(
            api.ProjectSettingsRequest(
                model_routing={
                    "global": {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                    },
                    "agents": {
                        "review": {
                            "model": "o4-mini",
                        }
                    },
                }
            )
        )

        self.assertEqual(updated["project_id"], "alpha")
        self.assertIn("model_routing", updated)
        self.assertEqual(
            updated["model_routing"]["agents"]["review"]["model"],
            "o4-mini",
        )

    def test_api_workspace_create_returns_http_400_for_invalid_path(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))

        with self.assertRaises(HTTPException) as ctx:
            api.post_current_project_workspace(
                api.ProjectWorkspaceRequest(
                    root=str(self.workspace_root / "missing_workspace"),
                    kind="generic",
                    label="Missing Workspace",
                )
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("does not exist", str(ctx.exception.detail))

    def test_api_workspace_create_returns_http_400_for_invalid_unity_root(self):
        api.post_project(api.ProjectRequest(project_id="alpha"))
        non_unity_root = (self.workspace_root / "plain_folder").resolve()
        non_unity_root.mkdir(parents=True, exist_ok=True)

        with self.assertRaises(HTTPException) as ctx:
            api.post_current_project_workspace(
                api.ProjectWorkspaceRequest(
                    root=str(non_unity_root),
                    kind="unity",
                    label="Not Unity",
                )
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("ProjectSettings", str(ctx.exception.detail))

    def test_chat_emits_started_and_state_updated_events(self):
        state = st.load_state()
        project_id = state.project_id
        subscriber = api._subscribe_project_events(project_id)
        original_graph_step = api.graph_step

        def fake_graph_step(current_state, _user_input, **_kwargs):
            current_state.phase = "PM_DISCUSS"
            current_state.last_assistant_message = "synthetic reply"
            return current_state

        api.graph_step = fake_graph_step
        try:
            response = api.post_chat(api.ChatRequest(message="hello"))
            self.assertEqual(response["reply"], "synthetic reply")

            started = subscriber.get_nowait()
            updated = subscriber.get_nowait()

            self.assertEqual(started["type"], "run_started")
            self.assertEqual(started["project_id"], project_id)
            self.assertEqual(updated["type"], "state_updated")
            self.assertEqual(updated["project_id"], project_id)
            self.assertEqual(updated["state"]["phase"], "PM_DISCUSS")
        finally:
            api.graph_step = original_graph_step
            api._unsubscribe_project_events(project_id, subscriber)

    def test_chat_emits_streaming_events_when_graph_pushes_deltas(self):
        state = st.load_state()
        project_id = state.project_id
        subscriber = api._subscribe_project_events(project_id)
        original_graph_step = api.graph_step

        def fake_graph_step(current_state, _user_input, **kwargs):
            stream_handler = kwargs.get("stream_handler")
            if stream_handler:
                stream_handler("第一段。")
                stream_handler("第二段。")
            current_state.phase = "DEV_COACHING"
            current_state.last_assistant_message = "第一段。第二段。"
            return current_state

        api.graph_step = fake_graph_step
        try:
            response = api.post_chat(api.ChatRequest(message="hello"))
            self.assertEqual(response["reply"], "第一段。第二段。")

            event_types = []
            while not subscriber.empty():
                event_types.append(subscriber.get_nowait()["type"])

            self.assertEqual(
                event_types,
                [
                    "run_started",
                    "assistant_stream_started",
                    "assistant_delta",
                    "assistant_delta",
                    "assistant_stream_completed",
                    "state_updated",
                ],
            )
        finally:
            api.graph_step = original_graph_step
            api._unsubscribe_project_events(project_id, subscriber)

    def test_chat_emits_tool_events_when_graph_reports_tool_activity(self):
        state = st.load_state()
        project_id = state.project_id
        subscriber = api._subscribe_project_events(project_id)
        original_graph_step = api.graph_step

        def fake_graph_step(current_state, _user_input, **kwargs):
            tool_event_handler = kwargs.get("tool_event_handler")
            if tool_event_handler:
                tool_event_handler(
                    {
                        "type": "tool_started",
                        "tool_name": "unity_find_files",
                        "args": {"pattern": "*.cs", "relative_path": "Assets/Scripts"},
                    }
                )
                tool_event_handler(
                    {
                        "type": "tool_completed",
                        "tool_name": "unity_find_files",
                        "args": {"pattern": "*.cs", "relative_path": "Assets/Scripts"},
                        "result": "Player.cs\nEnemy.cs",
                    }
                )
            current_state.phase = "DEV_COACHING"
            current_state.last_assistant_message = "tool ok"
            return current_state

        api.graph_step = fake_graph_step
        try:
            response = api.post_chat(api.ChatRequest(message="find scripts"))
            self.assertEqual(response["reply"], "tool ok")

            event_types = []
            while not subscriber.empty():
                payload = subscriber.get_nowait()
                event_types.append(payload["type"])

            self.assertEqual(
                event_types,
                [
                    "run_started",
                    "tool_started",
                    "tool_completed",
                    "state_updated",
                ],
            )
        finally:
            api.graph_step = original_graph_step
            api._unsubscribe_project_events(project_id, subscriber)

    def test_chat_passes_text_attachment_into_graph_input(self):
        captured = {}
        original_graph_step = api.graph_step

        attachment_text = "speed = 5\njump = true"
        attachment_b64 = base64.b64encode(attachment_text.encode("utf-8")).decode("ascii")

        def fake_graph_step(current_state, user_input, **_kwargs):
            captured["user_input"] = user_input
            current_state.phase = "DEV_COACHING"
            current_state.last_assistant_message = "attachment ok"
            return current_state

        api.graph_step = fake_graph_step
        try:
            response = api.post_chat(
                api.ChatRequest(
                    message="please inspect the attached config",
                    attachments=[
                        {
                            "kind": "file",
                            "name": "config.txt",
                            "mime_type": "text/plain",
                            "data_url": f"data:text/plain;base64,{attachment_b64}",
                            "size": len(attachment_text),
                        }
                    ],
                )
            )
            self.assertEqual(response["reply"], "attachment ok")
            self.assertIsInstance(captured["user_input"], list)
            flattened = "\n".join(
                item.get("text", "")
                for item in captured["user_input"]
                if isinstance(item, dict) and item.get("type") == "text"
            )
            self.assertIn("please inspect the attached config", flattened)
            self.assertIn("config.txt", flattened)
            self.assertIn("speed = 5", flattened)
        finally:
            api.graph_step = original_graph_step

    def test_chat_returns_attachment_warnings_in_response(self):
        original_graph_step = api.graph_step

        def fake_graph_step(current_state, user_input, **_kwargs):
            current_state.phase = "DEV_COACHING"
            current_state.last_assistant_message = "warning ok"
            return current_state

        api.graph_step = fake_graph_step
        try:
            response = api.post_chat(
                api.ChatRequest(
                    message="check this",
                    attachments=[
                        {
                            "kind": "file",
                            "name": "archive.zip",
                            "mime_type": "application/zip",
                            "data_url": "data:application/zip;base64,UEsDBA==",
                            "size": 6,
                        }
                    ],
                )
            )
            self.assertEqual(response["reply"], "warning ok")
            self.assertIn("attachment_warnings", response)
            self.assertTrue(response["attachment_warnings"])
            self.assertIn("unsupported file type", response["attachment_warnings"][0])
        finally:
            api.graph_step = original_graph_step

    def test_chat_image_attachment_uses_main_attachment_chain(self):
        captured = {}
        original_graph_step = api.graph_step

        def fake_graph_step(current_state, user_input, **_kwargs):
            captured["user_input"] = user_input
            current_state.phase = "DEV_COACHING"
            current_state.last_assistant_message = "image ok"
            return current_state

        api.graph_step = fake_graph_step
        try:
            response = api.post_chat(
                api.ChatRequest(
                    message="look at this image",
                    attachments=[
                        {
                            "kind": "image",
                            "name": "shot.png",
                            "mime_type": "image/png",
                            "data_url": "data:image/png;base64,AAAA",
                            "size": 4,
                        }
                    ],
                )
            )
            self.assertEqual(response["reply"], "image ok")
            self.assertIsInstance(captured["user_input"], list)
            self.assertTrue(
                any(
                    isinstance(item, dict) and item.get("type") == "image_url"
                    for item in captured["user_input"]
                )
            )
            self.assertEqual(response.get("attachment_warnings"), [])
        finally:
            api.graph_step = original_graph_step


if __name__ == "__main__":
    unittest.main()
