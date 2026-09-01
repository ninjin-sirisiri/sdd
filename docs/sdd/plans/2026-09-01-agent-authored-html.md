# Agent-authored HTML Implementation Plan

**Goal:** Replace mechanical Markdown-to-HTML rendering with validated, agent-authored HTML companions while preserving Markdown as the canonical source.

**Architecture:** A stateless Python policy owns target resolution, exact byte digests, edit permissions, HTML validation, and Git freshness decisions. The `html-docs` CLI exposes that policy to thin Cursor, Claude Code, OpenCode, pre-commit, and CI adapters; agents author the final HTML and the shared CSS supplies the visual system.

**Tech Stack:** Python 3.11 standard library, POSIX shell, static semantic HTML, shared CSS, Cursor/Claude Code/OpenCode hook APIs, Git, and pytest with temporary repositories.

**Spec:** `docs/sdd/specs/2026-09-01-agent-authored-html-design.md`

## Global Constraints

- The Target documents are exactly:
- `CONTEXT.md`
- `docs/adr/*.md`
- `docs/sdd/specs/*.md`
- `docs/sdd/plans/*.md`
- Each Target document pairs with the adjacent file having the same relative path and stem and the `.html` suffix.
- The shared stylesheet is `docs/sdd/assets/sdd.css`.
- Other Markdown files are outside this synchronization contract.
- Markdown remains the source of truth.
- Agent-authored HTML is a human-facing companion whose structure and visual hierarchy are deliberately designed by the agent, not copied from a generic Markdown preview.
- `scripts/sddlib/html_policy.py` is the single source for:
- Target document and adjacent companion resolution.
- Exact UTF-8 byte SHA-256 digests.
- Normal and bootstrap edit permissions.
- HTML metadata, security, structural, and text-fidelity validation.
- Staged-tree and PR-diff freshness checks.
- Host-neutral decisions, messages, affected paths, and exit statuses.
- The `scripts/html-docs` CLI exposes `edit-check`, `check`, `bootstrap`, and `doctor`.
- It accepts JSON on stdin and returns JSON on stdout with `decision`, `message`, `paths`, and expected digest fields.
- Exit code `0` means allow or pass, `1` means a synchronization or document violation, and `2` means invalid arguments, unavailable configuration, or an execution failure.
- The adapters translate each host payload to the common CLI contract and translate the result back to the host's allow / deny / feedback format.
- They do not implement digest or document logic themselves.
- Each adapter is explicitly enabled by the user; `html-docs doctor` reports missing, disabled, or incompatible registration.
- The local pre-commit wrapper passes the staged tree to `html-docs check`.
- CI passes the PR base reference and checkout tree to the same command.
- The pack provides provider-neutral commands and examples, not an automatically installed workflow.
- Existing pre-commit hooks are preserved and invoked by the wrapper rather than silently replaced.
- A Target Markdown edit succeeds before its HTML companion can be edited.
- A single tool call or patch cannot edit both files, even when its final content would be valid.
- HTML-only changes are rejected, including a visual-only design edit when the source digest is already current.
- Multiple Markdown edits may occur before one HTML update; the HTML must use the final digest.
- A Markdown edit after an HTML update makes that HTML stale again.
- Shared CSS may be edited without changing the Markdown or HTML digest.
- Deletion or movement is valid only when Markdown and its companion move or delete together.
- Multiple Target documents are checked independently, and a partial set fails the commit.
- Every companion contains a language-specific `html` element, charset, viewport, title, restrictive CSP, exactly one `sdd-source-digest` meta, and a shared CSS link.
- The body starts with a skip link.
- A `header` identifies the document kind.
- A `main` element has the content target ID and is programmatically focusable.
- Data tables include a caption and scoped header cells; when Markdown lacks a caption, the agent may derive a descriptive caption from the nearby heading and column labels without adding facts.
- When h2 or h3 headings exist, a named navigation outline is provided in an `aside`.
- It is sticky where the viewport permits and falls back to normal flow.
- On narrow screens the outline is exposed through native `details`; no JavaScript is required.
- When there are no h2 or h3 headings, no empty `nav` or `aside` is emitted.
- The agent preserves source facts, visible body content, headings, code, lists, tables, links, and their reading order.
- It may add navigation, skip-link text, document-kind labels, accessibility labels, and metadata, but may not summarize, omit, invent, or reorder source content.
- Glossary terms use `dl`, `dt`, and `dd`; an `_Avoid_` paragraph stays inside the related `dd` as a labeled secondary paragraph.
- An ADR remains a compact decision article and does not gain headings that are absent from Markdown.
- Spec h2 headings become semantic section blocks.
- Each plan `## Task N:` becomes an independent article with a visually prominent number and title, a left rule or number rail, and no invented status.
- Labeled lead paragraphs such as `Goal`, `Architecture`, and `Classification` become metadata / lead blocks without changing their values.
- Unknown source shapes use ordinary semantic HTML.
- Source heading levels are retained, including multiple h1 or skipped levels; those conditions produce warnings rather than automatic corrections.
- Heading IDs are stable slugs derived from heading text, with occurrence-order suffixes for duplicates, and all outline links resolve to those IDs.
- The shared system uses system fonts, relative type and spacing tokens, semantic light / dark colors, and a 60--75ch main reading measure.
- Heading rank is expressed by type scale and spacing, while section boundaries use whitespace, rules, and restrained accents.
- Document kind changes label, accent, and semantic block treatment, not the entire palette, font, or layout.
- Gradients, excessive shadows, all-block card layouts, color-only hierarchy, external fonts, and required animation are prohibited.
- Text and boundaries meet accessible contrast.
- Tables and long code scroll locally rather than causing page-wide horizontal overflow.
- The layout supports browser zoom and `prefers-reduced-motion`.
- The agent selects the dominant prose language for `html lang` and generated UI labels.
- Code and proper names do not determine the language.
- `und` is not accepted for a Target document.
- Only static semantic HTML and same-repository resources are allowed.
- Scripts, event attributes, executable inline content, frames, external stylesheets, external fonts, and network-dependent resources are prohibited.
- The restrictive CSP denies all unspecified sources and permits only the approved local stylesheet and local / data images.
- Raw HTML from Markdown is represented as text rather than trusted executable markup.
- The digest is computed over the exact Markdown file bytes, including line endings, trailing whitespace, and the final newline.
- Timestamps, Git commit identity, and sidecar state are not freshness evidence.
- The policy is stateless and reads the current Markdown and HTML on every event.
- `html-docs bootstrap <explicit paths>` enumerates only the requested existing Target documents whose companions are missing or lack digest metadata and reports their current digests.
- It grants a bounded bootstrap mode for those HTML paths, but does not create HTML.
- The agent authors each companion in a separate operation; validator success is required before the migration is committed.
- Normal mode never treats a missing companion as permission to write HTML.
- A Markdown edit is not rolled back because HTML authoring failed.
- The policy never generates or silently repairs HTML.
- A failed or incomplete HTML authoring attempt does not count as synchronized; an existing valid companion is not replaced by an unvalidated candidate.
- A missing, stale, unsafe, structurally invalid, or text-incomplete companion produces a clear path-specific message and a non-zero check result.
- A host adapter that is missing, disabled, receives unknown payload fields, times out, or cannot invoke the policy denies HTML editing and reports setup guidance.
- Markdown editing remains available.
- External or manual writes are outside direct ordering control and are caught by the Git / CI gate when they affect a commit.
- A failed local hook does not make CI pass.
- A failed CI check prevents merge until the pair is corrected.
- The common policy owns decisions; adapters do not duplicate them.
- The agent owns HTML content structure and visual hierarchy; validators do not create or alter it.
- Markdown owns facts and order; HTML owns presentation and semantic wrappers.
- CSS owns shared presentation; HTML does not carry inline or external styling.
- Host hooks provide best-effort edit ordering; Git / CI provides the commit boundary.

