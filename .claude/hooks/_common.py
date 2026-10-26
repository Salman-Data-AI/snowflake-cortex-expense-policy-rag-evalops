"""Shared helpers for the hook scripts. Standard library only, so hooks run without the venv."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# VERIFY: https://docs.anthropic.com/en/docs/claude-code/hooks (CLAUDE_PROJECT_DIR is set for command hooks)
PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def read_input() -> dict:
    """Hook input JSON from stdin; {} if stdin is empty or not a JSON object."""
    try:
        data = json.load(sys.stdin)
    except ValueError:  # includes JSONDecodeError and UnicodeDecodeError
        return {}
    return data if isinstance(data, dict) else {}


def tool(name: str) -> str:
    """The project venv's copy of a tool if there is one, else whatever is on PATH."""
    venv = PROJECT_DIR / ".venv" / "bin" / name
    return str(venv) if venv.exists() else (shutil.which(name) or name)


def run(args: list[str]) -> subprocess.CompletedProcess:
    """Run a check from the project root; a missing tool counts as a failure, not a crash."""
    try:
        return subprocess.run(args, cwd=PROJECT_DIR, capture_output=True, text=True)
    except OSError as e:
        return subprocess.CompletedProcess(args, 127, "", f"{args[0]}: {e}\n")
