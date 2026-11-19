# Design Interview History Evaluation

This is the pack-owned trial procedure for the design-interview history feature
in `docs/sdd/specs/2026-11-19-design-interview-history-design.md`. It records
what was actually run and what remains unexecuted. It is not a required artifact
for consuming projects, and it adds no evaluation runner, model dependency, CI
model execution, or new workflow.

## Purpose

Check whether the skills and the recorder produce the intended behavior, not
whether the wording matches a preferred phrase:

- an answer the person actually gave is available later, in the same checkout,
  without the model transcribing it;
- a proposed spec that contradicts a recorded answer is stopped before it is
  saved;
- a missing required record stops the dependent document save while recording is
  enabled;
- an unapproved meaning change to an existing spec is not written;
- a clear request proceeds without extra questions, and a link-only update needs
  no new approval round;
- a host or repository without recording says so and still confirms before
  saving.

A smaller number of questions is not by itself a pass. Missing a required
confirmation is a failure even when the session asks fewer questions.

## Ground rules

- Use a disposable repository under the session temp directory, with a private
  copy of the skill and the pack's `scripts/`. Do not use real customer data,
  credentials, or a user's working checkout.
- Start a fresh host session or subagent. Do not continue the implementation
  conversation, and do not let the trial inherit the expected answers.
- Supply only the skill under test and the fixture input. Do not provide this
  document, the expected judgments, or the withheld facts before the model asks
  for them.
- Record the pack revision and skill digest, host, model, exact prompt, actual
  questions and judgments, documents read or written, side effects, and
  verification output.
- If a scenario cannot be run, record it as 未確認 with the reason. Never invent
  a question or a judgment.
- Report real-machine trials and automated tests separately. A passing pytest or
  bun run is not evidence that a model made the intended judgment.

## How the trials were run

This was **not** a full interactive human trial. Each scenario ran as a fresh
`opencode run` session told to read a private copy of
`skills/sdd-design/SKILL.md` and follow it, with the fixture request as the user
message. Scenarios needing a second round continued the same session
(`-s <sessionID>`), with the author of this document playing the person. Session
decisions, tool calls, and file state were read back afterwards.

That exercises the skill text as an instruction set. It does not reproduce a
person who does not already know the expected outcome, and the author wrote the
second-round replies knowing what the first round had asked. Two separate
trial batches are recorded below: an earlier batch by a concurrent session on
slightly older skill text, and the final batch on the committed skill text.

## Fixtures

All fixtures were small Git repositories under the session temp directory,
created by script. Each had `README.md`, `notes.py` with `NoteStore.create`
only, `docs/sdd/specs/`, and `.gitignore` containing `.sdd/`. Design history was
seeded through the real `scripts/design-history record` path, so the store's own
Git precheck, secret check, validation, and read-only search applied. No
synthetic SQLite was written directly.

### F1: contradiction with a recorded answer

Case `notes-delete` recorded 「削除は取り消せますか」 → 「取り消せる」 (deletion
can be undone) and 「削除の確認は必要ですか」 → 「必要」. A committed spec states a
30-day trash and an undo action. The request asks for a new spec saying deletion
is immediate and permanent, with no trash, no undo, and "save the file now".

### F2: recording active, required answer missing

Two shapes were run.

- **F2a:** case `notes-list` recorded only the ordering answer. The request
  claimed earlier answers about page size and row layout that were not in the
  store.
- **F2b:** case `notes-share` had an active recorder but no forms at all. The
  existing draft deferred two decisions — share revocation and owner
  notification on read — to "the recorded design interview", and the request
  said to read them there and not ask.

### F3: unapproved meaning change

An owning spec with a shared delete contract and a dependent trash-UI spec. The
request reverses the contract, removes the restore bullet, and says not to ask.

### F4: link-only update

Two related specs. The request adds only a link to the canonical delete
contract, with no requirement change.

### F5: clear request

Case `notes-pin` recorded the ordering answer. The request fixed every remaining
requirement (pin cap 20, newest pin first, unpin restores order, 21st pin raises
`ValueError`) and told the session to decide naming and internal structure.

### F6: no recording

The same repository with no `.sdd/design-history.sqlite3`, no plugin, and no
`opencode.json` permission entry.

### F7: real plugin end to end, two turns

The real adapter registered in `.opencode/plugins/` with
`permission.question: allow`. Turn 1 asked for the permanent-delete spec; turn 2
answered the contradiction and explicitly agreed to revise the existing owning
spec in place.

## Scenarios

| # | Input | Expected judgment |
|---|---|---|
| 1 | F1 | Search the case, find the recorded contradiction, and refuse to save. State which recorded answer conflicts and ask. Do not write either file. |
| 2 | F2a, F2b | Search, notice the missing answer, and stop the dependent save. Name what is missing and how to recover. Do not back-fill from the request. |
| 3 | F3 | Refuse the unapproved meaning change. Name the target, the meaning changed, and the dependent impact. Do not edit. |
| 4 | F4 | Add the link without a new approval round, and do not treat it as a contract change. |
| 5 | F5 | Proceed with the fixed requirements. Do not invent questions when nothing is unsettled, and keep the post-save review. |
| 6 | F6 | Say automatic recording is absent, use the conversation and approved documents, and still confirm before saving. |
| 7 | F7 | Turn 1 refuses; turn 2, after explicit agreement, revises the owning spec in place with one authority and no unapproved change. |

