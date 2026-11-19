# Task 2 report: Import explicitly selected past logs

## Status

**DONE**, with one disclosed process problem (a concurrent sibling session wrote
the same files; see "Authorship and collision" below).

Commits: `cc2deba` (`feat: import explicitly selected past design interview
logs`), `245c98e` (`fix: report planned pairs consistently on import confirm`),
and `02b3d51` (`fix: refuse absence states and report secret imports as
omitted`). Range `2ac00ba..02b3d51`.

The import path is an explicit two-step operation the user drives by naming one
local file and one design case. `import-preview` reports the exact excerpt
pairs it would import and a machine-readable reason for every excluded pair,
and writes nothing (no database is created). `import-confirm` is the only
command that saves, and it re-reads the same named file. The source log is
opened read-only and stays byte-identical. Imported rows carry
`design-history.import` / `design-history-import`, never an `opencode.*` value.
Re-importing the same log adds no answer revision.

## What I implemented

### Import format (documented in CLI help, example under `tests/fixtures/`)

A small hand-writable UTF-8 JSON document, **not** a chat transcript:

```json
{
  "format": "design-history-import",
  "version": 1,
  "title": "Past interview: checkout cancel",
  "questions": [
    {
      "question": "削除は取り消せますか",
      "id": "checkout-cancel.q1",
      "header": "削除",
      "options": ["取り消せる", "取り消せない"],
      "answer": "取り消せる",
      "state": "answered"
    }
  ]
}
```

`question` and `answer` are required; `id`, `header`, `options` (ordered), and
`state` are optional. Unknown top-level or per-pair keys are refused rather than
silently dropped, so a pasted transcript field cannot ride along.

**Why one JSON format, not a transcript scraper.** The spec says to import only
pairs whose question/option/answer correspondence is *provable*, and the Global
Constraints forbid treating a model's interpretation as the person's statement.
A guesser over natural-language chat logs would violate both. A self-describing
excerpt document makes correspondence decidable by construction: the pair is
either exactly consistent with its own listed options or it is excluded with a
reason. The example file is
`tests/fixtures/design-history-import.example.json`; the mixed case
(importable + ambiguous + secret + duplicate) is
`tests/fixtures/design-history-import.mixed.json`.

### `scripts/sddlib/design_history_import.py` (new)

- `preview_import()` / `confirm_import()` — the only public import entry points.
  Preview reads the log and the database read-only; confirm re-reads and writes.
- Whole-log refusal with a token reason (`log-unreadable`, `log-too-large` at
  4 MiB, `log-not-utf8`, `log-not-json`, `log-not-an-object`,
  `unsupported-format`, `unsupported-version`, `unsupported-field`,
  `no-questions`). A markdown transcript fails as `log-not-json` with "a chat
  transcript is not a supported format".
- Per-pair exclusion reasons: `ambiguous-question-id`, `ambiguous-options`,
  `answer-not-in-options`, `changed-question`, `duplicate-pair`,
  `excerpt-too-long`, `invalid-pair-shape`, `invalid-question-id`,
  `missing-answer`, `missing-question`, `secret-detected`,
  `unsupported-answer-shape`, `unsupported-field`, `unsupported-state`.
- Two pairs claiming one question ID with different content exclude **both**
  (`ambiguous-question-id`) — keeping the first would be a guess. Identical
  repeats are `duplicate-pair`.
- A re-import cannot rewrite a question already imported for that case
  (`changed-question`); the recorded question text and options stay as first
  imported.
- Excerpt length caps (question 2000, header 200, option 500, answer 4000,
  id 200) refuse a transcript-shaped field rather than truncating it.
- `question_id_for()` mirrors `questionIDFor()` in the OpenCode adapter,
  including NFKC, lowercase, 40-character truncation counted in UTF-16 code
  units (so astral-plane characters truncate identically to JS `String#slice`),
  and explicit-ID preference. A Python test pins the same vectors as the bun
  adapter test.
