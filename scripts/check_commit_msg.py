"""Commit messages that mention a review finding (CR-n) must use the fix(review) format.

    fix(review): CR-3 <what changed>
    fix(review): CR-3, CR-5 <what changed>

Two entry points, one rule:
- git commit-msg hook (.githooks/commit-msg):  python3 scripts/check_commit_msg.py <message-file>
- Claude Code PreToolUse hook (.claude/hooks/check_commit_msg.sh):
      python3 scripts/check_commit_msg.py --pretooluse   (hook JSON on stdin; exit 2 blocks the command)
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

FORMAT_RE = re.compile(r"^fix\(review\): CR-[0-9]+(, CR-[0-9]+)* .+")
EXPECTED = "fix(review): CR-<n>[, CR-<n>...] <what changed>   e.g. fix(review): CR-3 Skip empty pages"
SEPARATORS = {"&&", "||", ";", "|", "&"}
HEREDOC_RE = re.compile(r"^\$\(cat <<-?\s*['\"]?(\w+)['\"]?\n(.*)\n\s*\1\s*\)$", re.S)
# Messages git writes itself (git revert, --fixup/--squash, merges) keep their own format.
GIT_GENERATED = ('Revert "', "fixup! ", "squash! ", "amend! ", "Merge ")
SCISSORS = "# ------------------------ >8 ------------------------"


def check_message(message: str) -> str | None:
    """Error text, or None when the message is fine."""
    message = message.lstrip("\n")
    if "CR-" not in message or FORMAT_RE.match(message) or message.startswith(GIT_GENERATED):
        return None
    subject = message.splitlines()[0] if message.strip() else ""
    return f"Commit message mentions CR- but doesn't match the review-fix format.\n  got:      {subject}\n" \
           f"  expected: {EXPECTED}"


def _unwrap(value: str) -> str:
    """-m "$(cat <<'EOF' ... EOF)" -> the heredoc text."""
    m = HEREDOC_RE.match(value.strip())
    return m.group(2) if m else value


def messages_from_command(command: str) -> list[str]:
    """Messages given with -m/--message to each `git ... commit` in a shell command line.

    A commit whose message comes from an editor or -F is not returned; the git hook checks those.
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:  # unbalanced quotes: let git report it
        return []
    commands, current = [], []
    for tok in tokens:
        if tok in SEPARATORS:
            commands.append(current)
            current = []
        else:
            current.append(tok)
    commands.append(current)

    messages = []
    for words in commands:
        if not words or Path(words[0]).name != "git" or "commit" not in words[1:]:
            continue
        args = words[words.index("commit") + 1:]
        parts = []
        for i, arg in enumerate(args):
            if arg in ("-m", "--message") or (re.fullmatch(r"-[a-zA-Z]*m", arg) and arg != "-m"):
                if i + 1 < len(args):
                    parts.append(_unwrap(args[i + 1]))
            elif arg.startswith("--message="):
                parts.append(_unwrap(arg.split("=", 1)[1]))
        if parts:
            messages.append("\n\n".join(parts))  # git joins several -m values as paragraphs
    return messages


def main(argv: list[str]) -> int:
    if argv[1:] == ["--pretooluse"]:
        try:
            data = json.load(sys.stdin)
        except ValueError:
            return 0
        command = ((data.get("tool_input") or {}).get("command") or "") if isinstance(data, dict) else ""
        errors = [e for m in messages_from_command(command) if (e := check_message(m))]
    elif len(argv) == 2:
        text = Path(argv[1]).read_text(encoding="utf-8").split(SCISSORS, 1)[0]  # drop `commit -v` diff
        message = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
        errors = [e for e in [check_message(message)] if e]
    else:
        print(__doc__, file=sys.stderr)
        return 2
    for e in errors:
        print(e, file=sys.stderr)
    if not errors:
        return 0
    # PreToolUse: exit 2 blocks the tool call and shows stderr to Claude. commit-msg: non-zero aborts.
    # VERIFY: https://docs.anthropic.com/en/docs/claude-code/hooks (PreToolUse exit 2 blocks the call)
    return 2 if argv[1:] == ["--pretooluse"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
