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


# ---------- markdown tables ----------

HEADER = "| Meal | Limit |\n|---|---:|"
ROWS = [f"| Meal type number {i} | ${i}0 |" for i in range(12)]
SMALL_TABLE = HEADER + "\n" + "\n".join(ROWS[:2])
LONG_TABLE = HEADER + "\n" + "\n".join(ROWS)  # ~94 tokens


def test_small_table_inside_prose_stays_in_one_chunk():
    chunks = split_pages(["Meal limits are below.\n\n" + SMALL_TABLE + "\n\nThey include tax."], 200, 20)
    assert len(chunks) == 1
    assert SMALL_TABLE in chunks[0].text


def test_table_that_does_not_fit_moves_whole_to_next_chunk():
    prose = " ".join(["Business meals need a documented purpose."] * 3)  # ~32 tokens
    chunks = split_pages([prose + "\n\n" + SMALL_TABLE], 50, 10)
    holding = [c for c in chunks if "| Meal |" in c.text]
    assert len(holding) == 1
    # Starts the next chunk, with no overlap prefix before the header.
    assert holding[0].text == SMALL_TABLE
    assert prose in chunks[0].text


def test_long_table_splits_only_between_rows():
    chunks = split_pages(["Intro.\n\n" + LONG_TABLE + "\n\nAfter the table there is prose."], 60, 10)
    pieces = [c for c in chunks if c.text.startswith(HEADER + "\n")]
    assert len(pieces) >= 2
    for c in chunks:
        assert approx_tokens(c.text) <= 60, c.text
    piece_rows = [line for p in pieces for line in p.text.splitlines()[2:] if line.startswith("|")]
    assert sorted(piece_rows) == sorted(ROWS), "every data row exactly once across the pieces"


def test_overlap_after_a_table_never_starts_mid_row():
    prose = " ".join(["Claims are reviewed by the department approver."] * 6)
    chunks = split_pages([SMALL_TABLE + "\n\n" + prose], 40, 15)
    assert len(chunks) >= 2
    first_line = chunks[1].text.splitlines()[0]
    assert not first_line.startswith("|") or first_line in SMALL_TABLE.splitlines()
    assert first_line.startswith("|") or not any(first_line in row for row in ROWS)


def test_oversized_single_row_falls_back_to_split_long():
    long_cell = " ".join(f"word{i}" for i in range(120))  # ~150 tokens on its own
    big_row = f"| Other | {long_cell} |"
    table = HEADER + "\n" + ROWS[0] + "\n" + big_row + "\n" + ROWS[1]
    chunks = split_pages([table], 50, 0)
    assert all(c.text.startswith(HEADER + "\n") for c in chunks)
    bodies = [c.text.split(HEADER + "\n", 1)[1] for c in chunks]
    assert ROWS[0] in bodies[0] and ROWS[1] in bodies[-1]
    fragments = [b for b in bodies if b not in (ROWS[0], ROWS[1])]
    assert len(fragments) >= 2, "the big row is split"
    assert " ".join(fragments).split() == big_row.split(), "fragments rebuild the row in order"
    for c in chunks:
        assert approx_tokens(c.text) <= 50, c.text


def test_header_too_wide_for_chunk_falls_back_to_split_long():
    header = "| " + " | ".join(f"Column heading {i}" for i in range(8)) + " |\n|" + "---|" * 8
    table = header + "\n| " + " | ".join(str(i) for i in range(8)) + " |"
    chunks = split_pages([table], 30, 0)
    assert len(chunks) >= 2
    assert " ".join(c.text for c in chunks).split() == table.split(), "no text lost or reordered"
    for c in chunks:
        assert approx_tokens(c.text) <= 30, c.text


def test_prose_with_pipes_is_not_a_table():
    # Prose after the pipe lines, so overlap is taken from text containing them: prose must keep using
    # the plain overlap, not the table-row-safe one.
    pipe_doc = [
        "Choose lodging | airfare | meals on the form. " * 4 + "\n\n"
        "| this line starts with a pipe\n| but there is no separator row |\n| so it is prose |\n\n"
        + "Submit the form within 45 days of the trip. " * 3
    ]
    slash_doc = [page.replace("|", "/") for page in pipe_doc]  # same lengths, clearly not a table
    with_pipes = split_pages(pipe_doc, 30, 5)
    with_slashes = split_pages(slash_doc, 30, 5)
    assert [c.text.replace("|", "/") for c in with_pipes] == [c.text for c in with_slashes]


def test_document_without_tables_is_chunked_as_before():
    # Expected output recorded from the chunker before table handling was added.
    pages = [
        "# Travel Regulations\n\nReceipts are required for lodging. Keep them for audit.\n\n"
        "## Airfare\n\nEconomy class is standard. Business class needs approval; document the reason. "
        "Upgrades paid by the traveler are fine.",
        "Short note on page two.\n\n## Meals\n\nMeals follow the per diem. No overnight stay, no meals.",
    ]
    expected = [
        ("# Travel Regulations", 1, "Travel Regulations"),
        ("# Travel Regulations\n\nReceipts are required for lodging. Keep them for audit.", 1,
         "Travel Regulations"),
        ("Keep them for audit.\n\n## Airfare\n\nEconomy class is standard.\n\nBusiness class needs approval;",
         1, "Airfare"),
        ("class needs approval;\n\ndocument the reason.\n\nUpgrades paid by the traveler are fine.", 1,
         "Airfare"),
        ("the traveler are fine.\n\nShort note on page two.", 2, "Airfare"),
        ("note on page two.\n\n## Meals\n\nMeals follow the per diem. No overnight stay, no meals.", 2,
         "Meals"),
    ]
    chunks = split_pages(pages, chunk_size=24, overlap=6)
    assert [(c.text, c.page_number, c.section) for c in chunks] == expected
