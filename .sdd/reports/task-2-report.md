# Task 2 Report

## What I implemented

- Added standard-library HTML parsing with ordered nodes, attributes, text, headings, landmarks, fragments, and parse errors.
- Added read-only authored HTML validation for digests, metadata, CSP, resources, safety, landmarks, outlines, heading IDs, tables, document kinds, language, and Markdown text fidelity.
- Added structured `violations` and `warnings` to validator results while preserving Task 1 interfaces and result shapes.
- Replaced the glossary, ADR, spec, and plan fixtures with authored examples, including duplicate and irregular-heading cases.

## Tests

- `uvx --from pytest pytest -q tests/test_html_policy.py`: 34 passed
- `python3 -m compileall -q scripts/sddlib/html_policy.py`: passed
- `git diff --check`: passed
- `uvx --from pytest pytest -q`: 89 passed, 1 failed

## Files changed

- `scripts/sddlib/html_policy.py`
- `tests/test_html_policy.py`
- `tests/fixtures/glossary/CONTEXT.html`
- `tests/fixtures/adr/0001-use-postgres.html`
- `tests/fixtures/spec/2026-01-01-example-design.md`
- `tests/fixtures/spec/2026-01-01-example-design.html`
- `tests/fixtures/spec/duplicate-headings.md`
- `tests/fixtures/spec/duplicate-headings.html`
- `tests/fixtures/spec/irregular-headings.md`
- `tests/fixtures/spec/irregular-headings.html`
- `tests/fixtures/plan/2026-01-01-example.html`
- `tests/fixtures/docs/sdd/assets/sdd.css`

## Notes

- The full-suite failure is `tests/test_render_docs.py::test_fixture_html_matches_goldens`; it compares the retired mechanical renderer output with the new authored fixtures. Task 8 owns removing or replacing that legacy golden test.
- The validator performs no file writes.
