# sdd

Skill pack for spec-driven development on Cursor, Claude Code, and OpenCode.

Markdown remains the source of truth. A Target document has a separately authored Agent-authored HTML companion beside it. Install this repository as a whole pack; do not copy a single `SKILL.md`.

There is no automatic HTML generation or repair. The agent owns the companion's semantic structure and visual hierarchy, while the shared stylesheet owns presentation. Companions are static, safe to open locally, and are not a place to embed scripts.

Python 3.11+ is required for `scripts/`. `gh` is required only for finish options 2 and 4.

## Artifact Contract

The Target documents are exactly:

- `CONTEXT.md`, paired with adjacent `CONTEXT.html`
- `docs/adr/*.md`, each paired with an adjacent same-stem `.html`
- `docs/sdd/specs/*.md`, each paired with an adjacent same-stem `.html`
- `docs/sdd/plans/*.md`, each paired with an adjacent same-stem `.html`

Other Markdown files, including `README.md`, skill text, and `docs/superpowers/`, are outside this synchronization contract. The shared stylesheet is `docs/sdd/assets/sdd.css`; copy the pack-owned `assets/sdd.css` there when setting up a consuming repository.

Every Agent-authored HTML companion records the exact current Canonical Markdown digest in its head:

```html
<meta name="sdd-source-digest" content="sha256:<64 lowercase hexadecimal characters>">
```

The digest covers the exact Markdown bytes, including line endings, trailing whitespace, and the final newline. Each companion must also have a language-specific `html` element, UTF-8 charset, viewport, title, restrictive CSP, one shared CSS link, a leading skip link, a document-kind `header`, and a focusable `main`. Preserve source facts, visible content, headings, code, lists, tables, links, and reading order. Use only static semantic HTML and same-repository resources.

## Semantic reconstruction (semantic-v1)

The strict contract above is the default and is unchanged. A Target can opt in to the additive `semantic-v1` contract by putting `<meta name="sdd-html-contract" content="semantic-v1">` in its companion head. An unknown contract value is rejected; it never falls back to strict inspection silently.

`scripts/sddlib/html_units.py` is the common lossless source scanner. It splits the exact Markdown bytes into source units for headings, paragraphs, nested list items, table header and body cells, fenced and indented code, inline code, links, images, and glossary terms and Avoid entries. Each unit records its kind, parent, stable ID, and half-open UTF-8 byte range in the original bytes, and is bound to the exact source digest. Unsupported Markdown syntax is reported explicitly instead of being dropped.

A `semantic-v1` companion embeds a non-executing JSON provenance map in `template#sdd-provenance`. Version 1 fixes the source path and digest, unit definitions, many-to-many mappings to visible representation target IDs, strict-preservation targets, supplementary representations and their source units, and calculations with inputs, formula, and result. `scripts/sddlib/html_semantic.py` performs the static coverage and exact-preservation pass: it compares the compact unit set against a fresh scan by ID, kind, range, digest, and parent; requires every unit to map to a visible `main` target that is not hidden, aria-hidden, or template-only; and checks code, paths, identifiers, link destinations, glossary terms, Avoid entries, numbers, units, comparison operators, and restricted `sum` / `count` / `ratio` / `scale` calculations with explicit inputs and recomputed results. A passing result is labelled `assurance: static-only`; it does not prove semantic preservation. Receipts under `docs/sdd/html-evidence/` are JSON auxiliary artifacts, not a new Target kind. The canonical filename is `docs/sdd/html-evidence/<sha256 of the canonical Target-relative path as UTF-8 bytes>.json`; `canonical_receipt_path()` and `Target.receipt_relative` derive it. Their version 1 schema fixes the source and HTML digests, CSS / resource / policy fingerprints, settings / rubric / profile versions, generation and H2 references, verification results, and per-condition decisions with evidence references. These schemas reject unknown fields, unknown versions, duplicate IDs, missing references, and missing required fields. Structural receipt checks are not proof of meaning preservation or model accuracy.

### Static SVG figures

