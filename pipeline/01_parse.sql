-- Step 1: parse staged PDFs that are not already in PARSED_DOCUMENTS.
-- Reads:  RAG_STARTER.RAW.DOCS_STAGE (directory table)
-- Writes: RAG_STARTER.RAW.PARSED_DOCUMENTS
-- A file is skipped when the same name AND checksum is already parsed, so pressing
-- "start from parse" twice parses nothing the second time.
-- VERIFY: https://docs.snowflake.com/en/sql-reference/functions/ai_parse_document

USE WAREHOUSE RAG_WH;

-- Make sure the directory table sees files uploaded since the last run.
ALTER STAGE RAG_STARTER.RAW.DOCS_STAGE REFRESH;

-- A file that changed (same name, new checksum) is reparsed: drop its old row first.
DELETE FROM RAG_STARTER.RAW.PARSED_DOCUMENTS p
USING DIRECTORY(@RAG_STARTER.RAW.DOCS_STAGE) d
WHERE p.file_name = d.relative_path
  AND p.file_md5 <> d.md5;

INSERT INTO RAG_STARTER.RAW.PARSED_DOCUMENTS
    (file_name, file_md5, parsed_at, parse_mode, page_count, content)
WITH new_files AS (
    SELECT d.relative_path, d.md5
    FROM DIRECTORY(@RAG_STARTER.RAW.DOCS_STAGE) AS d
    WHERE d.relative_path ILIKE '%.pdf'
      AND NOT EXISTS (
          SELECT 1
          FROM RAG_STARTER.RAW.PARSED_DOCUMENTS AS p
          WHERE p.file_name = d.relative_path
            AND p.file_md5 = d.md5
      )
),

parsed AS (
    SELECT
        relative_path,
        md5,
        -- The function returns JSON (as a string per the docs); TO_VARCHAR + PARSE_JSON works
        -- whether it comes back as a string or an object. VERIFY on the first run.
        PARSE_JSON(TO_VARCHAR(
            AI_PARSE_DOCUMENT(
                TO_FILE('@RAG_STARTER.RAW.DOCS_STAGE', relative_path),
                {'mode': 'LAYOUT', 'page_split': TRUE}
            )
        )) AS doc
    FROM new_files
)

SELECT
    relative_path AS file_name,
    md5 AS file_md5,
    CURRENT_TIMESTAMP() AS parsed_at,
    'LAYOUT' AS parse_mode,
    ARRAY_SIZE(doc:pages) AS page_count,
    doc AS content
FROM parsed;

-- Quick check: one row per PDF, with a page count.
SELECT file_name, page_count, parsed_at
FROM RAG_STARTER.RAW.PARSED_DOCUMENTS
ORDER BY file_name;