## File Structure

| Path | Responsibility |
|---|---|
| `scripts/sddlib/html_policy.py` | Target resolution, byte digests, edit permissions, HTML validation, and host-neutral results |
| `scripts/sddlib/md.py` | Shared Markdown source-text and heading/task extraction helpers used by policy validation |
| `scripts/html-docs` | JSON policy CLI for `edit-check`, `check`, `bootstrap`, and `doctor` |
| `scripts/sdd-html-pre-commit` | Versioned staged-tree wrapper that delegates to an existing hook |
| `adapters/cursor/html_docs_hook.py` | Cursor stdin/stdout hook adapter |
| `adapters/claude/html_docs_hook.py` | Claude Code command-hook adapter |
| `adapters/opencode/html_docs_plugin.ts` | OpenCode plugin adapter for tool-before and file-edited events |
| `adapters/*/fixtures/` | Host payload and response fixtures |
| `assets/sdd.css` | Pack-owned shared document stylesheet |
| `docs/sdd/assets/sdd.css` | Checked-in stylesheet used by the pack's authored HTML |
| `CONTEXT.html`, `docs/adr/*.html`, `docs/sdd/specs/*.html`, `docs/sdd/plans/*.html` | Authored HTML migration with current source digests |
| `tests/test_html_policy.py` | Unit tests for target resolution, digests, permissions, and HTML validation |
| `tests/test_html_docs.py` | CLI, staged-tree, PR-diff, bootstrap, and doctor tests |
| `tests/test_host_adapters.py` | Cursor and Claude Code payload mapping tests |
| `adapters/opencode/html_docs_plugin.test.ts` | OpenCode adapter mapping tests run by Bun |
| `tests/test_sdd_css.py` | Shared CSS contract tests |
| `tests/fixtures/{glossary,adr,spec,plan}/` | Authored structural and unsafe-markup fixtures |
| `README.md` | Installation, explicit setup, hook enablement, and CI instructions |
| `skills/sdd-design/SKILL.md` | Markdown-before-HTML authoring workflow |
| `skills/sdd-plan/SKILL.md` | Plan companion authoring and validation workflow |
| `skills/sdd/SKILL.md` | Pack routing and HTML policy references |
| `scripts/render-docs`, `scripts/sddlib/render.py`, `tests/test_render_docs.py` | Legacy renderer surfaces to remove in Task 8 |

