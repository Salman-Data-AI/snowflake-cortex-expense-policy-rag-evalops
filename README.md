# snowflake-cortex-expense-policy-rag-evalops

A small Snowflake RAG app over UC travel and expense policy PDFs: parsed with AI_PARSE_DOCUMENT,
searched with Cortex Search, answered with AI_COMPLETE, evaluated with TruLens through Snowflake
AI Observability, deployed with DCM, and run from one manual GitHub workflow.

Status: **Phase 1 (offline templates).** Nothing here has run against Snowflake yet. Every line
written from the docs but not yet run carries a `VERIFY` comment; the Phase 2 checklist below
has the command that lists them.

## How it works

```
documents/*.pdf
   │  upload (snow stage copy)
   ▼
RAW.DOCS_STAGE ──01_parse.sql──▶ RAW.PARSED_DOCUMENTS ──02_chunk.py──▶ RAG.DOCUMENT_CHUNKS
                                                                            │ 03_search.sql
                                                                            ▼
eval/questions.csv ──▶ EVAL.EVAL_QUESTIONS ──run_eval.py──▶ RAG.POLICY_SEARCH + AI_COMPLETE (app/ask.py)
                                               │
                                               ▼
                       AI Observability event table ──copy──▶ EVAL.EVAL_RESULTS ──compare.sql
```

| Step | Reads | Writes | Start from it when you change |
|---|---|---|---|
| Parse (`pipeline/01_parse.sql`) | stage directory table | `PARSED_DOCUMENTS` | documents, or a bad parse |
| Chunk (`pipeline/02_chunk.py`) | `PARSED_DOCUMENTS` | `DOCUMENT_CHUNKS` | `chunk_size`, `overlap` |
| Search (`pipeline/03_search.sql`) | `DOCUMENT_CHUNKS` | Cortex Search index | (always runs after chunk) |
| Evaluate (`eval/run_eval.py`) | `EVAL_QUESTIONS`, search service | `EVAL_RESULTS` | `top_k`, `model`, prompt |

Parse skips any file whose name and checksum are already in `PARSED_DOCUMENTS`, so starting from
Parse twice parses nothing the second time. Tick `reparse_all` to force it.

## Repository

```
.claude/                  Claude Code settings, check hooks, reviewer agent, review-triage/fix/reply commands
.githooks/                optional commit-msg hook (`git config core.hooksPath .githooks`)
CLAUDE.md, REVIEW.md      working rules for Claude Code; Claude PR review instructions and decision index
docs/decisions.md         design decisions (D-001 ...)
scripts/                  check_decisions.py (REVIEW.md index vs decisions.md), check_commit_msg.py
dcm/                      Snowflake objects (DCM project)
  manifest.yml            one target: DEV
  bootstrap.sql           one-time setup by hand: role, admin db, service user, resource monitor
  sources/definitions/    infra.sql (db, schemas, warehouse, stage), tables.sql (5 tables)
pipeline/                 01_parse.sql, 02_chunk.py, chunker.py, parsed_doc.py (page_texts), 03_search.sql,
                          reparse_all.sql, record_run.py, end_session.sql
config/rag.yaml           chunk_size, overlap, top_k, model, prompt_version, judge_model
app/                      ask.py (RagApp: Snowflake clients + TruLens spans), rag_core.py (RagCore: the
                          RAG logic, no TruLens/Snowflake), citations.py, prompt_v1.txt, settings.py
eval/                     questions.csv, run_eval.py, compare.sql, harbor/ (Phase 4)
tests/                    offline unit tests (chunker, page_texts, ask() with fakes, config, questions, file layout,
                          decision index, commit messages)
.github/workflows/        checks.yml (every push, no Snowflake), run-pipeline.yml (manual),
                          claude-review.yml (PRs labeled `claude-review`)
```

Two deliberate differences from the original plan:
- DCM definitions live in `dcm/sources/definitions/`, not `dcm/definitions/`: DCM requires the `sources/` folder.
- `dcm/bootstrap.sql` exists because DCM needs a role and a database/schema for its project object
  before its first plan. Cortex Search is in `03_search.sql` because DCM does not manage it.

## Phase 1 checklist (what's left for you)

- [x] Download the PDFs listed in `documents/manifest.csv` into `documents/` with those file names,
      check the URLs point at current versions, and fill in `download_date`.