`scripts/sddlib/html_svg.py` checks every SVG in a companion against a fixed static allowlist. Script, event attributes, `foreignObject`, animation, `style` attributes and elements, hyperlinks, and external URLs are rejected. The allowlist covers static groups, markers, shapes, and text; document-specific CSS is not allowed, so figures use the shared `sdd-figure`, `sdd-figure-plot`, `sdd-figure-svg`, `sdd-figure-explanation`, `sdd-data-table`, and `sdd-evidence` classes. The total SVG element count per document is limited to 5,000; an over-limit companion fails with a request to simplify it and is never truncated.

A supplementary `diagram` or `graph` in `template#sdd-provenance` must target a visible `figure` with a non-empty `figcaption`, a visible text explanation, and a data table whose text repeats the diagram labels or the graph series, axes, units, and values. Diagram node and edge entries name the source units that support them. Graph series and axes name their evidence units and unit labels. Colour can decorate a figure but cannot be the only carrier of meaning; labels must be visible in the SVG text and repeated in the table. These are static structural checks: the validator does not render, lay out, or judge a figure.

## Install

Set the pack root for commands that run against a consuming repository:

```bash
export SDD_PACK_ROOT=/absolute/path/to/sdd
```

### Claude Code

From this repository:

```bash
claude --plugin-dir .
```

After it loads, skills are namespaced by the plugin name `sdd`. Invoke `/sdd:sdd-design` (and `/sdd:sdd-plan`, `/sdd:sdd-execute`, `/sdd:sdd-goal`, `/sdd:sdd-finish`, `/sdd:sdd-review-fix`). The pack's `hooks/hooks.json` is the Claude Code plugin registration. For a repo-local registration, use `adapters/claude/hooks.json.example` and keep the adapter at `adapters/claude/html_docs_hook.py`.

### Cursor

Install this repo as a local plugin, then reload:

```bash
mkdir -p ~/.cursor/plugins/local
ln -sfn "$(pwd)" ~/.cursor/plugins/local/sdd
```

Then Command Palette -> **Developer: Reload Window**. Invoke `/sdd-design` (and `/sdd-goal`, `/sdd-review-fix`). Cursor does not prefix the plugin name. If the skill is missing after reload, confirm `~/.cursor/plugins/local/sdd/.cursor-plugin/plugin.json` exists.

Enable the Cursor Agent edit hook explicitly with `adapters/cursor/hooks.json.example`. It registers `preToolUse`, `afterFileEdit`, and `stop` with `failClosed: true` and the project-root-relative `adapters/cursor/html_docs_hook.py` command.

### OpenCode

Explicitly register `adapters/opencode/html_docs_plugin.ts` as `.opencode/plugins/html_docs_plugin.ts` in the consuming repository. It checks `tool.execute.before` before file edits and validates `file.edited` events afterward. Keep the plugin's relative access to the pack's `scripts/html-docs` entrypoint intact.

The built-in OpenCode `write` tool has no `bootstrap_paths` argument. For a missing or metadata-less Target companion, the plugin invokes the bounded `bootstrap` check internally before the write, so no host-specific argument is required.

The host registrations are opt-in. The pack does not install host configuration automatically. The examples live under `adapters/`; copy or link the required adapter and registration into the consuming repository without changing the paths expected by `html-docs doctor`.

## Authoring Workflow

1. Edit the Canonical Markdown in one native file-edit operation.
2. After that edit succeeds, compute the current digest over the exact Markdown bytes and put it in the separately authored adjacent HTML companion. Never edit the Markdown and its companion in one tool call or patch.
3. Preserve the source facts and order. Add only permitted presentation, metadata, labels, navigation, and semantic wrappers. Do not summarize, omit, invent, reorder, or trust raw HTML from Markdown.
4. Validate the pair from the consuming repository:

```bash
python3 "$SDD_PACK_ROOT/scripts/html-docs" check --paths CONTEXT.md CONTEXT.html
```

Use the corresponding Markdown and HTML paths for ADRs, specs, and plans. `html-docs edit-check` is the host-facing permission command; it accepts JSON on stdin and returns JSON with `decision`, `message`, `paths`, and expected digest fields. The common policy owns target resolution, digest, document, security, and freshness decisions; adapters only translate host events.

The normal Edit-order guarantee is Markdown first, then a separate HTML operation. HTML-only changes are rejected. Multiple Markdown edits may happen before one HTML update, but the companion must use the final digest. A Markdown edit after an HTML update makes that companion stale again. Shared CSS edits do not change the Markdown or HTML digest.