## Task 1: Implement target resolution, digests, and edit permissions

**Files:**

- Create `scripts/sddlib/html_policy.py`.
- Extend `scripts/sddlib/md.py` only with helpers needed to identify visible Markdown source text without changing `task_headings`, `plan_task_numbers`, `extract_task_heading`, or `extract_task` behavior.
- Create `tests/test_html_policy.py`.

**Steps:**

1. Define one target resolver that accepts a repository root and a repository-relative or absolute path. It must recognize only the exact target set in Global Constraints, resolve an adjacent same-stem `.html` companion, reject paths outside the repository, and return a no-op result for unrelated files.
2. Implement `sha256_file(path)` over `Path.read_bytes()` and return lowercase hexadecimal. Do not normalize line endings, whitespace, encoding, or final newlines.
3. Implement strict digest metadata parsing for exactly one `<meta name="sdd-source-digest" content="sha256:<64 lowercase hexadecimal characters>">` element. Missing, duplicate, malformed, or uppercase metadata must be distinguishable for bootstrap and validation messages.
4. Define the host-neutral result shape used by every later task:

   ```json
   {
     "decision": "allow",
     "message": "Markdown changed; author CONTEXT.html separately.",
     "paths": ["CONTEXT.md", "CONTEXT.html"],
     "expected_digests": {"CONTEXT.html": "sha256:<64 lowercase hexadecimal characters>"}
   }
   ```

   `decision` is `allow` or `deny`; `paths` is repository-relative and ordered; `expected_digests` is present for affected companions and empty otherwise.
5. Implement `check_edit(repo_root, paths, bootstrap_paths=(), new_source_paths=())` with these exact decisions: unrelated edits allow; a Target Markdown edit allows and reports its companion plus current digest; a single operation containing both paired paths denies; an HTML edit allows only when an existing companion has a valid digest different from the current Markdown digest; a missing or metadata-less companion denies unless its exact source is in `new_source_paths` from the preceding source-creation event or its exact path is in `bootstrap_paths`; deletion or movement is handled later by the Git diff checker and is not silently allowed by the edit policy.
6. Treat a newly created Target Markdown file as the source edit for its first separate HTML operation, while a missing companion for an existing Markdown file remains denied in normal mode.
7. Reject unknown policy arguments and malformed paths with a structured violation that later maps to exit code `2`; never write files from this module.

