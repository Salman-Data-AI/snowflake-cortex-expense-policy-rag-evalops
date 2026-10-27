---
description: Fix confirmed Claude review findings locally, run the checks, and stop before committing
argument-hint: <PR number> <CR-ids, e.g. CR-3 CR-5>
---

Fix the review findings I confirmed in `/review-triage`. Arguments: PR number first, then the
CR IDs: $ARGUMENTS

Only fix IDs that triage classified as **fix** and I confirmed. If an ID wasn't confirmed, stop and
say so.

1. Check out the PR's branch locally if it isn't already (`gh pr view <PR> --json headRefName`), and
   make sure it's up to date with the remote. Don't switch branches with uncommitted changes.
2. For each ID, read its thread (GraphQL `reviewThreads`, or `gh api .../pulls/<PR>/comments`) and
   the flagged code, then make the smallest change that fixes it. Add or adjust a test when the
   finding is about behavior.
3. Run the local checks from `CLAUDE.md` (`ruff check .`, `pytest -q`, `sqlfluff lint pipeline/ eval/
   --dialect snowflake`, and `python scripts/check_decisions.py` if the decision log changed). All
   must pass.
4. Follow the CLAUDE.md Workflow: ask the `reviewer` agent to review the change against the findings.
5. Stop and report, per ID: the diff, the test results, and a ready commit message in the format
   `fix(review): CR-n <what changed>` (one finding per commit where practical; several IDs as
   `fix(review): CR-3, CR-5 <summary>`). I commit and push myself.

Don't reply to or resolve any thread; the re-review or I will.
