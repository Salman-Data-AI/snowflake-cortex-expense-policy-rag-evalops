# snowflake-cortex-expense-policy-rag-evalops

A small Snowflake RAG app over UC travel and expense policy PDFs: parsed with AI_PARSE_DOCUMENT,
searched with Cortex Search, answered with AI_COMPLETE, evaluated with TruLens through Snowflake
AI Observability, deployed with DCM, and run from one manual GitHub workflow.

Status: **Phase 1 (offline templates).** Nothing here has run against Snowflake yet. Every line
written from the docs but not yet run carries a `VERIFY` comment; `grep -rn VERIFY .` is the
Phase 2 checklist.

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
dcm/                      Snowflake objects (DCM project)
  manifest.yml            one target: DEV
  bootstrap.sql           one-time setup by hand: role, admin db, service user, resource monitor
  sources/definitions/    infra.sql (db, schemas, warehouse, stage), tables.sql (5 tables)
pipeline/                 01_parse.sql, 02_chunk.py, chunker.py, 03_search.sql,
                          reparse_all.sql, record_run.py, end_session.sql
config/rag.yaml           chunk_size, overlap, top_k, model, prompt_version, judge_model
app/                      ask.py (RagApp), prompt_v1.txt, settings.py
eval/                     questions.csv, run_eval.py, compare.sql, harbor/ (Phase 4)
tests/                    offline unit tests (chunker, config, questions, file layout)
.github/workflows/        checks.yml (every push, no Snowflake), run-pipeline.yml (manual)
```

Two deliberate differences from the original plan:
- DCM definitions live in `dcm/sources/definitions/`, not `dcm/definitions/`: DCM requires the `sources/` folder.
- `dcm/bootstrap.sql` exists because DCM needs a role and a database/schema for its project object
  before its first plan. Cortex Search is in `03_search.sql` because DCM does not manage it.

## Phase 1 checklist (what's left for you)

- [ ] Download the PDFs listed in `documents/manifest.csv` into `documents/` with those file names,
      check the URLs point at current versions, and fill in `download_date`.
- [ ] Read them and replace every `TODO` in `eval/questions.csv` with the real expected answer.
      Edit or replace the draft questions freely; keep 2–3 `NONE` rows (answer: "Not in the documents.").
- [ ] Push to a new GitHub repo and confirm `checks.yml` passes.
- [ ] Add the three secret names (values come in Phase 2): `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY`.
- [ ] Optional: install Snowflake CLI locally (`pipx install snowflake-cli`, 3.24+ for DCM).

## Running checks locally

```bash
pip install -r requirements-dev.txt
ruff check . && pytest -q && sqlfluff lint pipeline/ eval/
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