**Tests:**

- `uvx --from pytest pytest -q tests/test_html_policy.py`
- Cover exact target matching, adjacent paths, absolute paths, path escape, byte-preserving digests for CRLF/trailing whitespace/final newline, metadata parsing, mixed operations, multiple Markdown edits before HTML, stale-after-source-edit, new-source bootstrap exception, normal missing companion denial, and unrelated/CSS-only no-op allow.

## Task 2: Add the authored HTML validator

**Files:**

- Complete `scripts/sddlib/html_policy.py` with the validator described below.
- Extend `tests/test_html_policy.py`.
- Add or replace fixtures under `tests/fixtures/glossary/`, `tests/fixtures/adr/`, `tests/fixtures/spec/`, and `tests/fixtures/plan/` with authored HTML examples.

**Steps:**

1. Parse HTML with the Python standard library and retain document order, element attributes, text nodes, headings, fragments, landmarks, tables, links, resources, and warnings. A malformed or unbalanced document is a violation.
2. Validate exact digest correspondence, one language `html` element, UTF-8 charset, viewport, title, restrictive CSP, exactly one digest meta, one same-repository stylesheet link to `docs/sdd/assets/sdd.css`, skip link to `main`, document-kind header, and focusable `main`.
3. Reject `script`, `iframe`, `frame`, `object`, `embed`, event attributes, `<style>`, style attributes, external stylesheets, external fonts, network-dependent images/media, executable inline content, and raw executable HTML. Preserve ordinary external source hyperlinks as links because they are source content rather than page resources.
4. Extract visible source content from Markdown without trusting raw HTML and compare it with the text under `main` in order. Ignore only permitted companion labels, navigation text, skip-link text, and document metadata; require code, list, table, link-label, and raw-HTML-as-text content to remain present. Report the first missing or reordered fragment with its source path.
5. Require `caption` and scoped `th` cells for every table. Require stable slug IDs for headings, occurrence-order suffixes for duplicate headings, and fragment targets that resolve. Preserve source heading levels; emit warnings, not failures, for multiple h1 or skipped levels.
6. Require a named `aside`/`nav` outline with native `details` when h2 or h3 exist, and reject empty `aside`/`nav` when they do not. Allow compact ADR pages with only an h1 and no outline.
7. Validate `html lang` as a non-`und` dominant prose language and validate that warnings are returned separately from violations. Do not generate, rewrite, or repair HTML.

**Tests:**

- `uvx --from pytest pytest -q tests/test_html_policy.py`
- Cover glossary `dl`/`dt`/`dd` and `_Avoid_`, ADR decision article without invented headings, spec nested outlines, plan task articles and lead metadata, duplicate headings, missing outlines, unsafe tags/resources, missing table labels, source-text omission/reordering, invalid digest, invalid language, and warning-only heading irregularities.

## Task 3: Implement the `html-docs` CLI

**Files:**

- Create executable `scripts/html-docs` using the existing `task-brief` wrapper pattern.
- Extend `scripts/sddlib/html_policy.py` only through its public policy functions; keep CLI parsing in a small module or the script entrypoint.
- Create `tests/test_html_docs.py`.

**Steps:**

1. Run from the consuming repository root and accept only these JSON stdin keys for `edit-check`: `operation`, `paths`, and optional `bootstrap_paths` and `new_source_paths`. Require `operation` to be `edit`, normalize paths through the shared resolver, print one JSON result plus a newline, and map policy violations to exit code `1` and invalid input/execution failures to `2`.
2. Implement `scripts/html-docs edit-check` as the sole host-facing permission command. It must not edit Markdown, HTML, CSS, configuration, or sidecar state.
3. Implement `scripts/html-docs check --staged` by reading `git diff --cached --name-status --find-renames -z`, and `scripts/html-docs check --base REF` by reading `git diff --name-status --find-renames REF...HEAD -z`. Accept exactly one of `--staged`, `--base REF`, or explicit repository-relative paths for deterministic tests.
4. For each affected Target pair, validate the authored HTML and source digest. Reject Markdown-only changes, HTML-only changes, stale pairs, missing pairs, mixed pair patches, one-sided rename/delete, and partial multi-document changes. Allow CSS-only and unrelated changes. Use Git status data only to decide affected pairs; use current bytes and HTML metadata as freshness evidence.
5. Implement `scripts/html-docs bootstrap PATH...` to enumerate only explicitly requested existing Target Markdown files whose companion is missing or metadata-less, returning current digests without creating files or changing policy state. Reject omitted or non-target paths.
6. Implement `scripts/html-docs doctor` to report a structured status for the Cursor, Claude Code, and OpenCode registrations described in Task 5. Missing, disabled, incompatible, or unreadable registration is a non-zero setup violation, not an automatic enablement.
7. Keep output stable and path-specific so adapters can pass `message`, `paths`, and `expected_digests` through without parsing human prose.

