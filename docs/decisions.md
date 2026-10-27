# Design decisions

One entry per non-obvious choice. `REVIEW.md` indexes them one line each; the Claude PR reviewer
reads both and does not flag a documented decision unless it causes a concrete defect, in which case
it names the `D-` ID it challenges.

Format (all fields required; `scripts/check_decisions.py` checks this and the index in CI):

```
## D-00x: <title>
Status: accepted | accepted (deferred) | superseded by D-00y
Date: YYYY-MM-DD        (when the decision first appeared in the repo)
Context: why this came up ("Rationale: TODO" when the reason isn't recorded anywhere)
Decision: what we chose
Alternatives considered: what else, and why not
Consequences: trade-offs we accept
Reviewer note: what a reviewer should not flag because of this
```

Deferred decisions also carry a `Revisit when:` line. A new or changed decision goes in the same PR
as the code, with its index line in `REVIEW.md`.

## D-001: Two workflows: offline checks on every push, Snowflake run manual only
Status: accepted
Date: 2026-10-26
Context: `checks.yml` "never connects to Snowflake, so it costs nothing" (its header comment), so it
can run on every push and pull request. Every Snowflake run spends credits (warehouse,
AI_PARSE_DOCUMENT, Cortex Search, LLM and evaluation calls) on a personal, cost-capped account with
a limited trial. Runs should happen only by choice, so each one is a deliberate experiment: change
one setting, run from the right step, compare. Running on every push would spend credits on commits
that change nothing in the pipeline.
Decision: `checks.yml` runs ruff, pytest, sqlfluff and YAML checks on every push and PR with no
Snowflake secrets. `run-pipeline.yml` is the only workflow that talks to Snowflake and runs only on
`workflow_dispatch`, one run at a time (`concurrency: run-pipeline`).
Alternatives considered: Running the pipeline on every push (spends credits on commits that change
nothing in the pipeline).
Consequences: Nothing touches Snowflake unless someone presses the button; Snowflake-dependent code
is only exercised by a manual run.
Reviewer note: Don't flag the lack of automatic Snowflake runs, or `checks.yml` not testing
Snowflake code paths.

## D-002: Every pipeline step persists to a table, so a run can start from any step
Status: accepted
Date: 2026-10-17
Context: Each step reads the table written by the step above it (`tables.sql`), and
`config/rag.yaml` maps each setting to the step a change in it needs (`chunk_size`/`overlap` →
chunk; `top_k`/`model`/`prompt_version` → evaluate). `PARSED_DOCUMENTS` holds "one row per parsed
file; later steps never call AI_PARSE_DOCUMENT" (`tables.sql`).
Decision: Parse → `PARSED_DOCUMENTS`, chunk → `DOCUMENT_CHUNKS`, search over that table, evaluate →
`EVAL_RESULTS`. `run-pipeline.yml` takes `start_from` = parse | chunk | evaluate.
Alternatives considered: Not recorded.
Consequences: Each step must be safe to start from on its own (re-run safe); tables can hold the
output of an earlier configuration until the step is rerun.
Reviewer note: Don't flag the intermediate tables as redundant, or ask for the pipeline to always
run end to end.

## D-003: Parsing is skipped for files whose name and checksum are already parsed
Status: accepted
Date: 2026-10-17
Context: Re-parsing "costs AI_PARSE_DOCUMENT credits for every page again" (`reparse_all.sql`), and
pressing "start from parse" twice should parse nothing the second time (`01_parse.sql`).
Decision: `01_parse.sql` parses only stage files whose `relative_path` and `md5` are not both in
`PARSED_DOCUMENTS`; a file with the same name and a new checksum has its old row deleted and is
parsed again. The `reparse_all` input clears the table to force a full reparse.
Alternatives considered: `reparse_all` exists as the opt-in override; other alternatives not
recorded.
Consequences: A change in parse settings (e.g. LAYOUT vs OCR) does not reparse unchanged files
unless `reparse_all` is ticked.
Reviewer note: Don't flag that unchanged files aren't reparsed after a code change; that is what
`reparse_all` is for.

## D-004: TruLens scores are copied into our own EVAL_RESULTS table
Status: accepted
Date: 2026-10-17
Context: "Every row in EVAL_RESULTS carries its settings and commit, so any score can be traced
back to exactly what produced it" (`eval/compare.sql`); runs are compared with plain SQL.
Decision: `eval/run_eval.py` copies per-question, per-metric scores from AI Observability into
`EVAL.EVAL_RESULTS` with the run's commit, `chunk_size`, `overlap`, `top_k`, `model`,
`prompt_version` and `judge_model`.
Alternatives considered: Not recorded.
Consequences: Scores are stored twice (AI Observability and EVAL_RESULTS); the copy depends on the
TruLens records format (marked VERIFY).
Reviewer note: Don't flag the duplicated storage, or suggest querying the AI Observability event
table directly instead.

