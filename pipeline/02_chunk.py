"""Step 2: split parsed documents into chunks.

Reads:  RAG_STARTER.RAW.PARSED_DOCUMENTS
Writes: RAG_STARTER.RAG.DOCUMENT_CHUNKS (all rows replaced on every run)
Settings: chunk_size and overlap from config/rag.yaml

Run from the repo root:  PYTHONPATH=. python pipeline/02_chunk.py
"""

from __future__ import annotations

import json

import pandas as pd

from app.settings import get_session, load_config
from pipeline.chunker import split_pages

CHUNKS_TABLE = "RAG_STARTER.RAG.DOCUMENT_CHUNKS"


def page_texts(content) -> list[str]:
    """AI_PARSE_DOCUMENT output with page_split -> list of page markdown, ordered by index."""
    doc = json.loads(content) if isinstance(content, str) else content
    if "pages" in doc:
        pages = sorted(doc["pages"], key=lambda p: p.get("index", 0))
        return [p.get("content", "") for p in pages]
    return [doc.get("content", "")]  # parsed without page_split


def main() -> None:
    cfg = load_config()
    session = get_session()

    rows = session.sql(
        "SELECT file_name, content FROM RAG_STARTER.RAW.PARSED_DOCUMENTS ORDER BY file_name"
    ).collect()
    if not rows:
        raise SystemExit("PARSED_DOCUMENTS is empty: run the pipeline from parse first.")

    records = []
    for row in rows:
        file_name = row["FILE_NAME"]
        chunks = split_pages(page_texts(row["CONTENT"]), cfg["chunk_size"], cfg["overlap"])
        for i, ch in enumerate(chunks):
            records.append(
                {
                    "CHUNK_ID": f"{file_name}#p{ch.page_number}#{i}",
                    "FILE_NAME": file_name,
                    "PAGE_NUMBER": ch.page_number,
                    "SECTION": ch.section,
                    "CHUNK_INDEX": i,
                    "CHUNK_TEXT": ch.text,
                    "CHUNK_SIZE": cfg["chunk_size"],
                    "OVERLAP": cfg["overlap"],
                }
            )
        print(f"{file_name}: {len(chunks)} chunks")

    df = pd.DataFrame(records)
    # Replace the rows in place (DELETE + append), not CREATE OR REPLACE: the table must keep
    # its identity and change tracking for the Cortex Search service built on it.
    session.sql(f"DELETE FROM {CHUNKS_TABLE}").collect()
    session.write_pandas(  # VERIFY: write_pandas with an existing table and fully qualified name
        df,
        table_name="DOCUMENT_CHUNKS",
        database="RAG_STARTER",
        schema="RAG",
        auto_create_table=False,
        overwrite=False,
    )
    session.sql(
        f"UPDATE {CHUNKS_TABLE} SET created_at = CURRENT_TIMESTAMP() WHERE created_at IS NULL"
    ).collect()
    print(f"Wrote {len(df)} chunks (chunk_size={cfg['chunk_size']}, overlap={cfg['overlap']})")


if __name__ == "__main__":
    main()
