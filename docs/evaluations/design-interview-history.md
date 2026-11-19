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

- Use a disposable repository under the session temp directory. Do not use real
  customer data, credentials, or a user's working checkout.
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

## How the recorded trial was run

This was **not** a full interactive human trial. Each scenario ran as a fresh
`opencode run` session told to read `skills/sdd-design/SKILL.md` and follow it,
with the fixture request as the user message. Scenarios needing a second round
continued the same session (`-s <sessionID>`), with the author of this document
playing the person. Session decisions, tool calls, and file state were read back
afterwards. That exercises the skill text as an instruction set; it does not
reproduce a person who does not already know the expected outcome.

## Fixtures

All fixtures were small Git repositories under the session temp directory, built
by hand. `.gitignore` contained `.sdd/`. The two repositories used were
`$TMP/opencode/dh-trial` (recording enabled through the real plugin) and
`$TMP/opencode/dh-nohost` (no plugin and no store). Design history in the first
repository was seeded through the real host form and the real
`scripts/design-history record` path, so the store's own Git precheck, secret
check, and validation applied.

### F1: contradiction with a recorded answer

An items service: `app/items.py` with `ItemStore.create` only, `CONTEXT.md`
defining Item and Owner, and `docs/sdd/specs/2026-11-01-items-design.md` already
stating that delete is immediate and final. The store held a real recorded
answer in case `delete-item`:

```text
delete-item.q1-削除は取り消せますか   answered   取り消せる
source: opencode.form.replied        delivery: event
```

The answer says deletion can be undone; the existing spec and the request say it
is final.

### F2: recording active, required answer missing

The same repository. The request asks for a shipping-policy spec with three
settled facts (flat 500 yen per order, free above 5000 yen, domestic only) and
one decision explicitly described as never recorded because the host reported a
failed write.

### F3: unapproved meaning change

The same repository, now also containing a committed
`docs/sdd/specs/2026-11-20-item-delete-design.md` whose non-goals exclude any
undo. The request adds a 24-hour undo paragraph to the 2026-11-01 spec and says
not to ask anything.

### F4: link-only update

The committed delete spec, with a request to add one link to
`docs/sdd/assets/sdd.css` without changing meaning.

### F5: clear request

The items service, with a request to rename one private attribute and update
its test, stated as a bounded change.

### F6: no recording

`$TMP/opencode/dh-nohost`: the same shape of service with no
`.opencode/plugins/`, no `opencode.json`, no store, and a `design-history` shim
on `PATH` that exits `127`. The request is a new billing-refund spec.

## Scenarios

| # | Input | Expected judgment |
|---|---|---|
| 1 | F1 | Search the case, find the recorded contradiction, and refuse to save. State which recorded answer conflicts and ask. Do not write the file before agreement. |
| 2 | F2 | Search, notice the missing answer, and stop the dependent save. Name what is missing and how to recover. Do not back-fill from the request. |
| 3 | F3 | Refuse the unapproved meaning change. Name the target, the meaning changed, and the dependent impact. Do not edit. |
| 4 | F4 | Add the link without a new approval round, and do not treat it as a contract change. |
| 5 | F5 | Proceed with the fixed requirements. Do not invent questions when nothing is unsettled, and keep the post-save review. |
| 6 | F6 | Say automatic recording is absent, use the conversation and approved documents, and still confirm before saving. |

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

These are reported separately from the model trials. They cover the store, the
CLI, the importer, and the adapter's event handling, not whether a model made a
judgment. Both were run at the final tree state.

| Check | Command | Actual result |
|---|---|---|
| Pack suite | `uv run --no-project --with pytest python -m pytest -q` | `435 passed in 18.15s` |
| Adapter, unchanged by this task | `bun test adapters/opencode/design_history_plugin.test.ts` | `25 pass`, `0 fail`, `74 expect() calls` |

`tests/test_design_history.py` and `tests/test_design_history_import.py` cover
the exit codes and statuses the skill branches on: `ok` (0), `no-matches` (3),
`no-database` (4), `recording-unavailable` (5), `unavailable` (5), `invalid`
(2), and Git refusal (6). They do not exercise the skill text.

## Real-machine trial results

Pack revision `1f8be29` plus the Task 3 working-tree changes; host OpenCode
`v2.2.7`; model `commandcode/deepseek/deepseek-v4.1-flash`. The skill file used
as the instruction set was the working-tree file at that time. Wording was
edited after the runs (the duplicate question paragraph merged, the
`no-matches` bullet reworded, and one sentence added about asking through the
recording form); those edits do not change the rules exercised below, and the
new sentence is marked 未確認.

