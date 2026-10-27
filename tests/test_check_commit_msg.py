import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_commit_msg import check_message, messages_from_command

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".claude" / "hooks" / "check_commit_msg.sh"


@pytest.mark.parametrize("message", [
    "fix(review): CR-3 Skip empty pages",
    "fix(review): CR-3, CR-12 Guard header width\n\nLonger body mentioning CR-3 again.",
    "feat: Keep markdown tables intact",          # no CR- at all: not checked
    "",
    "\nfix(review): CR-3 Leading blank line",     # git strips it before committing
    'Revert "fix(review): CR-3 Skip empty pages"\n\nThis reverts commit abc.',
    "fixup! fix(review): CR-3 Skip empty pages",
    "squash! fix(review): CR-3 Skip empty pages",
    "Merge branch 'fix-CR-3' into main",
])
def test_good_messages(message):
    assert check_message(message) is None


@pytest.mark.parametrize("message", [
    "fix: CR-3 Skip empty pages",                 # wrong type/scope
    "fix(review): Skip empty pages for CR-3",     # IDs must come first
    "fix(review): CR-3,CR-4 No space after comma",
    "fix(review): CR-3",                          # no summary
    "Address review findings\n\nFixes CR-3.",     # CR- only in the body
])
def test_bad_messages(message):
    error = check_message(message)
    assert error and "fix(review): CR-<n>" in error


def test_messages_from_command():
    heredoc = 'git commit -m "$(cat <<\'EOF\'\nfix(review): CR-1 Thing\n\nBody\nEOF\n)"'
    assert messages_from_command(heredoc) == ["fix(review): CR-1 Thing\n\nBody"]
    assert messages_from_command('git add . && git commit -am "fix: CR-2 x"') == ["fix: CR-2 x"]
    assert messages_from_command('git -C sub commit --message="a" -m b') == ["a\n\nb"]
    assert messages_from_command("git log --grep CR-3") == []
    assert messages_from_command("echo 'git commit -m x'") == []
    assert messages_from_command("git commit") == []               # editor: the git hook checks it


def run_hook(command: str) -> subprocess.CompletedProcess:
    payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                          "tool_input": {"command": command}})
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT),
           "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}"}
    return subprocess.run(["sh", str(HOOK)], input=payload, capture_output=True, text=True, env=env)


def test_pretooluse_hook_blocks_bad_message_with_exit_2():
    result = run_hook('git commit -m "fix: CR-3 wrong format"')
    assert result.returncode == 2
    assert "expected: fix(review): CR-<n>" in result.stderr


def test_pretooluse_hook_allows_good_message_and_other_commands():
    assert run_hook('git commit -m "fix(review): CR-3 Skip empty pages"').returncode == 0
    assert run_hook("ls -la").returncode == 0


def test_commit_msg_hook_reads_message_file(tmp_path):
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("fix: CR-3 wrong\n# Please enter the commit message\n")
    bad = subprocess.run([sys.executable, str(ROOT / "scripts/check_commit_msg.py"), str(msg)],
                         capture_output=True, text=True)
    assert bad.returncode == 1 and "expected" in bad.stderr
    msg.write_text("fix(review): CR-3 Right\n# CR- in a comment line is ignored\n")
    good = subprocess.run([sys.executable, str(ROOT / "scripts/check_commit_msg.py"), str(msg)])
    assert good.returncode == 0


def test_commit_msg_hook_ignores_verbose_diff_below_scissors(tmp_path):
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("docs: Tweak review guide\n"
                   "# ------------------------ >8 ------------------------\n"
                   "# Do not modify or remove the line above.\n"
                   "diff --git a/REVIEW.md b/REVIEW.md\n+Every inline finding starts with [CR-n]\n")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/check_commit_msg.py"), str(msg)])
    assert result.returncode == 0
