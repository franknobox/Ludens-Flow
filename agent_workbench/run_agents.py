"""Compatibility wrapper for legacy `python agent_workbench/run_agents.py` usage."""

from ludens_flow.cli import main
from ludens_flow.input_parser import parse_user_input

__all__ = ["main", "parse_user_input"]


if __name__ == "__main__":
    main()
