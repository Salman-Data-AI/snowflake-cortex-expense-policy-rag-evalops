"""page_texts: AI_PARSE_DOCUMENT output -> page list. Input shape as pipeline/parsed_doc.py assumes it
(page_split: {"pages": [{"index", "content"}]}; see the VERIFY there)."""

import json

from app.citations import label
from pipeline.chunker import split_pages
from pipeline.parsed_doc import page_texts


def _doc(*contents):
    return {"pages": [{"index": i, "content": c} for i, c in enumerate(contents)]}


def test_multi_page_ordered_by_index():
    doc = {
        "pages": [
            {"index": 2, "content": "third"},
            {"index": 0, "content": "first"},
            {"index": 1, "content": "second"},
        ]
    }
    assert page_texts(doc) == ["first", "second", "third"]


def test_json_string_input():
    assert page_texts(json.dumps(_doc("a", "b"))) == ["a", "b"]


def test_text_outside_pages_is_dropped():
    """Current behaviour: top-level content next to "pages" (e.g. text before the first page) is ignored."""
    doc = {"content": "preamble", **_doc("page one", "page two")}
    assert page_texts(doc) == ["page one", "page two"]


def test_empty_page_keeps_its_place():
    doc = _doc("one", "", "three")
    doc["pages"].append({"index": 3})  # no content key
    assert page_texts(doc) == ["one", "", "three", ""]


def test_no_pages_key_is_one_page():
    assert page_texts({"content": "whole document"}) == ["whole document"]
    assert page_texts({}) == [""]


def test_page_numbers_are_one_based_and_match_citations():
    doc = _doc("# Intro\n\nAlpha text.", "", "# Meals\n\nBeta text.")
    chunks = split_pages(page_texts(doc), chunk_size=100, overlap=0)
    pages = {c.text.split("\n\n")[-1]: c.page_number for c in chunks}
    assert pages == {"Alpha text.": 1, "Beta text.": 3}
    beta = next(c for c in chunks if "Beta" in c.text)
    assert label({"file_name": "f.pdf", "page_number": beta.page_number}) == "[f.pdf p.3]"
