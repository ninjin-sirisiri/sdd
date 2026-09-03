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

CI must not start a host application or subagent, call a network service, or use `gh`. A failed local hook does not make CI pass, and a failed CI check prevents merge until every affected Target pair is corrected. Deletion or movement is valid only when Markdown and its companion move or delete together.

Host hooks provide best-effort edit ordering only. Shell, MCP, manual, and hook-disabled writes are outside direct ordering control and are caught by the Git / CI gate when they affect a commit; they are not forcibly ordered.

## Pipeline

sdd-design -> sdd-plan -> sdd-execute -> sdd-finish

`sdd-execute` dispatches one isolated subagent per plan Task. The controller judges that Task complete and starts the next; there is no implementer/reviewer loop.

`sdd-goal` is the portable analog of Claude Code `/goal`: set a decidable completion condition and keep working until it holds. On Cursor invoke `/sdd-goal`. On Claude Code, native `/goal` still provides the overlay; `/sdd:sdd-goal` is the same work loop, and uses `sdd-execute` when the condition is a plan.

After stacked PRs exist, GitHub review fixes use `sdd-review-fix` (existing `sdd-stack/task-N` only). Land from the bottom on GitHub.

| Skill | When |
|---|---|
| sdd-review-fix | GitHub review on an open stacked PR after finish option 4 |

## Supporting Superpowers skills

This pack vendors Superpowers 6.3.0 skills used during implementation. You do not need the Superpowers plugin. Pipeline work still uses sdd-* (not brainstorming / writing-plans / executing-plans / subagent-driven-development / finishing-a-development-branch).

| Skill | When |
|---|---|
| test-driven-development | Bounded features and bugfixes; optional during execute |
| systematic-debugging | Bugs, test failures, unexpected behavior |
| verification-before-completion | Before sdd-finish claims the branch is complete |
| using-git-worktrees | Isolate: optional before implementation. Attach: existing `sdd-stack/task-N` from sdd-review-fix (`-b` forbidden) |
| requesting-code-review | Reviews the human asked for (not an execute gate) |
| receiving-code-review | Acting on review feedback |
| dispatching-parallel-agents | Independent investigations (not plan implementers) |

## Manual Check

1. In a throwaway git repo, invoke sdd-design, answer one glossary question, author `CONTEXT.md` and its adjacent `CONTEXT.html` separately, and run `html-docs check`.
2. On Cursor, confirm `/sdd-design` and `/sdd-goal` are visible and that `test-driven-development` / `systematic-debugging` are visible. On Claude Code, confirm `/sdd:sdd-design`, `/sdd:sdd-goal`, and the same supporting skills.
3. `python3 scripts/stack-prs --help` shows `--dry-run` and exits 0.
4. After stacked PRs exist, `/sdd-review-fix` (Claude Code: `/sdd:sdd-review-fix`) is visible. Confirm the skill forbids `-b`, `gh pr merge`, and `stack-prs` re-run.
