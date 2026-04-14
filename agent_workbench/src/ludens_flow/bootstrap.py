import os
from pathlib import Path


def load_env_if_available() -> None:
    """Load .env from common locations when python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    candidates: list[Path] = []

    env_var_value = str(os.environ.get("LUDENS_DOTENV_PATH", "")).strip()
    env_from_var = Path(env_var_value) if env_var_value else None
    if env_from_var is not None:
        candidates.append(env_from_var)

    candidates.append(Path.cwd() / ".env")

    # Source tree layout: agent_workbench/src/ludens_flow/*.py
    source_root_candidate = Path(__file__).resolve().parents[3] / ".env"
    candidates.append(source_root_candidate)

    seen = set()
    for candidate in candidates:
        normalized = candidate.expanduser().resolve() if str(candidate) else candidate
        key = str(normalized)
        if not key or key in seen:
            continue
        seen.add(key)
        if normalized.exists() and normalized.is_file():
            load_dotenv(normalized)
            return

    load_dotenv()
