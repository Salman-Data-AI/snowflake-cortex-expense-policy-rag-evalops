-- The five tables. Each pipeline step reads the table written by the step above it.
-- VERIFY: DEFINE TABLE syntax and change_tracking support in DCM.

-- Written by 01_parse.sql. One row per parsed file; later steps never call AI_PARSE_DOCUMENT.
define table RAG_STARTER.RAW.PARSED_DOCUMENTS (
    FILE_NAME   varchar        comment 'Path of the file in DOCS_STAGE',
    FILE_MD5    varchar        comment 'Checksum from the stage directory table; unchanged files are not reparsed',
    PARSED_AT   timestamp_ltz,
    PARSE_MODE  varchar        comment 'LAYOUT or OCR',
    PAGE_COUNT  number,
    CONTENT     variant        comment 'AI_PARSE_DOCUMENT output with page_split: {pages: [{index, content}]}'
);

-- Written by 02_chunk.py, read by the Cortex Search service.
-- Change tracking is required for a Cortex Search source table.
define table RAG_STARTER.RAG.DOCUMENT_CHUNKS (
    CHUNK_ID     varchar       comment 'file_name#page#chunk_index',
    FILE_NAME    varchar,
    PAGE_NUMBER  number        comment '1-based page the chunk starts on',
    SECTION      varchar       comment 'Nearest markdown heading above the chunk',
    CHUNK_INDEX  number        comment 'Position of the chunk within the file',
    CHUNK_TEXT   varchar,
    CHUNK_SIZE   number        comment 'Target size in tokens from rag.yaml',
    OVERLAP      number        comment 'Overlap in tokens from rag.yaml',
    CREATED_AT   timestamp_ltz
)
change_tracking = true;

-- Loaded from eval/questions.csv by eval/run_eval.py on every evaluation.
define table RAG_STARTER.EVAL.EVAL_QUESTIONS (
    QUESTION_ID        varchar,
    QUESTION           varchar,
    EXPECTED_ANSWER    varchar,
    EXPECTED_DOCUMENT  varchar comment 'File name, or NONE when the answer is not in the documents',
    CATEGORY           varchar,
    EXPECTED_PAGES     varchar comment '1-based physical page index in the PDF, |-separated; empty for NONE',
    KEY_FACTS          varchar comment 'Facts as pypdf renders them on those pages, |-separated (D-017)'
);

-- One row per press of the pipeline button.
define table RAG_STARTER.EVAL.PIPELINE_RUNS (
    RUN_ID          varchar,
    STARTED_AT      timestamp_ltz,
    FINISHED_AT     timestamp_ltz,
    START_FROM      varchar,
    REPARSE_ALL     boolean,
    STATUS          varchar,
    GIT_COMMIT      varchar,
    CHUNK_SIZE      number,
    OVERLAP         number,
    TOP_K           number,
    MODEL           varchar,
    PROMPT_VERSION  varchar
);

-- Copy of TruLens scores, one row per question per metric, with the run's settings attached.
define table RAG_STARTER.EVAL.EVAL_RESULTS (
    RUN_ID          varchar,
    APP_VERSION     varchar,
    QUESTION_ID     varchar,
    METRIC          varchar,
    SCORE           float,
    LATENCY_S       float,
    ANSWER          varchar,
    GIT_COMMIT      varchar,
    CHUNK_SIZE      number,
    OVERLAP         number,
    TOP_K           number,
    MODEL           varchar,
    PROMPT_VERSION  varchar,
    JUDGE_MODEL     varchar,
    RECORDED_AT     timestamp_ltz
);
