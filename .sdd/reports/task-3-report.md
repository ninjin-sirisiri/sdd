# Task 3 report: Confirm design intent before saving documents

## Status

**DONE**, with one disclosed process problem (a concurrent sibling session wrote
the same three files repeatedly; see "Authorship and collision" below).

Commits: `c2b3d21` (`feat: confirm design intent against recorded history before
saving documents`), `176dc56` (`docs: correct trial provenance in the design
history evaluation`), and `405a08e` (`docs: reconcile design history guidance
with verified host behavior`). Range `1f8be29..405a08e`.

All six brief requirements are implemented in `skills/sdd-design/SKILL.md`, the
README documents the real host behavior, and a six-scenario trial was actually
run in disposable repositories against OpenCode `v2.2.7` with the real adapter.

## What I implemented

### `skills/sdd-design/SKILL.md`

The existing judgment and narrowing rules were preserved. The new material is
placed so a session meets it before it writes: a pointer in Explore, a
`Confirm before saving` section between the interview and `Shared specification
and later phases`, a hook in the roadmap section, and an explicit step in the
`Architectural` ending.

- **Question selection** (brief item 1): ask only unsettled points that change
  the design — user-facing behavior, acceptance criteria, important constraints,
  and later-phase contracts. Combine independent topics, sequence dependent
  ones, present options with a recommendation and the reason, accept free text,
  and set no question-count minimum or maximum and no per-section approval. The
  earlier "one question is fine when one decision is open / do not use a fixed
  form" rules are merged here rather than duplicated.
- **Search before writing** (item 2): run
  `<pack-root>/scripts/design-history search --case <case>`, then compare planned
  statements against the raw records. The skill branches on the JSON `status`,
  not on an empty `results`, and lists all six statuses with their exit codes,
  including `recording-unavailable` versus `no-matches`. It also says to treat
  another case's answer as unrelated until the person says it applies.
- **New documents** (items 2 and 3): present goal, completion criteria,
  non-goals, and important constraints once and get explicit confirmation; for a
  roadmap also present the split and order before saving; keep the post-save
  document review and the approval after saving. Undecided items stay undecided
  with their impact and resolution point. If nothing is unsettled, invent no
  extra questions.
- **Existing documents** (item 4): do not rewrite a spec or roadmap until the
  target, the meaning being changed, and the impact on dependent work are agreed.
  History is evidence for reconciliation and never outranks an approved
  document; an agreed shared-contract change is reflected in the owning spec
  first. Link-only and typo edits need no new approval round.
- **Missing records** (item 5): when recording is enabled and a required answer
  cannot be obtained, stop the dependent document save, name the missing
  decision and its impact, and give recovery paths. The model may not back-fill.
- **Unsupported host or unenabled repo** (item 6): say plainly that automatic
  recording is absent, use the conversation and approved documents, and keep
  every other protection.

The section also states that recorded answers are excerpts, never rewritten, and
never treated as the person's consent; that imported logs are the same kind of
evidence; and that import is `import-preview` then `import-confirm` only after
the person agrees to the previewed pairs.

### `README.md`

A new `## Design History` section, in the style of the existing sections and
without restructuring unrelated ones:

- what is recorded (question text, header, ordered options, selected value or
  free text; answered/cancelled/unanswered/held/corrected as distinct states;
  corrections as new revisions) and what is not (attachments, credentials, tool
  output, transcripts, forms the plugin did not present; no external service);
- the five source values including `design-history.import`;
- storage at `<checkout>/.sdd/design-history.sqlite3` plus any SQLite sidecars,
  with the Git ignore/untracked requirement, and an explicit statement that Git
  exclusion is not access control;
- enablement for OpenCode V2 with the verified details (see below);
- search with the exact flags, the JSON shape, and a `status`/exit-code table;
- import as preview → confirm over one named file, JSON
  `design-history-import` v1 only, transcripts refused;
- recovery for each failure state;
- non-goals (Claude Code/Cursor, other worktrees, machines, repos, team sharing,
  external semantic search, full session capture).

### `docs/evaluations/design-interview-history.md`

A new trial procedure and record in the shape of
`docs/evaluations/skill-judgment-and-handoff.md`: purpose, ground rules, a plain
statement that the trial was skill-text-driven rather than an independent human
trial, fixtures, six scenarios with expected judgments, a record template,
automated results, real-machine results, setup checks, and a 未確認 list.

## Verification

### 1. Executor: pytest, worktree root, final state

```text
$ uv run --no-project --with pytest python -m pytest -q
435 passed in 18.77s
```

