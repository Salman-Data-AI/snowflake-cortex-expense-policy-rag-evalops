"""Record one row in PIPELINE_RUNS for a press of the pipeline button.

Called by run-pipeline.yml as its last step (it runs even if an earlier step failed).
  PYTHONPATH=. python pipeline/record_run.py --start-from chunk --status success
"""

from __future__ import annotations

import argparse
import os

from app.settings import get_session, git_commit, load_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-from", required=True, choices=["parse", "chunk", "evaluate"])
    parser.add_argument("--reparse-all", default="false")
    parser.add_argument("--status", required=True)
    parser.add_argument("--started-at", default=None, help="ISO timestamp the run began")
    args = parser.parse_args()

    cfg = load_config()
    session = get_session()
    session.sql(
        """
        INSERT INTO RAG_STARTER.EVAL.PIPELINE_RUNS
            (run_id, started_at, finished_at, start_from, reparse_all, status, git_commit,
             chunk_size, overlap, top_k, model, prompt_version)
        SELECT ?, COALESCE(TRY_TO_TIMESTAMP_LTZ(?), CURRENT_TIMESTAMP()), CURRENT_TIMESTAMP(),
               ?, ?, ?, ?, ?, ?, ?, ?, ?
        """,
        params=[  # VERIFY: Snowpark qmark binding with session.sql(params=...)
            os.environ.get("RUN_ID", "local"),
            args.started_at,
            args.start_from,
            args.reparse_all.lower() == "true",
            args.status,
            git_commit(),
            cfg["chunk_size"],
            cfg["overlap"],
            cfg["top_k"],
            cfg["model"],
            cfg["prompt_version"],
        ],
    ).collect()
    print(f"Recorded run {os.environ.get('RUN_ID', 'local')}: {args.status}")


if __name__ == "__main__":
    main()