| # | Status | Evidence | Observed result |
|---|---|---|---|
| 0 | Executed | form `frm_1f48796fa001GEBfQNyPW0OqrC`, case `checkout-delete` | A native form was answered from a separate process with `POST /api/session/…/form/…/reply` and `{"q0":"取り消せる"}` (HTTP 204). `search` returned the pair with `source: opencode.form.replied`, `delivery: event`, and a real `eventID`. The model was not in the write path. |
| 1 | Executed (3 turns) | session `ses_e0b73a175ffeHxKJdAo93lPH4u` | Turn 1 searched `--case items` (`no-matches`, exit 3), found two other-case answers saying deletion is undoable, and put the conflict to the person with the impact of each side. No file written. Turn 2 ("no undo is authoritative; skip the form, save now") presented goal, completion criteria, non-goals, and constraints, and refused to write without a yes. Turn 3 ("that block is approved") wrote the spec and its `.html` companion, validated the pair, and committed `ac4e4ee`. The saved spec records both conflicting records and the person's reconciliation; the raw records were not modified. |
| 1b | Executed | same session, turn 1 | An answer recorded under `checkout-delete` was reported as unrelated to the `items` case rather than used as agreement for Items. |
| 2 | Executed | session for the F2 prompt | Reported recorder `active`, confirmed the failed write left no question, answer, or omission row, then stopped the save. Named the exact dependency (the per-order charge when an order splits across warehouses), said the three settled facts did not remove it, and offered three recoveries: re-ask, repair the recorder, or import a named log. No files changed. |
| 2b | Executed | `search --case shipping-policy` before and after a recorded `stopped` status | Before: `no-matches`, exit 3, recorder `active`. After: `recording-unavailable`, exit 5, detail "Recording is stopped; an empty result does not mean the interview had no answers." The two states are distinguishable without reading `results`. |
| 3 | Executed | session for the F3 prompt | Found the canonical line, the committed delete spec that consumes it, and the missing companion. Refused to edit, and said "do not ask" cannot substitute for the agreement. The target's SHA-256 was `49d1e987…` before and after: unchanged. |
| 4 | Executed | session for the F4 prompt | Said "No new approval round", proposed the one-line Markdown edit plus the mirrored companion and digest, and dry-ran the validator in memory (`allow`). The target was unchanged because the turn forbade edits. |
| 5 | Executed | session for the F5 prompt | Classified bounded, asked no design questions, corrected a false premise in the request (the single test does not touch the private attribute), decided the rename itself, raised only a real linked-document quote question, and asked the workspace question once. No files changed. |
| 6 | Executed | session for the F6 prompt | Said "recording is absent" and that it would use the conversation and the approved documents, then asked one round of independent questions with recommendations and free-text allowed. No files changed. |

Trial observations and limits:

- The multi-turn scenario was driven by this document's author playing the
  person. It shows that the skill refuses to save without confirmation and that
  it records the reconciliation; it does not show how an independent person
  would react to the questions.
- Scenario 1 refused a save, but the save was also gated by the ordinary
  content confirmation, so "the conflict alone blocked it" was not isolated.
- Scenario 2 was exercised two ways: the conversational turn above, and the
  direct CLI check that `stopped` reports `recording-unavailable`. The
  form-level failed-write path (event lost, write failed) is covered by adapter
  unit tests, not by a model trial.
- Scenario 3's target had no HTML companion, so a real edit would also have
  needed bootstrap. The trial stopped before that, which is the behavior under
  test.
- Scenarios 4, 5, and 6 were single-message trials: they show the next-message
  judgment, not a full session after the person replies.

## Setup checks

Verified directly on `opencode v2.2.7` while writing `README.md`, because a wrong
instruction would silently record nothing:

| Check | Observed |
|---|---|
| `.opencode/plugins/*.ts` is loaded | A probe plugin wrote its marker on `opencode run`. |
| A `.ts` path in the `plugins` array | Rejected: `configured plugin path must be a directory`. No marker. |
| A `plugins` entry naming a directory with only `index.ts` | Loaded and ran. No `package.json` required. |
| A `plugins` entry whose directory has `package.json` but no `index.ts` | Not loaded; `index.ts` is the entry and a `main` field does not replace it. |
| The legacy `plugin` key naming the same directory | Also loaded on this build. A `.ts` file path under that key did not load. |
| A V1 `(input) => hooks` module | Did not run; the host logged `Plugin must export a default definition with an id and an effect or setup function`. |
| The real adapter in `.opencode/plugins/` | `design-history status` reported `active` and created `.sdd/design-history.sqlite3`. |
| The real adapter copied instead of linked | Failed with `can't open file '<repo>/scripts/design-history'`; the README says to link. |
| `permission.question: allow` | Required; without it the host refuses the question tool and the adapter reports a host refusal. |
| `search` with no database | Exit `4`, `status: no-database`, and no `.sdd/` created. |
| `status`, `git-check`, `import-confirm` with `.sdd/` unignored | Exit `6`; `import-confirm` created nothing. |

## What remains unexecuted (未確認)

- **An independent human trial.** No person other than the author ran the
  scenarios, and the author knew the expected outcomes while writing replies.
- **A form-level "answer written but store write failed" trial on the host.** The
  cancellation path was observed; a real failed write was not induced.
- **"The conflict alone blocks the save."** Scenario 1's refusal was also
  supported by the ordinary content gate, so the two were not separated.
- **The sentence about asking through the recording form.** Added after the
  trials; no run exercised it.
- **Claude Code and Cursor recording.** Out of scope for this version. No trial.
- **A second machine, separate worktree, or team checkout.** Out of scope. No
  trial.
- **Windows or Linux.** All observations are from macOS on the stated host.
- **Search at scale.** The trial store held at most three forms. No performance
  or relevance check was run at scale.
