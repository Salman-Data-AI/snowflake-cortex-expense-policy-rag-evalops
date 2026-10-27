---
description: Draft a reply to one Claude review thread, show it, and post it only after I approve
argument-hint: <PR number> <CR-id> [my reason]
---

Draft a reply to one review thread. Arguments: PR number, CR ID, then my reason if I gave one:
$ARGUMENTS

1. Read the thread for that CR ID (GraphQL `reviewThreads`; the thread whose first comment starts
   with `[CR-n]`) and note the `databaseId` of its first comment.
2. Write the reply from my reason. If I gave none, use the recorded decision in `docs/decisions.md`.
   Start it with exactly one of:
   - `Design decision (D-00x):` the choice is recorded; say why it holds here.
   - `Agreed, will fix:` valid; say what will change and where.
   - `Won't fix:` say why.
   If the rationale isn't in `docs/decisions.md`, also propose the entry (and its `REVIEW.md` index
   line), and don't cite a `D-` ID that doesn't exist yet.
3. Show me the reply text and the exact command, then stop and wait for my approval:
   `gh api repos/{owner}/{repo}/pulls/<PR>/comments/<comment databaseId>/replies -f body="..."`
4. Post it only after I approve in the current turn (Claude Code also asks before any `gh api` that
   writes). Don't resolve the thread; the re-review or I will.
