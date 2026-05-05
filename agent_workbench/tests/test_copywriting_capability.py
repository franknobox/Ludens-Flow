"""
文件功能：验证策划 Agent 文案子能力的最小生成闭环。
核心内容：mock LLM 输出，确认请求归一、模型调用与结构化结果解析可用。
"""

import base64
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)

from ludens_flow.capabilities.copywriting.design_copywriting import (
    build_design_copywriting_prompt,
    generate_design_copywriting,
    load_design_copywriting_context,
)
from ludens_flow.core.paths import create_project
from ludens_flow.core.schemas import DesignCopywritingRequest
from ludens_flow.core.state import init_workspace


class CopywritingCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        self.previous_project = os.environ.get("LUDENS_PROJECT_ID")
        self.previous_provider = os.environ.get("LLM_PROVIDER")
        self.previous_model = os.environ.get("LLM_MODEL")
        self.previous_key = os.environ.get("LLM_API_KEY")

        self.workspace_root = (_ROOT / "workspace_test_copywriting").resolve()
        shutil.rmtree(self.workspace_root, ignore_errors=True)
        os.environ["LUDENS_WORKSPACE_DIR"] = str(self.workspace_root)
        os.environ.pop("LUDENS_PROJECT_ID", None)
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["LLM_MODEL"] = "gpt-test"
        os.environ["LLM_API_KEY"] = "test-key"

        init_workspace()
        create_project("copy-test", set_active=True)

    def tearDown(self):
        shutil.rmtree(self.workspace_root, ignore_errors=True)
        self._restore_env("LUDENS_WORKSPACE_DIR", self.previous_workspace)
        self._restore_env("LUDENS_PROJECT_ID", self.previous_project)
        self._restore_env("LLM_PROVIDER", self.previous_provider)
        self._restore_env("LLM_MODEL", self.previous_model)
        self._restore_env("LLM_API_KEY", self.previous_key)

    def _restore_env(self, key: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    @patch("ludens_flow.capabilities.copywriting.design_copywriting.generate")
    def test_generate_design_copywriting_parses_structured_candidates(self, mock_generate):
        mock_generate.return_value = (
            '{"candidates":[{"id":"c1","text":"欢迎来到碎星港。",'
            '"notes":["fits the setting"],"tags":["dialogue","short"]}]}'
        )

        response = generate_design_copywriting(
            DesignCopywritingRequest(
                copy_type="dialogue",
                brief="生成一句港口 NPC 问候语",
                quantity=1,
                reference_ids=["__none__"],
            ),
            project_id="copy-test",
        )

        self.assertEqual(response.status, "generated")
        self.assertEqual(len(response.candidates), 1)
        self.assertEqual(response.candidates[0].text, "欢迎来到碎星港。")
        self.assertEqual(response.request.copy_type, "dialogue")
        self.assertIsNotNone(response.table)
        self.assertEqual(response.table.kind, "dialogue_csv")
        self.assertEqual(response.table.rows[0]["id"], "dlg_001")
        self.assertEqual(response.table.rows[0]["text"], response.candidates[0].text)
        mock_generate.assert_called_once()

    @patch("ludens_flow.capabilities.copywriting.design_copywriting.generate")
    def test_non_dialogue_copywriting_does_not_request_dialogue_csv(self, mock_generate):
        mock_generate.return_value = (
            '{"candidates":[{"id":"c1","text":"一枚刻着潮汐纹的旧铜币。"}]}'
        )

        response = generate_design_copywriting(
            DesignCopywritingRequest(
                copy_type="item",
                brief="生成一个道具短描述",
                quantity=1,
                reference_ids=["__none__"],
            ),
            project_id="copy-test",
        )

        self.assertEqual(response.request.copy_type, "item")
        self.assertEqual(len(response.candidates), 1)
        self.assertIsNone(response.table)
        _, kwargs = mock_generate.call_args
        self.assertNotIn("dialogue_csv", kwargs["user"])
        self.assertNotIn('"table"', kwargs["user"])

    def test_copywriting_prompt_schema_depends_on_copy_type(self):
        context = load_design_copywriting_context(
            "copy-test",
            ["__none__"],
            None,
        )
        dialogue_prompt = build_design_copywriting_prompt(
            DesignCopywritingRequest(
                copy_type="dialogue",
                brief="生成台词",
                reference_ids=["__none__"],
            ),
            context,
        )
        item_prompt = build_design_copywriting_prompt(
            DesignCopywritingRequest(
                copy_type="item",
                brief="生成道具描述",
                reference_ids=["__none__"],
            ),
            context,
        )

        self.assertIn("dialogue_csv", dialogue_prompt)
        self.assertIn('"table"', dialogue_prompt)
        self.assertNotIn("dialogue_csv", item_prompt)
        self.assertNotIn('"table"', item_prompt)

    @patch("ludens_flow.capabilities.copywriting.design_copywriting.generate")
    def test_generate_design_copywriting_loads_external_reference_files(self, mock_generate):
        mock_generate.return_value = '{"candidates":[{"id":"c1","text":"保留方言语气。"}]}'
        data_url = (
            "data:text/plain;base64,"
            + base64.b64encode("语气规则：角色说话要短促、直接。".encode("utf-8")).decode("ascii")
        )

        response = generate_design_copywriting(
            DesignCopywritingRequest(
                copy_type="dialogue",
                brief="生成一条 NPC 台词",
                quantity=1,
                reference_ids=["__none__"],
            ),
            project_id="copy-test",
            external_references=[
                {
                    "kind": "file",
                    "name": "style-rules.txt",
                    "data_url": data_url,
                }
            ],
        )

        self.assertIsNotNone(response.context)
        self.assertEqual(len(response.context.external_files), 1)
        self.assertEqual(response.context.external_files[0].name, "style-rules.txt")
        self.assertIn("语气规则", response.context.external_files[0].content)

        payload = response.to_dict()
        self.assertNotIn("prompt_preview", payload)
        self.assertNotIn("content", payload["context"]["external_files"][0])
        self.assertGreater(payload["context"]["external_files"][0]["content_chars"], 0)


if __name__ == "__main__":
    unittest.main()
