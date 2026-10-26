import pytest

from pipeline.chunker import approx_tokens, split_pages

SAMPLE_PAGES = [
    "# Travel Regulations\n\n"
    "Receipts are required for lodging and for any expense of $75 or more.\n\n"
    "## Airfare\n\n"
    + " ".join(["Economy class is the standard for all university travel."] * 40),
    "## Meals\n\n"
    "Meals are reimbursed at actual cost up to the per diem.\n\n"
    "Travel without an overnight stay does not qualify for meal reimbursement.",
]


def test_chunks_respect_size():
    chunks = split_pages(SAMPLE_PAGES, chunk_size=100, overlap=20)
    assert chunks, "expected at least one chunk"
    for ch in chunks:
        # Overlap prefix + body can exceed the target slightly at word boundaries.
        assert approx_tokens(ch.text) <= 100 + 5, ch.text


def test_headings_start_new_chunks_and_set_section():
    chunks = split_pages(SAMPLE_PAGES, chunk_size=200, overlap=0)
    sections = [c.section for c in chunks]
    assert sections[0] == "Travel Regulations"
    assert "Airfare" in sections
    assert "Meals" in sections
    meals = [c for c in chunks if c.section == "Meals"][0]
    assert meals.text.startswith("## Meals")


def test_page_numbers_follow_pages():
    chunks = split_pages(SAMPLE_PAGES, chunk_size=200, overlap=0)
    assert chunks[0].page_number == 1
    assert chunks[-1].page_number == 2


def test_overlap_repeats_tail_of_previous_chunk():
    chunks = split_pages(SAMPLE_PAGES, chunk_size=60, overlap=15)
    with_overlap = [
        (prev, cur) for prev, cur in zip(chunks, chunks[1:], strict=False)
        if cur.text.split()[0] in prev.text
    ]
    assert with_overlap, "later chunks should start with text from the previous chunk"


def test_no_text_is_lost_without_overlap():
    chunks = split_pages(SAMPLE_PAGES, chunk_size=80, overlap=0)
    joined = " ".join(c.text for c in chunks).split()
    original = " ".join(SAMPLE_PAGES).split()
    assert joined == original


def test_empty_input():
    assert split_pages([], 100, 10) == []
    assert split_pages(["", "   "], 100, 10) == []


@pytest.mark.parametrize("size,overlap", [(0, 0), (100, 100), (100, -1)])
def test_bad_settings_rejected(size, overlap):
    with pytest.raises(ValueError):
        split_pages(["text"], size, overlap)
