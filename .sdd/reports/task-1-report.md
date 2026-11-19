# Task 1 report: Capture and search live interview answers

## Status

**DONE**, with one disclosed process problem (a concurrent sibling session wrote
the same files; see "Authorship and collision" below).

Committed as `c06c5a1` (`feat: capture and search live design interview answers`)
plus `a9a6be9` (`fix: declare the design tool output schema for the host
dispatcher`).

The brief's hardest open question — how the plugin presents a design question as
a native form — is settled with live evidence and is implemented. The real-machine
trial shows select and free-text answers saved and retrievable from a separate
process by case, Japanese keyword, and question ID, with no model transcription.

## How the plugin presents a form (the open question, settled)

A V2 plugin **can** present a native form. There is no `ctx.form` namespace on
`setup(ctx)`, but the host exposes its own `question` tool as a tool definition
via `ctx.tool.list()`, and that definition has a callable
`execute(input, toolContext)` which opens a real OpenCode form and resolves with
the person's answer. The adapter registers `design_question`, calls the host
`question` tool from inside it, and puts a correlation token in the outgoing
`messageID`; the host copies that into `form.created.metadata.tool.messageID`, so
the plugin can prove which `frm_…` is its own. Answers are then correlated by
session ID + form ID and written to `.sdd/design-history.sqlite3` through
`scripts/design-history record`. The tool result returns only a count and an
acknowledgement — never question or answer text — so the model is not a
transcription path.

Verified live on `opencode v2.2.7` (see Verification 3).

Two corrections to `.sdd/notes/opencode-v2-form-ground-truth.md`, plus one
addition. The note is the controller's evidence record; I did not rewrite it,
because changing a shared evidence note is the controller's call, so these are
proposed corrections:

1. **`form.created` does fire** for forms created through the host `question`
   tool (it did not for `POST /api/session/{id}/form`, which is what the note
   measured). The adapter depends on it, and it is delivered with
   `metadata.tool.messageID`.
2. **`ctx.permission.hook("evaluate", …)` return values are ignored** on 2.2.7.
   `PluginHooks.trigger` runs the callbacks and then returns the *original*
   input object, so a plugin cannot grant the `question` permission. Whether a
   design question may be asked is decided by the agent's configured
   permissions. I removed the adapter's claim to grant it and made a denial
   report itself as a host refusal rather than as a user cancellation
   (`plugins: design history: the form was not answered: Permission denied: question`).

Also worth recording for Task 2/3: the runtime plugin context is a superset of
the published `@opencode-ai/plugin@1.17.12` types (`dist/v2/promise/context.d.ts`
declares only `agent, aisdk, catalog, command, integration, plugin, reference,
skill`). `tool`, `session`, `event`, `permission`, and `location` exist at
runtime and are absent from those types, so the adapter is typed against the
observed runtime shape.

A third host constraint, found by a real model call and fixed in `a9a6be9`: the
dispatcher inspects `"output" in result`, so a tool that returns a bare string
crashes with `a is not an Object`, and `{ output }` without a declared schema is
rejected with "Tool result declared output without an output schema". The design
tool therefore declares `output: { type: "string" }` and returns
`{ output: "<acknowledgement>" }`. A `~standard`-shaped schema is *not* usable
here: the host calls `schema["~standard"].jsonSchema[io]` as a function, and a
plain object there fails registration with "Skipping invalid tool registration".

## What I implemented

### `scripts/sddlib/design_history.py`

Append-only store at `<checkout>/.sdd/design-history.sqlite3`, usable without a
server.

- Tables `design_form`, `design_question`, `design_answer`, `design_omission`,
  `recorder_status`, `meta`; WAL, foreign keys, transactional writes.
- A form is bound to one checkout, one session ID, one form ID, one design case.
  Questions keep their ordinal, host field key, text, header, ordered options,
  free-text flag, and required flag.
- Answers are revisions, never updates: `design_answer` has
  `UNIQUE(question_pk, digest)` plus a monotonically increasing `revision`, so a
  correction is a new row and the original survives. States distinguish
  `answered`, `cancelled`, `unanswered`, `held`, `corrected`.