## Bootstrap

For an existing Target document whose companion is missing or lacks digest metadata, request bounded HTML bootstrap explicitly:

```bash
python3 "$SDD_PACK_ROOT/scripts/html-docs" bootstrap CONTEXT.md
```

Pass only the requested existing Target Markdown paths. HTML bootstrap reports current expected digests and grants bounded permission; it does not create HTML. Author every companion in a separate operation, then validate it with `html-docs check`. Normal mode never treats a missing companion as permission to write HTML.

## Doctor

Run this from the consuming repository after explicitly enabling Cursor, Claude Code, and OpenCode:

```bash
python3 "$SDD_PACK_ROOT/scripts/html-docs" doctor
```

The result reports one registration for each host. Missing, disabled, unreadable, or incompatible registrations are setup violations and return a non-zero result; `doctor` never writes configuration. A configured fixture repository should report enabled registrations at `.cursor/hooks.json`, `.claude/hooks.json` (or `hooks/hooks.json`), and `.opencode/plugins/html_docs_plugin.ts`.

## Host API

`html-docs host-api` exposes a version 1 stdin/stdout JSON protocol for hosts that validate authored candidates as if they were at their official paths. It reads one JSON request from stdin and writes one JSON envelope to stdout. The document root is the caller's current working directory. All content is supplied in memory as standard base64 bytes keyed by canonical repository-relative POSIX paths; the API never reads supplied candidate HTML from disk and never writes files or creates HTML.

Operations:

- `capabilities` returns the protocol and policy versions, limits, stage semantics, and the no-write / no-bootstrap contract.
- `discover` resolves supplied paths to Target source and companion pairs.
- `source-units` returns the version 1 source index and scanner-derived strict requirements for supplied Markdown bytes.
- `candidate-check` runs the common static validator for a Target pair. `stage: "structural"` performs static checks only and is never a final pass; it rejects a receipt. `stage: "final"` also requires a supplied receipt under `docs/sdd/html-evidence/` and binds the receipt's source, HTML, CSS, resource, policy, verification, and condition fields to the supplied input digests. A final receipt requires a `semantic-v1` companion.

Requests carry `version: 1`, `operation`, an optional `timeout_ms`, and an `inputs` object mapping relative paths to base64 bytes. `candidate-check` also carries `path`, `stage`, and, for final, `receipt`. Responses are `{"ok":true,"version":1,"operation":...,"root":...,"result":{...}}` or `{"ok":false,...,"error":{"code":...,"message":...}}`. Protocol and input failures exit `2` with a diagnostic on stderr. A static or binding denial has `ok: true`, `result.decision: "deny"`, and exit `1`; any non-zero exit also writes a one-line diagnostic to stderr. Markdown sources are limited to 2 MiB, candidate HTML to 8 MiB, and each input to 16 MiB within a 64 MiB request.

Error codes are stable machine-readable names, including `path-escape`, `path-invalid`, `unsupported-version`, `unsupported-schema`, `invalid-json`, `invalid-base64`, `invalid-encoding`, `missing-field`, `missing-input`, `input-too-large`, `too-many-inputs`, `too-many-paths`, `invalid-timeout`, `timeout`, `duplicate-input`, `not-target`, `invalid-stage`, `invalid-receipt-path`, `receipt-invalid-json`, `receipt-schema`, `unknown-field`, and `unknown-operation`. Errors include the affected path or details when they are known.

The API does not bootstrap, render, assess meaning, call a model, or decide publication. Bootstrap remains the explicit `html-docs bootstrap` operation. The receipt path is supplied by the caller; `sddlib.html_policy.canonical_receipt_path()` (or `Target.receipt_relative`) derives the canonical filename that Git and CI require. `capabilities` reports a policy version and a fingerprint over the static policy modules so a host can refuse a mismatched checkout.

## Git And CI

Install the local HTML freshness gate without silently replacing an existing pre-commit hook:

```bash
git_dir=$(git rev-parse --git-dir)
if [ -e "$git_dir/hooks/pre-commit" ]; then
  mv "$git_dir/hooks/pre-commit" "$git_dir/hooks/pre-commit.sdd-existing"
fi
ln -sfn "$SDD_PACK_ROOT/scripts/sdd-html-pre-commit" "$git_dir/hooks/pre-commit"
```

