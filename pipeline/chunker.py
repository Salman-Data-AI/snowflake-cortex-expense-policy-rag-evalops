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


def split_pages(pages: list[str], chunk_size: int, overlap: int) -> list[Chunk]:
    """Split a document given as a list of page texts (markdown) into chunks.

    - Paragraphs are packed together until adding the next one would exceed chunk_size.
    - A paragraph longer than chunk_size is broken into sentences, then words.
    - Each chunk after the first starts with the last `overlap` tokens of the previous one.
    - A markdown heading always starts a new chunk, so chunks don't straddle sections.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")

    chunks: list[Chunk] = []
    section = ""
    buf: list[str] = []
    buf_page = 1
    buf_section = ""
    budget = chunk_size - overlap  # room for new text once the overlap prefix is added

    def flush() -> None:
        nonlocal buf
        if not buf:
            return
        body = "\n\n".join(buf).strip()
        if body:
            prefix = _tail(chunks[-1].text, overlap) if chunks and overlap else ""
            text = f"{prefix}\n\n{body}".strip() if prefix else body
            chunks.append(Chunk(text=text, page_number=buf_page, section=buf_section))
        buf = []

    for page_no, page in enumerate(pages, start=1):
        for para in re.split(r"\n\s*\n", page or ""):
            para = para.strip()
            if not para:
                continue
            heading = HEADING_RE.match(para.splitlines()[0])
            if heading:
                flush()
                section = heading.group(1).strip()
            for piece in _split_long(para, budget):
                if buf and approx_tokens("\n\n".join(buf + [piece])) > budget:
                    flush()
                if not buf:
                    buf_page, buf_section = page_no, section
                buf.append(piece)
    flush()
    return chunks
