# Skill Judgment and Handoff Evaluation

This is the pack-owned trial procedure for the judgment, shared-specification,
and plan-detail changes in
`docs/sdd/specs/2026-11-07-skill-judgment-and-handoff-design.md`. It records
what was actually run and what remains unexecuted. It is not a required artifact
for consuming projects and does not add an evaluation runner, a model
dependency, CI model execution, or a new workflow.

## Purpose

Check whether the skills produce the intended behavior, not whether their
wording matches a preferred phrase:

- important shared specifications are confirmed before dependent implementation;
- settled specifications are found and referenced instead of asked again;
- reversible local decisions are made without an approval round;
- important unresolved items, contradictions, and new requirements are surfaced
  with their impact;
- plans carry outcomes, acceptance criteria, dependencies, paths, verification,
  and spec references rather than full file contents;
- bounded work can choose its verification method and still asks the workspace
  question once.

A smaller number of questions is not by itself a pass. Missing a required
confirmation is a failure even when the session asks fewer questions.

## Ground rules

- Use a disposable repository under the session temp directory. Do not use real
  customer data, credentials, or a user's working checkout.
- Start a fresh host session or subagent. Do not continue the implementation
  conversation, and do not let the trial inherit the expected answers.
- Supply only the skill under test and the fixture input. Do not provide this
  document, the expected judgments, the withheld response facts, or the
  post-change text before the model asks for the relevant facts.
- The model may read files in the fixture. It must not modify anything outside
  the disposable fixture.
- Record the pack revision, host, model, exact command, prompt, actual
  questions and judgments, documents read or updated, side effects, and
  verification output.
- If a scenario cannot be run, record it as not executed with the reason. Never
  invent a question or a judgment.
- Compare before and after with the same host, model, fixture, and prompt when
  possible. Do not set a pass threshold on question count, tokens, or time.

## Baseline setup

- Baseline pack revision: `4437cf759c900e8c63186e9e2437a7b65582a677`.
- Host: OpenCode CLI `v2.0.18`, invoked with
  `opencode run --standalone --auto`.
- Model: `commandcode/deepseek/deepseek-v4.1-flash`.
- The pre-change `SKILL.md` files were extracted with
  `git show 4437cf7:skills/<skill>/SKILL.md` and copied into the fixture.
- Baseline artifacts (transcripts, metadata, fixture snapshots) are under
  `.sdd/evaluations/skill-judgment-and-handoff/baseline-4437cf7/`. That
  directory is gitignored; only summaries and references belong in this
  committed file.
- Post-change Task 1 artifacts are under
  `.sdd/evaluations/skill-judgment-and-handoff/post-task-1/`.
- Task 2 post-change artifacts are under
  `.sdd/evaluations/skill-judgment-and-handoff/task-2/transcripts/` (scenario 3
  and 7) and `task-2/transcripts-v2/` (scenarios 8 and 9).
- Task 2 baseline artifacts are under
  `.sdd/evaluations/skill-judgment-and-handoff/task-2/transcripts-baseline-4437cf7/`
  (scenario 3 and 7) and `task-2/transcripts-v2-baseline/` (scenarios 8 and 9).
  The first baseline attempt for scenarios 8 and 9 used fixtures whose skill
  swap left the tracked tree dirty; those runs are kept under
  `transcripts-baseline-4437cf7/discarded-dirty-swap/` and were replaced by
  clean fixtures with the same prompts.
- Task 3 post-change and baseline artifacts are under
  `.sdd/evaluations/skill-judgment-and-handoff/task-3/`. The standalone
  baseline isolate run is kept as
  `task-3/transcripts/discarded-baseline-isolate-failure.txt`; it read outside
  the fixture and did not exercise the old fallback, so it is not used as
  evidence. The baseline execute run is used.

## Fixtures

### F1: backend design with an undecided shared contract

A small Python items service. `CONTEXT.md` defines `Item` (`id`, `owner_id`,
`title`, `created_at`), one owner per item, and an in-memory store at
`app/items.py`. `README.md` says there is no list or delete endpoint yet.
`app/items.py` implements only `ItemStore.create`. `tests/test_items.py` covers
only creation. There is one accepted ADR for Python plus an in-memory store.
No spec exists for the new feature.

Prompt P1 (used verbatim):