Keep `SDD_PACK_ROOT` available in the environment used by Git. The versioned wrapper runs `html-docs check --staged` first, then invokes `SDD_PRE_COMMIT_DELEGATE` or `$GIT_DIR/hooks/pre-commit.sdd-existing` with its arguments. Existing pre-commit hooks are preserved; the wrapper does not delete or edit them.

Provider-neutral CI runs from the checkout tree with `BASE_REF` set to the PR base commit or branch:

```bash
python3 "$SDD_PACK_ROOT/scripts/html-docs" check --base "$BASE_REF"
```

### Semantic receipt gate

`html-docs check` requires a version 1 receipt for every `semantic-v1` companion in the checked tree. The receipt must bind the exact source and HTML bytes, every CSS and resource fingerprint, the shared stylesheet, the canonical policy version and digest, and the recorded settings / rubric / profile identities. All verification checks must pass and all four conditions must be `met`. When a receipt or its artifacts change, the receipt must name a new generation whose parent is the previous generation; this distinguishes a re-evaluation from an edited copy. A legitimate same-source re-evaluation may change only the HTML when it stages the new receipt and generation. Strict companions keep the existing Markdown-before-HTML rule: an HTML-only change is still denied.

`check --staged` reads the Git index for source, companion, receipt, CSS, and resource bytes and never substitutes the worktree. A receipt that exists only in the worktree, a partially staged pair, a missing canonical receipt, an unknown receipt version, or any digest or fingerprint mismatch is denied. `--base` reads the checkout tree and compares the new receipt against the receipt at the merge base. Moving a Target pair requires a receipt at the new canonical path; old receipts may remain orphaned, but an orphaned HTML companion is not an exemption from the strict delete contract.

Receipt binding is static-only. CI does not call a model or network service, does not authenticate the receipt, and does not re-evaluate meaning, image quality, H2 approval, or the truth of the recorded profile and rubric identities. A recorded profile or rubric change must also change the settings version, which is the approval identity H3 bundles those choices under. H3 must compare repository receipts with its own saved evaluation and approvals. Trusted callers can pass `expected_versions` to `check_freshness()` or `bind_receipt()` when they have the approved identities.

CI must not start a host application or subagent, call a network service, or use `gh`. A failed local hook does not make CI pass, and a failed CI check prevents merge until every affected Target pair is corrected. Deletion or movement is valid only when Markdown and its companion move or delete together.

Host hooks provide best-effort edit ordering only. Shell, MCP, manual, and hook-disabled writes are outside direct ordering control and are caught by the Git / CI gate when they affect a commit; they are not forcibly ordered.

## Pipeline

sdd-design -> sdd-plan -> sdd-execute -> sdd-finish

Bounded work can be implemented in this session without a spec or plan. It still asks once whether to create a worktree. TDD is a method chosen by the behavior change and regression risk, not a gate in bounded work or in execute.

`sdd-execute` dispatches one isolated subagent per plan Task. The controller judges the Task complete from its deliverables and verification evidence, reuses evidence that still covers the final state, and starts the next Task. There is no implementer/reviewer loop and no automatic review gate; review happens when the human asks.

`sdd-finish` needs full-suite evidence that covers the final state. Reuse a valid record when it covers that state; otherwise run the suite.

`sdd-goal` is the portable analog of Claude Code `/goal`: set a decidable completion condition and keep working until it holds. On Cursor invoke `/sdd-goal`. On Claude Code, native `/goal` still provides the overlay; `/sdd:sdd-goal` is the same work loop, and uses `sdd-execute` when the condition is a plan.

After stacked PRs exist, GitHub review fixes use `sdd-review-fix` (existing `sdd-stack/task-N` only). Land from the bottom on GitHub.

| Skill | When |
|---|---|
| sdd-review-fix | GitHub review on an open stacked PR after finish option 4 |

## Judgment And Handoff

Confirm with the human only for unagreed user-facing behavior, permissions and safety, destructive operations, external side effects beyond an existing authorization, and costly or irreversible changes. Investigate repository facts before asking. Within the agreed spec and constraints, decide reversible implementation details such as naming, internal structure, component-local state, and the order of investigation, implementation, and tests. Record only the assumptions that affect later work.

