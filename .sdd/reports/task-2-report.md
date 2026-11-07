# Task 2 report: Align testing, verification evidence, and execution handoffs

## Status

DONE. Implementation committed as `1245330` (`feat: align testing,
verification evidence, and execution handoffs`). This report is committed
separately.

## What I implemented

### `skills/test-driven-development/SKILL.md`

- Changed the description and `When to Use` from an always-on rule to a method
  chosen when the behavior and regression risk justify it.
- Made the Iron Law conditional on choosing TDD. Implementation written first
  is kept when correct; add behavior tests and confirm they fail when the
  behavior is broken (temporary revert or mutation) instead of deleting
  working code.
- Removed the per-function test obligation, the fresh-implementation
  requirement, and the "delete code, start over" red-flag ending.
- Kept the red-green-refactor cycle and the requirement to confirm a failing
  test fails for the right reason when TDD is chosen.
- Rewrote rationalizations, red flags, the completion checklist, debugging
  integration, and the final rule to match the selected-method policy.

### `skills/test-driven-development/writing-good-tests.md`

- Removed the claim that strict TDD is the only path that produces honest
  tests.
- Kept behavior-first test selection, mutation checks, real-boundary tests, and
  mock discipline.
- Made "Tests Ship With the Implementation" allow implementation-first work
  with validated behavior tests.

### `skills/verification-before-completion/SKILL.md`

- Defined reusable evidence: executor, exact command, actual result, target
  change, and verification scope.
- Allowed evidence from a subagent, CI, or another executor without re-running
  it solely because the controller did not run it.
- Distinguished bare success claims, stale evidence after the target changed,
  and insufficient evidence. Re-run only the checks the impact requires.
- Kept "never present an unexecuted result as successful" and the safety
  boundary around completion claims.

### `skills/sdd-execute/SKILL.md`

- Required the controller to pass the canonical shared-spec path, dependent
  sections and decisions, and Global Constraints explicitly; another session's
  memory is not a substitute.
- Aligned completeness with the evidence contract: reuse valid implementer
  evidence; re-run only when it is bare, stale, or insufficient.
- Required the report to state later-phase decision status, including whether
  the canonical spec and any dependent document were updated. A changed
  later-phase premise must be inside the task's commit range.
- Added the unagreed user-facing/shared-contract decision to the controller
  stop conditions. Kept serial tasks, one isolated implementer, one resume,
  ledger syntax, HEAD/BASE checks, and review only when the human asks.

### `skills/sdd-execute/implementer-prompt.md`

- Added the shared-specification slot and the judgment policy: proceed on
  reversible decisions inside the agreed constraints; return `BLOCKED` or
  `NEEDS_CONTEXT` for important unagreed user-facing behavior, permissions,
  safety, destructive operations, external side effects beyond authorization,
  or costly or irreversible changes.
- Added the agreed later-phase change rule: update the canonical spec in this
  task's deliverables and commit range before reporting DONE; do not rewrite an
  already recorded range.
- Required verification evidence and later-phase decision/spec status in the
  report.

### `skills/sdd-finish/SKILL.md`

- Required full-suite evidence covering the final state, with the evidence
  fields and explicit reuse when it still covers the final state.
- Added the spec reflection check before the menu: later-phase decisions must
  be in the canonical spec; a dependent document that restates the old contract
  must be aligned or confirmed to delegate. A stale spec is surfaced and
  settled with the human before completion.
- Kept the four-option menu, branch handling, stacked-PR commands, and review
  rules unchanged.

### `docs/evaluations/skill-judgment-and-handoff.md`

- Added Task 2 fixtures F5-F7, supplementary check S3, the Task 2 trial record,
  baseline/post-change artifact references, and the Task 2 plan status.
- Updated the scenario 8 example command to standard-library `unittest`.
- Recorded only non-sensitive summaries; full transcripts and fixture copies
  remain under `.sdd/evaluations/skill-judgment-and-handoff/task-2/` (ignored).

## Verification

```text
$ uvx --from pytest pytest -q tests/test_md.py tests/test_task_brief.py tests/test_stack_prs.py
....................................                                     [100%]
36 passed in 4.78s

$ uvx --from pytest pytest -q
........................................................................ [ 50%]
......................................................................   [100%]
142 passed in 13.56s

$ git diff --check
(no output)

$ git diff -- skills/test-driven-development skills/verification-before-completion skills/sdd-execute skills/sdd-finish
(reviewed; changes are limited to the skills named in the brief)
```

The pytest results cover the pack's document/ledger/stack contracts. They are
not evidence that the model-behavior trials passed; those are reported
separately below.

## Trials

Mechanism: OpenCode CLI `v2.0.18` with `opencode run --standalone --auto`
against disposable fixture repositories. Model:
`commandcode/deepseek/deepseek-v4.1-flash`. Baseline skill content came from
`4437cf7`; post-change content came from the Task 2 working tree, unchanged
after the final trials. Prompts and fixtures did not contain expected answers,
evaluation criteria, withheld facts, or this report.

Artifacts: `.sdd/evaluations/skill-judgment-and-handoff/task-2/` (transcripts,
prompts, fixture copies, actual unittest output). The directory is gitignored.

### Executed post-change sessions

