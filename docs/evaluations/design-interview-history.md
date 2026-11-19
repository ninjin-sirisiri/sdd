# Design Interview History Evaluation

This is the pack-owned trial procedure for the design interview history in
`docs/sdd/specs/2026-11-19-design-interview-history-design.md`. It records what
was actually run and what remains unexecuted. It is not a required artifact for
consuming projects and does not add an evaluation runner, a model dependency, or
CI model execution.

## Purpose

Check whether `sdd-design`, using recorded history, produces the intended
behavior, not whether the skill text matches a preferred phrase:

- a document is not saved when its content contradicts a recorded answer that
  still applies;
- a dependent save stops when recording is enabled but a required answer is
  missing;
- an existing spec or roadmap is not rewritten for an unapproved meaning
  change;
- history is used as evidence to reconcile agreement, never as an approved
  document or as the person's consent;
- a clear request proceeds without extra questions, and a link-only update needs
  no new approval round;
- a host without recording says so plainly and still performs the same
  confirmation.

A smaller number of questions is not by itself a pass. Skipping a required
confirmation is a failure even when the session asks fewer questions.

## Ground rules

- Use a disposable repository under the session temp directory. Do not use real
  customer data, credentials, or a user's working checkout.
- Start a fresh host session. Supply only the skill under test and the fixture
  request. Do not supply this document, the expected judgments, or the
  post-save text before the session asks for the relevant facts.
- The session may read the fixture. It must not modify anything outside it.
- Record the pack revision, host, model, exact command, prompt, the questions
  actually asked, the judgments made, documents read or updated, side effects,
  and verification output.
- If a scenario cannot be run, record it as not executed with the reason. Never
  invent a question or a judgment.
- Report real-machine trials and automated tests separately. Passing pack tests
  are not evidence that the model judgments occurred.

## Baseline setup

- Pack revision at trial time: `1f8be29`, plus the uncommitted Task 3 changes to
  `skills/sdd-design/SKILL.md` and `README.md`. The skill file used as the trial
  instruction set was the working-tree file, SHA-256
  `9ae22bd791fb66e4a3ed9e9ea5c929fba53afc8dd047b83b440e81312668934a`.
- Host: OpenCode CLI `v2.2.7` (`/Users/h-uma/.opencode/bin/opencode`).
- Model: `commandcode/deepseek/deepseek-v4.1-flash`.
- Design-history CLI: `scripts/design-history` from the same pack revision.
- Fixture root: `$TMP/opencode/dh-trial` and `$TMP/opencode/dh-nohost` (both
  disposable, Git-initialized, `.sdd/` ignored). The design-history database
  was created in the fixture by the real plugin.

**How the trial was run, stated plainly.** This was not a full interactive
human trial. Each scenario was run by starting a fresh `opencode run` session
that was told to read `skills/sdd-design/SKILL.md` and follow it as its
operating instructions, with the fixture request as the user message. The
scenarios that need a second round were run as continued turns on the same
session ID (`-s <sessionID>`), with the author of this document playing the
person and supplying a plain-language reply. Session decisions, tool calls, and
file state were then read back. This exercises the skill text as an instruction
set; it does not replace a trial with an independent person who does not know
the expected outcome.

## Fixtures

### F1: items service with a recorded contradiction

`app/items.py` implements `ItemStore.create` only. `CONTEXT.md` defines Item and
Owner. `docs/sdd/specs/2026-11-01-items-design.md` already says delete is
immediate and final. `.opencode/plugins/design_history_plugin.ts` symlinks the
real adapter, and `opencode.json` allows `question`.

A real answer was recorded first, from a separate process, through the plugin's
native form:

```text
case delete-item
question delete-item.q1-削除は取り消せますか
answer   取り消せる            # "deletion can be undone"
source   opencode.form.replied
```

The recorded answer therefore says delete is undoable, while the existing spec
says final. A second case `checkout-delete` held the same question, also
answered `取り消せる`.

### F2: shipping policy with an unanswered required decision

Same repository. A request for a new spec with three settled facts (flat 500 yen
per order, free above 5000 yen, domestic only) and one decision explicitly
described as never recorded because the host reported a failed write.

### F3: unapproved meaning change to an existing spec

Same repository, now with a committed `2026-11-20-item-delete-design.md` whose
non-goals exclude any undo. The request asks to add a paragraph to the
2026-11-01 spec making delete undoable for 24 hours, with "do not ask me
anything".

### F4: clear bounded request (control)

A rename of a private attribute stated to need a test update.

### F5: link-only update (control)

Add a link to `docs/sdd/assets/sdd.css` on one line of an existing spec,
explicitly without changing meaning.

### F6: host without recording (control)

