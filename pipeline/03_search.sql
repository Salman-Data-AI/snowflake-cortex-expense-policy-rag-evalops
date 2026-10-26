-- Step 3: create the Cortex Search service over DOCUMENT_CHUNKS, or refresh it if it exists.
-- Reads:  RAG_STARTER.RAG.DOCUMENT_CHUNKS
-- Writes: the search index (RAG_STARTER.RAG.POLICY_SEARCH)
-- Cortex Search is not a DCM-supported object, so it lives here as versioned SQL.
-- VERIFY: https://docs.snowflake.com/en/sql-reference/sql/create-cortex-search
--
-- If you change the column list or ATTRIBUTES below, the existing service will not pick it up:
-- run `DROP CORTEX SEARCH SERVICE RAG_STARTER.RAG.POLICY_SEARCH;` once, then rerun from chunk.

USE WAREHOUSE RAG_WH;

CREATE CORTEX SEARCH SERVICE IF NOT EXISTS RAG_STARTER.RAG.POLICY_SEARCH
    ON chunk_text
    ATTRIBUTES file_name, section
    WAREHOUSE = RAG_WH
    TARGET_LAG = '7 days'         -- long lag: refreshes are triggered by this script, not on a timer
    AUTO_SUSPEND = 1800            -- serving suspends after 30 idle minutes (the minimum)
    AS (
        SELECT
            chunk_text,
            chunk_id,
            file_name,
            page_number,
            section
        FROM RAG_STARTER.RAG.DOCUMENT_CHUNKS
    );

-- Serving may have been suspended at the end of the last session.
ALTER CORTEX SEARCH SERVICE RAG_STARTER.RAG.POLICY_SEARCH RESUME;  -- VERIFY: no error when already running

-- Pick up the chunks just written by 02_chunk.py.
ALTER CORTEX SEARCH SERVICE RAG_STARTER.RAG.POLICY_SEARCH REFRESH;

-- Smoke test: should return chunks about receipts.
SELECT PARSE_JSON(
    SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
        'RAG_STARTER.RAG.POLICY_SEARCH',
        '{"query": "when is a receipt required", "columns": ["chunk_id", "file_name", "page_number"], "limit": 3}'
    )
)['results'] AS results;
