# Task 1 report: Define risk-based design and shared-spec handoffs

## Status

DONE. Committed as `6646301` (`feat: apply risk-based design and shared-spec handoffs`).

## What I implemented

### `skills/sdd-design/SKILL.md`

- Replaced the all-questions, frontier-exhaustion, fixed round format, and
  per-section approval rules with a risk-based interview.
- The interview ends on agreement on goal, acceptance criteria, important
  constraints, and decisions affecting later phases (or explicit impact for
  unresolved items), not on every implementation detail.
- Kept facts-before-questions, classification (spike/bounded/architectural) as
  an initial judgment that can be upgraded, approval before implementation, and
  the existing CONTEXT/ADR/HTML/commit contracts.
- Added `Shared specification and later phases`: record shared contracts in the
  earlier-phase spec, distinguish settled and undecided items with their
  resolution points, keep UI-local decisions local, and do not create a
  separate shared-spec document.
- Added `Starting a later phase`: read the canonical spec and implementation,
  do not re-ask settled facts, confirm only important unresolved items,
  contradictions, or new requirements, and name the canonical spec path and
  dependent scope in the later spec. Existing specs without a shared-contract
  section are recovered from documents/code/tests rather than re-interviewing
  everything. UI-only changes do not require a fictional backend spec.

### `skills/sdd-plan/SKILL.md`

- Removed the "actual commands or file contents for every step" obligation.
- Added `Task content`: deliverables, acceptance criteria, dependencies,
  relevant paths, verification and expected evidence, governing spec path, and
  shared-contract sections. Concrete snippets remain allowed when they prevent
  a known failure; full file contents and fully expanded steps are not required.
- Kept the required header, Global Constraints, `## Task N:` format, and HTML
  authoring/validation contract unchanged.

### `skills/sdd/SKILL.md`

- Added the judgment policy: confirm unagreed user-facing behavior, permissions
  and safety, destructive operations, external side effects beyond existing
  authorization, and costly/irreversible changes; make reversible decisions
  within the agreed constraints; investigate facts first.
- Made the supporting-skill boundary explicit: a supporting skill supplies a
  method and does not override the agreed spec/constraints or add its own TDD
  mandate, review gate, or global stop condition.
- Added the shared-specification entry point and canonical-path rule.
- Changed the bounded route so implementation can happen in-session with TDD
  optional, while keeping the once-per-session workspace question for both TDD
  and non-TDD bounded work.

### `docs/evaluations/skill-judgment-and-handoff.md` (new)

- Defines fixtures F1-F4, prompts P1-P4, and all 10 representative scenarios
  from the approved spec with input, withheld response facts, expected judgment,
  and side effects.
- Adds supplementary checks S1 (plan detail) and S2 (bounded entry).
- Records baseline revision `4437cf7` separately from post-change Task 1 trials,
  with explicit Executed / Not executed status.
- Includes the post-change trial plan for Tasks 2-6 and a record template.
- Contains only summaries and references; full transcripts and fixture copies
  are under `.sdd/evaluations/skill-judgment-and-handoff/` (gitignored).

## Verification

```text
$ uvx --from pytest pytest -q tests/test_md.py tests/test_task_brief.py
.........                                                                [100%]
9 passed in 0.25s

$ git diff --check
(no output)

$ git diff --cached --check
(no output)
```

Staged change set:

```text
A  docs/evaluations/skill-judgment-and-handoff.md
M  skills/sdd-design/SKILL.md
M  skills/sdd-plan/SKILL.md
M  skills/sdd/SKILL.md
```

I also reviewed `git diff --cached -- skills/sdd/SKILL.md skills/sdd-design/SKILL.md skills/sdd-plan/SKILL.md docs/evaluations/skill-judgment-and-handoff.md`.
No scripts, tests, adapters, hooks, CSS, existing ADRs, or past specs were
changed.

## Trials

Mechanism: OpenCode CLI `v2.0.18` with
`opencode run --standalone --auto` against disposable fixture repositories in
the session temp directory. Model: `commandcode/deepseek/deepseek-v4.1-flash`.
Baseline trials used `git show 4437cf7:skills/<skill>/SKILL.md` in the fixture.
Prompts were the same before and after. The trial sessions did not receive the
expected answers, evaluation criteria, withheld response facts, or this report.
Post-change trials used the Task 1 working-tree skills; the skill files were not
edited after the trials, and the committed revision is `6646301`.