- Answer maps are translated from host field keys (`q0`) to stable question IDs;
  unknown keys become an `unregistered-question` omission instead of an invented
  answer.
- `git_precheck()` refuses a non-repository, an escaping path, an unignored
  database, and a tracked database, and checks the `-wal`/`-shm`/`-journal`
  sidecars. It runs **before** anything is created.
- Secret detection drops the pair and writes a `secret-detected` omission
  without the text.
- `search()` opens SQLite with `mode=ro` and `PRAGMA query_only=ON`.

### `scripts/design-history`

`search` (case, question ID, Japanese-inclusive partial match over question,
options, and answer), `status`, `git-check` are read-only. `record` is the write
path the adapter drives (`register`, `reply`, `cancel`, `status`). Exit codes
separate no-database (4), no-matches (3), recording-unavailable (5), and
Git-refused (6), so an empty result is distinguishable from a broken recorder.

### `adapters/opencode/design_history_plugin.ts`

V2 `{ id, setup }` default export. Registers `design_question`, subscribes to
form events, filters on `event.type` (the stream is not type-filtered), handles
events in arrival order, and ignores any form it did not present. Waits for the
store write to be confirmed before telling the model an answer was recorded; a
lost `form.created` reports "not recorded" instead of implying success.

### Tests

`tests/test_design_history.py` (32 tests) and
`adapters/opencode/design_history_plugin.test.ts` (25 tests).

## Verification

### 1. Executor: pytest, worktree root

```text
$ uv run --no-project --with pytest python -m pytest -q
403 passed in 14.12s
```

Scope: whole suite, so the new tests plus every pre-existing test. Target
change: commit `c06c5a1`.

### 2. Executor: bun

```text
$ bun test adapters/opencode/design_history_plugin.test.ts
bun test v1.4.5 (a7733435c)
 25 pass
 0 fail
 74 expect() calls
Ran 25 tests across 1 file. [223.00ms]
```

Scope: adapter unit tests only (presentation, correlation, redelivery, secret,
cancel, checkout isolation, event filtering, permission-denial reporting).

### 3. Real-machine trial — real OpenCode V2, disposable repo

Version: `opencode v2.2.7` (`/Users/h-uma/.opencode/bin/opencode`). Disposable
repo: `/private/…/T/opencode/trial/repo`, `git init`, `.gitignore` = `.sdd/`.
Server: `opencode serve --port 4802 --hostname 127.0.0.1`.

The trial installed the real adapter as `.opencode/plugins/trial_adapter.ts`,
called the adapter's registered `design_question` tool with a real session
context, and answered the resulting native form from a **separate process**
through `POST /api/session/{id}/form/{id}/reply` — no model turn, no chat
transcription.

Adapter log (actual, final run after `a9a6be9`):

```text
setup
session=ses_e0bcacf67ffeGU364emR0cMdV7 tool=true
plugin: design history: the host is evaluating a design question permission
result={"output":"The design question form was answered and recorded in the design history (2/2 questions). The answer values are intentionally not repeated here."}
```

Answering process (actual):

```text
SEEN frm_1f435309b0014ndT1j0P4ETbZi ['q0', 'q1']
REPLY 204
```

Search from a separate process, in the repo:

```text
### by case
status: ok pairs: 2
  checkout-cancel.q1-削除は取り消せますか | answered | 取り消せる | opts: ['取り消せる', '取り消せない']
  checkout-cancel.q2-対象外はありますか | answered | 監査ログだけ残す | opts: []

### by Japanese keyword 監査
ok [('checkout-cancel.q2-対象外はありますか', '監査ログだけ残す')]

### by question id
ok 1
```

`grep -c "取り消せる\|監査ログ"` over the adapter log: **0** occurrences — the
answer text never reached the model-facing side.

### 4. Git exclusion

Unignored repo (`.gitignore` absent), actual:

```text
git-check rc=6
record rc=6
no db (good)
search status: no-database
no db after search (good)
```

