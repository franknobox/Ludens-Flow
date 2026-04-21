"""
文件功能：验证多模型路由策略的优先级与回退行为。
核心内容：覆盖 global/agent/capability/agent_capability 四层合并逻辑。
核心内容：验证 api_key_env 覆盖与环境默认兜底配置是否按预期生效。
"""

import os
import shutil
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)

from llm.modelrouter import resolve_model_config
from ludens_flow.core.paths import create_project, set_project_model_routing
from ludens_flow.core.state import init_workspace


class ModelRoutingTests(unittest.TestCase):
    def setUp(self):
        self.previous_workspace = os.environ.get("LUDENS_WORKSPACE_DIR")
        self.previous_project = os.environ.get("LUDENS_PROJECT_ID")
        self.previous_provider = os.environ.get("LLM_PROVIDER")
        self.previous_model = os.environ.get("LLM_MODEL")
        self.previous_key = os.environ.get("LLM_API_KEY")
        self.previous_base_url = os.environ.get("LLM_BASE_URL")
        self.previous_temp = os.environ.get("LLM_TEMPERATURE")
        self.previous_custom_key = os.environ.get("CUSTOM_MODEL_KEY")

        self.workspace_root = (_ROOT / "workspace_test_model_routing").resolve()
        shutil.rmtree(self.workspace_root, ignore_errors=True)
        os.environ["LUDENS_WORKSPACE_DIR"] = str(self.workspace_root)
        os.environ.pop("LUDENS_PROJECT_ID", None)

        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["LLM_MODEL"] = "gpt-fallback"
        os.environ["LLM_API_KEY"] = "test-key"
        os.environ["LLM_BASE_URL"] = ""
        os.environ["LLM_TEMPERATURE"] = "0.2"

        init_workspace()
        create_project("alpha", set_active=True)

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

        if self.previous_provider is None:
            os.environ.pop("LLM_PROVIDER", None)
        else:
            os.environ["LLM_PROVIDER"] = self.previous_provider

        if self.previous_model is None:
            os.environ.pop("LLM_MODEL", None)
        else:
            os.environ["LLM_MODEL"] = self.previous_model

        if self.previous_key is None:
            os.environ.pop("LLM_API_KEY", None)
        else:
            os.environ["LLM_API_KEY"] = self.previous_key

        if self.previous_base_url is None:
            os.environ.pop("LLM_BASE_URL", None)
        else:
            os.environ["LLM_BASE_URL"] = self.previous_base_url

        if self.previous_temp is None:
            os.environ.pop("LLM_TEMPERATURE", None)
        else:
            os.environ["LLM_TEMPERATURE"] = self.previous_temp

        if self.previous_custom_key is None:
            os.environ.pop("CUSTOM_MODEL_KEY", None)
        else:
            os.environ["CUSTOM_MODEL_KEY"] = self.previous_custom_key

    def test_resolve_model_config_uses_global_fallback_when_no_project_routing(self):
        cfg = resolve_model_config(
            project_id="alpha",
            agent_key="design",
            capability="discuss",
        )
        self.assertEqual(cfg.provider, "openai")
        self.assertEqual(cfg.model, "gpt-fallback")
        self.assertEqual(cfg.api_key, "test-key")

    def test_resolve_model_config_applies_priority_chain(self):
        set_project_model_routing(
            {
                "global": {
                    "provider": "openai_compatible",
                    "model": "gpt-global",
                    "base_url": "https://router.example/v1",
                },
                "agents": {
                    "design": {
                        "model": "gpt-design",
                    }
                },
                "capabilities": {
                    "discuss": {
                        "model": "gpt-capability",
                    }
                },
                "agent_capabilities": {
                    "design": {
                        "discuss": {
                            "model": "gpt-agent-capability",
                            "temperature": 0.35,
                        }
                    }
                },
            },
            project_id="alpha",
        )

        discuss_cfg = resolve_model_config(
            project_id="alpha",
            agent_key="design",
            capability="discuss",
        )
        self.assertEqual(discuss_cfg.provider, "openai_compatible")
        self.assertEqual(discuss_cfg.model, "gpt-agent-capability")
        self.assertEqual(discuss_cfg.base_url, "https://router.example/v1")
        self.assertAlmostEqual(discuss_cfg.temperature, 0.35, places=6)

        commit_cfg = resolve_model_config(
            project_id="alpha",
            agent_key="design",
            capability="commit",
        )
        self.assertEqual(commit_cfg.model, "gpt-design")

        pm_discuss_cfg = resolve_model_config(
            project_id="alpha",
            agent_key="pm",
            capability="discuss",
        )
        self.assertEqual(pm_discuss_cfg.model, "gpt-capability")

    def test_resolve_model_config_supports_api_key_env_override(self):
        os.environ["CUSTOM_MODEL_KEY"] = "special-key"
        set_project_model_routing(
            {
                "global": {
                    "provider": "openai",
                    "model": "gpt-special",
                    "api_key_env": "CUSTOM_MODEL_KEY",
                }
            },
            project_id="alpha",
        )

        cfg = resolve_model_config(
            project_id="alpha",
            agent_key="review",
            capability="commit",
        )
        self.assertEqual(cfg.model, "gpt-special")
        self.assertEqual(cfg.api_key, "special-key")


if __name__ == "__main__":
    unittest.main()
