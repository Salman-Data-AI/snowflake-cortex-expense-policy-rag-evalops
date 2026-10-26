-- Used only when the reparse_all checkbox is ticked: forget every parse so 01_parse.sql redoes all files.
-- Costs AI_PARSE_DOCUMENT credits for every page again.
DELETE FROM RAG_STARTER.RAW.PARSED_DOCUMENTS;
