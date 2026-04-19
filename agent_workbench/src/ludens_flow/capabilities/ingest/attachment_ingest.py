import base64
import io
from dataclasses import dataclass


MAX_ATTACHMENTS = 6
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS_PER_ATTACHMENT = 12000
MAX_TOTAL_ATTACHMENT_CHARS = 36000
IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".cs",
    ".js",
    ".ts",
    ".tsx",
    ".py",
    ".shader",
    ".hlsl",
    ".uxml",
    ".uss",
    ".asmdef",
    ".meta",
}


@dataclass
class AttachmentPayload:
    user_input: str | list
    warnings: list[str]


def _split_data_url(data_url: str) -> tuple[str, bytes]:
    if not data_url.startswith("data:") or "," not in data_url:
        raise ValueError("invalid data URL")

    header, payload = data_url.split(",", 1)
    mime_type = header[5:].split(";")[0] or "application/octet-stream"
    try:
        data = base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise ValueError("invalid base64 payload") from exc

    if len(data) > MAX_ATTACHMENT_BYTES:
        raise ValueError("attachment exceeds size limit")
    return mime_type, data


def _decode_text_bytes(raw: bytes) -> str:
    encodings = ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be", "gb18030")
    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _extract_pdf_text(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("PDF support requires pypdf") from exc

    reader = PdfReader(io.BytesIO(raw))
    chunks: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            chunks.append(page_text.strip())
    return "\n\n".join(chunks).strip()


def _truncate_text(text: str, *, max_chars: int) -> tuple[str, bool]:
    clean = text.strip()
    if len(clean) <= max_chars:
        return clean, False
    return clean[:max_chars].rstrip() + "\n...[truncated]", True


def _attachment_block(name: str, mime_type: str, text: str) -> str:
    return (
        f"[Attached File]\n"
        f"name: {name}\n"
        f"mime_type: {mime_type}\n"
        f"content:\n{text}"
    )


def _attachment_context_block(
    attachment_summaries: list[tuple[str, str]],
    *,
    has_images: bool,
) -> str:
    lines = ["[Attachment Context]"]

    if attachment_summaries:
        lines.append("Attached files for this turn:")
        for name, mime_type in attachment_summaries:
            lines.append(f"- {name} ({mime_type})")

    if has_images:
        lines.append("Attached images are also part of this turn context.")

    lines.extend(
        [
            "Usage rules:",
            "- Treat attached files and images as part of the user's current-turn context.",
            "- Read attached file content before answering questions about the file.",
            "- If exactly one file is attached and the user says 'the file', assume they mean that file.",
            "- When answering from an attached file, cite the file name explicitly.",
            "- If multiple files are attached and the request is ambiguous, ask which file the user means.",
        ]
    )
    return "\n".join(lines)


def build_attachment_user_input(
    message: str,
    *,
    attachments: list[dict] | None = None,
    fallback_parser=None,
) -> AttachmentPayload:
    if not attachments:
        if fallback_parser is None:
            return AttachmentPayload(user_input=message.strip(), warnings=[])
        return AttachmentPayload(user_input=fallback_parser(message), warnings=[])

    payload: list[dict] = []
    warnings: list[str] = []
    attachment_summaries: list[tuple[str, str]] = []

    if message.strip():
        payload.append({"type": "text", "text": message.strip()})

    has_images = False
    remaining_total_chars = MAX_TOTAL_ATTACHMENT_CHARS
    for attachment in (attachments or [])[:MAX_ATTACHMENTS]:
        kind = str(attachment.get("kind") or "file")
        name = str(attachment.get("name") or "attachment")
        data_url = str(attachment.get("data_url") or "")
        lower_name = name.lower()
        if not data_url.startswith("data:"):
            warnings.append(f"{name}: invalid attachment payload")
            continue

        if kind == "image":
            try:
                mime_type, _ = _split_data_url(data_url)
            except Exception as exc:
                warnings.append(f"{name}: {exc}")
                continue
            if mime_type not in IMAGE_MIME_TYPES:
                warnings.append(
                    f"{name}: unsupported image type '{mime_type}'"
                )
                continue
            payload.append({"type": "image_url", "image_url": {"url": data_url}})
            has_images = True
            continue

        if not (
            lower_name.endswith(".pdf")
            or any(lower_name.endswith(ext) for ext in TEXT_EXTENSIONS)
        ):
            warnings.append(f"{name}: unsupported file type")
            continue

        try:
            mime_type, raw = _split_data_url(data_url)
            if lower_name.endswith(".pdf") or mime_type == "application/pdf":
                text = _extract_pdf_text(raw)
            else:
                text = _decode_text_bytes(raw)
        except Exception as exc:
            warnings.append(f"{name}: {exc}")
            continue

        if not text.strip():
            warnings.append(f"{name}: no readable text content found")
            continue

        per_file_text, _ = _truncate_text(
            text,
            max_chars=min(MAX_TEXT_CHARS_PER_ATTACHMENT, remaining_total_chars),
        )
        if not per_file_text.strip():
            warnings.append(f"{name}: attachment budget exceeded")
            continue

        remaining_total_chars -= len(per_file_text)
        attachment_summaries.append((name, mime_type))
        payload.append(
            {
                "type": "text",
                "text": _attachment_block(name, mime_type, per_file_text),
            }
        )
        if remaining_total_chars <= 0:
            warnings.append("Attachment text budget reached; remaining files were skipped.")
            break

    if attachment_summaries or has_images:
        context_block = _attachment_context_block(
            attachment_summaries,
            has_images=has_images,
        )
        insert_at = 1 if payload and payload[0].get("type") == "text" else 0
        payload.insert(insert_at, {"type": "text", "text": context_block})

    if warnings:
        payload.append(
            {
                "type": "text",
                "text": "[Attachment Ingest Notes]\n"
                + "\n".join(f"- {warning}" for warning in warnings),
            }
        )

    return AttachmentPayload(user_input=payload or message.strip(), warnings=warnings)
