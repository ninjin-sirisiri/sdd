# Task 8 Report

## What I implemented

- Removed the retired mechanical renderer launcher and implementation.
- Removed the renderer-only test that compared generated output with exact HTML goldens.
- Removed the complete tracked vendored Markdown parser package and its license.
- Kept the authored HTML fixtures and their Markdown sources unchanged; they are covered by the structural policy assertions in `tests/test_html_policy.py`.
- Confirmed no executable or operational instruction references remain for the retired implementation.

## Tests run

- Baseline `uvx --from pytest pytest -q`: 136 passed, 1 failed at the obsolete exact-golden test.
- `uvx --from pytest pytest -q`: 124 passed.
- `git diff --check`: passed.
- `python3 scripts/html-docs check --staged`: allowed; no synchronized target documents were staged.
- Explicit all-target `python3 scripts/html-docs check --paths ...`: allowed with no violations or warnings.
- `cmp assets/sdd.css docs/sdd/assets/sdd.css`: passed.
- Runtime/reference scan: no executable or operational instruction references remained; documentation-only historical/design references were preserved.
- Explicit bootstrap in a temporary Markdown-only fixture: allowed, reported all four current digests, and created no HTML files.
- Normal `edit-check` and explicit `check` against the same missing companions: denied with the expected missing-companion results.

## Files changed

- Deleted the legacy renderer launcher, renderer module, renderer-only test, and 40 tracked files in the vendored parser surface.
- Added this report at `.sdd/reports/task-8-report.md`.

## Notes

- No target Markdown or authored HTML companion was modified.
- The broad reference search still finds documentation-only mentions in current design/plan records and expressly preserved historical material; none are runtime consumers or active operational instructions.
