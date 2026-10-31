"""Offline checks that the repository is complete and its data files are well formed."""

import ast
import csv
import re
from functools import cache
from pathlib import Path

import yaml
from pypdf import PdfReader

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


def _rag_label():
    """RagApp._label, taken from app/ask.py's source: importing app.ask needs TruLens."""
    tree = ast.parse((ROOT / "app/ask.py").read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_label")
    func.decorator_list = []
    namespace = {}
    exec(compile(ast.Module(body=[func], type_ignores=[]), "app/ask.py", "exec"), namespace)
    return namespace["_label"]


def test_prompt_citation_example_matches_label_format():
    text = (ROOT / "app/prompt_v1.txt").read_text()
    match = re.search(r"for example (\[(\S+) p\.(\d+)\])", text)
    assert match, "prompt has no citation example like [file.pdf p.N]"
    example, file_name, page = match.groups()
    assert _rag_label()({"file_name": file_name, "page_number": int(page)}) == example
    with open(ROOT / "documents/manifest.csv", newline="", encoding="utf-8") as f:
        assert file_name in {r["file_name"] for r in csv.DictReader(f)}


def test_questions_csv_shape():
    with open(ROOT / "eval/questions.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert set(rows[0]) == {
        "question_id", "question", "expected_answer", "expected_document", "category",
        "expected_pages", "key_facts",
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


def _gold_rows():
    with open(ROOT / "eval/questions.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@cache
def _pdf_pages(file_name: str) -> list[str]:
    """Text of each page of documents/<file_name>, whitespace collapsed and lower-cased."""
    reader = PdfReader(ROOT / "documents" / file_name)
    return [_normalise(page.extract_text() or "") for page in reader.pages]


def _normalise(text: str) -> str:
    return " ".join(text.split()).lower()


def _split(value: str) -> list[str]:
    return value.split("|") if value else []


def test_gold_pages_and_facts_are_well_formed():
    with open(ROOT / "documents/manifest.csv", newline="", encoding="utf-8") as f:
        manifest = {r["file_name"] for r in csv.DictReader(f)}
    for r in _gold_rows():
        qid, doc = r["question_id"], r["expected_document"]
        pages, facts = _split(r["expected_pages"]), _split(r["key_facts"])
        assert bool(pages) == bool(facts), f"{qid}: set both expected_pages and key_facts, or neither"
        if doc == "NONE":
            assert not pages, f"{qid}: unanswerable row has expected_pages/key_facts"
            continue
        assert doc in manifest, f"{qid}: {doc} not in documents/manifest.csv"
        assert (ROOT / "documents" / doc).is_file(), f"{qid}: documents/{doc} does not exist"
        assert all(fact.strip() for fact in facts), f"{qid}: empty key_fact in {r['key_facts']!r}"
        n_pages = len(_pdf_pages(doc))
        for page in pages:
            assert page.isdecimal() and 1 <= int(page) <= n_pages, (
                f"{qid}: page {page!r} not in 1..{n_pages} of {doc}"
            )


def test_gold_facts_on_expected_pages():
    """Each key_fact appears on at least one expected page (D-017: pypdf text, whitespace/case only)."""
    failures = []
    for r in _gold_rows():
        if not r["key_facts"]:
            continue
        qid, doc = r["question_id"], r["expected_document"]
        text = _pdf_pages(doc)
        pages = _split(r["expected_pages"])
        # Malformed or out-of-range pages are reported by test_gold_pages_and_facts_are_well_formed.
        on_pages = [text[int(p) - 1] for p in pages if p.isdecimal() and 1 <= int(p) <= len(text)]
        for fact in _split(r["key_facts"]):
            if not any(_normalise(fact) in page for page in on_pages):
                failures.append(f"{qid}: {fact!r} not on pages {pages} of {doc}")
    assert not failures, "\n".join(failures)
