"""Compatibility wrapper for legacy `agent_workbench.api` imports."""

from ludens_flow.api import app, main

__all__ = ["app", "main"]


if __name__ == "__main__":
    main()
