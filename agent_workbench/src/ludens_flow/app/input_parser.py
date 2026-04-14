import base64
import io
import logging
import mimetypes
import re
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


def _extract_image_path_candidates(text: str) -> list[tuple[str, str]]:
    """Return [(matched_text, path_text)] for likely local image paths."""
    ext_pattern = r"(?:png|jpg|jpeg|webp)"
    patterns = [
        rf'(?P<matched>"(?P<path>[^"\r\n]+\.(?:{ext_pattern}))")',
        rf"(?P<matched>'(?P<path>[^'\r\n]+\.(?:{ext_pattern}))')",
        rf"(?P<matched>(?<!\S)(?P<path>(?:[A-Za-z]:[\\/]|\.{{1,2}}[\\/]|[\\/])[^\r\n<>|?*]+?\.(?:{ext_pattern}))(?=$|\s))",
        rf"(?P<matched>(?<!\S)(?P<path>[A-Za-z0-9_.\-\\/]+\.(?:{ext_pattern}))(?=$|\s))",
    ]

    seen: set[tuple[str, str]] = set()
    candidates: list[tuple[str, str]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            matched_text = match.group("matched")
            path_text = match.group("path")
            key = (matched_text, path_text)
            if key in seen:
                continue
            if any(path_text in existing_path for _, existing_path in candidates):
                continue
            seen.add(key)
            candidates.append((matched_text, path_text))
    return candidates


def parse_user_input(text: str) -> Union[str, list]:
    """
    Parse the user input for local file paths representing images.
    If an image is found, convert the file to a base64 data URI and
    return a multimodal payload list. Otherwise returning the string.
    """
    payload = []
    text_content = text

    for matched_text, file_path_str in _extract_image_path_candidates(text):
        path = Path(file_path_str)
        if path.is_file():
            try:
                # Try PIL to compress large images to keep token usage stable.
                try:
                    from PIL import Image

                    with Image.open(path) as img:
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")

                        max_size = (512, 512)
                        img.thumbnail(max_size, Image.Resampling.LANCZOS)

                        buffered = io.BytesIO()
                        img.save(buffered, format="JPEG", quality=75)
                        base64_str = base64.b64encode(buffered.getvalue()).decode(
                            "utf-8"
                        )
                        mime_type = "image/jpeg"

                except ImportError:
                    logger.warning(
                        "Pillow (PIL) not installed. Large images might exceed LLM token limits. 'pip install Pillow' is recommended."
                    )
                    with open(path, "rb") as image_file:
                        base64_str = base64.b64encode(image_file.read()).decode("utf-8")
                    mime_type, _ = mimetypes.guess_type(path)
                    if not mime_type:
                        mime_type = "image/png"

                data_uri = f"data:{mime_type};base64,{base64_str}"

                payload.append({"type": "image_url", "image_url": {"url": data_uri}})
                text_content = text_content.replace(matched_text, "").strip()
            except Exception as e:
                logger.warning(f"Could not read image file {path}: {e}")

    if not payload:
        return text.strip()

    if text_content:
        payload.insert(0, {"type": "text", "text": text_content})

    return payload