- `form_identity(case)` is one import bucket per design case, deliberately
  independent of the log path, so a copied or moved log dedupes instead of
  duplicating. Each answer row records the log's SHA-256 as `eventID`, so two
  logs in one case keep per-answer provenance.

### `scripts/sddlib/design_history.py`

- `IMPORT_HOST = "design-history-import"`, `IMPORT_SOURCE =
  "design-history.import"`, `IMPORT_LOG_LIMIT_BYTES = 4 MiB`.
- `record_import()` — the store write path, reusing the existing schema,
  `_upsert_form`, `_register_questions`, `_insert_answer`, the
  `(question_pk, digest)` identity, and secret detection. It refuses another
  checkout via the existing `_require_same_checkout` + Git precheck.
- `_upsert_form` now honours a payload `host` (default `opencode-v2`), so an
  import is distinguishable in `design_form.host`.
- `imported_form_state()` — read-only lookup of already-imported
  question/option digests for a case, so a preview can say "already recorded"
  instead of "new".
- `answer_digest()` — the store's digest rule exposed so the importer does not
  duplicate it.
- `search()` results now include `answers[].eventID` (needed to show import
  provenance; additive to the Task 1 JSON contract).

### `scripts/design-history`

- `import-preview --log FILE --case CASE [--db PATH]` — writes nothing.
- `import-confirm --log FILE --case CASE [--db PATH]` — the only import writer.
- `--help` (top-level and per-command) documents the format, the two-step
  procedure, the exclusion-reason vocabulary, the exit codes, and states
  explicitly that "a preview is not consent" and the source is "never
  modified". `--log` is required; the tool never scans a directory — naming a
  directory fails with "name the local log explicitly".

### Tests

`tests/test_design_history_import.py` (32 tests) covers every item the brief
names, plus store-level failure states:
unique pairs import; ambiguous correspondence excluded with the exact reason;
secret-bearing pairs excluded and never stored; unsupported format refused;
preview writes nothing (no DB created, existing DB byte-identical); confirm
writes; re-run dedupes (row counts unchanged); changed answer becomes a new
revision; changed question is refused; imported pairs retrievable via ordinary
`search` by case, Japanese keyword, question ID, and source; input file
SHA-256 **and mtime** unchanged; only excerpts stored (column and byte checks);
Git precheck refusal; unreadable DB reports `unavailable` not
`nothing-to-import`; a copied log dedupes; directory refused; absence state and
value-less pair refused; secret answer reported as `omitted`, not
`alreadyRecorded`.

## Verification

### 1. Executor: pytest, worktree root

```text
$ uv run --no-project --with pytest python -m pytest -q
435 passed in 17.80s
```

Scope: whole suite (403 pre-existing + 32 import tests). Target change:
`02b3d51`.

### 2. Executor: bun, adapter unchanged

```text
$ bun test adapters/opencode/design_history_plugin.test.ts
bun test v1.4.5 (a7733435c)
 25 pass
 0 fail
 74 expect() calls
Ran 25 tests across 1 file. [157.00ms]
```

Scope: adapter unit tests only. No adapter file was modified by this task
(`git diff 2ac00ba..HEAD -- adapters/` is empty), so this confirms no breakage.

### 3. Real CLI run: disposable git repo, synthetic log

Repository `/private/…/T/opencode/dh-import-head/repo`: `git init -b main`,
`.gitignore` = `.sdd/`, two commits. Log: 5 pairs — one unique select pair, one
unique free-text pair, one answer outside its options, one secret-bearing pair,
one pair reusing the first pair's explicit ID with a different answer.

Preview (actual):

```text
preview rc=0
preview: ok | db exists: False | pairsInLog: 5
  importable: [(1, 'checkout-cancel.q2')]
  EXCLUDED 0 ambiguous-question-id | 2 pairs claim question ID 'checkout-cancel.q1' with different content, so none of them can be imported without guessing
  EXCLUDED 2 answer-not-in-options | the answer is not one of the listed options ('必要', '不要'), so the question/option/answer correspondence cannot be proven
  EXCLUDED 3 secret-detected | the pair contains a credential; it was not imported and its text was not stored
  EXCLUDED 4 ambiguous-question-id | 2 pairs claim question ID 'checkout-cancel.q1' with different content, so none of them can be imported without guessing
preview left .sdd? no
```