## D-005: Single DEV target; Sandbox deferred
Status: accepted (deferred)
Date: 2026-10-17
Context: Personal learning project on a trial account. One target is enough to practise DCM plan
and deploy end to end; a second environment adds cost and setup time without teaching anything new
yet.
Decision: `dcm/manifest.yml` defines one target, `DEV`; no Sandbox or other environment.
Alternatives considered: A Sandbox target (deferred).
Consequences: All Snowflake runs, manual and from GitHub, share one environment. Adding Sandbox
later is a second target in `dcm/manifest.yml`.
Reviewer note: Don't flag the missing second environment or environment-specific templating.
Revisit when: a second environment is needed.

## D-006: VERIFY comments mark lines not yet run against Snowflake
Status: accepted
Date: 2026-10-17
Context: Phase 1 is offline: "Nothing here has run against Snowflake yet. Every line written from
the docs but not yet run carries a `VERIFY` comment; `grep -rn VERIFY .` is the Phase 2 checklist"
(README).
Decision: Every such line carries a `VERIFY` comment (`-- VERIFY` in SQL, `# VERIFY` in YAML and
Python) saying what to check; `grep -rn VERIFY .` is the Phase 2 checklist. A VERIFY is removed only
after the line has actually run.
Alternatives considered: Not recorded.
Consequences: Many VERIFY comments stay in the code until Phase 2.
Reviewer note: Don't flag VERIFY comments themselves. Do flag a new docs-derived Snowflake line that
lacks one.

## D-007: Key-pair auth for GitHub Actions now; OIDC later
Status: accepted (deferred)
Date: 2026-10-17
Context: Key-pair auth is the quickest working setup during the trial. OIDC / workload identity is
the preferred end state because it avoids a long-lived credential stored in GitHub.
Decision: GitHub Actions authenticates to Snowflake as service user `GITHUB_RAG_SVC` with key-pair
(JWT) auth; the private key is the `SNOWFLAKE_PRIVATE_KEY` secret, written to a file for the run and
removed afterwards (`run-pipeline.yml`).
Alternatives considered: OIDC / workload identity federation (deferred).
Consequences: Accepted risk: a private key held as a GitHub secret for a dedicated service user on a
personal, cost-capped account. It must be rotated by hand.
Reviewer note: Don't flag the use of a stored key pair instead of OIDC.
Revisit when: before anything beyond personal use.

## D-008: Claude PR review is opt-in by label, non-blocking, and fixes are made locally
Status: accepted
Date: 2026-10-27
Context: The in-session reviewer agent leaves no record; PR review comments give a permanent trail
of what was checked, what was found and how each finding was closed. Opt-in by label because not
every PR is worth the cost (docs, config). Non-blocking because the reviewer is advisory and can
lack context; the developer decides what to fix. Fixes are made locally rather than by the bot so
the reviewer never has write access, PR text can't steer an agent that commits, and every fix is
tested before it's pushed.
Decision: `.github/workflows/claude-review.yml` reviews a PR only when it has the `claude-review`
label (full review whenever the label is added, incremental on later pushes; drafts skipped).
Removing and re-adding the label is the way to ask for a fresh full review. Reviews are `COMMENT`
only, the job is `continue-on-error` and not a required check, it gets no Snowflake secrets and no
tools that edit, commit or push. Findings are fixed on the developer's machine.
Alternatives considered: Not recorded.
Consequences: Unlabeled PRs get no AI review; the bot never fixes anything itself.
Reviewer note: Don't flag the review as missing from unlabeled PRs, or suggest that the bot apply
fixes or block merges.

