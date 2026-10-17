-- One-time account setup, run by hand as ACCOUNTADMIN before the first `snow dcm plan`.
-- DCM needs a role, and a database + schema to hold the DCM project object, before it can run.
-- Everything else (the RAG_STARTER database, warehouse, stage, tables) is created by DCM.
-- VERIFY: https://docs.snowflake.com/en/user-guide/dcm-projects/dcm-projects-use (privileges)

USE ROLE ACCOUNTADMIN;

-- Deployment role, used by you locally and by GitHub Actions.
CREATE ROLE IF NOT EXISTS RAG_DEPLOYER;
GRANT ROLE RAG_DEPLOYER TO ROLE SYSADMIN;
GRANT ROLE RAG_DEPLOYER TO USER IDENTIFIER(CURRENT_USER());

-- RAG_DEPLOYER creates the database and warehouse defined in dcm/sources/definitions/infra.sql.
GRANT CREATE DATABASE ON ACCOUNT TO ROLE RAG_DEPLOYER;
GRANT CREATE WAREHOUSE ON ACCOUNT TO ROLE RAG_DEPLOYER;

-- Cortex: AI_PARSE_DOCUMENT, Cortex Search, AI_COMPLETE.
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE RAG_DEPLOYER;

-- AI Observability (TruLens). VERIFY each line against
-- https://docs.snowflake.com/en/user-guide/snowflake-cortex/ai-observability (Required privileges).
GRANT APPLICATION ROLE SNOWFLAKE.AI_OBSERVABILITY_EVENTS_LOOKUP TO ROLE RAG_DEPLOYER;  -- VERIFY
-- CREATE EXTERNAL AGENT is needed on the schema where TruApp registers the app (RAG_STARTER.EVAL).
-- RAG_DEPLOYER owns that schema through DCM, so ownership should cover it. VERIFY on first run.
GRANT EXECUTE TASK ON ACCOUNT TO ROLE RAG_DEPLOYER;                                    -- VERIFY

-- Holder for the DCM project object.
CREATE DATABASE IF NOT EXISTS RAG_ADMIN;
CREATE SCHEMA IF NOT EXISTS RAG_ADMIN.DCM;
GRANT OWNERSHIP ON DATABASE RAG_ADMIN TO ROLE RAG_DEPLOYER COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA RAG_ADMIN.DCM TO ROLE RAG_DEPLOYER COPY CURRENT GRANTS;

-- A small warehouse just for DCM/CLI admin work (DCM also needs a temp stage in RAG_ADMIN.DCM).
CREATE WAREHOUSE IF NOT EXISTS RAG_ADMIN_WH
  WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE;
GRANT USAGE ON WAREHOUSE RAG_ADMIN_WH TO ROLE RAG_DEPLOYER;

-- Cost guard. Adjust credit_quota to your trial balance.
CREATE RESOURCE MONITOR IF NOT EXISTS RAG_MONITOR
  WITH CREDIT_QUOTA = 20 FREQUENCY = MONTHLY START_TIMESTAMP = IMMEDIATELY
  TRIGGERS ON 75 PERCENT DO NOTIFY
           ON 100 PERCENT DO SUSPEND;
ALTER WAREHOUSE RAG_ADMIN_WH SET RESOURCE_MONITOR = RAG_MONITOR;
-- After the first DCM deploy, also run:
--   ALTER WAREHOUSE RAG_WH SET RESOURCE_MONITOR = RAG_MONITOR;

-- Service user for GitHub Actions (key-pair auth). Paste the public key after generating it:
--   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
--   openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
CREATE USER IF NOT EXISTS GITHUB_RAG_SVC
  TYPE = SERVICE
  DEFAULT_ROLE = RAG_DEPLOYER
  DEFAULT_WAREHOUSE = RAG_ADMIN_WH
  COMMENT = 'GitHub Actions deployer for rag-starter';
-- ALTER USER GITHUB_RAG_SVC SET RSA_PUBLIC_KEY = '<contents of rsa_key.pub without header/footer>';
GRANT ROLE RAG_DEPLOYER TO USER GITHUB_RAG_SVC;

-- Finally, as RAG_DEPLOYER:
--   snow dcm create --target DEV --from dcm
