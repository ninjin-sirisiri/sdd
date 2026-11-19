# Task 3 report: Confirm design intent before saving documents

## Status

**DONE.** Commits `c2b3d21` (`feat: confirm design intent against recorded
history before saving documents`), `176dc56`, `405a08e`, `31becae`
(`docs: correct host registration and record the final design-history trial`),
`1a41ba8` (report), `3339221`, and `77331c6` (evaluation corrections), on top of
Task 2's `1f8be29`. Final HEAD is `77331c6`.

The skill, README, and evaluation are in place, and the judgment layer was
exercised on seven scenarios with the final skill text. Two README claims that
the host contradicts were found by the trial and corrected before that commit;
they would have left a user with a plugin that silently records nothing.

## What I implemented

### `skills/sdd-design/SKILL.md`

A new `## Confirm before saving` section sits between `Ungrillable and stop
conditions` and `Shared specification and later phases`, so it is encountered on
the path that already writes specs and roadmaps. It covers the six required
behaviors without deleting the judgment rules from the 2026-11-07 design:

- **Question choosing.** Added to `Interview`: ask only what changes the design
  and is still unsettled; combine independent topics, sequence dependent ones;
  when a choice has meaningfully different options, give options, a
  recommendation, and the reason, and accept free text; no minimum or maximum
  question count and no per-section approval. The existing rules — no fixed
  form, finish conditions, facts are your job, a recommendation is not an
  accepted decision — are untouched.
- **History lookup and reconciliation.** `Recorded history` tells the agent to
  search the case before writing and to branch on the JSON `status`
  (`ok`, `no-matches`, `no-database`, `recording-unavailable`, `unavailable`,
  `invalid`) and on exit codes 0/2/3/4/5/6, never on an empty `results`. It also
  says a raw record is never rewritten, an imported log is the same kind of
  evidence, and `import-preview` is not consent.
- **New documents.** Present goal, completion criteria, non-goals, and important
  constraints once, get explicit confirmation, then save; a roadmap also shows
  split and order, and a truly new roadmap keeps its approval after saving.
  Undecided items stay undecided with impact and resolution point.
- **Existing documents.** No rewrite until the target, the meaning changed, and
  the dependent impact are explicitly agreed; history never outranks an approved
  spec; a link-only or typo edit needs no new approval round.
- **Missing record.** Stop the dependent save while recording is enabled, name
  what is missing and how to recover, and never back-fill from the model.
- **Non-supporting host or unenabled repo.** Say automatic recording is absent,
  fall back to the conversation and approved documents, and keep every other
  protection.

The roadmap section and the `Endings` architectural step now call this gate
before writing, so the rule is reached at each save point. `Explore` points at
the history search for repos that record it.

### `README.md`

A `## Design History` section after the OpenCode install section, with: what is
recorded and what is deliberately not; the `.sdd/design-history.sqlite3`
location, WAL sidecars, and the Git-ignore/untracked requirement; enablement for
OpenCode V2 with the verified registration shapes and `permission.question:
allow`; search with the exit-code/`status` table; two-step import; recovery for
every failure state; the non-goals; and the statement that Git exclusion is not
access control. The existing `html_docs_plugin.ts` paragraph is intact.

### `docs/evaluations/design-interview-history.md`

Trial procedure in the shape of `docs/evaluations/skill-judgment-and-handoff.md`:
purpose, ground rules, how the trials were run, fixtures, scenarios, record
template, automated results, real-machine results in two separate batches, setup
checks, and an explicit 未確認 list.

## Verification

All commands ran in
`/Users/h-uma/.local/share/opencode/worktree/4df97a/design-interview-history` at
final HEAD `77331c6` unless a disposable repo is named.

### 1. Pack suite — pytest

Executor: me. Exact command and actual output:

```text
$ uv run --no-project --with pytest python -m pytest -q
........................................................................ [ 99%]
...                                                                      [100%]
435 passed in 18.30s
```

Scope: whole suite. Target change: `c2b3d21`..`77331c6` (docs/skill only; no
Python changed). 435 = 429 at Task 2's `245c98e` plus 6 tests the concurrent
Task 2 revision added in `02b3d51`.

### 2. Adapter — bun, unchanged by this task

```text
$ bun test adapters/opencode/design_history_plugin.test.ts
bun test v1.4.5 (a7733435c)
 25 pass
 0 fail
 74 expect() calls
Ran 25 tests across 1 file. [212.00ms]
```

`git diff --stat 1f8be29..77331c6 -- adapters/` is empty, so this confirms no
regression rather than new coverage.

### 3. HTML validator — not needed

This task changes `skills/`, `README.md`, and `docs/evaluations/`, none of which
is a Target document. No Target Markdown was edited, so
`html-docs check --paths docs/sdd/specs/2026-11-19-…` was not required and was
not run. No spec or plan HTML was created or edited.

### 4. Real-machine trial — 7 scenarios, final skill text

Host `opencode v2.2.7`; model `commandcode/deepseek/deepseek-v4.1-flash`. Every
fixture's private `.pack/skills/sdd-design/SKILL.md` was verified byte-identical
to `sha256:a952d163a39891fca84a40dc4104116575c367a932dd0b2a222d0ddb6d7abd1a`
before its run, so the trials used the committed text. Fixtures were disposable
Git repos under the session temp dir with `.sdd/` ignored; history was seeded
through the real `scripts/design-history record` path.

