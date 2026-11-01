"""Read AI_PARSE_DOCUMENT output. Pure Python (no Snowflake or pandas), so it is tested offline."""

from __future__ import annotations

import json


def page_texts(content) -> list[str]:
    """AI_PARSE_DOCUMENT output with page_split -> list of page markdown, ordered by index."""
    # VERIFY: https://docs.snowflake.com/en/sql-reference/functions/ai_parse_document
    #         page_split output is {"pages": [{"index": n, "content": "..."}]}, index 0-based and
    #         contiguous (page numbers come from list position, not index).
    #         Without page_split: {"content": "..."}.
    doc = json.loads(content) if isinstance(content, str) else content
    if "pages" in doc:
        pages = sorted(doc["pages"], key=lambda p: p.get("index", 0))
        return [p.get("content", "") for p in pages]
    return [doc.get("content", "")]  # parsed without page_split
