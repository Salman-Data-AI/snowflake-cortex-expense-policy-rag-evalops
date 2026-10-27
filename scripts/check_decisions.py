"""Check that REVIEW.md's decision index and docs/decisions.md agree. Run by checks.yml.

Fails if an index ID has no entry or an entry has no index line, if an ID is duplicated in either
file, if an index link points at the wrong anchor, or if an entry is missing a required field.

    python scripts/check_decisions.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_FIELDS = [
    "Status", "Date", "Context", "Decision", "Alternatives considered", "Consequences", "Reviewer note",
]
INDEX_RE = re.compile(r"^- (D-\d{3}): .+ → docs/decisions\.md#(\S+)\s*$")
HEADING_RE = re.compile(r"^## (D-\d{3}): .+$")


def _outside_fences(text: str) -> list[str]:
    lines, fenced = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced:
            lines.append(line)
    return lines


def index_entries(review_md: str) -> tuple[list[tuple[str, str]], list[str]]:
    """(ID, anchor) for each index line under '## Intentional decisions', and malformed '- D-' lines."""
    out, bad, in_section = [], [], False
    for line in _outside_fences(review_md):
        if line.startswith("## "):
            in_section = line.strip() == "## Intentional decisions"
        elif in_section and (m := INDEX_RE.match(line)):
            out.append((m.group(1), m.group(2)))
        elif in_section and line.startswith("- D-"):
            bad.append(line)
    return out, bad


def decision_entries(decisions_md: str) -> list[tuple[str, list[str]]]:
    """(ID, lines of the entry) for each '## D-nnn: title' heading."""
    out: list[tuple[str, list[str]]] = []
    for line in _outside_fences(decisions_md):
        if m := HEADING_RE.match(line):
            out.append((m.group(1), []))
        elif line.startswith("## "):
            out.append(("", []))  # a non-decision section ends the previous entry
        elif out:
            out[-1][1].append(line)
    return [(d, body) for d, body in out if d]


def check(review_md: str, decisions_md: str) -> list[str]:
    errors = []
    index, malformed = index_entries(review_md)
    entries = decision_entries(decisions_md)
    for line in malformed:
        errors.append(f"REVIEW.md: malformed index line (expected '- D-nnn: <title> → "
                      f"docs/decisions.md#d-nnn'): {line}")
    index_ids = [d for d, _ in index]
    entry_ids = [d for d, _ in entries]

    if not index:
        errors.append("REVIEW.md: no index lines under '## Intentional decisions'")
    for d, n in Counter(index_ids).items():
        if n > 1:
            errors.append(f"REVIEW.md: {d} is listed {n} times")
    for d, n in Counter(entry_ids).items():
        if n > 1:
            errors.append(f"docs/decisions.md: {d} has {n} entries")
    for d in sorted(set(index_ids) - set(entry_ids)):
        errors.append(f"REVIEW.md lists {d}, but docs/decisions.md has no '## {d}:' entry")
    for d in sorted(set(entry_ids) - set(index_ids)):
        errors.append(f"docs/decisions.md has {d}, but REVIEW.md has no index line for it")
    for d, anchor in index:
        if anchor != d.lower():
            errors.append(f"REVIEW.md: {d} links to #{anchor}, expected #{d.lower()}")
    for d, body in entries:
        fields = {}
        for line in body:
            if ":" in line:
                name, value = line.split(":", 1)
                fields.setdefault(name, value.strip())
        for field in REQUIRED_FIELDS:
            if field not in fields:
                errors.append(f"docs/decisions.md: {d} is missing '{field}:'")
            elif not fields[field]:
                errors.append(f"docs/decisions.md: {d} has an empty '{field}:'")
        if fields.get("Status", "").startswith("accepted (deferred)") and not fields.get("Revisit when"):
            errors.append(f"docs/decisions.md: {d} is deferred but has no 'Revisit when:'")
    return errors


def main(root: Path = ROOT) -> int:
    errors = check(
        (root / "REVIEW.md").read_text(encoding="utf-8"),
        (root / "docs" / "decisions.md").read_text(encoding="utf-8"),
    )
    for e in errors:
        print(e, file=sys.stderr)
    if not errors:
        print("Decision log OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
