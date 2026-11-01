"""Citation labels for retrieved chunks. Imports nothing, so it is tested offline."""

from __future__ import annotations


def label(hit: dict) -> str:
    """The bracketed source label a chunk is shown with, and that the model cites: [file.pdf p.N]."""
    return f"[{hit['file_name']} p.{hit['page_number']}]"
