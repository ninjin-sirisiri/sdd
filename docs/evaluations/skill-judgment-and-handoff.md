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

- **Input:** an implementer report containing the executor, command
  (`python3 -m pytest -q`), actual output (`12 passed in 0.31s`), changed files,
  target revision, and scope.
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
| 10. Isolation failure and secrets | Not executed | Requires the worktree and debugging changes in Tasks 3 and 4 | No baseline result. Planned for Tasks 3 and 4, then final Task 6. |
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

## Post-change trial plan for later tasks

| Owner | Checks to run | Notes |
|---|---|---|
| Task 1 | Scenarios 1, 2, 6; S1, S2 | Done in the table above with the Task 1 working tree. If Task 1 is amended, rerun the affected checks. |
| Task 2 | Scenarios 3, 7, 8, 9; rerun 1 and 2 if their text changes | Use the execute, TDD, verification, and finish fixtures. Capture the actual subagent report, commands, outputs, and target changes. Check that a shared-contract change reaches the canonical spec before completion. |
| Task 3 | Scenario 10, isolation part; setup choice with different lockfiles | Use a disposable repository; do not change real repository permissions or shared branches. Record the failed creation, the permission request, the chosen checkout, and any files changed. |
| Task 4 | Scenario 10, secrets part; proportional debugging | Use a fake token name and value; verify the output shows SET or UNSET but never the value. Check that a small defect does not trigger an unnecessary whole-design interview or all-layer defense. |
| Task 5 | Review and investigation behavior | Use its own plan checks; confirm that independent fixes can continue while an unclear item is held, and that investigation delegation does not authorize plan-task parallelism. |
| Task 6 | All 10 scenarios, plus S1 and S2 where relevant | Use the same inputs from fresh sessions, do not pass the criteria or withheld facts, and confirm the changed skill files were read. Record pack revision, host, model, inputs, actual questions and judgments, documents read or updated, verification output, and deviations. Reuse a prior result only when the target skill and required context have not changed. |

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
