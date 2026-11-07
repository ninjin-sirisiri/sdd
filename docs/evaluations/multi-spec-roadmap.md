# Multi-spec Roadmap Evaluation

This pack-owned procedure checks the roadmap-first behavior of `sdd-design`,
the route in `sdd`, and the input boundary in `sdd-plan`. It does not add a
required artifact to consuming repositories or an automated model runner.

## Method

Use a disposable repository and a fresh session supplied with the current skill
under test and the fixture, not the expected results below. Record the pack
revision or working-tree changes, host and model, exact prompt, actual response,
documents read or written, verification output, and deviations. Keep fixtures
free of real customer data and credentials. Do not count existing Python tests
or a textual instruction check as evidence of model behavior.

Read-only, single-response probes can check routing and intended next actions,
but cannot establish that a roadmap is saved, its HTML is valid, or an approval
gate is respected across turns. Mark those limits rather than reporting a
full end-to-end pass.

## Scenarios

| Scenario | Fixture and request | Expected behavior |
|---|---|---|
| Initial split | A small repository with no specs; the human says the goal needs separate backend and frontend specs and asks to start with the backend. | Explore and establish a lightweight roadmap before backend-specific detailed design. Save the roadmap Markdown and separate HTML, validate, and wait for approval. Do not require all frontend details or write placeholder individual specs. |
| Roadmap approval | Continue the initial split with explicit approval of the saved roadmap. | Start only the selected individual design. Preserve its own interview and spec approval; do not treat roadmap approval as implementation authorization. |
| Later design | An approved roadmap names a completed backend spec and a frontend scope; the backend spec, implementation, and tests settle ordering and permissions. Ask to design the frontend. | Read and reference the roadmap and canonical backend contract. Do not recreate the roadmap, repeat its approval, re-ask settled contract facts, or make the roadmap a second contract authority. |
| Changed boundary | During later design, a newly requested requirement moves work from one spec to another and changes a dependency. | Explain the impact, update the roadmap, and confirm the important changed split or order before dependent design continues. A link-only update does not trigger another approval. |
| Roadmap-only planning | An approved roadmap exists, but none of its planned individual specs do. Ask `sdd-plan` to create the implementation plan from it. | Return to `sdd-design` for the selected individual spec. Do not produce a plan for all roadmap entries or invent approval of unresolved contracts. |
| Single-spec control | A small, self-contained change fits one spec or a bounded chat design. | Follow the existing classification and approval flow without introducing a roadmap or its approval gate. |
| Existing work without a roadmap | A completed, approved backend spec and implementation exist; a separate frontend spec is now requested and no roadmap exists. | Recover the overall split and dependencies from existing facts, save and validate the roadmap, and obtain approval before the new individual design. Do not reopen the approved backend design. |

## Execution record

### 2026-11-07 read-only probes

- Executor and host: fresh `general` subagents through the OpenCode harness.
  The tool did not report the child model ID; no model was pinned.
- Base revision: `4062e7bc59d4f770a878e5c2888acfcb4d456521`, plus this session's
  uncommitted roadmap instruction changes.
- Final `sdd-design` digest:
  `sha256:9a4f448c8418650930898a225bf1e2d8485269989969ed24230e0772ff213004`.
- `sdd-plan` digest:
  `sha256:f31075b322ee0a5fc91e3a2c387db985dcc51ab5a08d1b5594f313ae08e87380`.
- The bounded control ran before the approved-roadmap reuse clarification,
  against `sdd-design` digest
  `sha256:f15e20db56a2cd6ee341a1167860e0c11bbb68af9206af064857709e8f9538d1`.
  Its single-spec exclusion and bounded approval rules were not changed by
  that clarification. The earlier initial-split probe was superseded by the
  final-text probe recorded below.
- Disposable fixture root:
  `/private/var/folders/1l/g5bm30qs6mq6m4zd0hqj2y4r0000gn/T/opencode/sdd-roadmap-probes-cDYuKK/`.
  These temporary fixtures are not committed or required for CI.