## D-009: Cortex Search is created in pipeline SQL, not DCM
Status: accepted
Date: 2026-10-17
Context: "Cortex Search is in 03_search.sql because DCM does not manage it" (README).
Decision: `pipeline/03_search.sql` creates the service if missing, resumes it and refreshes it on
every chunk or parse run.
Alternatives considered: Defining it in DCM (not supported).
Consequences: Changing the service's columns or attributes needs a manual `DROP CORTEX SEARCH
SERVICE` and a rerun from chunk (comment in `03_search.sql`).
Reviewer note: Don't flag the search service as missing from `dcm/`.

## D-010: Snowflake CLI is installed separately from requirements.txt
Status: accepted
Date: 2026-10-17
Context: The Snowflake CLI's "dependencies conflict with trulens-connectors-snowflake" (README,
`requirements.txt`, `run-pipeline.yml`).
Decision: Install it with `pipx install snowflake-cli` (3.24+ for DCM); `requirements.txt` holds
only the app, pipeline and evaluation packages.
Alternatives considered: One environment with both (dependency conflict).
Consequences: Two install steps; the CLI version is pinned only by `>=3.24.0` in the workflow.
Reviewer note: Don't flag `snowflake-cli` as missing from `requirements.txt`.

## D-011: sqlalchemy is pinned below 2.1
Status: accepted
Date: 2026-10-17
Context: `snowflake-sqlalchemy` (pulled in by TruLens) "fails to import on 2.1" (README,
`requirements.txt`).
Decision: `sqlalchemy>=2.0,<2.1` in `requirements.txt`.
Alternatives considered: Unpinned (breaks the import).
Consequences: sqlalchemy stays on 2.0 until `snowflake-sqlalchemy` supports 2.1.
Reviewer note: Don't flag the upper bound as unnecessary.

## D-012: A prompt change creates a new prompt_vN.txt
Status: accepted
Date: 2026-10-26
Context: "Evaluation results are keyed by `prompt_version`, so editing a file in place makes old
and new runs look identical" (CLAUDE.md).
Decision: Never edit an existing `app/prompt_vN.txt`; add `prompt_v(N+1).txt` and bump
`prompt_version` in `config/rag.yaml`. (`prompt_v1.txt` was edited in place once, in 4b4af35,
before it had ever run.)
Alternatives considered: Editing in place (makes runs indistinguishable).
Consequences: Old prompt files stay in the repo.
Reviewer note: Don't flag unused older prompt files. Do flag an edit to an existing prompt file.

## D-013: Markdown tables are kept whole when chunking
Status: accepted (applies once feat/chunker-keep-tables, 9c25512, is merged)
Date: 2026-10-27
Context: Splitting a table across chunks separates rows from their headers, so retrieved fragments
lose their meaning; Q07 (meal limits) depends on that table being retrieved whole.
Decision: `pipeline/chunker.py` keeps a pipe-style markdown table in one chunk when it fits, moves
it whole to the next chunk otherwise, and splits a table longer than `chunk_size` only between rows,
repeating the header and separator in every piece; a chunk that starts with a table gets no overlap.
(Implemented on `feat/chunker-keep-tables`, 9c25512; until that merges, `main` treats tables as
prose.)
Alternatives considered: Treating tables as prose (sentence/word splitting).
Consequences: Accepted trade-off: a table is not packed with neighbouring text to fill a chunk, so
the chunk before a table can be well under `chunk_size`, and a long table becomes several chunks
that each repeat the header. Pieces stay within `chunk_size`, except where a single word is longer
than the room left (as for prose). Table detection depends on AI_PARSE_DOCUMENT emitting pipe
tables (marked VERIFY).
Reviewer note: Once merged, don't flag short chunks before a table, repeated table headers, or
missing overlap on chunks that start with a table.

## D-014: DCM definitions live in dcm/sources/definitions/
Status: accepted
Date: 2026-10-17
Context: "DCM requires the `sources/` folder" (README, "deliberate differences from the original
plan").
Decision: DCM definition files are `dcm/sources/definitions/infra.sql` and `tables.sql`, not
`dcm/definitions/`.
Alternatives considered: `dcm/definitions/`, as in the original plan (DCM requires `sources/`).
Consequences: Paths differ from the original plan; `snow dcm` commands run with `--from dcm`.
Reviewer note: Don't flag the extra `sources/` level.

## D-015: dcm/bootstrap.sql is run by hand before the first DCM plan
Status: accepted
Date: 2026-10-17
Context: "`dcm/bootstrap.sql` exists because DCM needs a role and a database/schema for its project
object before its first plan" (README).
Decision: A one-time script, run by hand as ACCOUNTADMIN, creates the `RAG_DEPLOYER` role and its
grants, the `RAG_ADMIN` database and `RAG_ADMIN.DCM` schema that hold the DCM project object, the
`RAG_ADMIN_WH` warehouse, the resource monitor and the `GITHUB_RAG_SVC` service user. Everything
else is created by DCM.
Alternatives considered: Everything in DCM (not possible: the project object needs these first).
Consequences: Some objects live outside DCM and change only by editing and re-running the script by
hand.
Reviewer note: Don't flag account-level objects created outside DCM in `dcm/bootstrap.sql`.