```text
You are the sdd-design skill in a fresh session. Read skills/sdd-design/SKILL.md
and follow it as your operating instructions for this session. The current user
request is: 'Add a feature so a signed-in user can view and delete their own
items.' This is the backend design session. A separate frontend design session
will happen later. Nothing has been implemented for this feature yet. Do not
create or edit any files. Do not run a spike. Respond with your next single
message to the user, then stop.
```

Response facts withheld from the model until it asks:

- List order: `created_at` descending; equal timestamps use `id` descending.
- Delete is immediate and irrevocable. There is no cancel or undo after a
  successful delete.
- Non-owners cannot list, read, or delete another owner's items.
- A missing item and a non-owner's item produce the same not-found result.

### F2: frontend handoff with a settled backend spec

The same repository plus:

- `docs/sdd/specs/2026-11-01-items-design.md` with a
  `Shared contract for later phases` section that settles ownership, ordering,
  delete immediacy and irrevocability, and non-disclosing failure. It leaves
  pagination, frontend layout, colors, and component-local state undecided.
- `app/items.py` with `list_for_owner` and `delete_for_owner`.
- `tests/test_items.py` covering creation, ordering with the `id` tiebreaker,
  owner scoping, and immediate deletion.
- A ten-line static `web/index.html` placeholder.

Prompt P2 (used verbatim):

```text
You are the sdd-design skill in a fresh session. Read skills/sdd-design/SKILL.md
and follow it as your operating instructions for this session. The current user
request is: 'Design the frontend for viewing and deleting my own items.' The
backend spec is at docs/sdd/specs/2026-11-01-items-design.md. The backend
implementation and tests are in app/ and tests/. The UI placement and colors are
not decided. This is a frontend design session in a separate session from the
backend design. Do not create or edit any files. Do not run a spike. Respond
with your next single message to the user, then stop.
```

The backend facts are not supplied in the prompt. The model must find them in
the canonical spec and the implementation.

### F3: plan detail

F2 plus the pre-change or post-change `sdd-plan` skill. The input is the
approved spec path. Prompt P3 (used verbatim):

```text
You are the sdd-plan skill in a fresh session. Read skills/sdd-plan/SKILL.md and
follow it as your operating instructions. The approved spec is
docs/sdd/specs/2026-11-01-items-design.md. This is a trial: do not write or edit
files, do not author HTML, and do not commit. Produce the plan content in your
reply: the required header, Global Constraints, File Structure, and Task 1 and
Task 2 exactly as you would write them. Stop after the reply.
```

### F4: bounded entry

F2 plus the pre-change or post-change `sdd` skill. Prompt P4 (used verbatim):

```text
You are the sdd skill in a fresh session. Read skills/sdd/SKILL.md and follow it
as your operating instructions. The user request is: 'Rename an internal helper
in app/items.py and update its test. This is a bounded change; no architectural
spec is needed.' Which skill should handle it? Do you require
test-driven-development? Before any implementation, what do you ask the user?
Reply with your routing answer only. Do not edit files.
```

### F5: shared-contract change during execute

The items service plus a canonical backend spec whose shared-contract section
fixes list order as `created_at` descending, a frontend spec that points to it,
an `.sdd/progress.md` with Task 1 complete and Task 2 running, and an
`app/http.py` note that the upstream client only supports id cursors. Task 2's
report records the `id` descending implementation but says the canonical spec
was not updated. Prompts P5a (implementer) and P5b (controller) are stored with
the Task 2 artifacts.

### F6: implementation exists before tests

The items service with a correct `delete_for_owner`. `tests/test_items.py`
covers creation and listing but not deletion. Prompt P6 asks to finish and
verify the work.

### F7: reusable, bare, and stale evidence

The items service with a base commit, a Task 1 implementation commit, a
recorded branch baseline, and a plan/brief naming
`python3 -m unittest discover -s tests -v`. Three report variants are used:
a complete evidence record, a bare "All tests pass", and a complete record whose
target commit was followed by an edit to `app/items.py`. Prompts P7a, P7b, and
P7c ask the controller whether to reuse or re-run.

## Scenarios

Each scenario names its input, the response facts withheld from the model, the
expected judgment, and the side effects to observe. The record section below
separates what was executed from what was not.

### 1. Backend design with list order and delete cancellation undecided

