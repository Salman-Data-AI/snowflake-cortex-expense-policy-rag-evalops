"""Pure-Python text splitting. No Snowflake imports, so it is unit-tested offline.

Sizes are in approximate tokens (4 characters per token), matching the rule of thumb
Snowflake uses for Cortex Search; keep chunk_size at or below ~512 for the default
embedding model's context window.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CHARS_PER_TOKEN = 4
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
SENTENCE_RE = re.compile(r"(?<=[.!?;:])\s+")
# A markdown table: consecutive lines starting with "|", the second one a separator row (|---|:---:|).
# VERIFY: https://docs.snowflake.com/en/sql-reference/functions/ai_parse_document
#         Table detection assumes AI_PARSE_DOCUMENT LAYOUT mode outputs tables as pipe-style markdown.
SEPARATOR_RE = re.compile(r"^\s*\|\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")


@dataclass
class Chunk:
    text: str
    page_number: int  # 1-based page the chunk starts on
    section: str      # nearest markdown heading above the chunk ("" if none)


def approx_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN) if text else 0


def _split_long(piece: str, max_tokens: int) -> list[str]:
    """Break a paragraph that is too long on its own: sentences first, then words."""
    if approx_tokens(piece) <= max_tokens:
        return [piece]
    out: list[str] = []
    for sentence in SENTENCE_RE.split(piece):
        if approx_tokens(sentence) <= max_tokens:
            out.append(sentence)
            continue
        words, buf = sentence.split(), []
        for word in words:
            if buf and approx_tokens(" ".join(buf + [word])) > max_tokens:
                out.append(" ".join(buf))
                buf = []
            buf.append(word)
        if buf:
            out.append(" ".join(buf))
    return out


def _tail(text: str, tokens: int) -> str:
    """Last ~`tokens` tokens of text, cut on a word boundary."""
    if tokens <= 0:
        return ""
    chars = tokens * CHARS_PER_TOKEN
    if len(text) <= chars:
        return text
    cut = text[-chars:]
    space = cut.find(" ")
    return cut[space + 1:] if space != -1 else cut


def _is_row(line: str) -> bool:
    return line.lstrip().startswith("|")


def _row_safe_tail(text: str, tokens: int) -> str:
    """_tail, but never starting partway through a table row: skip ahead to the next line instead."""
    tail = _tail(text, tokens)
    start = len(text) - len(tail)
    if not tail or start == 0 or text[start - 1] == "\n":
        return tail
    line_start = text.rfind("\n", 0, start) + 1
    if not _is_row(text[line_start:].split("\n", 1)[0]):
        return tail
    newline = tail.find("\n")
    return tail[newline + 1:].lstrip("\n") if newline != -1 else ""


def _segments(para: str) -> list[tuple[str, bool]]:
    """A paragraph as (text, is_table) pieces. A paragraph with no table comes back unchanged."""
    lines = para.splitlines()
    out: list[tuple[str, bool]] = []
    prose: list[str] = []
    found = False
    i = 0
    while i < len(lines):
        if not _is_row(lines[i]):
            prose.append(lines[i])
            i += 1
            continue
        j = i
        while j < len(lines) and _is_row(lines[j]):
            j += 1
        if j - i >= 2 and SEPARATOR_RE.match(lines[i + 1]):
            found = True
            if prose:
                out.append(("\n".join(prose), False))
                prose = []
            out.append(("\n".join(lines[i:j]), True))
        else:
            prose.extend(lines[i:j])  # pipe lines without a separator row are ordinary text
        i = j
    if not found:
        return [(para, False)]
    if prose:
        out.append(("\n".join(prose), False))
    return out


def _table_pieces(table: str, chunk_size: int) -> list[str]:
    """A table as one piece if it fits in chunk_size, else pieces split between rows, each
    starting with the header and separator rows and staying within chunk_size."""
    if approx_tokens(table) <= chunk_size:
        return [table]
    lines = table.splitlines()
    header = "\n".join(lines[:2])
    if approx_tokens(header) >= chunk_size - 1:
        return _split_long(table, chunk_size)  # no room for rows next to the header: can't repeat it
    room = chunk_size - approx_tokens(header) - 1  # what a row fragment may use once the header is added

    def piece(rows: list[str]) -> str:
        return "\n".join([header, *rows])

    pieces: list[str] = []
    rows: list[str] = []
    for row in lines[2:]:
        if approx_tokens(piece([row])) > chunk_size:
            # This row is too long even alone with the header: fall back to _split_long (sentences,
            # then words) for this row only. Its fragments aren't valid table rows, but each still
            # starts with the header so it keeps the column names.
            if rows:
                pieces.append(piece(rows))
                rows = []
            pieces.extend(piece([fragment]) for fragment in _split_long(row, room))
            continue
        if rows and approx_tokens(piece(rows + [row])) > chunk_size:
            pieces.append(piece(rows))
            rows = []
        rows.append(row)
    if rows:
        pieces.append(piece(rows))
    return pieces


def split_pages(pages: list[str], chunk_size: int, overlap: int) -> list[Chunk]:
    """Split a document given as a list of page texts (markdown) into chunks.

    - Paragraphs are packed together until adding the next one would exceed chunk_size.
    - A paragraph longer than chunk_size is broken into sentences, then words.
    - Each chunk after the first starts with the last `overlap` tokens of the previous one.
    - A markdown heading always starts a new chunk, so chunks don't straddle sections.
    - A markdown table is kept whole: in the current chunk if it fits, else at the start of the
      next one. A table longer than chunk_size is split between rows, each piece starting with the
      header and separator rows. A chunk that starts with a table gets no overlap (the header
      takes its place), and overlap never starts partway through a table row.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")

    chunks: list[Chunk] = []
    has_table: list[bool] = []  # per chunk: its text includes table rows (overlap must respect them)
    section = ""
    buf: list[str] = []
    buf_page = 1
    buf_section = ""
    buf_starts_table = False
    buf_has_table = False
    budget = chunk_size - overlap  # room for new text once the overlap prefix is added

    def flush() -> None:
        nonlocal buf
        if not buf:
            return
        body = "\n\n".join(buf).strip()
        if body:
            prefix = ""
            if chunks and overlap and not buf_starts_table:
                prev = chunks[-1].text
                prefix = _row_safe_tail(prev, overlap) if has_table[-1] else _tail(prev, overlap)
            text = f"{prefix}\n\n{body}".strip() if prefix else body
            chunks.append(Chunk(text=text, page_number=buf_page, section=buf_section))
            has_table.append(buf_has_table or (bool(prefix) and has_table[-1]))
        buf = []

    def add(piece: str, page_no: int, is_table: bool) -> None:
        nonlocal buf_page, buf_section, buf_starts_table, buf_has_table
        # A chunk that starts with a table has no overlap prefix, so it has the full chunk_size.
        room = chunk_size if buf_starts_table else budget
        if buf and approx_tokens("\n\n".join(buf + [piece])) > room:
            flush()
        if not buf:
            buf_page, buf_section = page_no, section
            buf_starts_table, buf_has_table = is_table, False
        buf.append(piece)
        buf_has_table = buf_has_table or is_table

    for page_no, page in enumerate(pages, start=1):
        for para in re.split(r"\n\s*\n", page or ""):
            para = para.strip()
            if not para:
                continue
            heading = HEADING_RE.match(para.splitlines()[0])
            if heading:
                flush()
                section = heading.group(1).strip()
            for text, is_table in _segments(para):
                pieces = _table_pieces(text, chunk_size) if is_table else _split_long(text, budget)
                for piece in pieces:
                    add(piece, page_no, is_table)
    flush()
    return chunks
