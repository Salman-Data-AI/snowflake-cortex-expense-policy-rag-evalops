# CLAUDE.md

Snowflake Cortex RAG + evaluation over UC travel and expense policy PDFs. See README.md for the
pipeline and repository layout.

## Offline only

- No Snowflake account is connected to this machine. Never make Snowflake calls from here:
  no `snow` commands, no `get_session()`, no running `pipeline/02_chunk.py`, `pipeline/record_run.py`,
  `app/ask.py` or `eval/run_eval.py`. Those run only in `run-pipeline.yml` (manual) or Phase 2.
- Work that can be checked offline: `pipeline/chunker.py`, config, data files, tests, SQL lint.

## Checks

Run from the repo root with the venv active (`source .venv/bin/activate`). All three must pass:

```bash
ruff check .
pytest -q
sqlfluff lint pipeline/ eval/ --dialect snowflake
python scripts/check_decisions.py
```

These are the same checks as `.github/workflows/checks.yml`. `check_decisions.py` makes sure the
`REVIEW.md` decision index and `docs/decisions.md` match; pytest also runs it.

Hooks in `.claude/settings.json` run them automatically: after every edit of a `.py` file
(`ruff check <file>`), and ruff, pytest and sqlfluff when Claude stops (pytest covers the decision check). A failing Stop check sends Claude back once
to fix it; if it still fails, Claude stops and shows the failure.

## Workflow

For each task:

1. Implement it.
2. Stop hook checks pass.
3. Ask the `reviewer` agent (`.claude/agents/reviewer.md`) to review the branch, giving it the task
   spec word for word.
4. Fix every must-fix finding (rerun the checks); fix should-fix findings or say why not.
5. Stop and report the changes, test results and reviewer summary. I review, commit and push myself.

The report includes the reviewer's summary: its verdict and the findings, with what was fixed.

## PR and review workflow

PRs get an advisory Claude review when labeled `claude-review` (`REVIEW.md`, D-008). Findings are
tagged `[CR-n]`. To ask for a fresh full review, remove the label and add it again.

- **Branches:** rebase PR branches onto `main` (`git rebase origin/main`); don't merge `main` into
  them. After a rebase and force-push, the next Claude review is a full one.
- **Design decisions:** when you make a non-obvious design choice, add a `D-` entry to
  `docs/decisions.md` and its index line to `REVIEW.md` in the same PR.
  `python scripts/check_decisions.py` (also in `checks.yml`) checks they match.
- **Opening a PR:** fill in `.github/pull_request_template.md`, including Design decisions.
- **When a review arrives:** start with `/review-triage <PR>`. Never fix or reply before I've
  confirmed the triage.
- **Fixing findings** (`/review-fix`): read the open threads with `gh`, fix, run the local checks,
  then show me the diff and a commit message `fix(review): CR-n <summary>` (one finding per commit
  where practical). I commit and push myself (see Git). To check my own commit messages too, enable
  the git hook once per clone: `git config core.hooksPath .githooks`.
- **Answering a thread** (`/review-reply`): draft the reply, show it to me, and post it only after I
  approve, via `gh api repos/{owner}/{repo}/pulls/{n}/comments/{comment_id}/replies`. Start every reply
  with one of `Design decision (D-00x):`, `Agreed, will fix:` or `Won't fix:`. If the rationale isn't
  in `docs/decisions.md`, propose adding it. Don't resolve threads yourself; the re-review or I will.
- **Enforced by `.claude/settings.json`:** `ask` for `gh api` calls that may write (any `-X`/`--method`,
  `-f`/`-F`/`--field`/`--raw-field`/`--input`, any flag before the endpoint, replies,
  `resolveReviewThread`; GraphQL reads and `--paginate` reads prompt too), `gh pr review`,
  `gh pr merge`, `gh pr comment`, `gh pr edit`, `gh pr close` and `gh issue comment`; a
  `PreToolUse` hook rejects a `git commit` that mentions `CR-` in any other format.

## Git

I commit and push myself. Never run `git commit` or `git push`. `.claude/settings.json` has `deny`
rules for both.

Never change anything under `.claude/` (settings, hooks, agents) or `CLAUDE.md` without my approval
in the current turn. This covers every way of changing them: the Edit and Write tools, and Bash
(`sed -i`, `echo >`, `tee`, `mv`, `cp`, `rm`, `git checkout`/`restore`, or a script that writes the
file). The `ask` rules for `Edit(/.claude/**)` and `Edit(/CLAUDE.md)` don't catch all of these.

## Python

Python 3.12 everywhere: `.python-version`, `pyproject.toml` (`target-version`), and both workflows.
Change them together.

## VERIFY convention

Any line written from the docs but not yet run against Snowflake carries a `VERIFY` comment saying
what to check. Add one when you write such a line; remove it only after it has actually run.
`grep -rn VERIFY .` is the Phase 2 checklist.

## Prompts

A prompt change creates a new `app/prompt_vN.txt` and bumps `prompt_version` in `config/rag.yaml`;
don't edit an existing prompt file. Evaluation results are keyed by `prompt_version`, so editing
a file in place makes old and new runs look identical.