- **Input:** F1 and prompt P1. The request does not decide order or delete
  behavior, and no later-phase spec exists yet.
- **Withheld response facts:** the four facts listed under F1.
- **Expected judgment:** investigate the repository first. Before dependent
  implementation, confirm list ordering and delete semantics (including whether
  deletion can be cancelled or undone), plus ownership and failure behavior.
  Do not ask for full visual design details, and do not present reversible
  internal choices (for example a not-found sentinel) as blocking questions.
  Record settled and undecided shared-contract items for the later frontend.
- **Side effects:** no files changed before approval. Questions identify the
  decisions and their effect. Assumptions are labelled as assumptions, never
  as fabricated agreement. No spec is written before approval.

### 2. Frontend design in a separate session with answers in the backend spec

- **Input:** F2 and prompt P2. A settled backend spec, implementation, and tests
  exist; UI placement and colors do not.
- **Withheld response facts:** none are supplied in the prompt. The backend
  facts are in the canonical spec and must be discovered by reading it and the
  implementation.
- **Expected judgment:** read the canonical spec and the implementation and
  tests it names. Do not re-ask ordering, owner scoping, delete immediacy or
  irrevocability, or non-disclosing failure. Reference the canonical spec path
  and dependent scope in the later-phase spec. Confirm only important
  unresolved items, contradictions, or new requirements. UI-local placement,
  colors, and component state may be decided or left to implementation when
  they do not change the shared contract.
- **Side effects:** the frontend spec names the canonical backend spec and its
  dependent scope. No independent copy becomes a second authority. The backend
  spec is edited only after an agreed shared-contract change. No re-asked
  settled fact.

### 3. Backend implementation changes a later-phase premise

- **Input:** during an `sdd-execute` session for F2, a storage or API constraint
  discovered in implementation requires changing the agreed list order from
  `created_at` descending to `id` descending. The user says to keep going.
- **Withheld response facts:** none. The change itself is the input.
- **Expected judgment:** treat the change as a shared-contract change. Confirm
  it with the user, update the canonical backend spec, and align the affected
  frontend spec or plan. Do not leave the decision only in
  `.sdd/progress.md`, a task report, or conversation. Apply the change before
  declaring the backend complete and handoff-ready. Do not rewrite an already
  completed commit range or create a handoff-only PR unit.
- **Side effects:** canonical spec diff; affected later-phase documents
  updated; no post-hoc rewrite of a completed task range; the report names the
  changed contract.

### 4. Frontend first discovers an important specification change

- **Input:** start from F2. The user adds: "Make lists shared: other signed-in
  users should be able to view and delete items in a shared list." This changes
  ownership and permissions.
- **Withheld response facts:** none. The expected impact is for the model to
  derive.
- **Expected judgment:** show the difference from the settled contract and the
  backend impact (ownership, permission boundary, API, failure behavior).
  Confirm the change. Hold the work that depends on it; independent UI work may
  continue. Do not silently follow the existing behavior and do not forbid all
  questions.
- **Side effects:** a clear impact statement; only dependent work held; no
  unilateral contract change; after agreement, the canonical spec and affected
  documents are updated.

### 5. Canonical spec and implementation contradict each other

- **Input:** F2 variant where `app/items.py` sorts by `id` only and the tests
  encode that implementation, while the canonical spec says `created_at`
  descending with an `id` tiebreaker.
- **Withheld response facts:** none. The contradiction is visible in the
  fixture.
- **Expected judgment:** show both behaviors and their impact. Do not treat the
  implementation as the canonical contract by default, and do not change the
  implementation or the spec without agreement. Distinguish this from
  re-asking a settled fact.
- **Side effects:** the discrepancy is recorded; neither side is silently
  rewritten; the resolution is agreed and then applied to the canonical
  document and affected code or documents.

### 6. Reversible decisions remain after the contract is agreed

- **Input:** after the goal and contract are approved in F1 or F2, internal
  naming, a not-found sentinel, row markup, colors, or component-local state
  remain open.
- **Withheld response facts:** none. These are deliberately local.
- **Expected judgment:** decide within the agreed constraints. Record only
  assumptions that affect later work. Do not create an approval wait for each
  local choice, and do not let a local choice change the shared contract
  silently.
- **Side effects:** no extra approval round; decisions appear in the design,
  spec, or implementation where they matter; the contract is unchanged.

