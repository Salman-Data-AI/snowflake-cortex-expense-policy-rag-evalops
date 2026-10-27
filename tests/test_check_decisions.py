from scripts.check_decisions import ROOT, check, main

REVIEW = """# Review guide

## Intentional decisions

- D-001: Offline checks only → docs/decisions.md#d-001
- D-002: Tables per step → docs/decisions.md#d-002
"""

ENTRY = """Status: accepted
Date: 2026-10-27
Context: why
Decision: what
Alternatives considered: none
Consequences: some
Reviewer note: don't flag it
"""

DECISIONS = f"""# Design decisions

```
## D-099: an example heading inside a code fence
```

## D-001: Offline checks only
{ENTRY}
## D-002: Tables per step
{ENTRY}"""


def test_passing_sample():
    assert check(REVIEW, DECISIONS) == []


def test_index_without_entry_and_entry_without_index():
    review = REVIEW + "- D-003: Missing entry → docs/decisions.md#d-003\n"
    decisions = DECISIONS + "\n## D-004: Not indexed\n" + ENTRY
    errors = check(review, decisions)
    assert any("D-003" in e and "no '## D-003:' entry" in e for e in errors)
    assert any("D-004" in e and "no index line" in e for e in errors)


def test_duplicate_ids_and_wrong_anchor():
    review = REVIEW + "- D-002: Again → docs/decisions.md#d-001\n"
    decisions = DECISIONS + "\n## D-001: Duplicate\n" + ENTRY
    errors = check(review, decisions)
    assert "REVIEW.md: D-002 is listed 2 times" in errors
    assert "docs/decisions.md: D-001 has 2 entries" in errors
    assert "REVIEW.md: D-002 links to #d-001, expected #d-002" in errors


def test_missing_required_field():
    decisions = DECISIONS.replace("Reviewer note: don't flag it\n", "", 1)
    assert check(REVIEW, decisions) == ["docs/decisions.md: D-001 is missing 'Reviewer note:'"]


def test_empty_field_and_deferred_without_revisit():
    decisions = DECISIONS.replace("Context: why\n", "Context:\n", 1)
    decisions = decisions.replace("Status: accepted\n", "Status: accepted (deferred)\n", 1)
    no_revisit = "docs/decisions.md: D-001 is deferred but has no 'Revisit when:'"
    errors = check(REVIEW, decisions)
    assert "docs/decisions.md: D-001 has an empty 'Context:'" in errors
    assert no_revisit in errors
    with_revisit = decisions.replace("Reviewer note: don't flag it\n",
                                     "Reviewer note: don't flag it\nRevisit when: later\n", 1)
    assert no_revisit not in check(REVIEW, with_revisit)


def test_malformed_index_line_is_reported():
    review = REVIEW.replace("→ docs/decisions.md#d-002", "-> docs/decisions.md#d-002")
    errors = check(review, DECISIONS)
    assert any(e.startswith("REVIEW.md: malformed index line") and "D-002" in e for e in errors)


def test_heading_in_code_fence_is_not_an_entry():
    assert all("D-099" not in e for e in check(REVIEW, DECISIONS))


def test_repo_decision_log_passes():
    assert main(ROOT) == 0