Scope: the whole suite, including the pre-existing tests plus
`tests/test_design_history.py` and `tests/test_design_history_import.py`.
Target: `405a08e`. This is unchanged from the Task 2 baseline of 435, which is
expected — this task adds no production code.

### 2. Executor: bun, adapter unchanged

```text
$ bun test adapters/opencode/design_history_plugin.test.ts
bun test v1.4.5 (a7733435c)
 25 pass
 0 fail
 74 expect() calls
Ran 25 tests across 1 file. [204.00ms]
```

`git diff --stat -- adapters/` is empty, so this confirms no adapter regression.

### 3. Real host: a recorded answer exists without model transcription

Disposable repo `$TMP/opencode/dh-trial`, the real adapter symlinked to
`.opencode/plugins/design_history_plugin.ts`, `permission.question: allow`.
A native form was presented by the plugin and answered from a **separate
process**:

```text
form=frm_1f48796fa001GEBfQNyPW0OqrC
reply http=204
```

Search returned the pair with `source: opencode.form.replied`,
`delivery: event`, and a real `eventID`, so the model was not in the write path.

### 4. Trial scenario 1 — recorded answer contradicts the proposed spec

Session `ses_e0b73a175ffeHxKJdAo93lPH4u`, three turns, against a store holding
「削除は取り消せますか」→「取り消せる」 for case `delete-item` while the request
said delete is final.

- Turn 1: searched `--case items` (`no-matches`, exit 3), found the two
  other-case answers, and presented the conflict with the impact of each side.
  **No file written.**
- Turn 2 ("no undo is authoritative; skip the form, save now"): presented goal,
  completion criteria, non-goals, and constraints, and **refused to write**
  without an explicit yes.
- Turn 3 ("that block is approved"): wrote the spec and its `.html` companion,
  validated the pair, and committed `ac4e4ee` **inside the fixture**. The saved
  spec records the conflicting records and the person's reconciliation; both raw
  records are byte-unchanged.

### 5. Trial scenario 2 — required record missing while recording is enabled

- The recorder reported `active`, and the failed write had left **no** question,
  answer, or omission row — the session confirmed this from the store rather
  than assuming it.
- It **stopped** the save, named the exact dependency (the per-order charge when
  an order splits across warehouses), explained why the three settled facts did
  not remove it, and offered re-ask / repair / import as recovery. No files
  changed. It did not invent a value.
- Separately, `search` before and after a recorded `stopped` status:

```text
before: no-matches           rc=3  recorder=active
after:  recording-unavailable rc=5  "Recording is stopped; an empty result does
                                      not mean the interview had no answers."
```

### 6. Trial scenario 3 — unapproved meaning change to an existing spec

The session found the canonical "delete is final" line, the committed delete
spec consuming it, and the missing companion; it refused the edit and said
"do not ask" cannot replace the agreement. The target's SHA-256 was `49d1e987…`
before and after: **unchanged**.

### 7. Control cases

- **Clear request** (rename a private attribute): classified bounded, asked no
  design questions, corrected a false premise in the request, decided the rename
  itself, and asked the workspace question once. No files changed.
- **Link-only update**: said "No new approval round", proposed the one-line
  Markdown edit plus the mirrored companion and digest, and dry-ran the
  validator in memory (`allow`). No approval round requested.
- **Non-supporting host**: said "recording is absent" and that it would use the
  conversation and approved documents, then asked one round of independent
  questions. No files changed.

### 8. Setup checks against the real host

Run because the README would otherwise instruct users into a silent no-op:

```text
.opencode/plugins/*.ts autodiscovery            loaded, marker written
plugins: [<path>.ts]                            refused: "configured plugin path
                                                must be a directory"
plugins: [<dir with index.ts only>]             loaded and ran (no package.json)
plugins: [<dir with package.json, no index.ts>] not loaded
legacy plugin: [<same dir>]                     also loaded on this build
V1 (input) => hooks module                      did not run; host logged
                                                "Plugin must export a default
                                                definition with an id and an
                                                effect or setup function"
real adapter in .opencode/plugins/              status: active, .sdd/ created
real adapter copied instead of linked           "can't open file
                                                '<repo>/scripts/design-history'"
```

## Decisions that affect later phases

- **Canonical spec not updated.** `docs/sdd/specs/2026-11-19-design-interview-history-design.md`
  was not changed, and no Target document was touched
  (`git diff --name-only 1f8be29..HEAD` lists only `README.md`,
  `skills/sdd-design/SKILL.md`, and `docs/evaluations/design-interview-history.md`).
  Therefore no HTML companion is owed. The implementation matches the spec's
  steps 1, 4, and 5 and the 記録できない場合 section; the only new facts are host
  setup behavior, recorded in the README and the evaluation.
