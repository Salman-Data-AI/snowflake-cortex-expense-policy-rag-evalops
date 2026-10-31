"""Step 4: evaluate the app with TruLens through Snowflake AI Observability.

1. Load eval/questions.csv into EVAL_QUESTIONS (replacing what was there).
2. Register RagApp as a TruApp, versioned by commit + settings.
3. Create a run over EVAL_QUESTIONS, invoke the app on every question.
4. Compute metrics with a Cortex LLM judge and wait for them.
5. Copy per-question scores into EVAL_RESULTS with the run's settings attached.

Run from the repo root:  PYTHONPATH=. python eval/run_eval.py
Docs (VERIFY each call on first run):
  https://docs.snowflake.com/en/user-guide/snowflake-cortex/ai-observability/evaluate-ai-applications
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime

import pandas as pd

from app.ask import RagApp
from app.settings import REPO_ROOT, app_version, get_session, git_commit, load_config

METRICS = ["context_relevance", "groundedness", "answer_relevance", "correctness"]
QUESTIONS_TABLE = "RAG_STARTER.EVAL.EVAL_QUESTIONS"
POLL_SECONDS = 15
TIMEOUT_SECONDS = 30 * 60

os.environ.setdefault("TRULENS_OTEL_TRACING", "1")  # VERIFY: on by default in trulens 2.x


def load_questions(session) -> pd.DataFrame:
    df = pd.read_csv(REPO_ROOT / "eval" / "questions.csv", dtype=str).fillna("")
    df.columns = [c.upper() for c in df.columns]
    session.sql(f"DELETE FROM {QUESTIONS_TABLE}").collect()
    # VERIFY: write_pandas maps the CSV columns (incl. EXPECTED_PAGES, KEY_FACTS) to EVAL_QUESTIONS
    # by name, and empty strings (NONE rows) load as '' rather than failing.
    session.write_pandas(
        df, table_name="EVAL_QUESTIONS", database="RAG_STARTER", schema="EVAL",
        auto_create_table=False, overwrite=False,
    )
    print(f"Loaded {len(df)} questions into {QUESTIONS_TABLE}")
    return df


def wait_for(run, done: set[str], label: str) -> str:
    start = time.time()
    while True:
        status = str(run.get_status())
        print(f"  {label}: {status}")
        if any(status.endswith(s) for s in done):
            return status
        if "FAILED" in status or time.time() - start > TIMEOUT_SECONDS:
            raise SystemExit(f"{label} did not finish: {status}")
        time.sleep(POLL_SECONDS)


def main() -> None:
    from trulens.apps.app import TruApp
    from trulens.connectors.snowflake import SnowflakeConnector
    from trulens.core.run import RunConfig

    cfg = load_config()
    session = get_session()
    session.use_schema("RAG_STARTER.EVAL")  # TruApp registers its External Agent here
    questions = load_questions(session)

    version = app_version(cfg)
    run_id = os.environ.get("RUN_ID", datetime.now(UTC).strftime("local-%Y%m%d-%H%M%S"))
    run_name = f"run-{run_id}"

    rag = RagApp(session=session, cfg=cfg)
    connector = SnowflakeConnector(snowpark_session=session)
    tru_app = TruApp(
        rag,
        app_name=cfg["app_name"],
        app_version=version,
        connector=connector,
        main_method=rag.answer,
    )

    run = tru_app.add_run(
        run_config=RunConfig(
            run_name=run_name,
            description=f"commit {git_commit()[:7]}",
            label=cfg.get("settings_label") or "baseline",
            source_type="TABLE",
            dataset_name=QUESTIONS_TABLE,
            dataset_spec={  # VERIFY: uppercase column names resolve
                "RECORD_ROOT.INPUT": "QUESTION",
                "RECORD_ROOT.GROUND_TRUTH_OUTPUT": "EXPECTED_ANSWER",
            },
            llm_judge_name=cfg["judge_model"],
        )
    )
    print(f"App {cfg['app_name']} version {version}, run {run_name}")

    run.start()  # blocking: invokes the app once per question
    wait_for(run, {"INVOCATION_COMPLETED", "INVOCATION_PARTIALLY_COMPLETED"}, "invocation")

    run.compute_metrics(metrics=METRICS)  # asynchronous
    wait_for(run, {"COMPLETED", "PARTIALLY_COMPLETED"}, "metrics")

    copy_scores(session, run, questions, cfg, version, run_id)


def copy_scores(session, run, questions: pd.DataFrame, cfg: dict, version: str, run_id: str) -> None:
    """One EVAL_RESULTS row per question per metric."""
    records = run.get_records()  # columns: record_id, input, output, latency, <metric columns>
    base = {"record_id", "input", "output", "latency"}
    metric_cols = [c for c in records.columns if c not in base]  # VERIFY: metric column names
    by_question = dict(zip(questions["QUESTION"], questions["QUESTION_ID"], strict=True))

    rows = []
    for _, rec in records.iterrows():
        for metric in metric_cols:
            rows.append(
                {
                    "RUN_ID": run_id,
                    "APP_VERSION": version,
                    "QUESTION_ID": by_question.get(rec["input"], "UNMATCHED"),
                    "METRIC": metric,
                    "SCORE": pd.to_numeric(rec[metric], errors="coerce"),
                    "LATENCY_S": pd.to_numeric(rec["latency"], errors="coerce"),
                    "ANSWER": str(rec["output"]),
                    "GIT_COMMIT": git_commit(),
                    "CHUNK_SIZE": cfg["chunk_size"],
                    "OVERLAP": cfg["overlap"],
                    "TOP_K": cfg["top_k"],
                    "MODEL": cfg["model"],
                    "PROMPT_VERSION": cfg["prompt_version"],
                    "JUDGE_MODEL": cfg["judge_model"],
                }
            )
    df = pd.DataFrame(rows)
    session.write_pandas(
        df, table_name="EVAL_RESULTS", database="RAG_STARTER", schema="EVAL",
        auto_create_table=False, overwrite=False,
    )
    session.sql(
        "UPDATE RAG_STARTER.EVAL.EVAL_RESULTS SET recorded_at = CURRENT_TIMESTAMP() "
        "WHERE recorded_at IS NULL"
    ).collect()

    summary = df.groupby("METRIC")["SCORE"].mean().round(3)
    print(f"\nCopied {len(df)} scores to EVAL_RESULTS for run {run_id}")
    print(summary.to_string())


if __name__ == "__main__":
    main()
