"""GitHub read-only collaboration capability."""

from .readonly import fetch_github_snapshot, parse_github_repo_ref

__all__ = ["fetch_github_snapshot", "parse_github_repo_ref"]
