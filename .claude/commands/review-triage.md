---
description: Triage the Claude review findings on a PR before fixing or replying to any of them
argument-hint: <PR number>
---

Triage the Claude review on PR #$ARGUMENTS. This is the entry point for every review: don't fix,
reply, commit or resolve anything in this command.

1. Read the latest Claude review body (`gh api repos/{owner}/{repo}/pulls/$ARGUMENTS/reviews`; the
   one whose body has `<!-- claude-review`) and every unresolved thread whose first comment starts
   with `[CR-` (GraphQL `reviewThreads`), including all human replies. GraphQL reads need `-f`, which
   Claude Code asks me to approve (with `.claude/settings.local.json` from Setup, D-016).
2. For each finding, read the flagged code at the PR head, `docs/decisions.md`, `REVIEW.md`, the PR
   description (`gh pr view $ARGUMENTS`), and the commits that touched those lines.
3. Classify each finding, with one line of reasoning:
   - **fix**: the finding is valid and belongs in this PR.
   - **design decision**: a recorded or explainable choice. Name the `D-` ID, or say no entry
     exists yet.
   - **agree but defer**: valid, but out of scope for this PR.
   - **disagree**: the finding is wrong for another reason.
4. Show one table: ID, severity, classification, reasoning, proposed action. Mark every row where
   you're unsure and need my reason.
5. Stop and wait. I confirm or change the classifications.
6. After I confirm, hand off: fixes to `/review-fix $ARGUMENTS <CR-ids>`, everything else to
   `/review-reply $ARGUMENTS <CR-id> [reason]`. For a design decision with no `D-` entry, propose the
   entry (for `docs/decisions.md` and the `REVIEW.md` index) first.
