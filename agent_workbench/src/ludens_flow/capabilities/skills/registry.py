"""Global Skill registry with project-level enablement.

Skills are installed globally under workspace/skills/installed/<skill_id>/.
Projects only store which global Skills are enabled for that project.
"""

from __future__ import annotations

import json
import re
import shutil
import base64
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from ludens_flow.capabilities.paths import (
    SKILL_SETTINGS_FILE,
    get_draft_skills_dir,
    get_installed_skills_dir,
    get_project_skill_settings_file,
    get_skill_draft_dir,
    get_skill_install_dir,
    get_skills_root_dir,
)
from ludens_flow.core.paths import resolve_project_id


SUPPORTED_SKILL_AGENTS = {"design", "pm", "engineering", "review"}
MAX_SKILL_FILE_BYTES = 2 * 1024 * 1024
MAX_SKILL_PACKAGE_BYTES = 12 * 1024 * 1024
ALLOWED_PACKAGE_ROOTS = {"assets", "examples", "references", "scripts", "agents"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slugify(value: str) -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9\u4e00-\u9fa5._-]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-.")
    return raw


def _skill_dir(skill_id: str) -> Path:
    safe_id = _normalize_skill_id(skill_id)
    return get_skill_install_dir(safe_id)


def _draft_skill_dir(skill_id: str) -> Path:
    safe_id = _normalize_skill_id(skill_id)
    return get_skill_draft_dir(safe_id)


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