| # | Scenario | Observed | Pass |
|---|---|---|---|
| 1 | Proposed spec contradicts a recorded answer | Searched `--case notes-delete` (`ok`), quoted both recorded answers, put the reversal with four options and a recommendation, saved nothing | yes |
| 2a | Missing record (claimed answers) | Found only the ordering answer, attributed page size and layout to the current request instead of fabricating a record | partial (see below) |
| 2b | Required record genuinely absent, recording active | `search` `no-matches` with recorder `active`; verified all tables empty; stopped the save, named both decisions, gave recoveries | yes |
| 3 | Unapproved meaning change | Refused, named owning and dependent specs, no file touched | yes |
| 4 | Link-only update | Made the edit without an approval round, checked history first | yes |
| 5 | Clear request | No invented questions, spec saved, self-review fixed its own contradiction | yes |
| 6 | No recording | Said `no-database` and "automatic recording is absent", used conversation and approved documents | yes |
| 7 | Real plugin, two turns | Turn 1 refused and reported the real form cancellation; turn 2 revised the owning spec in place after explicit agreement, one authority | yes |

Side effects: scenarios 2a, 4, 5, and 7 wrote documents in their own disposable
repos and nowhere else. Scenarios 1, 2b, 3, and 6 wrote nothing. No fixture
commit touched this worktree.

### 5. Host setup checks that changed the documentation

Directly measured, because a wrong README instruction records nothing and does
not fail loudly:

```text
.ts path in `plugins`                        -> refused: "configured plugin path must be a directory"
.opencode/plugins/*.ts, no key               -> real adapter ran, recorder status active
nested .opencode/plugins/sub/*.ts            -> not loaded
.opencode/design_history/index.ts only       -> failed: "Could not read package.json"
same dir + package.json (name)               -> ran
legacy `plugin` key with that dir package    -> ran; a .ts path under it was refused
V1 default function / named exports only     -> "Plugin must export a default definition with an id and an effect or setup function"
adapter copied instead of linked             -> "can't open file '<repo>/scripts/design-history'"; recorder inactive
permission.question: deny                    -> host refusal reported, no row written, no false success
search with no database                      -> exit 4, status no-database, no .sdd/ created
status/record/import-confirm with .sdd/ unignored -> exit 6, nothing created
```

Two README claims were wrong before this commit and are corrected: that a
`package.json` is never needed for a `plugins` directory entry (false outside
`.opencode/plugins/`), and that `search` can exit 6 (it never writes). The
corrections are in `31becae`.

## Decisions affecting later phases

- **Pre-save confirmation is its own gate.** It does not replace the post-save
  document review or implementation approval. I removed a concurrent draft
  sentence that made one presentation serve both, because the canonical spec
  says this confirmation must not substitute for those gates.
- **Branch on `status`, not on emptiness.** Encoded in the skill and the README
  table, with `recording-unavailable` (5) explicitly distinguished from
  `no-matches` (3).
- **Registration guidance now matches the host.** Auto-discovery under
  `.opencode/plugins/` is the simplest verified setup; a `plugins` entry must be
  a directory; a directory outside `.opencode/plugins/` needs a `package.json`;
  `permission.question: allow` is required. Task 3 is the last task, but any
  later doc that repeats the old guidance must be corrected.
- **Canonical spec not updated.**
  `docs/sdd/specs/2026-11-19-design-interview-history-design.md` still matches
  what was implemented. No premise a later phase depends on changed, and no
  further phase exists.

## Files changed

- `skills/sdd-design/SKILL.md` — question-choosing rules, `## Confirm before
  saving`, roadmap and `Endings` hooks, `Explore` pointer.
- `README.md` — `## Design History` section (what is recorded, enablement,
  search, import, recovery, non-goals, Git-is-not-access-control).
- `docs/evaluations/design-interview-history.md` — new trial procedure and
  record.

No Python, adapter, spec, plan, or Target HTML changed.

## Notes and concerns

- **Concurrent sibling session.** A second session edited the same two files
  while I worked (the same collision Task 1 reported). It committed `c2b3d21`
  with the first draft of the skill, README, and evaluation; I verified every
  claim against the host, corrected two false README statements, rewrote the
  evaluation to separate the two trial batches, and committed `31becae`. The
  skill text and evaluation now describe the committed content, not either
  session's draft. Every claim above was re-checked against `77331c6`.
- **Scenario 2a is only a partial pass.** It saved in turn 1 and attributed the
  new facts to the current request rather than inventing earlier answers. That
  is defensible and arguably correct, but it did not exercise the missing-record
  stop. Scenario 2b is the clean case.
- **The confirmation gate is not cleanly demonstrated.** Scenario 5 saved
  without obtaining confirmation and said so; scenario 7 turn 2 obtained
  agreement, but I wrote that reply knowing the expected outcome. No run shows
  an independent person confirming and then the save proceeding.
- **Scenario 1 and 3 refusals are not isolated** from the ordinary content gate.
  Both agents cited the recorded conflict as a distinct reason, but the save was
  also blocked by the normal pre-save content confirmation.
- **A real store write failure was not induced on the host.** Cancellation was
  observed on the real form; the failed-write path is covered only by adapter
  unit tests.
- **Everything is one- or two-turn.** These are scripted-subagent trials, not an
  interactive human trial, and the evaluation says exactly that.
- The disposable fixtures and trial transcripts are under
  `/private/var/folders/1l/g5bm30qs6mq6m4zd0hqj2y4r0000gn/T/opencode/t3-eval/`.
  They are not committed, contain no user data, and use only synthetic prompts.

### Unexecuted, marked 未確認 in the evaluation

An independent human trial; a form-level failed write on the host; isolating the
recorded-conflict refusal from the content gate; a clean independent
confirmation-then-save run; Claude Code and Cursor recording; a second machine,
separate worktree, or team checkout; Windows and Linux; and search at scale.
