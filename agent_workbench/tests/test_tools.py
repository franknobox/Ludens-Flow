import base64
import os
import sys
import unittest
import builtins
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

os.chdir(_ROOT)

from ludens_flow.app.input_parser import parse_user_input
from ludens_flow.app.attachment_ingest import build_attachment_user_input
from ludens_flow.tools import search as search_tool


# 1x1 transparent PNG
_TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO2M4X8AAAAASUVORK5CYII="


class _MockDDGS:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def text(self, query: str, max_results: int = 5):
        yield {
            "title": f"Result for {query}",
            "href": "https://example.com",
            "body": f"Top {max_results} mock result",
        }


class ToolsTests(unittest.TestCase):
    def test_web_search_returns_error_when_ddgs_missing(self):
        with patch("ludens_flow.tools.search.DDGS", None):
            result = search_tool.web_search("unity test")
        self.assertIn("Web Search is disabled", result)

    def test_web_search_uses_mocked_ddgs(self):
        with patch("ludens_flow.tools.search.DDGS", _MockDDGS):
            result = search_tool.web_search("unity", max_results=2)
        self.assertIn("Result for unity", result)
        self.assertIn("https://example.com", result)

    def test_parse_user_input_without_image_returns_plain_text(self):
        parsed = parse_user_input("hello world")
        self.assertIsInstance(parsed, str)
        self.assertEqual(parsed, "hello world")

    def test_parse_user_input_with_image_returns_multimodal_payload(self):
        image_path = _ROOT / "test_dummy.png"
        image_path.write_bytes(base64.b64decode(_TINY_PNG_B64))
        try:
            real_import = builtins.__import__

            def _import_without_pil(
                name, globals=None, locals=None, fromlist=(), level=0
            ):
                if name == "PIL" or name.startswith("PIL."):
                    raise ImportError("mock no pillow")
                return real_import(name, globals, locals, fromlist, level)

            with patch("builtins.__import__", side_effect=_import_without_pil):
                parsed = parse_user_input("look test_dummy.png please")
            self.assertIsInstance(parsed, list)
            self.assertTrue(any(item.get("type") == "image_url" for item in parsed))
            image_items = [item for item in parsed if item.get("type") == "image_url"]
            self.assertTrue(
                image_items[0]["image_url"]["url"].startswith("data:image/")
            )
        finally:
            image_path.unlink(missing_ok=True)

    def test_parse_user_input_with_absolute_image_path_returns_multimodal_payload(self):
        image_path = (_ROOT / "test_dummy_abs.png").resolve()
        image_path.write_bytes(base64.b64decode(_TINY_PNG_B64))
        try:
            real_import = builtins.__import__

            def _import_without_pil(
                name, globals=None, locals=None, fromlist=(), level=0
            ):
                if name == "PIL" or name.startswith("PIL."):
                    raise ImportError("mock no pillow")
                return real_import(name, globals, locals, fromlist, level)

            with patch("builtins.__import__", side_effect=_import_without_pil):
                parsed = parse_user_input(f"look {image_path} please")
            self.assertIsInstance(parsed, list)
            self.assertTrue(any(item.get("type") == "image_url" for item in parsed))
        finally:
            image_path.unlink(missing_ok=True)

    def test_parse_user_input_with_absolute_image_path_containing_spaces_returns_multimodal_payload(
        self,
    ):
        image_dir = _ROOT / "test image dir"
        image_dir.mkdir(exist_ok=True)
        image_path = (image_dir / "test image spaced.png").resolve()
        image_path.write_bytes(base64.b64decode(_TINY_PNG_B64))
        try:
            real_import = builtins.__import__

            def _import_without_pil(
                name, globals=None, locals=None, fromlist=(), level=0
            ):
                if name == "PIL" or name.startswith("PIL."):
                    raise ImportError("mock no pillow")
                return real_import(name, globals, locals, fromlist, level)

            with patch("builtins.__import__", side_effect=_import_without_pil):
                parsed = parse_user_input(f"look {image_path} please")
            self.assertIsInstance(parsed, list)
            self.assertTrue(any(item.get("type") == "image_url" for item in parsed))
        finally:
            image_path.unlink(missing_ok=True)
            image_dir.rmdir()

    def test_build_attachment_user_input_reads_text_attachment(self):
        attachment_text = "public class PlayerController {}"
        attachment_b64 = base64.b64encode(attachment_text.encode("utf-8")).decode("ascii")

        result = build_attachment_user_input(
            "please review",
            attachments=[
                {
                    "kind": "file",
                    "name": "PlayerController.cs",
                    "mime_type": "text/plain",
                    "data_url": f"data:text/plain;base64,{attachment_b64}",
                }
            ],
            fallback_parser=parse_user_input,
        )

        self.assertIsInstance(result.user_input, list)
        text_items = [
            item["text"]
            for item in result.user_input
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        self.assertTrue(any("please review" in item for item in text_items))
        self.assertTrue(any("PlayerController.cs" in item for item in text_items))
        self.assertTrue(any("public class PlayerController" in item for item in text_items))
        self.assertTrue(any("[Attachment Context]" in item for item in text_items))
        self.assertTrue(
            any("If exactly one file is attached" in item for item in text_items)
        )

    def test_build_attachment_user_input_rejects_unsupported_image_mime(self):
        result = build_attachment_user_input(
            "what is in this image",
            attachments=[
                {
                    "kind": "image",
                    "name": "fake-image.txt",
                    "mime_type": "text/plain",
                    "data_url": "data:text/plain;base64,SGVsbG8=",
                }
            ],
        )

        self.assertTrue(result.warnings)
        self.assertIn("unsupported image type", result.warnings[0])
        self.assertIsInstance(result.user_input, list)
        self.assertFalse(
            any(
                isinstance(item, dict) and item.get("type") == "image_url"
                for item in result.user_input
            )
        )

    @unittest.skipUnless(
        os.getenv("RUN_INTERNET_TESTS") == "1",
        "Set RUN_INTERNET_TESTS=1 to run real web search integration test.",
    )
    def test_web_search_real_integration(self):
        result = search_tool.web_search("latest unity version", max_results=1)
        self.assertIsInstance(result, str)
        self.assertTrue(result.strip())
        self.assertNotIn("Web Search is disabled", result)
        self.assertNotIn("Web search failed:", result)


if __name__ == "__main__":
    unittest.main()
