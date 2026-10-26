"""Offline checks that the repository is complete and its data files are well formed."""

import csv
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = [
    "README.md",
    "requirements.txt",
    "documents/manifest.csv",
    "dcm/manifest.yml",
    "dcm/bootstrap.sql",
    "dcm/sources/definitions/infra.sql",
    "dcm/sources/definitions/tables.sql",
    "pipeline/01_parse.sql",
    "pipeline/02_chunk.py",
    "pipeline/03_search.sql",
    "pipeline/reparse_all.sql",
    "config/rag.yaml",
    "app/ask.py",
    "app/prompt_v1.txt",
    "eval/questions.csv",
    "eval/run_eval.py",
    "eval/compare.sql",
    ".github/workflows/checks.yml",
    ".github/workflows/run-pipeline.yml",
]

TABLES = ["PARSED_DOCUMENTS", "DOCUMENT_CHUNKS", "EVAL_QUESTIONS", "PIPELINE_RUNS", "EVAL_RESULTS"]


def test_required_files_exist():
    missing = [f for f in REQUIRED_FILES if not (ROOT / f).exists()]
    assert not missing, f"missing: {missing}"


def test_all_five_tables_defined():
    sql = (ROOT / "dcm/sources/definitions/tables.sql").read_text().upper()
    for t in TABLES:
        assert f".{t} (" in sql, f"{t} not defined"


def test_config_has_experiment_settings():
    cfg = yaml.safe_load((ROOT / "config/rag.yaml").read_text())
    for key in ["chunk_size", "overlap", "top_k", "model", "prompt_version", "judge_model"]:
        assert key in cfg, key
    assert 0 <= cfg["overlap"] < cfg["chunk_size"] <= 512
    assert (ROOT / f"app/prompt_{cfg['prompt_version']}.txt").exists()


def test_prompt_has_placeholders():
    text = (ROOT / "app/prompt_v1.txt").read_text()
    assert "{context}" in text and "{question}" in text


def test_questions_csv_shape():
    with open(ROOT / "eval/questions.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert set(rows[0]) == {
        "question_id", "question", "expected_answer", "expected_document", "category",
    }
    assert 10 <= len(rows) <= 15
    ids = [r["question_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate question_id"
    unanswerable = [r for r in rows if r["expected_document"] == "NONE"]
    assert 2 <= len(unanswerable) <= 3
    for r in unanswerable:
        assert "not in the documents" in r["expected_answer"].lower()


def test_expected_documents_are_in_manifest():
    with open(ROOT / "documents/manifest.csv", newline="", encoding="utf-8") as f:
        files = {r["file_name"] for r in csv.DictReader(f)}
    with open(ROOT / "eval/questions.csv", newline="", encoding="utf-8") as f:
        expected = {r["expected_document"] for r in csv.DictReader(f)} - {"NONE"}
    assert expected <= files, f"not in manifest: {expected - files}"
