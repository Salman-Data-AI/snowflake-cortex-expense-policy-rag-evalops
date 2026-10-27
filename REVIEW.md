# Review guide

## Purpose

What the Claude PR review (`.github/workflows/claude-review.yml`) checks, how it rates findings, and
what it leaves alone. The review is **advisory**: it posts `COMMENT` reviews only, never blocks a
merge, and never changes code. It runs only on PRs labeled `claude-review`: adding the label starts
a full review, and later pushes get an incremental re-review of the new commits. To ask for a fresh
full review, remove the label and add it again. Human reviewers can use the same checklist.

## Severity

| Severity | Use for |
|---|---|
| `blocker` | Wrong results, data loss, secret exposure, or runaway Snowflake cost |
| `bug` | Incorrect behavior that doesn't reach blocker level |
| `risk` | Likely to break later, fragile assumptions, missing safeguards or tests |
| `nit` | Small, cheap, clear improvements only. Skip anything debatable |

Every inline finding starts with `[CR-n] <severity>:`. IDs run across the whole PR.

## Checklist

- **Correctness and edge cases:** empty input, missing files, bad config values, ordering, encodings.
- **SQL idempotency and re-run safety:** each pipeline step must be safe to start from (`start_from`)
  and to run twice; no duplicate rows, no lost rows.
- **Parse-skip logic:** a file is skipped only when name *and* checksum match `PARSED_DOCUMENTS`; a
  changed file is reparsed; `reparse_all` still forces everything.
- **Chunker behavior at boundaries:** chunk size and overlap limits, headings, page breaks, tables,
  empty pages; no text lost or duplicated beyond the overlap.
- **Prompt/eval leakage:** expected answers (`eval/questions.csv`, `EVAL_QUESTIONS.EXPECTED_ANSWER`)
  must never reach the app prompt or retrieval.
- **Credentials and secrets:** none in code, config, logs, workflow output or artifacts.
- **Snowflake cost risks:** warehouse size, `AUTO_SUSPEND`, services left running (Cortex Search
  serving), loops that call AI functions per row, anything that reparses unnecessarily.
- **Workflow permissions and triggers:** least privilege, which events run what, which secrets each
  job sees, manual-only for anything touching Snowflake.
- **Tests for new logic:** new offline logic has unit tests that would fail if it regressed.
- **Undocumented decisions:** a non-obvious design choice in the diff with no `D-` entry → flag as
  `risk` and suggest the entry.

## Don't flag

- Style that the linters in `checks.yml` already enforce (ruff, sqlfluff).
- `VERIFY` comments; they are expected until Phase 2 (D-006).
- Anything listed under Intentional decisions, unless it causes a concrete defect. Then start the
  finding with `Challenges D-00x:` and say why.

## Intentional decisions

- D-001: Offline checks on every push; Snowflake runs are manual only → docs/decisions.md#d-001
- D-002: Every pipeline step persists to a table, so a run can start from any step → docs/decisions.md#d-002
- D-003: Parsing is skipped when name and checksum are already parsed → docs/decisions.md#d-003
- D-004: TruLens scores are copied into our own EVAL_RESULTS table → docs/decisions.md#d-004
- D-005: Single DEV target; Sandbox deferred → docs/decisions.md#d-005
- D-006: VERIFY comments mark lines not yet run against Snowflake → docs/decisions.md#d-006
- D-007: Key-pair auth for GitHub Actions now; OIDC later → docs/decisions.md#d-007
- D-008: Claude PR review is opt-in by label, non-blocking, fixes made locally → docs/decisions.md#d-008
- D-009: Cortex Search is created in pipeline SQL, not DCM → docs/decisions.md#d-009
- D-010: Snowflake CLI is installed separately from requirements.txt → docs/decisions.md#d-010
- D-011: sqlalchemy is pinned below 2.1 → docs/decisions.md#d-011
- D-012: A prompt change creates a new prompt_vN.txt → docs/decisions.md#d-012
- D-013: Markdown tables are kept whole when chunking (once feat/chunker-keep-tables merges) → docs/decisions.md#d-013
- D-014: DCM definitions live in dcm/sources/definitions/ → docs/decisions.md#d-014
- D-015: dcm/bootstrap.sql is run by hand before the first DCM plan → docs/decisions.md#d-015
- D-016: gh write ask rules are local-only, so CI can post reviews → docs/decisions.md#d-016