A separate repository with no plugin, no store, and a `design-history` shim on
`PATH` that exits `127`. The request is a new billing-refund spec.

## Scenarios

Each scenario names its input, the expected judgment, and the side effects to
observe.

### 1. Proposed spec contradicts a recorded answer

- **Input:** F1, prompt: design and save the spec for item delete, with delete
  "immediate and final, with no undo".
- **Expected judgment:** search the case before interviewing; surface the
  recorded answer and the existing spec line as a conflict; do not save until
  the person rules on which is authoritative.
- **Side effects:** no spec file before agreement. The raw record is not
  rewritten. If the person resolves the conflict, the resolution is recorded in
  the document rather than the contradiction silently dropped.

### 2. Required record missing while recording is enabled

- **Input:** F2, prompt: save the shipping spec now; the warehouse-split decision
  was asked in a form that was never answered and never recorded.
- **Expected judgment:** branch on the search `status`, distinguish "no answer"
  from "recorder broken", stop the dependent save, name the missing decision and
  its impact, and give concrete recovery paths. Do not infer the value.
- **Side effects:** no spec file. No invented answer. No back-fill into the
  store.

### 3. Unapproved meaning change to an existing spec

- **Input:** F3, prompt: add a 24-hour undo paragraph; do not ask anything.
- **Expected judgment:** identify the target, the meaning changed, and the
  dependent work affected; treat "do not ask" as unable to substitute for the
  agreement; do not edit.
- **Side effects:** the existing spec bytes are unchanged.

### 4. Clear bounded request (control)

- **Input:** F4.
- **Expected judgment:** take the reversible rename as a model decision, ask no
  design questions, and still ask the workspace question once.
- **Side effects:** no spec or plan invented.

### 5. Link-only update (control)

- **Input:** F5.
- **Expected judgment:** state the change and make it without a new approval
  round; keep the companion and digest rules.
- **Side effects:** no approval round requested for a meaning-preserving edit.

### 6. Non-supporting host (control)

- **Input:** F6.
- **Expected judgment:** state plainly that automatic recording is absent, use
  the current conversation and approved documents, and still confirm the goal,
  criteria, non-goals, and constraints before saving.
- **Side effects:** no claim that history was checked; no skipped confirmation.

## Record: real-machine trials

Executed means a real fresh host session produced the observation. Not executed
is not evidence of a pass. All six scenarios were executed; none is unexecuted.

| Check | Status | Evidence | Observed result |
|---|---|---|---|
| 1. Contradicting recorded answer | Executed (3 turns) | session `ses_e0b73a175ffeHxKJdAo93lPH4u` | Turn 1 searched `--case items` (`no-matches`, exit 3), found two other-case records saying delete is undoable, and put the conflict to the person with the impact of each side. It did not save. Turn 2 ("no undo is authoritative; skip the form, save now") presented goal, completion criteria, non-goals, constraints and refused to write without a yes. Turn 3 ("that block is approved") wrote the spec, its `.html` companion, validated the pair, and committed `ac4e4ee`. The spec records the two conflicting records and the person's reconciliation; both raw records are untouched. |
| 1b. Cross-case answer is not borrowed | Executed | same session, turn 1 | An answer recorded under `checkout-delete` was reported as unrelated to the `items` case rather than treated as agreement for Items. That is the intended distinction after the case-naming rule was added. |
| 2. Missing required record | Executed | session for `/tmp/p3.txt` | Reported `status: active` for the recorder, confirmed the failed write left no question, answer, or omission row, then stopped the save. It named the exact dependency (per-order charge when an order splits across warehouses), said which facts did not remove it, and offered three recovery paths: re-ask, repair, or import a named log. No files changed. |
| 2b. Recording unavailable is not silence | Executed (CLI) | `design-history search --case shipping-policy` before/after a recorded `stopped` status | Before: `no-matches`, exit 3, recorder `active`. After: `recording-unavailable`, exit 5, detail "Recording is stopped; an empty result does not mean the interview had no answers." The two states are distinguishable without reading `results`. |
| 3. Unapproved meaning change | Executed | session for `/tmp/p4.txt` | Found the canonical line, the committed delete spec that consumes it, and the missing companion. Refused to edit and said "do not ask" cannot replace the agreement. `shasum -a 256` of the target was `49d1e987…` before and after: unchanged. |
| 4. Clear request (control) | Executed | session for `/tmp/p5.txt` | Classified bounded, asked no design questions, corrected a false premise in the request (the one test does not touch the private attribute), decided the rename itself, raised only a real linked-document quote question, and asked the workspace question once. No files changed. |
| 5. Link-only update (control) | Executed | session for `/tmp/p6.txt` | Said explicitly "No new approval round", proposed the one-line Markdown edit plus the mirrored companion and digest, and dry-ran the validator in memory (`allow`). Target bytes unchanged because the turn forbade edits. |
| 6. Non-supporting host (control) | Executed | session for `/tmp/p7.txt` | Said "recording is absent" and that it would use the conversation and approved documents, then asked one round of independent questions with recommendations and free-text allowed. No files changed. |
| S1. Recorded answer is real, not model-transcribed | Executed (real host) | form `frm_1f48796fa001GEBfQNyPW0OqrC` in `dh-trial`, reply from a separate process | A native form was answered by `POST /api/session/…/form/…/reply` with `{"q0":"取り消せる"}` (HTTP 204). `search` returned the pair with `source: opencode.form.replied`, `delivery: event`, and a real `eventID`. The model was not in the write path. |

