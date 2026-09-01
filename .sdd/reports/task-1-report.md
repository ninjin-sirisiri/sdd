# Task 1 Report

## What I implemented

- Added target resolution for `CONTEXT.md` and the direct ADR, spec, and plan target directories, including adjacent companion paths.
- Added exact-byte SHA-256 digests and strict digest metadata status parsing.
- Added stateless normal, new-source, and bootstrap edit permission decisions with structured results and input errors.
- Added focused coverage for target matching, path handling, digest bytes, metadata statuses, edit ordering, bootstrap exceptions, stale companions, and no-op edits.

## Tests

- `uvx --from pytest pytest -q tests/test_html_policy.py`: 17 passed
- `uvx --from pytest pytest -q`: 73 passed
- `git diff --check`: passed

## Files changed

- `scripts/sddlib/html_policy.py`
- `tests/test_html_policy.py`
- `.sdd/reports/task-1-report.md`

## Notes

- `scripts/sddlib/md.py` did not need changes for this task; Markdown visible-text extraction belongs to the later validator work.
- No validator, CLI, adapter, CSS, migration, or renderer-removal behavior was added.