- **3 implementer (F5).** Returned `BLOCKED`, not a fabricated agreement. It
  read the canonical shared contract and the upstream constraint, said "keep
  going" authorizes continued work but does not choose between changing the
  agreed user-facing order and working around the client, and listed the
  options and impacts. It did not edit the spec or invent agreement.
- **3 controller (F5).** Judged Task 2 incomplete. It accepted the report's
  evidence (executor, command, output, target, scope; HEAD equaled the target)
  but failed the later-phase gate because the canonical spec still said
  `created_at` and the report admitted no update. It required one resume to
  update the canonical spec on top of the existing Task 2 commit, confirmed the
  UI spec already delegated, and only then record completion. It did not
  rewrite Task 1's range.
- **7 (F6).** Kept the correct delete implementation. It planned behavior tests
  for owned delete, non-owner rejection, and an unknown id, plus mutation
  checks proving each test fails for the intended reason, then a full-suite
  run. It did not delete working code or require a test per function.
- **8 (F7).** Validated all five evidence fields, confirmed HEAD equaled the
  reported target, and confirmed the tracked tree was unchanged. It reused the
  evidence without re-running and recorded the completion range.
- **9a (F7).** Refused to record completion from "All tests pass" alone. It ran
  the named suite at HEAD, obtained five passing tests, but still required the
  report to carry the evidence fields and canonical-spec status; it proposed one
  resume.
- **9b (F7).** Found that HEAD was a later commit that edited `app/items.py`
  after the report target. It treated the report as stale, re-ran the suite at
  HEAD, and recorded the new range. It did not reuse the stale run.
- **S3 finish (F5).** Did not show the menu. It re-ran the full suite at HEAD,
  found the canonical spec still had the old order and the report admitted no
  update, noted the UI spec delegated, and required human confirmation plus a
  follow-up commit before the menu.

### Baseline comparisons

- Scenario 3 implementer and controller: the pre-change sessions also refused
  to invent the contract change and also withheld completion for the missing
  spec update. The post-change controller used the explicit spec-reflection
  gate and reused valid evidence; the baseline controller re-ran the tests and
  inferred the requirement from the brief. This is a codification and evidence
  improvement, not a new capability.
- Scenario 7: the baseline session chose a non-destructive path too, but only
  after flagging that the pre-change skill told it to delete the implementation
  and re-derive it. The post-change skill had no such conflict.
- Scenario 8: the baseline controller re-ran the same command even though HEAD
  matched the target, citing the pre-change verification skill's "trusting
  agent success reports" red flag. The post-change controller reused the valid
  evidence.
- Scenario 9a: the baseline controller ran the suite and recorded completion
  from its own fresh run; the post-change controller also ran the suite but
  required the report evidence and spec status before recording. Neither
  claimed success from the bare declaration.
- Scenario 9b: both baseline and post-change controllers detected the stale
  target and re-ran the affected suite. The pre-change rule was already safe
  for this case.

### Executed vs not executed

Executed: scenarios 3, 7, 8, 9a, 9b, and supplementary finish check S3.
Not executed in Task 2: scenarios 4, 5, and 10. They remain with Task 6 or the
tasks that own those skills. No result was fabricated.

### Trial limits

- Sessions are one-shot replies; they show the next-message judgment, not a
  full multi-round execution with file edits.
- The baseline scenario 3 implementer wrote its report file despite the prompt
  saying not to edit files; the post-change v3 run did not. The baseline report
  was restored before the controller trial.
- The first baseline attempt for scenarios 8 and 9 used fixtures whose skill
  swap left the tracked tree dirty. Those runs were discarded and rerun with
  clean fixtures; discarded transcripts are retained under the artifact
  directory.
- Scenarios 8 and 9 ran before a final dependent-document clause was added to
  the `sdd-execute` completeness bullet. That clause does not govern evidence
  reuse; the final clause is exercised by the scenario 3 controller and S3
  trials.
- The finish check S3 is a next-message trial, not a full merge/PR run.

## Files changed

- `skills/test-driven-development/SKILL.md`
- `skills/test-driven-development/writing-good-tests.md`
- `skills/verification-before-completion/SKILL.md`
- `skills/sdd-execute/SKILL.md`
- `skills/sdd-execute/implementer-prompt.md`
- `skills/sdd-finish/SKILL.md`
- `docs/evaluations/skill-judgment-and-handoff.md`

No scripts, tests, adapters, hooks, CSS, existing ADRs, or past specs were
changed.

## Concerns

- The spec-reflection check and evidence contract are validated by one-shot
  trials. Task 6 should rerun the affected scenarios after all skill files are
  frozen and should exercise a full execute/finish round.
- The pre-change controller also caught the missing spec update in scenario 3.
  The change makes the requirement explicit and adds the dependent-document
  check; it should not be reported as the first time the model could detect the
  problem.
- Scenario 9b behaved the same before and after. The evidence-reuse improvement
  is demonstrated by scenario 8, not by stale-evidence handling.
- The report path `.sdd/reports/task-2-report.md` previously held a report for
  an unrelated HTML-validator task (`ca18095`). This task overwrote it as the
  brief directs; the prior content remains in git history.
- The evaluation document references gitignored local artifacts; those are
  Task evidence, not pack deliverables.
