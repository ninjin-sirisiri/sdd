# Agent-authored HTML design

**Classification:** architectural

**Chosen approach:** Replace the deterministic Markdown-to-HTML rendering path with Agent-authored HTML while keeping Markdown canonical. Enforce the Markdown-before-HTML edit order with one stateless Python policy, thin adapters for Cursor, Claude Code, and OpenCode, and a Git freshness gate for pre-commit and CI.

## Problem

The current `render-docs` path mechanically converts Markdown into a nearly identical HTML preview. It gives every document the same shallow presentation even when the source is a glossary, ADR, specification, or implementation plan. It also cannot make an agent choose a structure that explains the document to a human reader.

The replacement must preserve the Markdown source contract, keep generated artifacts safe to open locally, and prevent an HTML companion from drifting away from the source. Host hooks can reject a file-edit tool call, but no supported host can force the next tool call to be HTML, and shell, MCP, manual, or disabled-hook writes cannot be fully controlled.

## Goals

- Make the outline of every SDD document visible within about three seconds.
- Improve long-document reading and review of goals, decisions, constraints, and tasks.
- Let the agent intentionally choose semantic HTML and visual hierarchy for each target document.
- Keep Markdown as the only canonical source and keep HTML as a checked-in adjacent companion.
- Enforce the source-before-companion order as far as host APIs allow and block stale or HTML-only commits.
- Support Cursor, Claude Code, OpenCode, local Git hooks, and provider-neutral CI through one policy contract.
- Preserve safe local viewing with static HTML, shared CSS, no JavaScript, and no external resources.

## Non-goals

- Applying the companion rule to arbitrary Markdown, README files, skill text, or `docs/superpowers/`.
- Making HTML canonical or co-canonical.
- Automatically generating or automatically repairing the final HTML.
- Keeping `render-docs` as a normal or legacy preview path.
- Adding a JavaScript document application, search, scroll tracking, external fonts, CDN assets, or pixel-diff CI.
- Supporting a hard guarantee over manual, external-process, or hook-disabled writes.
- Running host applications or subagents in CI.

## Architecture

### Canonical artifacts

The Target documents are exactly:

- `CONTEXT.md`
- `docs/adr/*.md`
- `docs/sdd/specs/*.md`
- `docs/sdd/plans/*.md`

Each Target document pairs with the adjacent file having the same relative path and stem and the `.html` suffix. The shared stylesheet is `docs/sdd/assets/sdd.css`. Other Markdown files are outside this synchronization contract.

Markdown remains the source of truth. Agent-authored HTML is a human-facing companion whose structure and visual hierarchy are deliberately designed by the agent, not copied from a generic Markdown preview.

### Shared policy

`scripts/sddlib/html_policy.py` is the single source for:

- Target document and adjacent companion resolution.
- Exact UTF-8 byte SHA-256 digests.
- Normal and bootstrap edit permissions.
- HTML metadata, security, structural, and text-fidelity validation.
- Staged-tree and PR-diff freshness checks.
- Host-neutral decisions, messages, affected paths, and exit statuses.

The `scripts/html-docs` CLI exposes `edit-check`, `check`, `bootstrap`, and `doctor`. It accepts JSON on stdin and returns JSON on stdout with `decision`, `message`, `paths`, and expected digest fields. Exit code `0` means allow or pass, `1` means a synchronization or document violation, and `2` means invalid arguments, unavailable configuration, or an execution failure.

### Host adapters

The pack includes thin adapters for the native file-edit events of Cursor, Claude Code, and OpenCode. The adapters translate each host payload to the common CLI contract and translate the result back to the host's allow / deny / feedback format. They do not implement digest or document logic themselves.

Cursor uses its pre-tool edit decision and post-file-edit / stop feedback. Claude Code uses its pre-tool and post-tool hook events and plugin hook configuration. OpenCode uses its plugin tool-before decision and file-edited event. Each adapter is explicitly enabled by the user; `html-docs doctor` reports missing, disabled, or incompatible registration.

### Git and CI adapters

The local pre-commit wrapper passes the staged tree to `html-docs check`. CI passes the PR base reference and checkout tree to the same command. The pack provides provider-neutral commands and examples, not an automatically installed workflow. Existing pre-commit hooks are preserved and invoked by the wrapper rather than silently replaced.

### Shared CSS

The pack owns `assets/sdd.css`. Explicit setup places it at `docs/sdd/assets/sdd.css` in the consuming repository. Agent-authored HTML may use the shared semantic classes and `data-*` hooks, but may not add inline styles, document-specific stylesheets, or external stylesheets. CSS-only changes are allowed and are validated separately from Markdown / HTML freshness.

## Semantic reconstruction contract

The strict contract above remains the default and is unchanged. A Target may opt in to `semantic-v1` only by declaring `<meta name="sdd-html-contract" content="semantic-v1">` in the companion head; an unknown contract value is rejected rather than falling back to strict inspection.