- **Setup instructions carry a host-specific correction.** An explicit
  `plugins` entry must be a directory whose `index.ts` is the entry; a `.ts` file
  path is refused, and `package.json` is not required. Autodiscovery of
  `.opencode/plugins/*.ts` needs no config key. The adapter must be linked, not
  copied, or it resolves the CLI inside the consuming repo. These are documented
  as verified on `v2.2.7`, not as a general OpenCode guarantee.
- **Skill ordering.** `Confirm before saving` sits before `Shared specification
  and later phases` so it is met before any save; the roadmap and Architectural
  sections point back to it rather than restating it.
- **`search` never exits 6.** The README documents that Git refusal is reported
  by `status`, `record`, and `import-confirm`, because `search` opens the store
  read-only.

## Files changed (`1f8be29..405a08e`)

- `skills/sdd-design/SKILL.md`
- `README.md`
- `docs/evaluations/design-interview-history.md` (new)

Not modified: `adapters/opencode/*`, `scripts/sddlib/*`, `scripts/design-history`,
`tests/*`, any spec, plan, `CONTEXT.md`, or ADR.

## Authorship and collision (disclosed, not hidden)

A concurrent session in this same worktree wrote `skills/sdd-design/SKILL.md`,
`README.md`, and `docs/evaluations/design-interview-history.md` while I was
working, in several bursts between 00:40 and 01:35. It first produced the bulk
of the skill section and the README section; I then stopped writing, let the
tree stabilize, and independently verified every claim against the real code and
the real host.

That verification found four defects, which `405a08e` fixes:

1. **A `.ts` file path in the `plugins` array.** The README told users to
   register `.opencode/plugins/design_history_plugin.ts` that way. On `v2.2.7`
   the host refuses it with "configured plugin path must be a directory" and
   loads nothing.
2. **A later claim that a `plugins` entry needs `package.json`.** It does not: a
   directory with only `index.ts` loads, and a `package.json` `main` does not
   override `index.ts`. The README now documents what was measured.
3. **"Copy or link" the adapter.** Copying breaks its relative
   `../../scripts/design-history`; the real run failed with
   `can't open file '<repo>/scripts/design-history'`. The README now says to
   link, and names `SDD_DESIGN_HISTORY_CLI` as the fallback.
4. **"WAL sidecars".** The store never sets WAL; the observed
   `PRAGMA journal_mode` is `delete`. The README now says "any `-wal`, `-shm`, or
   `-journal` sidecars that exist", matching `SIDECAR_SUFFIXES` and the actual
   journal mode.

The sibling also left the evaluation document as a template with three
unfilled placeholders (`<!-- AUTOMATED-RESULTS -->`, `<!-- TRIAL-RESULTS -->`,
`<!-- UNEXECUTED -->`). I replaced it with the record above, covering the
fixtures and sessions I actually ran.

I kept the sibling's skill-text improvements where they were more faithful to
the brief than my draft: separating the pre-save confirmation from the post-save
review and from implementation approval, the "ask through the recording form"
sentence, and the tightened "confirm the split and order before saving and keep
the approval after saving" wording for a truly new roadmap.

Root cause is the same as Tasks 1 and 2: one worker per worktree. Task 3 was the
last task, so there is no later phase to collide with.

## Notes and concerns

- **`pack writing to itself`**: `README.md` instructs consuming repositories to
  use `./scripts/design-history`, which is correct from the pack root but not
  from a consumer. The verify line and the search/import examples are shown from
  the pack root; a consumer would use `"$SDD_PACK_ROOT/scripts/design-history"`.
  I left the examples as pack-root invocations because the surrounding README
  sections use the same convention, and the enablement step already names
  `SDD_PACK_ROOT`.
- **未確認 items** (also listed in the evaluation doc): an independent human
  trial; a real host "answer written but store write failed" run; isolating
  "conflict alone blocks the save" from the ordinary content gate; the
  ask-through-the-form sentence (added after the trials); Claude Code and Cursor;
  another machine, worktree, or team checkout; Windows and Linux; and search at
  scale.
- The stored `journal_mode` is `delete`, so a `-wal` sidecar will not normally
  appear. The Git precheck still checks all three suffixes, which is correct.
- The fixture repository's delete spec commit `ac4e4ee` is inside the disposable
  repo only; it is not part of the pack.
- `.sdd/reports/task-3-report.md` previously held an unrelated stale report; it
  is fully replaced by this file.