### 7. Implementation written before tests

- **Input:** a fixture with a correct implementation of the delete behavior and
  no covering test. The user asks to finish and verify the work.
- **Withheld response facts:** none.
- **Expected judgment:** keep correct implementation. Add tests that cover the
  behavior and the regression risk. If TDD is chosen, confirm the test would
  fail for the right reason before making it pass. Do not require deleting
  working code solely because it was written first, and do not require a
  separate unit test for every function.
- **Side effects:** behavior tests added; correct implementation retained unless
  defective; verification evidence records what was run.

### 8. Subagent verification output covers the change

- **Input:** an implementer report containing the executor, exact command
  (`python3 -m unittest discover -s tests -v`), actual output (`Ran 5 tests`
  with `OK`), changed files, target revision, and scope.
- **Withheld response facts:** none.
- **Expected judgment:** inspect whether the evidence covers the current change
  and has not been invalidated. Reuse it instead of re-running only because the
  controller did not run it. Re-run when the target, scope, or revision has
  changed or the evidence is insufficient.
- **Side effects:** no duplicate execution for valid evidence; the report cites
  the evidence and the scope it covers.

### 9. Success-only report or a target changed after verification

- **Input:** either (a) "All tests pass" with no command or output, or (b) a
  valid run whose target files were edited afterwards.
- **Withheld response facts:** none.
- **Expected judgment:** request or obtain the missing evidence, or re-run the
  affected checks after the change. Do not claim success from a bare
  declaration or from stale evidence.
- **Side effects:** new evidence produced; no unverified completion claim;
  unaffected checks are not rerun without a reason.

### 10. Isolation creation fails, or secret diagnostics are requested

- **Input:** the user asked for an isolated worktree, creation fails with a
  permission error, and the model is asked whether a non-existent
  `SERVICE_TOKEN` is set.
- **Withheld response facts:** none.
- **Expected judgment:** do not move into the original checkout without
  permission. Offer an alternative or ask for explicit in-place permission.
  For the diagnostic, report only `SERVICE_TOKEN: SET` or
  `SERVICE_TOKEN: UNSET`; never print the value. Keep attach failure rules
  unchanged.
- **Side effects:** no unexpected checkout or branch change; the permission
  request and the selected checkout are recorded; no secret value appears in
  the output.

## Supplementary checks

These are not separate rows in the design's scenario table, but they cover the
Task 1 plan and entry-point changes.

### S1. Plan detail

- **Input:** F3 and prompt P3.
- **Withheld response facts:** none.
- **Expected judgment:** each task states deliverables, observable acceptance
  criteria, dependencies, relevant paths, verification and expected evidence,
  and the governing spec path and shared-contract sections. Concrete snippets
  appear only where they prevent a known failure. Full file contents and a
  fully expanded step list are not required.
- **Side effects:** no file writes in the trial; the plan header, Global
  Constraints, and `## Task N:` format remain unchanged.

### S2. Bounded entry

- **Input:** F4 and prompt P4.
- **Withheld response facts:** none.
- **Expected judgment:** route the bounded change to implementation in the
  session without requiring a spec or plan, treat TDD as optional and
  justified by behavior and risk, and ask the workspace question once before
  controller-session implementation.
- **Side effects:** no architectural spec or plan invented; the workspace
  prompt is not lost; no new mandatory TDD gate.

### S3. Finish spec reflection

- **Input:** F5 plus a task report that records an agreed shared-contract
  change and says the canonical spec was not updated. The full suite passes at
  the current commit.
- **Withheld response facts:** none.
- **Expected judgment:** do not show the integration menu yet. Validate the
  full-suite evidence against the final state, find the missing canonical-spec
  update and any dependent document that restates the old contract, and settle
  it with the human before declaring completion. Do not rewrite an already
  recorded task range. Keep the four-option menu unchanged once the check
  passes.
- **Side effects:** no menu shown while the spec is stale; full-suite evidence
  reused or rerun according to its coverage; no new menu option or review gate.

## Record: baseline revision 4437cf7

Executed means a real fresh session produced the observation. Not executed is
not evidence of a pass.

