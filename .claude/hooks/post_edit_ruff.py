"""PostToolUse hook (Edit|Write|MultiEdit): ruff check the edited file if it is Python.

Exit 0 silently when the file isn't .py or ruff passes. Exit 2 with ruff's output on stderr when
it fails; for PostToolUse that shows the output to Claude (the edit itself has already happened).
"""

from __future__ import annotations

import sys

from _common import read_input, run, tool


def main() -> int:
    data = read_input()
    # VERIFY: https://docs.anthropic.com/en/docs/claude-code/hooks (tool_input.file_path, absolute, for
    # Edit/Write/MultiEdit)
    file_path = (data.get("tool_input") or {}).get("file_path", "")
    if not file_path.endswith(".py"):
        return 0
    result = run([tool("ruff"), "check", file_path])
    if result.returncode == 0:
        return 0
    sys.stderr.write(result.stdout + result.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