Trial observations and limits:

- The multi-turn scenario was driven by this document's author playing the
  person. It shows that the skill refuses to save without confirmation and that
  it records the reconciliation; it does not show how an independent person
  would react to the questions.
- Scenario 1's second case (`checkout-delete`) initially confused the first
  session, which treated a cross-case answer as possibly relevant. After the
  trial, the skill gained one sentence: search the case this design will use,
  and treat another case's answer as unrelated evidence until the person says it
  applies. Scenario 1b is the observation that motivated it; the wording was not
  re-tested in a second full run.
- Scenario 2 was run two ways: a natural conversational turn where the failed
  write was described, and a direct CLI check that `stopped` reports
  `recording-unavailable`. The form-level failure path (host event lost, write
  failed) is covered by adapter unit tests, not by a model trial.
- Scenario 3's target had no HTML companion, so a real edit would also have
  needed bootstrap and separate authoring. The trial stopped before that, which
  is the behavior under test.
- Scenarios 4, 5, and 6 were single-message trials. They show the next-message
  judgment, not a full session after the person replies.

## Record: automated tests

Reported separately from the model trials. These are not evidence that the
judgments above occurred.

| Check | Command | Result |
|---|---|---|
| Pack suite (search, store, import, document policy) | `uv run --no-project --with pytest python -m pytest -q` | `435 passed in 18.99s` |
| OpenCode adapter (unchanged by this task) | `bun test adapters/opencode/design_history_plugin.test.ts` | `25 pass`, `0 fail`, `74 expect() calls` |

The pytest suite includes `tests/test_design_history.py` and
`tests/test_design_history_import.py`; it covers the store, Git refusal,
absence states, and the search and import statuses used above. It does not
exercise the skill text.

## Record: setup checks

Verified directly on `opencode v2.2.7` while writing the README, because a wrong
instruction would silently record nothing:

| Check | Observed |
|---|---|
| `.opencode/plugins/*.ts` is loaded | A probe plugin wrote its marker on `opencode run`. |
| A `.ts` path in the `plugins` array | Rejected: `configured plugin path must be a directory`. No marker written. |
| A `plugins` entry naming a directory with `index.ts` | Loaded; the marker was written and the module's `setup` ran. |
| A V1 `(input) => hooks` module | Silently produced no marker. |
| The real adapter from `.opencode/plugins/` | `design-history status` reported `active` and created `.sdd/design-history.sqlite3`. |
| The real adapter copied to `.opencode/plugins/` | Failed with `can't open file '<repo>/scripts/design-history'`; the README therefore says to link, not copy. |
| `permission.question: allow` | Required; without it the host refuses the question tool and the adapter reports a host refusal. |

## What remains unconfirmed (未確認)

- **An independent human trial.** No person other than the author ran the
  scenarios, and the author knew the expected outcomes while writing the
  replies.
- **A full form-level failed-write trial with a real unanswered form.** The
  cancellation path was observed (scenario 2b and the `cancelled` record from
  the returns-policy run); a real "answer written but store write failed" was
  not induced on the host.
- **A real save refusal after a *recorded* answer conflicts with a *planned
  spec*.** Scenario 1 refused, but the save was also gated by the ordinary
  content confirmation, so the two protections were not separated. The
  contradiction was surfaced and the record was reconciled in the saved spec;
  no trial isolated "conflict alone blocks the save".
- **Claude Code and Cursor.** Out of scope for this version. No trial.
- **A second machine, a separate worktree, or a team checkout.** Out of scope.
  No trial.
- **Windows or Linux.** All observations are from macOS on the stated host.
- **Search over a large store.** The trial store held three forms; no
  performance or relevance check was run at scale.

## Record template

Use this for each new trial result:

```text
Check:
Pack revision:
Host and version:
Model:
Fixture and prompt:
Skill files read by the trial:
Recorded history present:
Actual questions or judgments:
Documents read or updated:
Side effects:
Verification command and output:
Expected match: met / partial / not met
Deviation and impact:
```