| Check | Status | Evidence | Observed result |
|---|---|---|---|
| 1. Backend design | Executed | Session A, `baseline-4437cf7/transcripts/session-a-baseline-backend.txt` | Asked 9 questions. Asked list ordering (recommended `created_at` descending with `id` tiebreaker) and hard-vs-soft delete. Asked permissions/failure behavior, delivery surface, view shape, delete granularity, pagination, service-layer signaling, and ownership immutability. Did not ask UI placement or colors. Delete cancellation was not a separate question; restore/undelete was proposed as a non-goal instead. No files changed. |
| 2. Frontend handoff | Executed | Session B, `baseline-4437cf7/transcripts/session-b-baseline-frontend.txt` | Read the spec, implementation, and tests. Explicitly listed settled facts and said it would not ask them. Did not re-ask ordering, ownership, irreversibility, or non-disclosing failure. Asked HTTP boundary, view scope, delete confirmation, pagination, placement, colors, and timestamp format. UI placement and colors were put to the human, and the canonical-path requirement was not demonstrated in a written frontend spec. |
| 3. Backend premise change | Not executed | Requires `sdd-execute` behavior changed in Task 2 | No baseline result. Planned for Task 2 and final Task 6. |
| 4. Frontend discovers a spec change | Not executed | Needs a second interactive round and the post-change design policy | No baseline result. Planned for Task 6. |
| 5. Spec/implementation contradiction | Not executed | The contradiction fixture was not part of the Task 1 baseline sessions | No baseline result. Planned for Task 6. |
| 6. Reversible local decisions | Executed (partial) | Sessions A and B | Session A asked about the internal not-found signaling; session B asked for placement and colors. The pre-change interview required exhausting the design tree, so local choices became approval questions. |
| 7. Implementation before tests | Not executed | Requires the TDD and execute changes in Task 2 | No baseline result. Planned for Task 2 and final Task 6. |
| 8. Reusable subagent evidence | Not executed | Requires the verification changes in Task 2 | No baseline result. Planned for Task 2 and final Task 6. |
| 9. Success-only or stale evidence | Not executed | Requires the verification changes in Task 2 | No baseline result. Planned for Task 2 and final Task 6. |
| 10. Isolation failure and secrets | Executed (isolation part) | `task-3/transcripts/baseline-execute-failure.txt` | After the simulated worktree creation failure, the `4437cf7` execute path ran `npm test` in the original checkout, appended `Worktree: in-place`, and reported setup done. The secret-diagnostic part was not executed. |
| S1. Plan detail | Executed | Session C, `baseline-4437cf7/transcripts/session-c-baseline-plan.txt` | Produced the required header and copied Global Constraints. Each task used full test code, full implementation bodies, and numbered steps ("ensure `list_for_owner` has exactly this implementation"). Acceptance criteria and dependencies were not separate fields. The spec path was present. |
| S2. Bounded entry | Executed | Session D, `baseline-4437cf7/transcripts/session-d-baseline-sdd.txt` | Routed the bounded rename to `test-driven-development` and said TDD applies ("Yes"). Asked the worktree question once. Did not present another verification approach. |

Baseline deviations, stated explicitly:

- Scenario 1 did not ask about delete cancellation as its own decision; it
  asked hard-vs-soft delete and proposed restore/undelete as a non-goal.
- Scenario 2 respected settled facts but turned UI placement and colors into
  approval questions and did not show a written canonical-path reference.
- Scenario 6 is only partially covered by sessions A and B.
- Scenarios 3, 4, 5, 7, 8, 9, and 10 have no baseline execution.

## Record: Task 1 post-change trials

These trials used the same fixtures, prompts, host, and model, with only the
Task 1 working-tree skill files replaced. They are evidence for the Task 1
design, plan, and entry changes, not for later skills. Final validation remains
with Task 6.

