-- Database, schemas, warehouse and the document stage.
-- VERIFY: DEFINE syntax per https://docs.snowflake.com/en/user-guide/dcm-projects/dcm-projects-supported-entities

define database RAG_STARTER
    comment = 'Snowflake RAG starter: UC travel and expense policy assistant';

define schema RAG_STARTER.RAW
    comment = 'Staged PDFs and parsed documents';

define schema RAG_STARTER.RAG
    comment = 'Chunks and the Cortex Search service';

define schema RAG_STARTER.EVAL
    comment = 'Test questions, pipeline runs and evaluation results';

define warehouse RAG_WH
with
    warehouse_size = '{{wh_size}}'
    auto_suspend = 60
    auto_resume = true
    initially_suspended = true
    comment = 'Pipeline, search refresh and evaluation';

-- AI_PARSE_DOCUMENT needs server-side encryption and a directory table on the stage.
-- VERIFY: encryption is immutable in DCM; if the first deploy creates it wrong, drop the stage by hand.
define stage RAG_STARTER.RAW.DOCS_STAGE
    directory = (enable = true)
    encryption = (type = 'SNOWFLAKE_SSE')
    comment = 'Source PDFs, uploaded unchanged from documents/';