Artifacts:

- `.sdd/evaluations/skill-judgment-and-handoff/baseline-4437cf7/` (metadata,
  transcripts, fixture snapshots)
- `.sdd/evaluations/skill-judgment-and-handoff/post-task-1/` (metadata,
  transcripts)

### Executed baseline sessions (revision 4437cf7)

- **A: backend design (scenario 1).** Asked 9 questions: delivery surface vs
  README, list vs detail, non-owner failure semantics, hard vs soft delete,
  delete granularity, list ordering, pagination, service-layer not-found
  signaling, and ownership immutability. It did ask ordering (recommended
  `created_at` descending with `id` tiebreaker) and hard-vs-soft delete, but did
  not ask about cancellation/undo separately; restore/undelete was proposed as
  a non-goal. It asked reversible internal questions and made no file changes.
- **B: frontend handoff (scenario 2).** Read the backend spec, implementation,
  and tests. Explicitly listed settled facts and did not re-ask ordering,
  ownership, irreversibility, or non-disclosing failure. Asked HTTP boundary,
  view scope, delete confirmation, pagination, placement, colors, and timestamp
  format. UI placement/colors became approval questions; no written canonical
  path reference was demonstrated.
- **C: plan detail (S1).** Produced the required header and copied Global
  Constraints, but used full test code, full implementation bodies, and numbered
  steps including "ensure the implementation is exactly this". Acceptance
  criteria and dependencies were not separate fields.
- **D: bounded entry (S2).** Routed the bounded rename to
  `test-driven-development`, said TDD applies, and asked the worktree question
  once.

### Executed post-change sessions (Task 1 working tree)

- **A post (scenario 1).** Asked 5 questions: service vs HTTP scope, list vs
  detail, 404 vs 403 for non-owners, hard-vs-soft delete, and ordering plus
  pagination as one contract question. It named the shared-contract section it
  would write, and no longer asked internal signaling, ownership immutability,
  or UI details. Delete cancellation was still covered only as hard-vs-soft
  delete, not as a separate undo question.
- **B post (scenario 2).** Read the canonical spec, implementation, tests, and
  placeholder. Listed the settled facts it would not ask (order, owner scoping,
  immediate/irrevocable delete, non-disclosing failure, pagination). Referenced
  the canonical spec path and said an HTTP contract change needs agreement to
  amend it. Took placement, colors, and date presentation as local defaults
  without an approval round. Asked only the HTTP boundary, identity source,
  create-flow scope, and delete interaction.
- **C post (S1).** Each task had a deliverable, dependencies, acceptance
  criteria, verification/evidence, and a shared-contract note. It named
  specific spec sections and used short snippets only where they prevented a
  known failure, with no full file contents or expanded step obligation.
- **D post (S2).** Routed the bounded change to in-session implementation,
  stated TDD is optional with a lighter verification approach available, and
  asked the worktree question once.

### Not executed

Scenarios 3, 4, 5, 7, 8, 9, and 10 were not run in Task 1. They depend on
`sdd-execute`, TDD, verification, finish, worktree, or debugging behavior owned
by Tasks 2-4, or require a later interactive/contradiction fixture. They are
recorded as not executed in the evaluation document and scheduled in its
post-change plan (Tasks 2, 3, 4, and final Task 6). No result was invented.

## Files changed

- `skills/sdd/SKILL.md`
- `skills/sdd-design/SKILL.md`
- `skills/sdd-plan/SKILL.md`
- `docs/evaluations/skill-judgment-and-handoff.md` (new)

## Concerns

- The delete-cancellation question was not asked as its own question in either
  backend trial. Both asked hard-vs-soft delete, which is adjacent, and the
  post-change model did not restate "immediate and irrevocable" as a separate
  confirmation. Task 6 should check whether this exact shared-contract fact is
  confirmed before dependent implementation.
- The trials are one-shot first messages, not full multi-round sessions. They
  show question selection and local-decision behavior but not the later rounds,
  contradiction handling, or file/spec updates.
- Post-change trials used the working tree before the commit, not a tagged
  revision. The committed skill files match the trial content; later tasks must
  rerun if these files change.
- The evaluation document references gitignored local artifacts under
  `.sdd/evaluations/`; those are Task evidence, not pack deliverables.