Confirm (actual):

```text
confirm rc=0
confirm: ok | saved 1 pair(s) from the named log | counts: {'pairsInLog': 5, 'importable': 1, 'alreadyRecorded': 0, 'excluded': 4, 'recorded': 1}
  recorded: [('checkout-cancel.q2', '監査ログだけ残す')]
```

Ordinary search after confirm (actual):

```text
search1: ok | pairs: 1
   checkout-cancel.q2 | design-history.import | design-history-import | answered | 監査ログだけ残す | import | import:69d91f038f0fb...
```

Re-run confirm, then search again (actual):

```text
re-confirm: ok | every importable pair is already recorded; nothing was written | counts: {'pairsInLog': 5, 'importable': 0, 'alreadyRecorded': 1, 'excluded': 4, 'recorded': 0}
search2: ok | pairs: 1
rows: {'design_form': 1, 'design_question': 1, 'design_answer': 1, 'design_omission': 0}
```

Input file byte-identical (actual):

```text
checksum before:
69d91f038f0fb64b71078f56cb2595f0f9b8f31e0954960a9d4a07232de3a268  .../past-interview.json
checksum after:
69d91f038f0fb64b71078f56cb2595f0f9b8f31e0954960a9d4a07232de3a268  .../past-interview.json
stat before: 1795102516 965
stat after:  1795102516 965
```

Git exclusion (actual):

```text
.gitignore:1:.sdd/	.sdd/design-history.sqlite3
```

### 4. Unsupported format (actual)

```text
$ design-history import-preview --log chat.md --case checkout-cancel
rc=2
status: invalid | reason: log-not-json
detail: import log .../chat.md is not the JSON import format (...); a chat transcript is not a supported format

$ design-history import-preview --log other.json --case checkout-cancel
rc=2
status: invalid | reason: unsupported-format
detail: import log is not the documented format: 'format' must be 'design-history-import', got 'chat-log'
```

### 5. Secret and ambiguous reasons, and no non-excerpt data

Exclusion reasons are quoted verbatim in Verification 3. Database byte scan
(actual):

```text
  'sk-proj-abcdefghijklmnopqrstuvwxyz012345' in db -> False
  'password:' in db -> False
  'たぶん必要' in db -> False
  '# Session' in db -> False
  'system-reminder' in db -> False
  'tool_use' in db -> False
  'tool_result' in db -> False
  'attachment' in db -> False
  excerpt 監査ログだけ残す in db -> True
```

### 6. Store-level failure states (direct `record_import`, actual)

```text
absence state -> refused: import state 'cancelled' is not an answer; only answered, held, corrected pairs can be imported
no value -> refused: import pair 'c.q1' requires a non-empty value; absence is not an importable answer
secret pair -> {"ok": true, "action": "import", "recorded": [], "alreadyRecorded": [], "omitted": ["c.q1"]}
stored answers -> []
omission -> secret-detected
secret bytes in db -> False
```

### 7. Preview does not touch an existing database (actual, second trial repo)

```text
preview rc=0
db before=b327af1393fb8df42c49738e7e90d7889b9d8b4c5a1ba40b8d449e9c8592399d
db after =b327af1393fb8df42c49738e7e90d7889b9d8b4c5a1ba40b8d449e9c8592399d
```

### 8. Search filters over imported data (actual)

```text
Japanese keyword: ok [('checkout-cancel.q2', '監査ログだけ残す')]
question ID: ok 1
import source: ok 1
live source: no-matches 0
```

(`design-history.import` is retrievable; `opencode.form.created` does not match
an import.)

## Decisions that affect later phases

- **Import commands**: `design-history import-preview --log FILE --case CASE`
  and `design-history import-confirm --log FILE --case CASE`; the confirmed
  pair set is always re-derived from the same file, not remembered from the
  preview. Task 3 must document this two-step procedure and treat a non-zero
  preview exit as a reason not to confirm.
