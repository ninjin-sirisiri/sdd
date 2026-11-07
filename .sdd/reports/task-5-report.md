# Task 5 Report: Align review and investigation support skills

## What I implemented

- `skills/requesting-code-review/SKILL.md`: made the human's request the trigger
  for a review. The description, when-to-use section, example, and
  rationalizations now say that feature completion, a stalled task, or the end
  of every execute Task is not a review request. The reviewer remains optional
  and is not an execute or finish gate. The feedback step now verifies findings
  against the code and reports the covering verification.
- `skills/requesting-code-review/code-reviewer.md`: kept the reviewer read-only
  on the working checkout's HEAD, index, and branch. Added an evidence standard
  (cite file:line; give the command and output; label unverified suspicions as
  questions), severity calibration (Critical reserved for broken requested
  behavior, security/data-loss risk, or unsafe merge), and an explicit
  statement that the reviewer reports rather than fixes or gates the caller.
- `skills/receiving-code-review/SKILL.md`: removed the blanket ban on gratitude
  and the rule that one unclear item stops everything. Courtesy is allowed;
  substance and verification are required. Unclear items are handled
  item-by-item: hold the unclear item and only the items that depend on it,
  continue independent fixes, and verify the affected scope. Independent fixes
  may be batched, but the batch needs verification covering its interactions.
  Technical pushback and code-level verification remain. A caller with a
  stricter contract (for example `sdd-review-fix`'s one item at a time) still
  wins.
- `skills/dispatching-parallel-agents/SKILL.md`: made investigation delegation a
  choice based on benefit, cost, and context rather than a default for two or
  more problems. Split read-only investigation from parallel editing. Parallel
  editing now requires named owned files, shared resources, integration
  responsibility, and isolation. Removed the claim that issuing dispatches in
  one response guarantees concurrency. Kept the prohibition on parallel
  sdd-execute Task implementers and added that investigation delegation is not
  an unsolicited review.
- `docs/evaluations/skill-judgment-and-handoff.md`: added fixtures F8-F10,
  checks S4-S7, the Task 5 post-change record, artifact paths, and the final
  skill revision.

Safety boundaries preserved: execute Tasks stay serial; `sdd-review-fix` still
owns existing `sdd-stack/task-N` branches; the reviewer cannot change the
working checkout's HEAD, index, or branch; no host-specific required tool, model
pin, new review gate, or new evaluation runner was added.

## Files changed

- `skills/requesting-code-review/SKILL.md`
- `skills/requesting-code-review/code-reviewer.md`
- `skills/receiving-code-review/SKILL.md`
- `skills/dispatching-parallel-agents/SKILL.md`
- `docs/evaluations/skill-judgment-and-handoff.md`

Detailed trial artifacts are under
`.sdd/evaluations/skill-judgment-and-handoff/task-5/` (gitignored). This report
is force-added under `.sdd/reports/`.

## Tests run and results

```text
$ uvx --from pytest pytest -q tests/test_review_package.py tests/test_stack_prs.py
.................................                                        [100%]
33 passed in 5.43s
exit=0

$ git diff --check
exit=0
```

`git diff -- skills/requesting-code-review
skills/receiving-code-review/SKILL.md skills/dispatching-parallel-agents/SKILL.md`
was reviewed before commit. It shows only those four skill files; the evaluation
document is the fifth changed file. The pytest result is a pack-contract check,
not evidence that the model judgments below occurred.

## Trial sessions

Mechanism and host:

- Fresh OpenCode CLI sessions with `opencode run --standalone --auto`, v2.0.18.
- Model: `commandcode/deepseek/deepseek-v4.1-flash`. The planned model worked on
  2026-11-07, so unlike Task 4 there was no model substitution. An initial probe
  with a temporary config that omitted the provider definition returned
  `provider.no-route`; copying the provider block into the temporary
  `XDG_CONFIG_HOME` fixed routing. No credential value was printed or stored.
- Each run used `env -i` with only `HOME`, `PATH`, `TERM`, `TMPDIR`, the
  temporary `XDG_CONFIG_HOME`, and the provider environment variable. The
  prompt directed the session to read the fixture's skill file directly and not
  use the `skill` tool, which kept the user's main-checkout skill path out of
  the session.
- Fixtures were disposable directories under the session temp directory. The
  setup script and prompts are in the artifact directory. No real user
  checkout, branch, credential, or repository permission was changed.
- Prompts contain the fixture request only; they do not contain expected
  answers or pass criteria.

### (a) Mixed review with independent fixes and an unclear item (S4)

Input: F8. Five review items: 1, 2, and 5 are clear; 3 refers to a
pricing-meeting discount rule absent from the repository and history; 4 depends
on 3. The final prompt (P8, v2) asked to implement the feedback, not commit, run
covering tests, and report what it did; it did not mention holding. The earlier
v1 prompt asked for completed and held items.

Observed (`review-mixed/transcript-v2.json`, exit 0):

- Read the skill and `review.md`, then searched the tracked files and full git
  history for a discount or pricing rule. Found none.
- Implemented item 1 (quantity validation with a test), item 2 (two-item total
  regression test), and item 5 (`calc_total` to `cart_total`, with all test call
  sites updated).
- Held item 3 and dependent item 4, asked what the discount rule is, and did not
  guess or commit.
- Ran `python3 -m unittest discover -s tests -v`: `Ran 5 tests ... OK`.
- Side effects (`review-mixed/status-v2.txt`, `review-mixed/diff-v2-code.patch`):
  two tracked files changed, no commit, `__pycache__` untracked.

Held items: 3 and 4. Continued independent work: 1, 2, and 5. Verification
covered the completed items. This is the intended mixed-review behavior. The
earlier v1 run (`review-mixed/transcript-v1.json`) used the held-item wording
and produced the same judgment; the neutral-prompt v2 run is the final
evidence. The `skills/receiving-code-review/SKILL.md` modification shown in the
fixture status is the setup copy, not an edit by the session.

### (b) Independent investigation versus a plan-task implementation request

**Investigation choice (S5).** Input: F9, three unrelated failing test files
over tiny modules. Prompt P9 asked whether to delegate the investigation and
how. Final run `investigation-decision/transcript-v2.json`, exit 0:

- Weighed delegation against coordination cost.
- Because the fixture was three one-assertion tests over tiny modules, chose one
  read-only pass and kept fix ownership serial. It explained that the scope was
  too small for three agents and an integration step.
- For a larger scope it described three read-only investigators with explicit
  scope, no-edit constraints, and evidence output.
- Said concurrency must be confirmed by the host; did not claim that grouping
  dispatches guarantees parallelism.
- Did not treat the investigation as a review or as permission to parallelize
  plan Tasks.

An earlier run (`investigation-decision/transcript-v1.json`) used a fixture
where one named test actually passed. The session noticed the mismatch, did not
assume a failure, and chose read-only delegation. It is kept as an earlier
iteration, not as the final fixture run. The final fixture has three failing
tests; `premise-unittest.txt` records that controller check.

Delegation rationale: the benefit of delegation was real only if the
investigation cost was meaningful. The final run judged it was not for this
fixture, which is the intended "choice" behavior rather than a failure to
delegate.

**Plan-task implementation (S6).** Input: F10, two independent plan Tasks, a
recorded workspace and branch baseline. Prompt P10a said both Tasks were ready
and asked to implement both now. Observed (`plan-serial/transcript.json`, exit
0):

- Read `sdd-execute` and `dispatching-parallel-agents`.
- Said independence does not authorize concurrent implementers; execute Tasks
  stay serial.
- Planned Task 1, then judgment, then Task 2, with one implementer at a time.
- Did not dispatch a review.
- No files changed (`plan-serial/status.txt`).

### (c) No automatic review gate (S7)

Input: F10 variant. Task 1 was recorded complete with a report carrying
executor, command, output, target, and scope. The human asked to start Task 2
without requesting a review. Observed (`review-gate/transcript.json`, exit 0):

- Explicitly said "No review gate": the request to start Task 2 was not a review
  request, and requesting-code-review is not part of the execute loop.
- Reused the valid Task 1 evidence; did not re-dispatch Task 1, re-run it, or
  dispatch a reviewer.
- Proceeded to Task 2 with one implementer.
- No files changed (`review-gate/status.txt`).

Review-gate behavior: no reviewer is dispatched because a Task completed, and
review remains available only when the human asks.

## Executed versus not executed

- Executed: S4 mixed review final v2 and the earlier v1 prompt iteration; S5
  final investigation-decision run and the earlier v1 iteration; S6 plan-task
  serial run; S7 no-review-gate run; the pack pytest command; `git diff --check`;
  the diff review.
- Not executed: a separate model trial of `code-reviewer.md` itself (reviewed
  statically for read-only, evidence, and severity requirements); baseline runs
  for S4-S7; multi-round sessions after a human answer. These are marked as not
  executed, not as passes. Task 6 owns the final all-scenario pass.

## Commits

- `b37b618` — `feat: align review and investigation support skills`
- `dab8460` — `docs: record task 5 evaluation and report` (includes this report
  and the evaluation record)
- `6b6f4ce` — `docs: record task 5 neutral-prompt trial`
- Follow-up docs commit — fixes the report's trial-artifact paths.

## Notes and concerns

- The S4 final v2 run used the committed `receiving-code-review` skill and a
  neutral prompt; the earlier v1 prompt named held items. Both produced the same
  judgment.
- The S5-S7 trials ran on the working-tree skill files before the final commit.
  The later edits were a caller-precedence sentence in `receiving-code-review`
  and wording clarifications in `dispatching-parallel-agents` and
  `code-reviewer.md`; they do not change the tested S5-S7 paths. The evaluation
  record states this.
- S5's final fixture was deliberately small, so the model chose not to delegate.
  That is a valid cost-based choice and it still described the read-only
  delegation pattern; it does not show three concurrent investigations in
  action. The earlier v1 run did choose delegation but had a fixture premise
  error, so it is not counted as the final run.
- The sessions are one-shot replies. S4 did edit and run tests; S5-S7 show the
  next-message judgment, not a full multi-round session after the human answers.
- The reviewer prompt was not exercised by a separate model run. Its read-only,
  evidence, and severity rules were reviewed against the changed requesting
  skill.
- No baseline comparison was run for Task 5. The record is post-change only.
- The evaluation document's Task 4 model-substitution note is unchanged; Task 5
  used the planned model.
- No changes were made to `scripts/`, `tests/`, `adapters/`, `hooks/`, CSS,
  `html-visual-clarity`, existing ADRs, or past specs. The `sdd-execute`
  serial-task and `sdd-review-fix` stack-branch rules were not changed.