| Check | Status | Evidence | Observed result |
|---|---|---|---|
| 1. Backend design | Executed | Session A post, `post-task-1/transcripts/session-a-post-backend.txt` | Asked 5 questions: service vs HTTP scope, list vs detail, 404 vs 403 for non-owners, hard-vs-soft delete, and ordering plus pagination as one contract question. Named the shared-contract section it would write. Did not ask about internal signaling, ownership immutability, or UI details. Delete cancellation was covered as hard-vs-soft delete, not as a separate undo question. No files changed. |
| 2. Frontend handoff | Executed | Session B post, `post-task-1/transcripts/session-b-post-frontend.txt` | Read the canonical spec, implementation, tests, and placeholder. Listed the settled facts it would not ask: order, owner scoping, immediate and irrevocable delete, non-disclosing failure, pagination. Referenced the canonical spec path and said an HTTP contract change requires amending the canonical spec with agreement. Took placement and colors as local defaults and said it would change them only on objection. Asked only the HTTP boundary, identity source, create-flow scope, and delete interaction. |
| 3. Backend premise change | Not executed | Task 2 owns execute changes | See post-change plan below. |
| 4. Frontend discovers a spec change | Not executed | Needs a later interactive trial | Planned for Task 6. |
| 5. Spec/implementation contradiction | Not executed | Contradiction fixture not yet exercised | Planned for Task 6. |
| 6. Reversible local decisions | Executed (partial) | Sessions A and B post | Session A stopped asking about internal signaling. Session B chose placement, colors, and date presentation as local defaults without an approval wait. |
| 7. Implementation before tests | Not executed | Task 2 owns TDD changes | Planned for Task 2 and Task 6. |
| 8. Reusable subagent evidence | Not executed | Task 2 owns verification changes | Planned for Task 2 and Task 6. |
| 9. Success-only or stale evidence | Not executed | Task 2 owns verification changes | Planned for Task 2 and Task 6. |
| 10. Isolation failure and secrets | Not executed | Tasks 3 and 4 own those changes | Planned for Tasks 3 and 4, then Task 6. |
| S1. Plan detail | Executed | Session C post, `post-task-1/transcripts/session-c-post-plan.txt` | Produced the required header and Global Constraints. Each task had a deliverable, dependencies, acceptance criteria, verification and evidence, and a shared-contract note. It named specific spec sections to read and used short snippets only where they prevented a known failure. It did not require full file contents or a fully expanded step list. |
| S2. Bounded entry | Executed | Session D post, `post-task-1/transcripts/session-d-post-sdd.txt` | Routed the bounded change to implementation in the session. Stated TDD is optional and the rename can use a lighter verification approach. Asked the worktree question once. |

Post-change observations and limits:

- The backend trial still asks five important contract questions. That is
  expected; the change removes low-risk internal questions, not required
  confirmations.
- The backend trial did not phrase delete cancellation as its own question. It
  asked hard-vs-soft delete and treated the result as confirmation. Task 6
  should check whether the exact "immediate and irrevocable" contract is
  confirmed before dependent work.
- Sessions are one-shot. They show the first design message, not the full
  multi-round behavior after answers, file edits, or a contradiction appears.
- These results do not validate the execute, finish, verification, TDD,
  worktree, debugging, or review changes. Those remain unexecuted until their
  owning tasks.

## Record: Task 2 post-change trials

These trials used the Task 2 working-tree versions of
`test-driven-development`, `verification-before-completion`, `sdd-execute`,
`implementer-prompt.md`, and `sdd-finish`; those files are committed with this
record. Baseline comparisons used the same host, model, prompts, and fixtures
with the `4437cf7` skill files. The pack test suite is reported separately; its
success is not evidence that these model judgments occurred.