- **Import source values**: `design-history.import` (form + answer `source`)
  and `design-history-import` (`host`), `delivery = "import"`. No
  `opencode.*` value means an import. Task 3 may branch on `source` to tell
  recorded from imported history; both are legitimate evidence.
- **Import statuses**: import reports reuse the Task 1 search vocabulary plus
  `nothing-to-import` (`status`, exit 3). Exit codes stay 0/2/3/4/5/6. A
  missing/invalid log is `invalid` (exit 2) with a `reason` token; an
  unreadable database is `unavailable` (exit 5). "No history" is never
  reported as "every pair is already recorded" and vice versa.
- **Preview scope**: an import is per design case. The same case imported from
  two logs shares one import form; per-answer `eventID` carries the log's
  SHA-256. Re-import of a pair that differs only in question text/options is
  refused as `changed-question` rather than overwriting.
- **JSON contract change**: `search` result answers gained `eventID` (additive;
  no existing field changed). Task 3 may read it.
- **Canonical spec**: `docs/sdd/specs/2026-11-19-design-interview-history-design.md`
  was **not** updated. The implementation matches steps 3 and the
  "記録できない場合" section; the new facts are command names, format, and
  reason tokens, which belong in Task 3's README. No premise Task 3 depends on
  changed.

## Files changed (`cc2deba`, `245c98e`, `02b3d51`)

- `scripts/sddlib/design_history_import.py` (new)
- `scripts/sddlib/design_history.py`
- `scripts/sddlib/design_history_cli.py`
- `tests/test_design_history_import.py` (new)
- `tests/fixtures/design-history-import.example.json` (new)
- `tests/fixtures/design-history-import.mixed.json` (new)

Not modified: `adapters/opencode/*`, `README.md`, `skills/`, existing specs,
the plan.

## Authorship and collision (disclosed, not hidden)

A concurrent session in this same worktree wrote the same Task 2 files between
23:57 and 00:22 and committed `cc2deba` and `245c98e`. As in Task 1, I stopped
writing rather than overwrite in-flight work, waited for the tree to stay
stable, then independently reviewed the committed code and verified it end to
end rather than inheriting its claims. My review found three real defects that
the tests did not catch, fixed with failing tests first in `02b3d51`:

1. `record_import` stored a non-answer `state` (e.g. `cancelled`) together with
   a value, so a cancellation became an answer carrying agreement.
2. `record_import` stored an `answered` pair with `value: None` as an empty
   answer.
3. A secret-bearing answer reached through the store returned
   `alreadyRecorded` instead of `omitted`, because `_insert_answer` signals both
   "duplicate" and "secret" the same way. The secret was still never stored;
   the report was wrong.

I also fixed `import-preview --help` / `import-confirm --help`, which demanded
`--log` instead of printing the documented format, and added the two-step
procedure to the help for Task 3. A directory passed as `--log` is now covered
by a test proving it is refused, not scanned. Every claim above was re-run by
me against `02b3d51`.

Root cause: one worker per worktree. Task 3 can collide the same way.

## Notes and concerns

- `.sdd/reports/task-2-report.md` previously held an unrelated stale report;
  it is fully replaced by this file.
- The import format is deliberately the only supported input. A user with a
  Claude Code or Cursor transcript must hand-write the excerpt document; that
  is a documented cost of refusing to guess correspondence, and Task 3's
  README should say so plainly.
- The 4 MiB whole-log cap and the per-field excerpt caps are heuristics. They
  are generous for a real excerpt list and refuse transcript-shaped input, but
  a pathological legitimate question could hit the question cap; the reason
  token makes that visible rather than silent.
- `design_form.metadata_json` stores the log's file name, byte count, and
  SHA-256. That is provenance, not content; it is not a transcript excerpt.
- Git exclusion is not access control; the database is created with the default
  file mode. README wording belongs to Task 3.
- Imported rows are append-only like live answers, so a wrong import is
  corrected by a new revision, not by editing history.
