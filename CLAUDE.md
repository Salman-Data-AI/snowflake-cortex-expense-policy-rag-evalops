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
```

These are the same checks as `.github/workflows/checks.yml`.

Hooks in `.claude/settings.json` run them automatically: after every edit of a `.py` file
(`ruff check <file>`), and all three when Claude stops. A failing Stop check sends Claude back once
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