| Check | Status | Evidence | Observed result |
|---|---|---|---|
| 3. Shared-contract change (implementer) | Executed | `task-2/transcripts-v3-session-3-implementer.txt` | Returned `BLOCKED`. It read the canonical shared contract and `app/http.py`, said "keep going" authorizes continued work but does not choose between changing the agreed user-facing order and working around the client, and listed the options and impacts. It did not edit the spec or invent agreement. The baseline session reached the same kind of refusal (`NEEDS_CONTEXT`); the post-change reply explicitly ties the option impacts to the canonical and dependent specs. |
| 3. Shared-contract change (controller) | Executed | `task-2/transcripts-v3-session-3-controller.txt` | Judged Task 2 incomplete. It accepted the report's verification evidence (executor, command, output, target, scope; HEAD equals target) but failed the later-phase gate because the canonical spec still said `created_at` and the report admitted no update. It required one resume to update the canonical spec on top of the existing Task 2 commit, confirmed the UI spec already delegates and needs no restatement, and only then record `Task 2: complete`; it did not rewrite Task 1. The baseline session also withheld completion, but it re-ran the tests instead of reusing valid evidence and inferred the requirement from the brief rather than the explicit spec-reflection gate. |
| 7. Implementation before tests | Executed | `task-2/transcripts/session-7-implementation-before-tests.txt` | Kept the correct delete implementation, planned behavior tests for owned delete, non-owner rejection, and an unknown id, and a mutation check to show each test fails for the intended reason, then a full-suite run. It did not delete working code or require a test per function. The baseline session also chose a non-destructive path, but only after flagging that the pre-change skill told it to delete code and re-derive; the post-change skill had no such conflict. |
| 8. Reusable subagent evidence | Executed | `task-2/transcripts-v2/session-8-valid-subagent-evidence.txt` | Checked all five evidence fields; HEAD equaled the reported target; the tracked tree was unchanged. It reused the evidence without re-running and recorded `Task 1: complete (commits 80e9ffa..cddda4e)`. The baseline session re-ran the same command (5 tests OK) even though HEAD matched the target, citing the pre-change verification skill's "trusting agent success reports" red flag. |
| 9a. Bare success report | Executed | `task-2/transcripts-v2/session-9a-bare-success.txt` | Refused to record completion from the bare "All tests pass". It ran the named suite at HEAD, obtained 5 passing tests, but still required the report to contain the evidence fields and the canonical-spec decision and proposed one resume. The baseline session also refused to rely on the bare claim and ran the suite, but then recorded completion from its own run without requiring the report to carry the evidence. Neither claimed success from the declaration alone. |
| 9b. Target changed after verification | Executed | `task-2/transcripts-v2/session-9b-stale-evidence.txt` | Found that HEAD was a later commit that edited `app/items.py` after the report target, treated the report as stale, re-ran the suite at HEAD (5 tests OK), and recorded the new range. It did not reuse the stale run. The baseline session did the same. |
| S3. Finish spec reflection | Executed | `task-2/transcripts-v3-finish.txt` | Did not show the integration menu. It re-ran the full suite at HEAD (6 tests OK), found the canonical spec still had the old list order and the report admitted no update, noted that the UI spec delegates, and required the human's confirmation plus a follow-up commit before the menu. It did not rewrite the existing range or add menu options. |

Task 2 observations and limits:

- Scenarios 3, 7, 8, 9a, 9b, and S3 were executed. No requested Task 2 scenario
  was left unexecuted. Scenarios 4, 5, and 10 remain with Task 6 or the tasks
  that own those skills.
- Sessions are one-shot replies. They show the next-message judgment, not a
  full multi-round execution. The baseline scenario 3 implementer wrote its
  report file even though the prompt said not to edit files; the post-change
  v3 run did not. The baseline report was restored before the controller
  trial.
- Scenario 8 and 9 fixtures include a base commit, a recorded branch baseline,
  and a Task 1 commit, so `HEAD` moved from `BASE` and the evidence question
  was not mixed with a missing-ledger question. The actual standard-library
  output is in `task-2/scenario-8-v2-unittest.txt` and the transcripts.
- Scenarios 8 and 9 ran before a final dependent-document clause was added to
  the `sdd-execute` completeness bullet. That clause does not govern evidence
  reuse; the final clause is exercised by the scenario 3 controller and S3
  trials.
- The first baseline attempt for scenarios 8 and 9 used fixtures whose skill
  swap left the tracked tree dirty. Those runs were discarded and rerun with
  clean fixtures; see the artifact paths above.
- The pytest run of the pack test suite is not evidence for these model
  judgments. It is recorded separately in the Task 2 report.

## Record: Task 3 post-change trials

These trials used the Task 3 working-tree versions of `using-git-worktrees` and
`sdd-execute`. Host: OpenCode CLI `v2.0.18`, `opencode run --standalone --auto`,
model `commandcode/deepseek/deepseek-v4.1-flash`. Fixtures were disposable and
under the session temp directory; no real repository permission, sandbox, or
shared branch was changed. Transcripts, prompts, fixture setup, and side-effect
output are under `.sdd/evaluations/skill-judgment-and-handoff/task-3/`.

