from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


_PROMPT_DIR = Path(__file__).resolve().parents[3] / "prompts"


@dataclass
class PromptTemplate:
    role_persona: str = ""
    task_instruction: str = ""
    context_injection: str = ""
    output_contract: str = ""
    profile_instruction: str = ""

    def build_system_prompt(self) -> str:
        sections = [
            ("Role & Persona", self.role_persona),
            ("Task Instruction", self.task_instruction),
            ("Context Injection", self.context_injection),
            ("Output Contract", self.output_contract),
        ]

        parts: list[str] = []
        for title, content in sections:
            content = (content or "").strip()
            if not content:
                continue
            parts.append(f"## {title}\n{content}")
        return "\n\n".join(parts).strip()


def _extract_section(text: str, name: str) -> str:
    start_tag = f"==={name}==="
    start_idx = text.find(start_tag)
    if start_idx == -1:
        return ""

    content_start = start_idx + len(start_tag)
    next_idx = text.find("===", content_start)
    if next_idx == -1:
        return text[content_start:].strip()
    return text[content_start:next_idx].strip()


def _has_layered_sections(text: str) -> bool:
    return "===ROLE_PERSONA===" in text


def load_prompt_template(filename: str) -> Optional[PromptTemplate]:
    prompt_path = _PROMPT_DIR / filename
    if not prompt_path.exists():
        return None

    content = prompt_path.read_text(encoding="utf-8").strip()
    if not content:
        return PromptTemplate()

    if _has_layered_sections(content):
        return PromptTemplate(
            role_persona=_extract_section(content, "ROLE_PERSONA"),
            task_instruction=_extract_section(content, "TASK_INSTRUCTION"),
            context_injection=_extract_section(content, "CONTEXT_INJECTION"),
            output_contract=_extract_section(content, "OUTPUT_CONTRACT"),
            profile_instruction=_extract_section(content, "PROFILE_INSTRUCTION"),
        )

    legacy_parts = content.split("===PROFILE_INSTRUCTION===")
    system_prompt = legacy_parts[0].strip() if legacy_parts else ""
    profile_instruction = legacy_parts[1].strip() if len(legacy_parts) > 1 else ""
    return PromptTemplate(
        role_persona=system_prompt,
        profile_instruction=profile_instruction,
    )
