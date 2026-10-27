#!/bin/sh
# PreToolUse hook (Bash): block a `git commit` whose message mentions CR- but isn't
# "fix(review): CR-n <summary>". The rule lives in scripts/check_commit_msg.py, shared with the
# git commit-msg hook in .githooks/. Hook JSON arrives on stdin.
# VERIFY: https://docs.anthropic.com/en/docs/claude-code/hooks (PreToolUse input: tool_input.command)
exec python3 "${CLAUDE_PROJECT_DIR:-.}/scripts/check_commit_msg.py" --pretooluse