### 5. Other repository isolation

```text
other repo sees: no-matches 0      # foreign case not visible here
original repo sees its own: ok 2
```

### 6. Re-delivery

```text
answers before=2 after=2
```

A repeated `record` with the same event/answer digest did not create a second
revision.

### 7. Cancel vs answered

```text
[('cancelled', ['cancelled'])]
```

Cancel is a distinct state with no answer value, not an empty agreement.

### 8. Search with no database

```text
search status: no-database
no db after search (good)
```

### 9. Secret handling

```text
recorded: [], omitted: ["tok"]
results: 1 omissions: [{'reason': 'secret-detected', ...}]
leak: False
```

### 10. Permission denial and tool-output shape (found and fixed during this task)

Live, before the fix: `agent=general error Tool.Error: Permission denied: question`,
and the hook's returned `{effect:"allow"}` was ignored (the dispatcher runs the
callback, then returns the original object). After the fix the adapter reports a
host refusal, and a bun test pins that behavior. With
`opencode.json` → `{"permission":{"question":"allow"}}` the full loop above
succeeds.

Live model call against a probe tool, before `a9a6be9`:

```text
probe_bare_string({})    → a is not an Object. (evaluating '"output"in a')
probe_obj_no_schema({})  → Tool result declared output without an output schema
```

After declaring `output: { type: "string" }` and returning `{ output }`, the
adapter's tool registers and its result encodes (the run above). A bun test
asserts `tool.output` equals `{ type: "string" }`.

Refinement from an independent cross-check on the committed revision: the
schema shape only has to be a *plain JSON Schema*; both
`{ type: "string" }` and `{ type: "object", properties: { output: … } }` are
accepted and both encode `{ output }`. A `~standard`-style wrapper
(`{"~standard": {version, vendor, jsonSchema, validate}}`) is **not** accepted —
the host expects that member to be a map of functions, and a wrong shape is
rejected silently at registration, so the tool disappears from the catalog
rather than failing loudly. Keep the plain JSON Schema.

## Independent verification of the committed revision

Re-run separately against `a9a6be9` (`git archive HEAD`) in a fresh disposable
repo `/private/…/T/opencode/dh-live`, `opencode v2.2.7`, so the checks below do
not depend on the earlier trial's state.

```text
$ curl -X POST /api/session/$SID/prompt   # model calls tools.design_question(...)
# pending form, observed via GET /api/session/$SID/form:
[('frm_1f4397c56001w1yP1k3StQNCee', 'sdd_design:a0ce4e601963dea5483375ac',
  [('q0', '削除'), ('q1', '移行')])]
$ curl -X POST .../$FORM/reply -d '{"answer":{"q0":"取り消せる","q1":"既存の設定ファイルを手で移す必要がある"}}'
REPLY 204

$ python3 scripts/design-history search --case live-checkout-cancel
live-checkout-cancel.q1-削除は取り消せますか | answered | ['取り消せる']
live-checkout-cancel.q2-移行で困ることは何ですか | answered | ['既存の設定ファイルを手で移す必要がある']
```

The `sdd_design:` prefix proves the form is the plugin's own; a select answer and
a free-text answer were both stored with no model turn transcribing them. In
the session transcript, the free-text answer string appears **only** in the
user-side tool input that I authored; it is absent from every tool result, so
the model never received the answer value.

Separately re-checked on the same revision:

```text
cancel:   live-cancel.q1-この確認は取り消しますか | cancelled | [('cancelled', None)]
git:      git-check rc=6 (not-ignored); search status no-database; no .sdd/ created
other repo: own=ok 2, other=no-database 0
redelivery: record rc=0 recorded=[]; answers before=3 after=3
secret:   recorded=[] omitted=['…q1…']; secret bytes in db: False; omission reason secret-detected
read-only: sha256 db before == after search (UNCHANGED)
git state: .gitignore:4:.sdd/ matches; ls-files reports the db untracked
```

## Decisions affecting later phases