**Tests:**

- `uvx --from pytest pytest -q tests/test_html_docs.py`
- Use temporary Git repositories for staged and `REF...HEAD` diffs, new pairs, multiple pairs, CSS-only changes, HTML-only changes, stale pairs, rename, delete, malformed JSON, unknown fields, bootstrap output, exit codes, and doctor registration states.

## Task 4: Update the shared CSS and migrate authored HTML

**Files:**

- Update `assets/sdd.css` and keep `docs/sdd/assets/sdd.css` byte-identical.
- Author or update every current Target companion: `CONTEXT.html`, all `docs/adr/*.html`, all `docs/sdd/specs/*.html`, and all `docs/sdd/plans/*.html`.
- Add `tests/test_sdd_css.py`.

**Steps:**

1. Preserve the existing system-font tokens and add selectors for `skip-link`, `document-header`, `document-kind`, `document-layout`, `document-outline`, `metadata`, `decision-article`, `term-entry`, `avoid-terms`, and plan task number/rail treatments. Use relative spacing and type tokens rather than one-off layout values.
2. Make desktop pages use a readable 60--75ch main measure with a secondary outline that is sticky only when the viewport permits. Make narrow pages use the native `details` outline, remove page-wide horizontal overflow, and keep tables and `pre` blocks locally scrollable.
3. Add light/dark semantic colors, accessible focus states and boundaries, browser zoom support, and `prefers-reduced-motion` handling. Do not add gradients, excessive shadows, external fonts, or JavaScript.
4. Manually author the current repository companions from their Markdown sources. Preserve every source fact, body text, heading, code block, list, table, link, and order; add only permitted labels, metadata, navigation, and semantic wrappers. Put the exact current Markdown digest in each head.
5. Use `dl` for `CONTEXT.md`, compact decision articles for ADRs, h2/h3 sections and outline navigation for specs, and independent numbered articles with no invented status for every `## Task N:` in plans. Do not migrate `docs/superpowers/`.
6. Run the browser checklist against representative glossary, ADR, spec, and plan pages from a local server:

   ```bash
   python3 -m http.server 8000 --directory .
   ```

   Check desktop and mobile widths, light and dark modes, keyboard skip/outline navigation, browser zoom, reduced motion, the three-second outline, squint separation, and page-wide overflow. Stop the server after the check.

**Tests:**

- `uvx --from pytest pytest -q tests/test_sdd_css.py`
- `cmp assets/sdd.css docs/sdd/assets/sdd.css`
- `git diff --check`
- Run `python3 scripts/html-docs check --paths CONTEXT.md CONTEXT.html` and the equivalent explicit checks for every migrated Target pair.

## Task 5: Add Cursor, Claude Code, and OpenCode adapters

**Files:**

- Create executable `adapters/cursor/html_docs_hook.py` and `adapters/cursor/hooks.json.example`.
- Create executable `adapters/claude/html_docs_hook.py` and `hooks/hooks.json` for the Claude plugin registration.
- Create `adapters/opencode/html_docs_plugin.ts` and `adapters/opencode/html_docs_plugin.test.ts`.
- Add payload fixtures under `adapters/cursor/fixtures/`, `adapters/claude/fixtures/`, and `adapters/opencode/fixtures/`.
- Complete `html-docs doctor` registration checks and extend `tests/test_host_adapters.py`.

