"""Read-only GitHub integration helpers.

This module intentionally avoids local git commands and GitHub write APIs.
It only reads repository collaboration state through GitHub's HTTP API.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

GITHUB_API_BASE = "https://api.github.com"
GITHUB_WEB_RE = re.compile(r"^https?://github\.com/([^/\s]+)/([^/\s#?]+)", re.I)
GITHUB_SSH_RE = re.compile(r"^git@github\.com:([^/\s]+)/([^/\s#?]+)", re.I)
OWNER_REPO_RE = re.compile(r"^([^/\s]+)/([^/\s#?]+)$")


class GitHubReadError(RuntimeError):
    pass


def _clean_repo_name(repo: str) -> str:
    return str(repo or "").strip().removesuffix(".git")


def parse_github_repo_ref(value: str) -> Dict[str, str]:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("GitHub repo is required.")

    match = GITHUB_WEB_RE.match(raw) or GITHUB_SSH_RE.match(raw) or OWNER_REPO_RE.match(raw)
    if not match:
        raise ValueError("GitHub repo must be owner/repo or a github.com repository URL.")

    owner = match.group(1).strip()
    repo = _clean_repo_name(match.group(2))
    if not owner or not repo:
        raise ValueError("GitHub repo owner and name are required.")

    return {
        "owner": owner,
        "repo": repo,
        "url": f"https://github.com/{owner}/{repo}",
    }


def _github_token() -> str:
    token = (
        os.getenv("LUDENS_GITHUB_TOKEN")
        or os.getenv("GITHUB_TOKEN")
        or os.getenv("GH_TOKEN")
        or ""
    ).strip()
    if token:
        return token
    return _github_token_from_dotenv()


def _github_token_from_dotenv() -> str:
    candidates: List[Path] = []
    explicit = str(os.getenv("LUDENS_DOTENV_PATH", "")).strip()
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(Path.cwd() / ".env")
    candidates.append(Path(__file__).resolve().parents[5] / ".env")
    candidates.append(Path(__file__).resolve().parents[4] / ".env")

    seen: set[str] = set()
    for candidate in candidates:
        try:
            path = candidate.expanduser().resolve()
        except Exception:
            continue
        key = str(path)
        if key in seen or not path.exists() or not path.is_file():
            continue
        seen.add(key)

        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                match = re.match(r"^\s*(LUDENS_GITHUB_TOKEN|GITHUB_TOKEN|GH_TOKEN)\s*=\s*(.*)\s*$", line)
                if not match:
                    continue
                value = match.group(2).strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                    value = value[1:-1].strip()
                if value:
                    return value
        except OSError:
            continue
    return ""


def _headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Ludens-Flow",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request_json(path: str) -> Any:
    request = Request(f"{GITHUB_API_BASE}{path}", headers=_headers())
    try:
        with urlopen(request, timeout=12) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload) if payload else None
    except HTTPError as exc:
        detail = exc.reason
        try:
            raw = exc.read().decode("utf-8")
            body = json.loads(raw) if raw else {}
            detail = body.get("message") or detail
        except Exception:
            pass
        raise GitHubReadError(f"GitHub API {exc.code}: {detail}") from exc
    except URLError as exc:
        raise GitHubReadError(f"GitHub API request failed: {exc.reason}") from exc


def _safe_request(path: str, errors: List[str], fallback: Any) -> Any:
    try:
        return _request_json(path)
    except GitHubReadError as exc:
        errors.append(str(exc))
        return fallback


def _repo_path(owner: str, repo: str, suffix: str = "") -> str:
    base = f"/repos/{quote(owner)}/{quote(repo)}"
    return f"{base}{suffix}"


def _short_sha(value: str) -> str:
    return str(value or "")[:7]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _login(raw: Any) -> str:
    if isinstance(raw, dict):
        return str(raw.get("login") or "").strip()
    return ""


def _commit_author(commit: Dict[str, Any]) -> str:
    author = commit.get("author")
    if isinstance(author, dict):
        name = str(author.get("name") or "").strip()
        if name:
            return name
    return _login(commit.get("author")) or "unknown"


def _status_for_ref(owner: str, repo: str, ref: str, errors: List[str]) -> str:
    if not ref:
        return "unknown"
    payload = _safe_request(
        _repo_path(owner, repo, f"/commits/{quote(ref, safe='')}/status"),
        errors,
        {},
    )
    state = str(payload.get("state") or "").lower() if isinstance(payload, dict) else ""
    if state in {"success", "failure", "pending", "error"}:
        return "failure" if state == "error" else state
    return "unknown"


def _review_decision(owner: str, repo: str, number: int, errors: List[str]) -> str:
    reviews = _safe_request(
        _repo_path(owner, repo, f"/pulls/{number}/reviews?per_page=30"),
        errors,
        [],
    )
    if not isinstance(reviews, list) or not reviews:
        return "pending"
    states = [str(item.get("state") or "").upper() for item in reviews if isinstance(item, dict)]
    if "CHANGES_REQUESTED" in states:
        return "changes_requested"
    if "APPROVED" in states:
        return "approved"
    return "pending"


def _summarize(
    branches: List[Dict[str, Any]],
    commits: List[Dict[str, Any]],
    pulls: List[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    workflow_runs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    open_prs = [item for item in pulls if item.get("state") == "open"]
    failing_runs = [
        item
        for item in workflow_runs
        if item.get("conclusion") in {"failure", "timed_out", "cancelled", "action_required"}
    ]
    active_authors = sorted(
        {
            str(item.get("author") or "").strip()
            for item in commits
            if str(item.get("author") or "").strip()
        }
    )
    return {
        "branch_count": len(branches),
        "recent_commit_count": len(commits),
        "open_pr_count": len(open_prs),
        "open_issue_count": len(issues),
        "failing_ci_count": len(failing_runs),
        "active_authors": active_authors[:8],
    }


def fetch_github_snapshot(repo_config: Dict[str, str]) -> Dict[str, Any]:
    repo = parse_github_repo_ref(
        f"{repo_config.get('owner', '')}/{repo_config.get('repo', '')}"
    )
    owner = repo["owner"]
    repo_name = repo["repo"]
    errors: List[str] = []
    token_configured = bool(_github_token())

    repo_payload = _request_json(_repo_path(owner, repo_name))
    default_branch = str(repo_payload.get("default_branch") or "main")

    branches_api = _safe_request(
        _repo_path(owner, repo_name, "/branches?per_page=30"),
        errors,
        [],
    )
    if not isinstance(branches_api, list):
        branches_api = []

    branches = [
        {
            "name": str(item.get("name") or ""),
            "is_default": str(item.get("name") or "") == default_branch,
            "is_protected": bool(item.get("protected")),
            "last_commit": _short_sha((item.get("commit") or {}).get("sha", "")),
            "last_commit_time": "",
        }
        for item in branches_api
        if isinstance(item, dict)
    ]

    commits_api = _safe_request(
        _repo_path(owner, repo_name, f"/commits?sha={quote(default_branch, safe='')}&per_page=20"),
        errors,
        [],
    )
    if not isinstance(commits_api, list):
        commits_api = []
    commits = []
    for item in commits_api:
        if not isinstance(item, dict):
            continue
        commit = item.get("commit") if isinstance(item.get("commit"), dict) else {}
        author = commit.get("author") if isinstance(commit.get("author"), dict) else {}
        commits.append(
            {
                "sha": str(item.get("sha") or ""),
                "short_sha": _short_sha(str(item.get("sha") or "")),
                "message": str(commit.get("message") or "").splitlines()[0],
                "author": _login(item.get("author")) or _commit_author(commit),
                "timestamp": str(author.get("date") or ""),
                "branch": default_branch,
                "url": str(item.get("html_url") or ""),
            }
        )

    pulls_api = _safe_request(
        _repo_path(owner, repo_name, "/pulls?state=all&sort=updated&direction=desc&per_page=20"),
        errors,
        [],
    )
    if not isinstance(pulls_api, list):
        pulls_api = []
    pulls = []
    for item in pulls_api[:20]:
        if not isinstance(item, dict):
            continue
        number = int(item.get("number") or 0)
        head = item.get("head") if isinstance(item.get("head"), dict) else {}
        base = item.get("base") if isinstance(item.get("base"), dict) else {}
        merged = bool(item.get("merged_at"))
        state = "merged" if merged else str(item.get("state") or "open")
        head_sha = str(head.get("sha") or "")
        review_decision = (
            _review_decision(owner, repo_name, number, errors)
            if token_configured
            else "pending"
        )
        checks_status = (
            _status_for_ref(owner, repo_name, head_sha, errors)
            if token_configured
            else "unknown"
        )
        pulls.append(
            {
                "id": int(item.get("id") or number),
                "number": number,
                "title": str(item.get("title") or ""),
                "state": state,
                "author": _login(item.get("user")) or "unknown",
                "source_branch": str(head.get("ref") or ""),
                "target_branch": str(base.get("ref") or ""),
                "created_at": str(item.get("created_at") or ""),
                "updated_at": str(item.get("updated_at") or ""),
                "review_decision": review_decision,
                "checks_status": checks_status,
                "url": str(item.get("html_url") or ""),
            }
        )

    issues_api = _safe_request(
        _repo_path(owner, repo_name, "/issues?state=open&sort=updated&direction=desc&per_page=20"),
        errors,
        [],
    )
    if not isinstance(issues_api, list):
        issues_api = []
    issues = [
        {
            "id": int(item.get("id") or item.get("number") or 0),
            "number": int(item.get("number") or 0),
            "title": str(item.get("title") or ""),
            "state": str(item.get("state") or "open"),
            "author": _login(item.get("user")) or "unknown",
            "updated_at": str(item.get("updated_at") or ""),
            "labels": [
                str(label.get("name") or "")
                for label in item.get("labels", [])
                if isinstance(label, dict) and str(label.get("name") or "").strip()
            ],
            "url": str(item.get("html_url") or ""),
        }
        for item in issues_api
        if isinstance(item, dict) and not item.get("pull_request")
    ]

    runs_api = _safe_request(
        _repo_path(owner, repo_name, "/actions/runs?per_page=10"),
        errors,
        {},
    )
    workflow_items = runs_api.get("workflow_runs", []) if isinstance(runs_api, dict) else []
    workflow_runs = [
        {
            "id": int(item.get("id") or 0),
            "name": str(item.get("name") or item.get("display_title") or "Workflow"),
            "status": str(item.get("status") or ""),
            "conclusion": str(item.get("conclusion") or ""),
            "branch": str(item.get("head_branch") or ""),
            "event": str(item.get("event") or ""),
            "updated_at": str(item.get("updated_at") or ""),
            "url": str(item.get("html_url") or ""),
        }
        for item in workflow_items
        if isinstance(item, dict)
    ]

    repo_info = {
        "owner": owner,
        "repo": repo_name,
        "url": str(repo_payload.get("html_url") or repo["url"]),
        "description": str(repo_payload.get("description") or ""),
        "default_branch": default_branch,
        "private": bool(repo_payload.get("private")),
        "stars": int(repo_payload.get("stargazers_count") or 0),
        "forks": int(repo_payload.get("forks_count") or 0),
        "open_issues_count": int(repo_payload.get("open_issues_count") or 0),
    }

    return {
        "configured": True,
        "repo": repo_info,
        "summary": _summarize(branches, commits, pulls, issues, workflow_runs),
        "branches": branches,
        "commits": commits,
        "pull_requests": pulls,
        "issues": issues,
        "workflow_runs": workflow_runs,
        "errors": errors,
        "fetched_at": _iso_now(),
        "auth": {"token_configured": token_configured},
    }