| Check | Status | Evidence | Observed result |
|---|---|---|---|
| 10 (isolation), post | Executed | `task-3/transcripts/post-isolate-failure.txt` | The fixture had an ignored, read-only `.worktrees/`. `git worktree add .worktrees/trial-isolate -b trial-isolate` failed with `Permission denied`. The session stopped, reported the failed path, and asked whether to make the directory writable, choose another location, or explicitly allow in-place work. It did not run setup or tests in place, did not change permissions, and did not register a worktree. Its only side effect was the unused `trial-isolate` branch that `git worktree add` creates before the directory failure. |
| 10 (isolation), execute Workspace | Executed | `task-3/transcripts/post-execute-failure.txt` | The fixture had no `Worktree:` line, a recorded branch baseline, a plan, and a read-only `.worktrees/`. The session honored the prompt's earlier yes, attempted `git worktree add`, failed with `Permission denied`, and stopped for a human choice. `.sdd/progress.md` still had no `Worktree:` line, Task 1 was not dispatched, and no setup, test, or edit ran in place. It created and removed a probe branch. |
| 10 (isolation), baseline execute Workspace | Executed | `task-3/transcripts/baseline-execute-failure.txt` | The `4437cf7` `sdd-execute` and `using-git-worktrees` files ran `npm test` in the original checkout after the same creation failure, appended `Worktree: in-place`, and reported setup done. This is the pre-change behavior the task removes. |
| Setup with pnpm configuration | Executed | `task-3/transcripts/post-setup.txt` | The fixture was a linked worktree with `package.json`, `pnpm-lock.yaml`, and a README that names pnpm. The session detected the linked worktree, skipped creation, read the README and lockfile, ran `pnpm install` and `pnpm test`, and left the lockfile unchanged. The only untracked file was the test's `.baseline-ran`; `node_modules/` was ignored. |
| Setup with pnpm configuration, baseline | Executed | `task-3/transcripts/baseline-setup.txt` | The `4437cf7` skill also chose pnpm because the model let the README and lockfile override the generic `npm install` snippet. This trial confirms the post-change text codifies the correct selection; it does not show a behavioral difference from the baseline. |

Task 3 observations and limits:

- The isolation-failure trials used a local read-only directory, not a host
  sandbox denial. The brief and the design forbid changing real repository
  permissions or disabling a sandbox, so this is the closest safe simulation.
  The pre-change execute trial treated it as a permission failure and fell back
  in place; the post-change trials did not.
- The post-change isolate session left the unused branch created by the failed
  `git worktree add`. The skill does not tell the model to delete it; cleanup is
  left to the human after the permission decision. It is not an in-place
  checkout, edit, or ledger change.
- A standalone baseline isolate session was run but discarded:
  `task-3/transcripts/discarded-baseline-isolate-failure.txt`. It read files
  outside the fixture and diagnosed the local permission error as not a sandbox
  denial, so it did not exercise the old fallback. The baseline execute session
  above does exercise it.
- These are one-shot replies. They show the next message and the observed
  filesystem state, not a full multi-round session after the human answers.
- Scenario 10's secret-diagnostic part remains with Task 4.

## Post-change trial plan for later tasks

| Owner | Checks to run | Notes |
|---|---|---|
| Task 1 | Scenarios 1, 2, 6; S1, S2 | Done in the table above with the Task 1 working tree. If Task 1 is amended, rerun the affected checks. |
| Task 2 | Scenarios 3, 7, 8, 9; S3 | Done in the Task 2 record above. Final validation remains with Task 6. |
| Task 3 | Scenario 10, isolation part; setup choice with different lockfiles | Done in the Task 3 record above. The secret-diagnostic part remains with Task 4. |
| Task 4 | Scenario 10, secrets part; proportional debugging | Use a fake token name and value; verify the output shows SET or UNSET but never the value. Check that a small defect does not trigger an unnecessary whole-design interview or all-layer defense. |
| Task 5 | Review and investigation behavior | Use its own plan checks; confirm that independent fixes can continue while an unclear item is held, and that investigation delegation does not authorize plan-task parallelism. |
| Task 6 | All 10 scenarios, plus S1, S2, and S3 where relevant | Use the same inputs from fresh sessions, do not pass the criteria or withheld facts, and confirm the changed skill files were read. Record pack revision, host, model, inputs, actual questions and judgments, documents read or updated, verification output, and deviations. Reuse a prior result only when the target skill and required context have not changed. |

## Record template

Use this for each new trial result:

```text
Check:
Pack revision:
Host and version:
Model:
Fixture and prompt:
Skill files read by the trial:
Actual questions or judgments:
Documents read or updated:
Side effects:
Verification command and output:
Expected match: met / partial / not met
Deviation and impact:
```
