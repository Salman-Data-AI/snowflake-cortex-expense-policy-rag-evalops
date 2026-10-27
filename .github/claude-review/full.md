You are doing an advisory code review of pull request #{{PR}} in {{REPO}}. Full review of the whole
PR: the `claude-review` label was just added (or re-added to ask for a fresh full review), or the
last reviewed commit no longer exists after a rebase.

Earlier Claude findings may already exist on this PR. Don't repost a finding that still has an
unresolved `[CR-n]` thread on the same problem; leave those threads alone (the incremental re-review
closes them out). New IDs continue from `CR-{{NEXT_ID}}`.

- Commit range: `{{BASE_SHA}}..{{HEAD_SHA}}` (BASE is the merge base with the PR's base branch)
- First finding ID: `CR-{{NEXT_ID}}`

You may read the repository, run `git diff`, `git log`, `git show`, `gh pr view`, `gh pr diff`, and
`gh api` on this PR's reviews and review comments. Never edit files, commit, push, approve, request
changes, merge, or call any GraphQL mutation. You cannot run the code or reach Snowflake.

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

When all inline comments are posted, submit exactly one review with event `COMMENT`:

```
gh api repos/{{REPO}}/pulls/{{PR}}/reviews -X POST -f event=COMMENT -f commit_id={{HEAD_SHA}} -f body="..."
```

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
