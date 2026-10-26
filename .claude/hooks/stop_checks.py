"""Stop hook: run the offline checks (same as checks.yml) before Claude finishes a turn.

- Checks pass: exit 0.
- Checks fail, first stop: failing output on stderr, exit 2, so Claude keeps going and fixes them.
- Checks fail again on the retry (stop_hook_active is true): say so and exit 1, so Claude stops and
  the failure is shown to the user. One retry only; there is deliberately no counter.
"""

from __future__ import annotations

import sys

from _common import read_input, run, tool

CHECKS = [
    ["ruff", "check", "."],
    ["pytest", "-q"],
    ["sqlfluff", "lint", "pipeline/", "eval/", "--dialect", "snowflake"],
]

GAVE_UP = "Checks still failing after one retry; stopping. See output above.\n"


def main() -> int:
    data = read_input()
    # VERIFY: https://docs.anthropic.com/en/docs/claude-code/hooks (stop_hook_active is true when Claude
    # is already continuing because a Stop hook blocked the previous stop)
    retrying = bool(data.get("stop_hook_active"))

    failures = []
    for cmd in CHECKS:
        result = run([tool(cmd[0]), *cmd[1:]])
        if result.returncode != 0:
            failures.append(f"$ {' '.join(cmd)}\n{result.stdout}{result.stderr}")
    if not failures:
        return 0

    if retrying:
        # VERIFY: https://docs.anthropic.com/en/docs/claude-code/hooks (a non-2 exit is non-blocking, and
        # the notice shows the user only the first line of stderr, so the message goes first; "above"
        # is the output from the blocked first stop)
        sys.stderr.write(GAVE_UP + "\n".join(failures))
        return 1
    sys.stderr.write("\n".join(failures))
    return 2


if __name__ == "__main__":
    sys.exit(main())