- **Storage**: `scripts/sddlib/design_history.py` with tables
  `design_form`/`design_question`/`design_answer`/`design_omission`/`recorder_status`.
  Answer identity is `(question_pk, digest)` + `revision`; a correction is a new
  revision. Task 2 must reuse this, not re-derive it.
- **Question IDs**: `questionIDFor()` = explicit ID, else a NFKC slug of the
  question text (`checkout-cancel.q1-削除は取り消せますか`). Task 2's import must
  produce the same shape to stay searchable alongside live records.
- **Source values**: `opencode.form.created`, `opencode.form.replied`,
  `opencode.form.cancelled`, `opencode.plugin`.
- **Failure states**: `recorder_status` rows with `active`, `cancelled`,
  `event-loss`, `stopped`, `error`. Search returns `recording-unavailable`
  instead of a bare empty result when the recorder is stopped or failed.
- **Search contract**: JSON `{status, detail, database, recorder, filters,
  results, omissions}`; exit 0 ok, 3 no-matches, 4 no-database, 5 unavailable,
  6 Git-refused. Task 3 must branch on `status`, not on an empty `results`.
- **Git-exclusion and secret handling** are enforced in the store, not the
  adapter, so Task 2's importer inherits them for free.
- **Canonical spec**: `docs/sdd/specs/2026-11-19-design-interview-history-design.md`
  was **not** updated. The implementation matches it; the only new facts are
  host-API evidence, recorded here and in the ground-truth note correction
  above, not spec changes.

## Files changed (commits `c06c5a1`, `a9a6be9`)

- `scripts/sddlib/design_history.py` (new)
- `scripts/sddlib/design_history_cli.py` (new)
- `scripts/design-history` (new, executable)
- `adapters/opencode/design_history_plugin.ts` (new)
- `adapters/opencode/design_history_plugin.test.ts` (new)
- `tests/test_design_history.py` (new)

`adapters/opencode/html_docs_plugin.ts` and `.test.ts` were not modified.
Neither commit touches `skills/`, `README.md`, existing specs, or the plan.

## Authorship and collision (disclosed, not hidden)

Two OpenCode sessions ran this same Task 1 brief against this same worktree
simultaneously (`ses_e0c1cb7a0ffeqNGSG418xhDInp`, mine, and
`ses_e0c1d1f9cffeGgVscEiEwAdAOU`). The sibling repeatedly overwrote
`design_history.py`, `design_history_cli.py`, and the adapter between 22:46 and
23:07 while I was working. I stopped writing to avoid destroying in-flight work,
then — after the sibling went idle and the tree stayed stable — verified the
surviving implementation end to end myself and fixed two real defects in it (the
false permission-grant claim, and a tool return shape that crashed the host
dispatcher). The committed code is therefore a mix of both sessions' work; every
claim in this report was re-verified by me against `c06c5a1` + `a9a6be9`, not
inherited from a report.

Root cause is worth fixing for later tasks: dispatch one worker per worktree, or
give each worker its own worktree, otherwise Task 2 and Task 3 can collide the
same way.

## Notes and concerns

- `detail.json`, `detail2.json`, and `serve.log` are untracked leftovers from the
  controller's earlier probe. `serve.log` contains a **server password**; they
  are not part of this task and were deliberately left out of the commit. They
  should be deleted, not committed.
- The disposable trial repo and probe repos are under
  `/private/…/T/opencode/`; they contain no user data, no credentials beyond the
  throwaway test server password, and no session transcripts.
- The store trusts the adapter's `checkout` argument after the precheck. A
  hostile local process could still pass a different checkout; this is the same
  trust boundary as the existing CLI tools and is not elevated by this change.
- Git exclusion is not access control. The database is created with the default
  file mode (`0644` under the usual umask), and nothing in the implementation
  sets a stricter mode; treating `.gitignore` as secrecy would be wrong. The
  README wording for this belongs to Task 3.
- `design_question` currently requires the agent to be permitted to use the host
  `question` tool. If a consuming repo denies `question`, design history cannot
  record, and the adapter now says exactly that. Task 3's README should document
  the required `permission.question` setting.
