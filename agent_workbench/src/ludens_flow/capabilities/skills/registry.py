"""Global Skill registry with project-level enablement.

Skills are installed globally under workspace/skills/installed/<skill_id>/.
Projects only store which global Skills are enabled for that project.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ludens_flow.core.paths import get_project_dir, get_workspace_root_dir, resolve_project_id


SUPPORTED_SKILL_AGENTS = {"design", "pm", "engineering", "review"}
SKILL_SETTINGS_FILE = "skill_settings.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slugify(value: str) -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9\u4e00-\u9fa5._-]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-.")
    return raw


def _skills_root() -> Path:
    return get_workspace_root_dir() / "skills"


def _installed_skills_dir() -> Path:
    return _skills_root() / "installed"


def _skill_dir(skill_id: str) -> Path:
    safe_id = _normalize_skill_id(skill_id)
    return _installed_skills_dir() / safe_id


def _normalize_skill_id(skill_id: Any, fallback_name: str = "") -> str:
    normalized = _slugify(str(skill_id or "").strip())
    if not normalized:
        normalized = _slugify(fallback_name)
    if not normalized:
        raise ValueError("Skill id or name is required.")
    return normalized


def _normalize_agents(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return ["engineering"]
    agents: list[str] = []
    for item in raw:
        value = str(item or "").strip().lower()
        if value in SUPPORTED_SKILL_AGENTS and value not in agents:
            agents.append(value)
    return agents or ["engineering"]


def _normalize_tags(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    tags: list[str] = []
    for item in raw:
        value = str(item or "").strip()
        if value and value not in tags:
            tags.append(value)
    return tags[:12]


def normalize_skill_manifest(raw: Any, *, source: str = "external") -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Skill manifest must be a JSON object.")

    name = str(raw.get("name") or "").strip()
    if not name:
        raise ValueError("Skill manifest is missing required field: name.")

    skill_id = _normalize_skill_id(raw.get("id"), name)
    manifest = {
        "id": skill_id,
        "name": name,
        "description": str(raw.get("description") or "").strip()
        or "外部导入的 Skill 能力包。",
        "version": str(raw.get("version") or "0.1.0").strip() or "0.1.0",
        "source": source,
        "agents": _normalize_agents(raw.get("agents") or raw.get("scope")),
        "tags": _normalize_tags(raw.get("tags")),
        "updated_at": _now_iso(),
    }
    return manifest


def _read_manifest(path: Path) -> Optional[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return normalize_skill_manifest(raw, source=str(raw.get("source") or "external"))
    except Exception:
        return None


def list_skills() -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    installed_dir = _installed_skills_dir()
    if installed_dir.exists():
        for entry in installed_dir.iterdir():
            if not entry.is_dir():
                continue
            manifest = _read_manifest(entry / "skill.json")
            if not manifest:
                continue
            skills = [item for item in skills if item.get("id") != manifest["id"]]
            skills.append(manifest)

    skills.sort(key=lambda item: (str(item.get("source") or ""), str(item.get("name") or "")))
    return skills


def import_external_skill(manifest: Any, *, prompt: str | None = None) -> dict[str, Any]:
    normalized = normalize_skill_manifest(manifest, source="external")
    target_dir = _skill_dir(normalized["id"])
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "skill.json").write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if prompt is not None:
        (target_dir / "prompt.md").write_text(str(prompt), encoding="utf-8")
    return normalized


def delete_skill(skill_id: str) -> str:
    safe_id = _normalize_skill_id(skill_id)
    target_dir = _skill_dir(safe_id)
    if not target_dir.exists():
        raise FileNotFoundError(f"Skill not found: {safe_id}")
    shutil.rmtree(target_dir)

    for project in (get_workspace_root_dir() / "projects").iterdir() if (get_workspace_root_dir() / "projects").exists() else []:
        settings_file = project / SKILL_SETTINGS_FILE
        if not settings_file.exists():
            continue
        settings = _read_project_skill_settings(project.name)
        enabled = [item for item in settings.get("enabled_skill_ids", []) if item != safe_id]
        _write_project_skill_settings(project.name, enabled)
    return safe_id


def _project_skill_settings_file(project_id: str | None = None) -> Path:
    resolved = resolve_project_id(project_id)
    if not resolved:
        raise ValueError("Project id is required.")
    return get_project_dir(resolved) / SKILL_SETTINGS_FILE


def _read_project_skill_settings(project_id: str | None = None) -> dict[str, Any]:
    settings_file = _project_skill_settings_file(project_id)
    if not settings_file.exists():
        return {"enabled_skill_ids": []}
    try:
        raw = json.loads(settings_file.read_text(encoding="utf-8"))
    except Exception:
        return {"enabled_skill_ids": []}
    enabled = raw.get("enabled_skill_ids")
    if not isinstance(enabled, list):
        enabled = []
    return {"enabled_skill_ids": [_normalize_skill_id(item) for item in enabled if str(item).strip()]}


def _write_project_skill_settings(project_id: str | None, enabled_skill_ids: list[str]) -> dict[str, Any]:
    settings_file = _project_skill_settings_file(project_id)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    available_ids = {item["id"] for item in list_skills()}
    normalized = []
    for item in enabled_skill_ids:
        skill_id = _normalize_skill_id(item)
        if skill_id in available_ids and skill_id not in normalized:
            normalized.append(skill_id)
    payload = {"enabled_skill_ids": normalized, "updated_at": _now_iso()}
    settings_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def get_project_skills(project_id: str | None = None) -> dict[str, Any]:
    resolved = resolve_project_id(project_id)
    if not resolved:
        raise ValueError("Project id is required.")
    settings = _read_project_skill_settings(resolved)
    available_ids = {item["id"] for item in list_skills()}
    enabled = [item for item in settings["enabled_skill_ids"] if item in available_ids]
    return {
        "project_id": resolved,
        "skills": list_skills(),
        "enabled_skill_ids": enabled,
    }


def set_project_skill_enabled(
    skill_id: str,
    enabled: bool,
    *,
    project_id: str | None = None,
) -> dict[str, Any]:
    resolved = resolve_project_id(project_id)
    safe_id = _normalize_skill_id(skill_id)
    available_ids = {item["id"] for item in list_skills()}
    if safe_id not in available_ids:
        raise FileNotFoundError(f"Skill not found: {safe_id}")

    current = set(_read_project_skill_settings(resolved)["enabled_skill_ids"])
    if enabled:
        current.add(safe_id)
    else:
        current.discard(safe_id)
    _write_project_skill_settings(resolved, sorted(current))
    return get_project_skills(resolved)