- [x] Read them and replace every `TODO` in `eval/questions.csv` with the real expected answer.
      Edit or replace the draft questions freely; keep 2–3 `NONE` rows (answer: "Not in the documents.").
- [x] Push to a new GitHub repo and confirm `checks.yml` passes.
- [ ] Add the three secret names (values come in Phase 2): `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY`.
      (`SNOWFLAKE_USER` and `SNOWFLAKE_PRIVATE_KEY` are added; `SNOWFLAKE_ACCOUNT` is still missing.)
- [ ] Optional: install Snowflake CLI locally (`pipx install snowflake-cli`, 3.24+ for DCM).

## Done beyond the original plan

- CLAUDE.md: working rules for Claude Code (offline only, checks, VERIFY convention) (#2).
- Python 3.12 everywhere: `.python-version`, `pyproject.toml` and both workflows (#1, #2).
- Check hooks (ruff on edit; ruff, pytest, sqlfluff on stop) and the `reviewer` agent (#3).
- Table-aware chunking: markdown tables are kept whole in one chunk (#4).
- Verifiable gold set: `expected_pages` and `key_facts` in `eval/questions.csv`, checked against the PDFs by a test (#7).
- TruLens-free core: `rag_core.py`, `citations.py` and `parsed_doc.py` with offline tests (#10).
- PR review workflow: opt-in Claude review, decision log, triage/fix/reply commands (#5, #6, #8, #9).

## Running checks locally

```bash
pip install -r requirements-dev.txt
ruff check . && pytest -q && sqlfluff lint pipeline/ eval/ --dialect snowflake && python scripts/check_decisions.py
```

## Phase 2: first run (summary)

1. Open the trial in a region with AI_PARSE_DOCUMENT, Cortex Search, AI_COMPLETE and AI Observability.
2. Run `dcm/bootstrap.sql` as ACCOUNTADMIN; set the public key on `GITHUB_RAG_SVC`; fill the GitHub secrets.
3. Put your account identifier in `dcm/manifest.yml`, then from the repo root:
   `snow dcm create --target DEV --from dcm`, `snow dcm plan --target DEV --from dcm`, `snow dcm deploy --target DEV --from dcm`.
4. Run each step by hand once (`snow sql -f pipeline/01_parse.sql`, `PYTHONPATH=. python pipeline/02_chunk.py`, ...),
   then `PYTHONPATH=. python -m app.ask "a question"`, then `PYTHONPATH=. python eval/run_eval.py`.
5. Press the button: Actions → run-pipeline → start_from = parse. Then again with parse (nothing reparsed), then evaluate.
6. End every session with `snow sql -f pipeline/end_session.sql`.

Python dependencies: `pip install -r requirements.txt` for the app; the Snowflake CLI is installed
separately (`pipx install snowflake-cli`) because its dependencies conflict with `trulens-connectors-snowflake`.
`sqlalchemy` is pinned below 2.1 because `snowflake-sqlalchemy` (pulled in by TruLens) fails to import on 2.1.

## Phase 2 checklist

- [ ] Re-run from Chunk plus an eval; compare Q07 before and after the table fix.
- [ ] Confirm AI_PARSE_DOCUMENT `page_split` output shape (D-013 and the `page_texts` VERIFY):
      page indexes contiguous, no text outside pages.
- [ ] Every document in `PARSED_DOCUMENTS` has more than zero pages.
- [ ] Check how tables spanning two pages come out of the parser.
- [ ] Confirm `RagApp.search` passes `top_k` (a run returns `top_k` hits).
- [ ] Confirm retrieve and generate spans appear in Snowsight's evaluation view (the `super()` delegation VERIFY).
- [ ] Work through the remaining VERIFY lines. Snowflake-side VERIFY lines (31 as of be04c47):

  ```bash
  grep -rn VERIFY pipeline app eval dcm config .github/workflows/run-pipeline.yml
  ```

  `grep -rn VERIFY .` also lists prose mentions and the Claude Code tooling (`.claude/`,
  `claude-review.yml`); exclude `.venv` if you have one.

## Later

- Policy limits table (audit task 8): deferred until after Phase 3.
- Empty-retrieval behaviour: to be decided in the Phase 3 prompt v1 vs v2 experiment.
