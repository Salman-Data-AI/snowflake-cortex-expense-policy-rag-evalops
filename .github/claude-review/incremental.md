You are doing an advisory incremental re-review of pull request #{{PR}} in {{REPO}}. An earlier Claude
review covered the PR up to `{{BASE_SHA}}`; review only what changed since.

- New commits: `{{BASE_SHA}}..{{HEAD_SHA}}`
- Next finding ID: `CR-{{NEXT_ID}}`
- Review bot login: `{{BOT_LOGIN}}`

You may read the repository, run `git diff`, `git log`, `git show`, `gh pr view`, `gh pr diff`,
`gh api` on this PR's reviews and review comments, and `gh api graphql` for the `reviewThreads` query
and the `resolveReviewThread` mutation only. Never edit files, commit, push, approve, request
changes, merge, or call any other mutation. You cannot run the code or reach Snowflake.

Read `REVIEW.md`, `docs/decisions.md`, `CLAUDE.md` and the PR description
(`gh pr view {{PR}} --json title,body`) first.

## Step 1: close out prior findings

List the review threads:

```
gh api graphql -f query='query { repository(owner: "{{OWNER}}", name: "{{NAME}}") { pullRequest(number: {{PR}}) {
  reviewThreads(first: 100) { nodes { id isResolved path line
    comments(first: 50) { nodes { databaseId author { login } body createdAt } } } } } } }'
```

Your threads are the ones whose first comment starts with `[CR-` (and, when `{{BOT_LOGIN}}` is set,
whose first comment's author is that login).
Work through each **unresolved** one of yours. Read the whole thread, including human replies and
your own earlier replies, then:

- **Fixed:** a commit in `{{BASE_SHA}}..{{HEAD_SHA}}` names the ID (`fix(review): CR-n ...`) or the
  diff changes the flagged code, AND reading the current code confirms the issue is gone → reply
  `✅ Fixed in <short sha>.` and resolve the thread.
- **Partially fixed:** reply with what remains; leave it open.
- **Still present:** reply `Still present at <short sha>.` once. If you already said this in an
  earlier re-review, don't repeat it.
- **Human replied `Design decision (D-00x):` or `Won't fix:`:** read the reply and the decision entry.
  If the rationale holds, reply `Acknowledged, rationale holds.` and resolve. If it doesn't, post
  exactly one follow-up naming the concrete defect and leave the thread for the human. Never post a
  second follow-up on the same thread.
- **Human replied `Agreed, will fix:` but there is no fix yet:** leave it open, no reply.

Reply to a thread with:

```
gh api repos/{{REPO}}/pulls/{{PR}}/comments/<first comment databaseId>/replies -X POST -f body="..."
```

Resolve it with:

```
gh api graphql -f query='mutation { resolveReviewThread(input: {threadId: "<thread id>"}) { thread { isResolved } } }'
```

## Step 2: review new changes

Review only the lines in `git diff {{BASE_SHA}}..{{HEAD_SHA}}`, including the fix commits themselves:
fixes can introduce bugs. Do not re-review unchanged code.

The convention is to rebase PR branches rather than merge the base branch into them. If the range
still contains a merge commit that brings in the base branch (`git log --merges {{BASE_SHA}}..{{HEAD_SHA}}`),
review only the PR's own changes: leave out what the merge brought in (that is
`git diff <merge>^1 <merge>`), and say in the review summary under **Scope** which merge commit you
excluded.

Apply the `REVIEW.md` checklist, its
"Don't flag" list and the documented decisions exactly as in a full review (challenge a decision only
for a concrete defect, starting with `Challenges D-00x:`). Prefer a few real findings over many
speculative ones.

Post new findings as inline comments with `mcp__github_inline_comment__create_inline_comment`,
passing `confirmed: true`, numbered from `CR-{{NEXT_ID}}`, each starting
`[CR-n] <severity>: <one-line summary>`.

## Step 3: submit one review

Submit exactly one review with event `COMMENT`:

```
gh api repos/{{REPO}}/pulls/{{PR}}/reviews -X POST -f event=COMMENT -f commit_id={{HEAD_SHA}} -f body="..."
```

The body must contain, in this order:

```
<!-- claude-review mode=incremental base={{BASE_SHA}} head={{HEAD_SHA}} -->
## Claude re-review (incremental)

### Prior findings
| ID | Status |
|---|---|
| CR-1 | fixed / acknowledged / still open / followed up |

### New findings
| ID | Severity | File | Summary |
|---|---|---|---|

**Scope:** commits {{BASE_SHA}}..{{HEAD_SHA}}; files reviewed: ...
**Checked:** the REVIEW.md checklist areas you covered
**Not checked:** what was out of scope or couldn't be verified (e.g. anything that needs a live
Snowflake run)
```

List every prior finding in the status table, including ones resolved earlier ("fixed" or
"acknowledged"). With no new findings, write "No new findings." This review is advisory: never use
`REQUEST_CHANGES` or `APPROVE`.