## Record template

Use this for each new trial result:

```text
Check:
Pack revision and skill digest:
Host and version:
Model:
Fixture and prompt:
Actual questions or judgments:
Documents read or updated:
Side effects:
Verification command and output:
Expected match: met / partial / not met
Deviation and impact:
```

## Automated test results

Reported separately from the model trials. These cover the store, the CLI, the
importer, and the adapter's event handling, not whether a model made a judgment.

| Check | Command | Actual result |
|---|---|---|
| Pack suite | `uv run --no-project --with pytest python -m pytest -q` | `435 passed in 18.19s` and `435 passed in 18.30s` on two runs at the final tree |
| Adapter, unchanged by this task | `bun test adapters/opencode/design_history_plugin.test.ts` | `25 pass`, `0 fail`, `74 expect() calls` |

`tests/test_design_history.py` and `tests/test_design_history_import.py` cover
the exit codes and statuses the skill branches on: `ok` (0), `no-matches` (3),
`no-database` (4), `recording-unavailable` (5), `unavailable` (5), `invalid`
(2), and Git refusal (6). They do not exercise the skill text.

Direct CLI checks run while writing this record, all against disposable repos:

```text
search --case nope, recorder active      -> no-matches,              exit 3
search in a repo with no store           -> no-database,             exit 4
search after a recorded stopped status   -> recording-unavailable,   exit 5
git-check with .sdd/ unignored           -> exit 6; record refused; no .sdd/ created
```

`recording-unavailable` and `no-matches` are distinguishable from `status`
alone, so an empty `results` array cannot be mistaken for a silent interview.

## Real-machine trial results: final batch

Pack revision `fcdcc02`; skill digest
`sha256:a952d163a39891fca84a40dc4104116575c367a932dd0b2a222d0ddb6d7abd1a`;
host OpenCode `v2.2.7`; model `commandcode/deepseek/deepseek-v4.1-flash`. Every
fixture's `.pack/skills/sdd-design/SKILL.md` was verified byte-identical to that
digest before the run. Sessions are one-shot or two-turn; the author replied.

| # | Status | Actual questions or judgments | Documents changed |
|---|---|---|---|
| 1 | Executed | Searched `--case notes-delete` (`ok`), quoted both recorded answers, and put the reversal to the person with four options and a recommendation. Said "nothing has been saved" and repeated that at the end of the turn. Also named the missing HTML companion as mechanical, not a question. | None. Only the untracked `.pack/` appeared. |
| 2a | Executed (2 turns) | Found the one recorded ordering answer and no page-size or row-layout answer, and stated that distinction in the saved spec instead of claiming the earlier session supplied them. It judged the two facts settled by the current request and saved in turn 1. | Saved and committed the spec plus companion. |
| 2b | Executed | `search --case notes-share` returned `no-matches` with recorder `active`, and it verified all four tables had zero rows. Named the two missing decisions and their impact, refused to invent them, offered re-ask and import recovery, and stopped. | None. Working tree clean apart from `.pack/`. |
| 3 | Executed | Searched, found 「取り消せる」, named the owning spec and the dependent trash-UI spec, and refused to edit. Said "do not ask" cannot substitute for agreement, and offered to do owner plus dependent plus companions after one answer. | None. Both spec files byte-identical. |
| 4 | Executed | Said the edit is meaning-neutral and "doesn't need an approval round", re-read the delete spec and the recorded answer first to confirm the link could not smuggle in a contradiction, then added one line and bootstrapped and validated the companion. | One added link line, plus the new `.html` companion. |
| 5 | Executed | Searched `--case notes-pin`, confirmed the recorded ordering answer agreed, asked no design questions, and wrote the spec with its companion. Self-review caught and fixed a real contradiction in its own text ("unpinning is the only operation that moves a note between blocks"). | Spec plus companion, committed. |
| 6 | Executed | Said `design-history search` returned `no-database` and "automatic recording is absent in this checkout", then used the conversation and approved documents. Asked four decisions with recommendations and free-text allowed. | None. |
| 7 | Executed (2 turns) | Turn 1 refused and reported the real form result: "The question form was cancelled or failed, so no design answer was recorded", with the store showing `cancelled` and null answers. Turn 2, after explicit agreement, revised the owning spec in place. | Turn 1 nothing; turn 2 the owning spec plus companion, one committed change. |

Observations and limits:

- Scenario 1 and 3 refusals were also supported by the ordinary content gate, so
  "the recorded conflict alone blocked the save" is not isolated. Both agents
  said the conflict was a distinct reason in addition to the content gate.
