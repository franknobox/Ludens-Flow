"""
文件功能：验证策划 Agent 文案子能力的最小生成闭环。
核心内容：mock LLM 输出，确认请求归一、模型调用与结构化结果解析可用。
"""

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

from ludens_flow.capabilities.copywriting.design_copywriting import generate_design_copywriting
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
        mock_generate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