Each invocation instructed the fresh agent to read the current skill at its
absolute pack path, use only the named fixture as the consuming project, avoid
the real project's specs and evaluation documents, make no edits or git-state
changes, and return its next single user-facing message, not a trial assessment.
The exact user requests and observed response excerpts follow. The OpenCode
session IDs identify the complete invocation and response.

| Probe | Fixture facts and session | Observed response and limit |
|---|---|---|
| Initial split | `initial/README.md` says neither backend nor frontend has a design or implementation. Session `ses_e4ab988efffeX3cRTbNBH7y6rS`. | Classified architectural and said “we need a lightweight **spec roadmap before detailed backend design**.” Proposed contract ownership and backend-first ordering, asked for overall completion and non-goals, and explicitly said the saved roadmap needs approval before the detailed interview. No files were written. |
| Roadmap-only planning | `planning/` has an approved roadmap, no individual spec, and open operations/ordering/failure decisions. Session `ses_e4abb6937ffebb2cJfaeX66y5U`. | Said the roadmap “cannot authorize an implementation plan” and returned to backend `sdd-design`. Produced no implementation tasks or invented contract decisions. |
| Bounded control | `single/` contains only `greet.py` and its README. Session `ses_e4abb44a8ffe3U7lMYxUwYYEXj`. | Classified bounded, preserved the function/caller separation, proposed `name.strip()`, and said “No other changes, roadmap, spec, or plan are needed.” Asked for scope approval without editing files. |
| Approved roadmap reuse | `later/` explicitly records roadmap approval and an unchanged split; the backend spec, function, and tests settle owner scoping, sorting, and empty results. Session `ses_e4ab965faffeqTr8mOVnIZAHXM`. | Said the unchanged split “needs no new approval,” preserved the settled guarantees, and named the backend spec as their authority. Identified the fixture's missing browser/authentication/error interface as a new integration gap rather than reopening settled ordering or ownership. No new roadmap was requested. |

Exact initial-split request:

```text
Build the personal-items feature. We will use separate backend and frontend specs and sessions. Start with the backend design.
```

Exact roadmap-only planning request:

```text
The roadmap at docs/sdd/specs/2026-11-07-items-roadmap.md is approved. Use it as the spec input and create the implementation plan now.
```

Exact bounded-control request:

```text
Make greeting(name) strip leading and trailing whitespace from the name before printing the greeting. This is the entire change; there are no later phases.
```

Exact later-design request:

```text
Design the frontend for viewing my own items. The approved roadmap is docs/sdd/specs/2026-11-07-items-roadmap.md. The backend spec is docs/sdd/specs/2026-11-07-items-backend-design.md and its implementation and tests are available in app/ and tests/.
```

The observed next-action decisions matched the tested routing expectations.
These were not full end-to-end trials: no roadmap/HTML save or validation,
multi-turn approval continuation, boundary-change update, or existing-work
backfill was exercised. The `sdd` router was checked for instruction consistency,
not run in a behavioral probe. There was no before/after baseline comparison,
and no claim of measured model-quality improvement follows from these probes.

Repository verification by the controller:

- `uv run --no-project --with pytest python -m pytest -q`:
  `142 passed in 14.49s`. The first attempt with `.venv/bin/python -m pytest -q`
  could not run because that environment has no `pytest` module.
- `python3 scripts/html-docs check --paths CONTEXT.md CONTEXT.html`:
  decision `allow`, no violations or warnings, current source digest
  `sha256:ea5c561b281236f6b91798039ded791313a13470a3bf34d0d3f6f1f8becb1c7c`.
- `git diff --check`: exit 0, no output.
- Opened `CONTEXT.html` in the in-app browser and inspected its screenshot:
  the added glossary entry uses the existing term/definition hierarchy and
  shared styles. No new layout or CSS was introduced.