**Steps:**

1. Cursor adapter: accept Cursor hook JSON on stdin, recognize `preToolUse`, `afterFileEdit`, and `stop`, extract only `Write`, `Edit`, `MultiEdit`, and `Delete` target paths, call `scripts/html-docs edit-check`, and emit Cursor `permission: allow|deny` plus user/agent messages. Unknown event fields or malformed payloads deny HTML edits and report setup guidance; non-target edits remain allowed. The example config must register the adapter with `preToolUse`, `afterFileEdit`, and `stop`, `failClosed: true`, and project-root-relative command paths.
2. Claude adapter: accept `PreToolUse` and `PostToolUse` hook payloads, match `Edit|Write|MultiEdit|NotebookEdit` only where the payload contains target paths, invoke the same CLI contract, and emit `hookSpecificOutput` with `hookEventName`, `permissionDecision`, and `permissionDecisionReason`. The plugin hook file must use `${CLAUDE_PLUGIN_ROOT}/adapters/claude/html_docs_hook.py`, retain Markdown availability, and deny on unknown or failed policy calls.
3. OpenCode adapter: export a plugin function from `adapters/opencode/html_docs_plugin.ts` using the host-provided plugin context and no external npm package. Map `tool.execute.before` to a policy call that throws on deny and map `file.edited` to post-edit validation/feedback. Invoke the Python CLI with argument arrays rather than shell interpolation. Expose pure payload-to-request helpers so the Bun test can cover allow, deny, bootstrap, unknown input, and policy failure without starting OpenCode.
4. Keep all digest, target, validation, and freshness decisions in `html_policy.py`; adapters may only parse host payloads, invoke the CLI, and map responses.
5. Make `doctor` check the exact registration markers and executable command paths for each host. It must report one result per host and never write configuration.

**Tests:**

- `uvx --from pytest pytest -q tests/test_host_adapters.py`
- `bun test adapters/opencode/html_docs_plugin.test.ts`
- Feed every adapter fixture through its stdin/module boundary and assert allow, deny, bootstrap, unknown-input, timeout/policy-failure, and feedback mappings.

## Task 6: Add the local Git wrapper and CI contract

**Files:**

- Create executable `scripts/sdd-html-pre-commit`.
- Create `tests/test_sdd_html_pre_commit.py`.
- Add provider-neutral CI and existing-hook delegation instructions to `README.md` in Task 7; do not add a provider-specific workflow.

**Steps:**

1. Make the wrapper resolve the repository root with `git rev-parse --show-toplevel`, call `python3 "$SDD_PACK_ROOT/scripts/html-docs" check --staged`, and stop with the policy exit code on failure.
2. After a successful freshness check, delegate to the executable path in `SDD_PRE_COMMIT_DELEGATE`, or to `$GIT_DIR/hooks/pre-commit.sdd-existing` when that file exists. Pass through all wrapper arguments and preserve the delegate exit code. If no delegate exists, exit `0`.
3. Do not replace, delete, or edit an existing hook automatically. The documented setup must move or copy an existing hook to the `.sdd-existing` name before installing the versioned wrapper.
4. Define the CI invocation as `python3 "$SDD_PACK_ROOT/scripts/html-docs" check --base "$BASE_REF"`, where `BASE_REF` resolves to the provider's PR base commit or branch. The implementation must not call a host application, subagent, network service, or `gh`.

**Tests:**

- `uvx --from pytest pytest -q tests/test_sdd_html_pre_commit.py`
- Use temporary repositories to verify staged pass/fail, delegate pass/fail, absent delegate, `SDD_PRE_COMMIT_DELEGATE`, PR-base diff, and unchanged existing hook contents.

## Task 7: Update pack instructions and remove automatic-generation language

**Files:**

- Update `README.md`.
- Update `skills/sdd-design/SKILL.md`, `skills/sdd-plan/SKILL.md`, and `skills/sdd/SKILL.md`.
- Add any host setup examples under `adapters/` rather than creating host-specific configuration in the consuming repository.

**Steps:**

