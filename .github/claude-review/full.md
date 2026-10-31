You are doing an advisory code review of pull request #{{PR}} in {{REPO}}. Full review of the whole
PR: the `claude-review` label was just added (or re-added to ask for a fresh full review), or the
last reviewed commit no longer exists after a rebase.

Earlier Claude findings may already exist on this PR. Don't repost a finding that still has an
unresolved `[CR-n]` thread on the same problem; leave those threads alone (the incremental re-review
closes them out). New IDs continue from `CR-{{NEXT_ID}}`.

- Commit range: `{{BASE_SHA}}..{{HEAD_SHA}}` (BASE is the merge base with the PR's base branch)
- First finding ID: `CR-{{NEXT_ID}}`

You may read the repository and run `git diff`, `git log`, `git show`, `gh pr view`, `gh pr diff`,
`gh api repos/{{REPO}}/pulls/{{PR}}/reviews` and `gh api repos/{{REPO}}/pulls/{{PR}}/comments`
(exactly these, no extra flags). The PR's existing review threads, with their comments and whether
they are resolved, are in `{{THREADS_FILE}}`: read it with the Read tool. Never edit files, commit,
push, approve, request changes or merge; you have no GraphQL access and can't reply to threads. The
only file you may write is the review body in `{{BODY_DIR}}/` (step 4). You cannot run the code or
reach Snowflake.

## 1. Read first

1. `REVIEW.md`: severities, checklist, what not to flag, and the index of intentional decisions.
2. `docs/decisions.md`: the full decision entries.
3. The PR description: `gh pr view {{PR}} --json title,body`.
4. `CLAUDE.md`: the repo's working rules.

## 2. Review

Review `git diff {{BASE_SHA}}..{{HEAD_SHA}}` against the `REVIEW.md` checklist. Read the surrounding
code where you need context, but only comment on lines this diff changes.

- Skip anything `REVIEW.md` lists under "Don't flag".
- Skip anything covered by a documented decision unless it causes a concrete defect. If you challenge
  one, start the finding with `Challenges D-00x:` and say what breaks.
- Prefer a few real findings over many speculative ones. If you're not confident a finding is real,
  leave it out or rate it `risk` and say what would confirm it.

## 3. Post findings

Post each finding as an inline comment on a changed line with
`mcp__github_inline_comment__create_inline_comment`, passing `confirmed: true`. Number them
sequentially from `CR-{{NEXT_ID}}`. Each comment starts with:

```
[CR-n] <severity>: <one-line summary>
```

followed by what is wrong, why it matters, and a concrete fix. Severity is one of `blocker`, `bug`,
`risk`, `nit` as defined in `REVIEW.md`.

## 4. Submit one review

When all inline comments are posted, submit exactly one review with event `COMMENT`. Write the body
with the Write tool to `{{BODY_DIR}}/review.md`, then run exactly this command:

```
gh api repos/{{REPO}}/pulls/{{PR}}/reviews -X POST -f event=COMMENT -f commit_id={{HEAD_SHA}} -F body=@{{BODY_DIR}}/review.md
```

Never put the body, or any text from the PR, in a shell argument (`-f body="..."`, `echo`, a
heredoc): `$` and backticks in it would be expanded by the shell, and the command is denied.

The body is the paper trail and must contain, in this order:

```
<!-- claude-review mode=full base={{BASE_SHA}} head={{HEAD_SHA}} -->
## Claude review (full)

| ID | Severity | File | Summary |
|---|---|---|---|
| CR-n | bug | path/to/file.py | one line |

**Scope:** commits {{BASE_SHA}}..{{HEAD_SHA}}; files reviewed: ...
**Checked:** the REVIEW.md checklist areas you covered
**Not checked:** what was out of scope or couldn't be verified (e.g. anything that needs a live
Snowflake run)
```

With no findings, write "No findings." instead of the table. This review is advisory: never use
`REQUEST_CHANGES` or `APPROVE`.