`scripts/sddlib/html_units.py` is the common lossless source scanner. It splits the exact Markdown bytes into source units for headings, paragraphs, nested list items, table header and body cells, fenced and indented code, inline code, links, images, and glossary terms and Avoid entries. Every unit records its kind, parent, stable ID, and a half-open UTF-8 byte range in the original bytes, and is bound to the exact source digest. Unsupported Markdown syntax is reported as an explicit unsupported construct instead of being dropped; a document with any unsupported construct is incomplete and cannot pass semantic validation.

A `semantic-v1` companion embeds a non-executing JSON provenance map in `template#sdd-provenance`. The version 1 schema fixes the source path and digest, the unit definitions, many-to-many mappings from units to visible representation target IDs, strict-preservation targets for code, paths, identifiers, link destinations, glossary names, and Avoid entries, supplementary representations with their source units, and calculations with inputs, formula, and result. The schema rejects unknown fields, unknown versions, duplicate IDs, missing references, and missing required fields. A common validator checks the full unit set, references, and static safety; semantic sufficiency remains a separate assessment.

An evaluation receipt under `docs/sdd/html-evidence/` is a JSON auxiliary artifact, not a new Target kind. Version 1 fixes the source path and digest, the complete HTML bytes digest, CSS / resource / policy fingerprints, settings / rubric / profile versions, generation and H2 references, verification results, and per-condition decisions with evidence references. The receipt is not a signature and is not proof of model accuracy; CI checks its structure and binding, not meaning or image quality.

## Data flow

1. An agent attempts a native file edit.
2. The host adapter sends the operation and path set to `html-docs edit-check`.
3. A Markdown edit is allowed. A mixed Markdown-plus-HTML operation is denied before any file is changed.
4. After a successful Markdown edit, the adapter returns the paired HTML path and current digest as an HTML-update requirement. The host may allow other work, but the next tool call is not guaranteed to be HTML.
5. An HTML edit is allowed only when the current Markdown digest differs from the digest recorded in the existing HTML. A missing or metadata-less companion requires explicit bootstrap, except that creating a new Target Markdown document counts as the source edit for its first separate HTML operation.
6. The agent writes a complete HTML companion in a separate operation, including the current digest and the required semantic and visual structure.
7. The post-edit validator checks the new companion. It does not generate, rewrite, or repair it. An invalid result is reported as stale until the agent writes a valid replacement.
8. `html-docs check` verifies every affected pair before a local commit and in CI. A valid pair is the completion condition.

### Edit-order invariants

- A Target Markdown edit succeeds before its HTML companion can be edited.
- A single tool call or patch cannot edit both files, even when its final content would be valid.
- HTML-only changes are rejected, including a visual-only design edit when the source digest is already current.
- Multiple Markdown edits may occur before one HTML update; the HTML must use the final digest.
- A Markdown edit after an HTML update makes that HTML stale again.
- Shared CSS may be edited without changing the Markdown or HTML digest.
- Deletion or movement is valid only when Markdown and its companion move or delete together.
- Multiple Target documents are checked independently, and a partial set fails the commit.

## Agent-authored HTML

### Common shell

Every companion contains a language-specific `html` element, charset, viewport, title, restrictive CSP, exactly one `sdd-source-digest` meta, and a shared CSS link. The body starts with a skip link. A `header` identifies the document kind. A `main` element has the content target ID and is programmatically focusable. Data tables include a caption and scoped header cells; when Markdown lacks a caption, the agent may derive a descriptive caption from the nearby heading and column labels without adding facts.

When h2 or h3 headings exist, a named navigation outline is provided in an `aside`. It is sticky where the viewport permits and falls back to normal flow. On narrow screens the outline is exposed through native `details`; no JavaScript is required. When there are no h2 or h3 headings, no empty `nav` or `aside` is emitted.

### Content and document kinds

The agent preserves source facts, visible body content, headings, code, lists, tables, links, and their reading order. It may add navigation, skip-link text, document-kind labels, accessibility labels, and metadata, but may not summarize, omit, invent, or reorder source content.

Glossary terms use `dl`, `dt`, and `dd`; an `_Avoid_` paragraph stays inside the related `dd` as a labeled secondary paragraph. An ADR remains a compact decision article and does not gain headings that are absent from Markdown. Spec h2 headings become semantic section blocks. Each plan `## Task N:` becomes an independent article with a visually prominent number and title, a left rule or number rail, and no invented status. Labeled lead paragraphs such as `Goal`, `Architecture`, and `Classification` become metadata / lead blocks without changing their values.

Unknown source shapes use ordinary semantic HTML. Source heading levels are retained, including multiple h1 or skipped levels; those conditions produce warnings rather than automatic corrections. Heading IDs are stable slugs derived from heading text, with occurrence-order suffixes for duplicates, and all outline links resolve to those IDs.

### Visual system

The shared system uses system fonts, relative type and spacing tokens, semantic light / dark colors, and a 60--75ch main reading measure. Heading rank is expressed by type scale and spacing, while section boundaries use whitespace, rules, and restrained accents. Document kind changes label, accent, and semantic block treatment, not the entire palette, font, or layout.

Gradients, excessive shadows, all-block card layouts, color-only hierarchy, external fonts, and required animation are prohibited. Text and boundaries meet accessible contrast. Tables and long code scroll locally rather than causing page-wide horizontal overflow. The layout supports browser zoom and `prefers-reduced-motion`.