1. Replace statements that HTML is generated with the canonical Markdown plus Agent-authored HTML companion contract. Document the exact target paths, adjacent HTML paths, shared CSS setup, digest metadata, and validation commands.
2. In `sdd-design`, after a canonical Markdown edit instruct the agent to author the HTML in a separate native file-edit operation, include the current digest, run `html-docs` validation, and never invoke the retired renderer. Keep CONTEXT and ADR formatting requirements unchanged.
3. In `sdd-plan`, replace the `render-docs` command with separate plan Markdown and HTML authoring, `html-docs check`, and a commit of both files. Preserve the exact plan header and `## Task N:` requirements.
4. In `sdd`, route HTML-related synchronization failures to the common policy and retain the existing SDD pipeline and no-Superpowers/no-subagent-in-CI rules.
5. Document explicit Cursor, Claude Code, and OpenCode enablement, `html-docs doctor`, local pre-commit installation, provider-neutral CI, bootstrap procedure, and the fact that shell/MCP/manual/hook-disabled writes are caught at Git/CI rather than forcibly ordered.
6. Do not modify or migrate legacy `docs/superpowers/` documents. Historical review/spec files may retain historical `render-docs` references when they are not part of the active instructions.

**Tests:**

- `git diff --check`
- `python3 scripts/html-docs doctor` reports the three explicit adapter registrations in a configured fixture repository.

## Task 8: Retire the mechanical renderer and finish integration coverage

**Files:**

- Delete `scripts/render-docs`.
- Delete `scripts/sddlib/render.py`.
- Delete `tests/test_render_docs.py`.
- Delete the unused vendored `scripts/_vendor/mistune/` package and `scripts/_vendor/mistune-LICENSE` after confirming no remaining runtime import.
- Replace mechanical HTML goldens in `tests/fixtures/` with authored fixtures validated by `tests/test_html_policy.py`.
- Update any remaining active references found by `git grep`.

**Steps:**

1. Confirm with `git grep -n "sddlib\.render\|from sddlib import render\|import mistune\|scripts/render-docs" -- ':!docs/superpowers/**' ':!docs/reviews/**'` that only the planned deletion and tests remain, then remove the renderer and its vendor dependency.
2. Replace exact HTML golden comparisons with structural, security, digest, text-fidelity, and warning assertions. Keep Markdown fixtures for glossary, ADR, spec, plan, duplicate headings, missing outline, unsafe markup, and irregular heading cases.
3. Run the complete suite and policy checks:

   ```bash
   uvx --from pytest pytest -q
   git diff --check
   python3 scripts/html-docs check --staged
   ```

4. Verify that all active target pairs have matching source digests, all target HTML links resolve to the checked-in stylesheet, no target HTML contains forbidden executable content, and `assets/sdd.css` matches `docs/sdd/assets/sdd.css`.
5. Run `python3 scripts/html-docs bootstrap` with explicit legacy paths in a temporary fixture repository and confirm it reports digests without creating HTML. Run normal mode against the same missing companions and confirm it denies the HTML edit.

**Tests:**

- `uvx --from pytest pytest -q`
- `git grep -n "render-docs\|sddlib\.render\|mistune" -- ':!docs/superpowers/**' ':!docs/reviews/**'` returns no active runtime or instruction references.
- `cmp assets/sdd.css docs/sdd/assets/sdd.css`
- `python3 scripts/html-docs check --paths CONTEXT.md CONTEXT.html docs/adr/0001-land-stacked-prs-without-restack.md docs/adr/0001-land-stacked-prs-without-restack.html docs/adr/0002-agent-authored-html.md docs/adr/0002-agent-authored-html.html docs/adr/0003-html-edit-order-and-freshness-gate.md docs/adr/0003-html-edit-order-and-freshness-gate.html docs/sdd/specs/2026-09-01-agent-authored-html-design.md docs/sdd/specs/2026-09-01-agent-authored-html-design.html docs/sdd/specs/2026-09-01-stacked-pr-review-fix-design.md docs/sdd/specs/2026-09-01-stacked-pr-review-fix-design.html docs/sdd/plans/2026-09-01-agent-authored-html.md docs/sdd/plans/2026-09-01-agent-authored-html.html docs/sdd/plans/2026-09-01-stacked-pr-review-fix.md docs/sdd/plans/2026-09-01-stacked-pr-review-fix.html`