A supporting skill supplies a method. It does not override the agreed spec, the constraints, or the calling skill's execution contract, and it does not add its own mandatory TDD rule, review gate, or global stop condition.

### One goal, multiple specs

When work needs multiple specs, including separate backend and frontend phases,
`sdd-design` first saves
`docs/sdd/specs/YYYY-MM-DD-<topic>-roadmap.md` and its separately authored HTML
companion, validates the pair, and waits for human approval before detailed
individual design. The Spec roadmap records the overall goal and completion
criteria, each spec's scope and completion criteria, dependencies and design
order, contract ownership, important unresolved items, and the next spec to
design. It is not a detailed design, implementation plan, or calendar.

After approval, design the selected individual spec through the normal flow.
Roadmap approval does not approve that spec or authorize implementation. Later
design sessions read and reference the roadmap, add actual spec paths as they
become available, and update changed boundaries or dependencies. Important
changes to the agreed split or ordering need confirmation; adding links does
not. Shared-contract details remain in their owning canonical spec, not in a
second shared-spec document. `sdd-plan` accepts an approved individual spec,
never the roadmap alone. Single-spec work and bounded changes do not require
a roadmap.

### Backend shared contract to a separate frontend session

1. In the backend design, identify the contract a later phase will consume and record it in the backend spec: expected user operations and results, the API or data meaning the later phase depends on, permissions, state changes, error behavior, and settled versus undecided items. Ask about shared-contract decisions that block dependent work before implementing against them. For example, list ordering, pagination, and whether a delete can be cancelled or undone belong before the backend work that depends on them.
2. During backend implementation, when an agreed shared-contract item changes, reflect the decision in the canonical backend spec before declaring the backend complete and handing it off. Do not leave it only in `.sdd/progress.md`, a task report, or conversation, and do not rewrite an already recorded task range.
3. Start the frontend design in a separate session. Read the canonical backend spec plus the implementation and tests it names. Reference the spec path and the dependent scope in the frontend spec; do not create a second authority. Do not re-ask facts that the spec, code, or tests already settle. Confirm only important unresolved items, contradictions, or new requirements, with their impact.

### UI-only change

A UI-only change does not need a fictional backend spec or a new dependency. When the change has no later phase, keep placement, colors, component-local state, and similar choices inside the agreed constraints. Decide them in the frontend design or implementation, record only assumptions that affect later work, and do not add an approval round for each local choice. If a local choice would change a shared contract, treat it as a contract change instead.

## Supporting Superpowers skills

This pack vendors Superpowers 6.3.0 skills used during implementation. You do not need the Superpowers plugin. Pipeline work still uses sdd-* (not brainstorming / writing-plans / executing-plans / subagent-driven-development / finishing-a-development-branch).

| Skill | When |
|---|---|
| test-driven-development | Chosen by behavior and regression risk; optional in bounded work and execute |
| systematic-debugging | Bugs, test failures, unexpected behavior |
| verification-before-completion | Before a completion claim or sdd-finish; evidence must cover the final state |
| using-git-worktrees | Isolate: optional before implementation; if creation fails, ask for another mechanism or explicit in-place permission. Attach: existing `sdd-stack/task-N` from sdd-review-fix (`-b` forbidden) |
| requesting-code-review | Reviews the human asked for (not an execute or finish gate) |
| receiving-code-review | Acting on review feedback |
| dispatching-parallel-agents | Independent investigations (not plan implementers) |

## Manual Check

1. In a throwaway git repo, invoke sdd-design, answer one glossary question, author `CONTEXT.md` and its adjacent `CONTEXT.html` separately, and run `html-docs check`.
2. On Cursor, confirm `/sdd-design` and `/sdd-goal` are visible and that `test-driven-development` / `systematic-debugging` are visible. On Claude Code, confirm `/sdd:sdd-design`, `/sdd:sdd-goal`, and the same supporting skills.
3. `python3 scripts/stack-prs --help` shows `--dry-run` and exits 0.
4. After stacked PRs exist, `/sdd-review-fix` (Claude Code: `/sdd:sdd-review-fix`) is visible. Confirm the skill forbids `-b`, `gh pr merge`, and `stack-prs` re-run.