### Language and safety

The agent selects the dominant prose language for `html lang` and generated UI labels. Code and proper names do not determine the language. `und` is not accepted for a Target document.

Only static semantic HTML and same-repository resources are allowed. Scripts, event attributes, executable inline content, frames, external stylesheets, external fonts, and network-dependent resources are prohibited. The restrictive CSP denies all unspecified sources and permits only the approved local stylesheet and local / data images. Raw HTML from Markdown is represented as text rather than trusted executable markup.

## Synchronization evidence

The HTML head contains exactly:

```html
<meta name="sdd-source-digest" content="sha256:<64 lowercase hexadecimal characters>">
```

The digest is computed over the exact Markdown file bytes, including line endings, trailing whitespace, and the final newline. Timestamps, Git commit identity, and sidecar state are not freshness evidence. The policy is stateless and reads the current Markdown and HTML on every event.

### Bootstrap

`html-docs bootstrap <explicit paths>` enumerates only the requested existing Target documents whose companions are missing or lack digest metadata and reports their current digests. It grants a bounded bootstrap mode for those HTML paths, but does not create HTML. The agent authors each companion in a separate operation; validator success is required before the migration is committed. Normal mode never treats a missing companion as permission to write HTML.

## Error handling

- A Markdown edit is not rolled back because HTML authoring failed.
- The policy never generates or silently repairs HTML.
- A failed or incomplete HTML authoring attempt does not count as synchronized; an existing valid companion is not replaced by an unvalidated candidate.
- A missing, stale, unsafe, structurally invalid, or text-incomplete companion produces a clear path-specific message and a non-zero check result.
- A host adapter that is missing, disabled, receives unknown payload fields, times out, or cannot invoke the policy denies HTML editing and reports setup guidance. Markdown editing remains available.
- External or manual writes are outside direct ordering control and are caught by the Git / CI gate when they affect a commit.
- A failed local hook does not make CI pass. A failed CI check prevents merge until the pair is corrected.

## Testing

The automated suite covers the Python policy and adapters without starting host applications.

- Unit tests cover target matching, adjacent pair resolution, exact SHA-256 bytes, digest metadata parsing, normal / bootstrap permissions, mixed patches, unknown payloads, and exit codes.
- Temporary Git repositories cover staged changes, PR-base changes, new pairs, multiple documents, CSS-only changes, HTML-only changes, stale pairs, rename, delete, and existing hook wrappers.
- Authored fixtures cover Glossary, ADR, Spec, and Plan structures, including `<dl>`, task articles, lead metadata, nested h2 / h3 outlines, duplicate headings, missing outlines, unsafe markup, and irregular heading warnings.
- Validator tests cover landmarks, skip links, `lang`, CSP, allowed resources, heading IDs, outline links, text order, code, lists, tables, and inaccessible or missing table labels.
- Source-unit tests cover exact UTF-8 byte ranges under CRLF and Japanese text, nested lists, table headers and cells, code, inline code and links, glossary terms and Avoid entries, unsupported constructs, and schema rejection of unknown fields, versions, duplicate IDs, and missing receipt fields.
- Each host adapter has payload fixtures for allow, deny, bootstrap, unknown input, and policy failure. No host application or subagent is run in CI.
- Exact HTML golden comparisons are replaced by structural, security, digest, and text-fidelity assertions.
- Browser verification uses representative authored documents in desktop / mobile and light / dark modes and checks the three-second outline, squint separation, keyboard navigation, zoom, reduced motion, and page-wide overflow.

## Consuming paths and setup

- Canonical Markdown: `CONTEXT.md`, `docs/adr/*.md`, `docs/sdd/specs/*.md`, `docs/sdd/plans/*.md`
- Agent-authored HTML: adjacent same-stem `.html`
- Shared CSS: `docs/sdd/assets/sdd.css`
- Policy source and CLI: `scripts/sddlib/html_policy.py`, `scripts/html-docs`
- Host setup: explicit Cursor, Claude Code, and OpenCode adapter enablement, checked by `html-docs doctor`
- Local enforcement: a versioned pre-commit wrapper that preserves existing hooks
- CI enforcement: provider-neutral `html-docs check --base <ref>` invocation

The first migration explicitly bootstraps the current Target documents in this repository and replaces their mechanically generated companions with authored HTML. Legacy `docs/superpowers/` documents are not migrated. The migration is one coordinated change, but every Markdown and HTML pair is edited in separate operations.

## Implementation boundaries

The implementation may reorganize files, but it must preserve these boundaries:

- The common policy owns decisions; adapters do not duplicate them.
- The agent owns HTML content structure and visual hierarchy; validators do not create or alter it.
- Markdown owns facts and order; HTML owns presentation and semantic wrappers.
- CSS owns shared presentation; HTML does not carry inline or external styling.
- Host hooks provide best-effort edit ordering; Git / CI provides the commit boundary.

The approved ADRs are `docs/adr/0002-agent-authored-html.md` and `docs/adr/0003-html-edit-order-and-freshness-gate.md`.