def _parse_simple_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse the common SKILL.md YAML header without adding a YAML dependency."""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    end_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {}, text

    metadata: dict[str, Any] = {}
    for raw_line in lines[1:end_index]:
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            metadata[key] = value

    body = "\n".join(lines[end_index + 1:]).lstrip()
    return metadata, body or text


def _manifest_from_skill_md(skill_md_path: str, data: bytes) -> tuple[dict[str, Any], str]:
    try:
        text = data.decode("utf-8")
    except Exception as exc:
        raise ValueError("SKILL.md must be valid UTF-8 Markdown.") from exc

    frontmatter, _body = _parse_simple_frontmatter(text)
    folder_name = Path(skill_md_path.replace("\\", "/")).parent.name
    name = str(frontmatter.get("name") or folder_name or "Imported Skill").strip()
    description = str(frontmatter.get("description") or "").strip()
    manifest = {
        "id": frontmatter.get("id") or folder_name or name,
        "name": name,
        "description": description or "外部导入的 SKILL.md 能力包。",
        "version": str(frontmatter.get("version") or "0.1.0"),
        "agents": frontmatter.get("agents") or ["engineering"],
        "tags": _normalize_tags([frontmatter.get("name") or folder_name]),
    }
    return manifest, text


def _decode_data_url(value: str) -> bytes:
    text = str(value or "")
    if "," in text and text.lower().startswith("data:"):
        text = text.split(",", 1)[1]
    try:
        return base64.b64decode(text, validate=True)
    except Exception as exc:
        raise ValueError("Skill file data must be base64 encoded.") from exc


def _file_bytes_from_payload(item: dict[str, Any]) -> bytes:
    if "data_url" in item:
        data = _decode_data_url(str(item.get("data_url") or ""))
    elif "base64" in item:
        data = _decode_data_url(str(item.get("base64") or ""))
    elif "text" in item:
        data = str(item.get("text") or "").encode("utf-8")
    else:
        data = b""
    if len(data) > MAX_SKILL_FILE_BYTES:
        raise ValueError("A single Skill file is too large.")
    return data


def _normalize_package_path(path: Any) -> str:
    raw = str(path or "").replace("\\", "/").strip()
    raw = raw.lstrip("/")
    parts = [part for part in raw.split("/") if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        raise ValueError(f"Unsafe Skill package path: {raw}")
    return "/".join(parts)


def _relative_to_skill_root(path: str, root_prefix: str) -> str:
    normalized = _normalize_package_path(path)
    prefix = _normalize_package_path(root_prefix) if root_prefix else ""
    if prefix:
        if normalized == prefix.rstrip("/"):
            return ""
        marker = prefix.rstrip("/") + "/"
        if not normalized.startswith(marker):
            raise ValueError(f"File is outside Skill root: {path}")
        normalized = normalized[len(marker):]
    return _normalize_package_path(normalized)


def _safe_copy_package_file(target_dir: Path, rel_path: str, data: bytes) -> None:
    rel = _normalize_package_path(rel_path)
    first = rel.split("/", 1)[0]
    if rel not in {"skill.json", "prompt.md", "SKILL.md", "draft_meta.json"} and first not in ALLOWED_PACKAGE_ROOTS:
        return
    if rel in {"skill.json", "SKILL.md"}:
        return
    target = (target_dir / rel).resolve()
    root = target_dir.resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"Unsafe Skill package path: {rel}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def _replace_skill_dir(target_dir: Path, manifest: dict[str, Any], files: list[tuple[str, bytes]]) -> None:
    with tempfile.TemporaryDirectory(prefix="ludens-skill-") as tmp:
        tmp_dir = Path(tmp) / manifest["id"]
        tmp_dir.mkdir(parents=True, exist_ok=True)
        (tmp_dir / "skill.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        for rel_path, data in files:
            _safe_copy_package_file(tmp_dir, rel_path, data)

        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_dir), str(target_dir))


def _install_skill_package(
    manifest: Any,
    *,
    prompt: str | None = None,
    files: list[tuple[str, bytes]] | None = None,
    source: str = "external",
) -> dict[str, Any]:
    normalized = normalize_skill_manifest(manifest, source=source)
    package_files = list(files or [])
    if prompt is not None:
        package_files = [
            item for item in package_files if _normalize_package_path(item[0]) != "prompt.md"
        ]
        package_files.append(("prompt.md", str(prompt).encode("utf-8")))
    target_dir = _skill_dir(normalized["id"])
    _replace_skill_dir(target_dir, normalized, package_files)
    return normalized


def _read_manifest(path: Path) -> Optional[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return normalize_skill_manifest(raw, source=str(raw.get("source") or "external"))
    except Exception:
        return None


def list_skills() -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    installed_dir = get_installed_skills_dir()
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
    return _install_skill_package(manifest, prompt=prompt, source="external")


def import_external_skill_bundle(files: Any) -> dict[str, Any]:
    if not isinstance(files, list) or not files:
        raise ValueError("Skill package files are required.")

    package: list[tuple[str, bytes]] = []
    total_bytes = 0
    for item in files:
        if not isinstance(item, dict):
            continue
        rel_path = _normalize_package_path(item.get("path") or item.get("relative_path"))
        data = _file_bytes_from_payload(item)
        total_bytes += len(data)
        if total_bytes > MAX_SKILL_PACKAGE_BYTES:
            raise ValueError("Skill package is too large.")
        package.append((rel_path, data))

    skill_json_candidates = [
        (path, data)
        for path, data in package
        if path.lower().endswith("/skill.json") or path.lower() == "skill.json"
    ]
    skill_md_candidates = [
        (path, data)
        for path, data in package
        if path.endswith("/SKILL.md") or path == "SKILL.md"
    ]

    if skill_json_candidates:
        manifest_path, manifest_data = sorted(
            skill_json_candidates,
            key=lambda item: (item[0].count("/"), len(item[0])),
        )[0]
        root_prefix = manifest_path.rsplit("/", 1)[0] if "/" in manifest_path else ""
        try:
            manifest = json.loads(manifest_data.decode("utf-8"))
        except Exception as exc:
            raise ValueError("skill.json must be valid UTF-8 JSON.") from exc
        prompt_override: str | None = None
    elif skill_md_candidates:
        manifest_path, manifest_data = sorted(
            skill_md_candidates,
            key=lambda item: (item[0].count("/"), len(item[0])),
        )[0]
        root_prefix = manifest_path.rsplit("/", 1)[0] if "/" in manifest_path else ""
        manifest, prompt_override = _manifest_from_skill_md(manifest_path, manifest_data)
    else:
        raise ValueError("Skill package must contain skill.json or SKILL.md.")

    rel_files: list[tuple[str, bytes]] = []
    for path, data in package:
        rel = _relative_to_skill_root(path, root_prefix)
        if rel == "SKILL.md":
            rel = "prompt.md"
        rel_files.append((rel, data))
    return _install_skill_package(
        manifest,
        prompt=prompt_override,
        files=rel_files,
        source="external",
    )


def import_external_skill_zip(data_url: str) -> dict[str, Any]:
    data = _decode_data_url(data_url)
    if len(data) > MAX_SKILL_PACKAGE_BYTES:
        raise ValueError("Skill zip package is too large.")
    with tempfile.TemporaryDirectory(prefix="ludens-skill-zip-") as tmp:
        zip_path = Path(tmp) / "skill.zip"
        zip_path.write_bytes(data)
        package: list[dict[str, Any]] = []
        try:
            with zipfile.ZipFile(zip_path) as archive:
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    if info.file_size > MAX_SKILL_FILE_BYTES:
                        raise ValueError("A single Skill file is too large.")
                    content = archive.read(info.filename)
                    package.append(
                        {
                            "path": info.filename,
                            "base64": base64.b64encode(content).decode("ascii"),
                        }
                    )
        except zipfile.BadZipFile as exc:
            raise ValueError("Invalid Skill zip package.") from exc
    return import_external_skill_bundle(package)


def _github_zip_urls(url: str) -> list[str]:
    parsed = urlparse(str(url or "").strip())
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise ValueError("Only GitHub repository URLs are supported.")
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        raise ValueError("GitHub URL must include owner and repository.")
    owner, repo = parts[0], parts[1].removesuffix(".git")
    branch = "main"
    if len(parts) >= 4 and parts[2] == "tree":
        branch = parts[3]
    branches = [branch]
    if branch == "main":
        branches.append("master")
    return [f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{item}" for item in branches]


def import_external_skill_github(url: str) -> dict[str, Any]:
    errors: list[str] = []
    for zip_url in _github_zip_urls(url):
        try:
            request = urllib.request.Request(
                zip_url,
                headers={"User-Agent": "Ludens-Flow Skill Importer"},
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                data = response.read(MAX_SKILL_PACKAGE_BYTES + 1)
            if len(data) > MAX_SKILL_PACKAGE_BYTES:
                raise ValueError("GitHub Skill package is too large.")
            return import_external_skill_zip(base64.b64encode(data).decode("ascii"))
        except Exception as exc:
            errors.append(str(exc))
            continue
    raise ValueError("Failed to import Skill from GitHub URL: " + "; ".join(errors[-2:]))


def create_skill_draft(
    manifest: Any,
    *,
    prompt: str,
    project_id: str | None = None,
    source_agent: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_skill_manifest(manifest, source="draft")
    target_dir = _draft_skill_dir(normalized["id"])
    metadata = {
        "project_id": resolve_project_id(project_id) if project_id else "",
        "source_agent": str(source_agent or "").strip(),
        "reason": str(reason or "").strip(),
        "created_at": _now_iso(),
    }
    files = [
        ("prompt.md", str(prompt or "").encode("utf-8")),
        ("draft_meta.json", json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8")),
    ]
    _replace_skill_dir(target_dir, normalized, files)
    return normalized


def build_enabled_skill_context(
    *,
    project_id: str | None,
    agent_key: str,
    max_chars: int = 12000,
) -> str:
    resolved = resolve_project_id(project_id)
    if not resolved:
        return ""
    agent = str(agent_key or "").strip().lower()
    project_skills = get_project_skills(resolved)
    enabled_ids = set(project_skills.get("enabled_skill_ids") or [])
    if not enabled_ids:
        return ""

    chunks: list[str] = []
    used_chars = 0
    for manifest in project_skills.get("skills", []):
        if manifest.get("id") not in enabled_ids:
            continue
        if agent not in manifest.get("agents", []):
            continue
        prompt_path = _skill_dir(str(manifest["id"])) / "prompt.md"
        try:
            prompt_text = prompt_path.read_text(encoding="utf-8").strip()
        except Exception:
            prompt_text = ""
        if not prompt_text:
            continue
        chunk = (
            f"### {manifest.get('name')} ({manifest.get('id')})\n"
            f"- 适用 Agent: {', '.join(manifest.get('agents') or [])}\n"
            f"- 说明: {manifest.get('description', '')}\n"
            f"- 标签: {', '.join(manifest.get('tags') or [])}\n\n"
            f"{prompt_text[:6000]}"
        ).strip()
        if used_chars + len(chunk) > max_chars:
            break
        chunks.append(chunk)
        used_chars += len(chunk)

    if not chunks:
        return ""
    return (
        "以下是当前项目启用、且适用于你这个 Agent 的 Skills。"
        "它们是可复用的工作方法或约束。只在与本轮任务相关时使用；不要机械复述 Skill 名称。\n\n"
        + "\n\n---\n\n".join(chunks)
    )


def delete_skill(skill_id: str) -> str:
    safe_id = _normalize_skill_id(skill_id)
    target_dir = _skill_dir(safe_id)
    if not target_dir.exists():
        raise FileNotFoundError(f"Skill not found: {safe_id}")
    shutil.rmtree(target_dir)

    projects_dir = get_skills_root_dir().parent / "projects"
    for project in projects_dir.iterdir() if projects_dir.exists() else []:
        settings_file = project / SKILL_SETTINGS_FILE
        if not settings_file.exists():
            continue
        settings = _read_project_skill_settings(project.name)
        enabled = [item for item in settings.get("enabled_skill_ids", []) if item != safe_id]
        _write_project_skill_settings(project.name, enabled)
    return safe_id


def _project_skill_settings_file(project_id: str | None = None) -> Path:
    return get_project_skill_settings_file(project_id)


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