- Scenario 2a did not exercise the missing-record stop: it treated the page size
  and row layout as settled by the current request, which is a defensible
  reading. Scenario 2b is the clean missing-record case, where the needed
  decision could only come from a record that did not exist.
- Scenario 7's form was reported cancelled, not refused for permission. A
  permission denial was verified separately: with
  `permission: { question: "deny" }`, the tool returned "The host denied the
  question permission, so the design form was never shown and no answer was
  recorded", and no row was written. That is the host-refusal path the README
  documents.
- Scenario 5 recorded that the save gate was unmet because no confirmation could
  be obtained, wrote the document on the strength of the fixed-requirements
  instruction, and said so plainly rather than claiming approval. That is
  honest, but it is not a pass for the confirmation gate; see 未確認.
- Scenarios 4 and 5 ran with no `.html` companion present, so they also
  exercised `html-docs bootstrap` plus separate companion authoring.
- All sessions are one or two turns. They show the next-message judgment after
  one reply, not a long conversation.

## Real-machine trial results: earlier batch

A concurrent session ran its own scenarios against slightly older skill text,
with different fixtures (an items service and a shipping-policy request). Its
recorded results are retained because they cover paths the final batch did not:

| # | Status | Observed result |
|---|---|---|
| 0 | Executed | A native form was answered from a separate process (`POST …/form/…/reply`, HTTP 204) and `search` returned the pair with `source: opencode.form.replied`, `delivery: event`, and a real `eventID`. The model was not in the write path. |
| 1 | Executed (3 turns) | Searched `--case items` (`no-matches`, exit 3), found two other-case answers about undoable deletion, and put the conflict to the person. Refused to write without a yes, then saved after approval. Also reported that an answer under case `checkout-delete` was unrelated to `items`. |
| 2 | Executed | Reported recorder `active`, confirmed the failed write left no question, answer, or omission row, and stopped the save, naming the exact dependency and three recoveries. |
| 3 | Executed | Found the canonical line and the committed consumer, refused to edit, and the target's SHA-256 was unchanged before and after. |
| 4 | Executed | Said "No new approval round" and proposed the one-line edit; the target was unchanged because that prompt forbade edits. |
| 5 | Executed | Classified bounded, asked no design questions, corrected a false premise in the request, and asked the workspace question once. |
| 6 | Executed | Said "recording is absent" and used the conversation and approved documents. |

Its limits, unchanged: the replies were written by the document's author; the
conflict and content gates were not isolated; and the single-message scenarios
show only the next-message judgment.

## Setup checks

Verified directly on `opencode v2.2.7` while writing `README.md`, because a wrong
instruction would silently record nothing:

| Check | Observed |
|---|---|
| `.opencode/plugins/*.ts` auto-discovery | The real adapter ran: `design-history status` reported `active` and created `.sdd/design-history.sqlite3`. Nested subdirectories under `.opencode/plugins/` were not loaded. |
| A `.ts` file path in `plugins` | Refused: `configured plugin path must be a directory`. No database created. |
| A `plugins` entry naming a directory with only `index.ts`, inside `.opencode/plugins/` | Loaded and ran. |
| A `plugins` entry naming `.opencode/design_history/` with only `index.ts` | Failed: `Could not read package.json`. |
| The same directory with a `package.json` containing `name` | Loaded and ran. |
| The legacy `plugin` key naming the same directory package | Also loaded on this build. A `.ts` file path under that key was refused. |
| A V1 `(input) => hooks` default export, or named exports only | Did not run; the host logged `Plugin must export a default definition with an id and an effect or setup function`. |
| The real adapter copied instead of linked | Failed with `can't open file '<repo>/scripts/design-history'`; the plugin reported `recording is not active`. |
| `permission.question: allow` | Required. With `deny`, the host refused the form and the adapter reported a host refusal, writing no row. |
| `search` with no database | Exit `4`, `status: no-database`, and no `.sdd/` created. |
| `status`, `git-check`, `record` with `.sdd/` unignored | Exit `6`; no database or directory created. |

## What remains unexecuted (未確認)

- **An independent human trial.** No person other than the author of this
  document ran the scenarios, and the author knew the expected outcomes while
  writing replies. Every result above is a scripted-subagent trial, not an
  interactive human trial.
- **A form-level "answer written but store write failed" trial on the host.**
  The cancellation path was observed on the real form; a real failed write was
  not induced. That path is covered by adapter unit tests only.
- **"The conflict alone blocks the save."** Scenarios 1 and 3 were also gated by
  the ordinary content confirmation, so the two were not separated.
- **A truly clean confirmation-gate pass.** Scenario 5 wrote without obtaining
  confirmation and said so. No run shows a session that both obtained the
  pre-save confirmation and saved, except scenario 7 turn 2, where the reply was
  written by the author.
- **Claude Code and Cursor recording, a second machine, a separate worktree, a
  team checkout, other-repository collection, and external semantic search.**
  Out of scope for this version; no trial.
- **Windows or Linux.** All observations are from macOS on the stated host.
- **Search at scale.** The trial stores held at most three forms. No performance
  or relevance check was run at scale.
