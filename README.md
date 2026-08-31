# sdd

Skill pack for spec-driven development on Cursor and Claude Code.

Markdown is canonical. HTML is generated beside it. Install this repository as a whole pack — do not copy a single SKILL.md.

Generated HTML escapes raw HTML and sets a restrictive Content-Security-Policy. Treat it as a local reading aid, not as a place to embed scripts.

Python 3.11+ is required for `scripts/`. `gh` is required only for finish options 2 and 4.

## Install

### Claude Code

From this repository:

```bash
claude --plugin-dir .
```

After it loads, skills are namespaced by the plugin name `sdd`. Invoke `/sdd:sdd-design` (and `/sdd:sdd-plan`, `/sdd:sdd-execute`, `/sdd:sdd-finish`).

### Cursor

Install this repo as a local plugin, then reload:

```bash
mkdir -p ~/.cursor/plugins/local
ln -sfn "$(pwd)" ~/.cursor/plugins/local/sdd
```

Then Command Palette → **Developer: Reload Window**. Invoke `/sdd-design` (Cursor does not prefix the plugin name). If the skill is missing after reload, confirm `~/.cursor/plugins/local/sdd/.cursor-plugin/plugin.json` exists.

## Pipeline

sdd-design → sdd-plan → sdd-execute → sdd-finish

## Supporting Superpowers skills

This pack vendors Superpowers 6.3.0 skills used during implementation. You do not need the Superpowers plugin. Pipeline work still uses sdd-* (not brainstorming / writing-plans / executing-plans / subagent-driven-development / finishing-a-development-branch).

| Skill | When |
|---|---|
| test-driven-development | Bounded features, bugfixes, and implementer TDD |
| systematic-debugging | Bugs, test failures, unexpected behavior |
| verification-before-completion | Before claiming complete, fixed, or passing |
| using-git-worktrees | Optional isolation (ask once before implementation; not required) |
| requesting-code-review | Reviews outside sdd-execute |
| receiving-code-review | Acting on review feedback |
| dispatching-parallel-agents | Independent investigations (not plan implementers) |

## Manual check

1. In a throwaway git repo, invoke sdd-design, answer one glossary question, confirm `CONTEXT.md` and `CONTEXT.html` appear.
2. On Cursor, confirm `/sdd-design` is visible and that `test-driven-development` / `systematic-debugging` are visible. On Claude Code, confirm `/sdd:sdd-design` and the same supporting skills.
3. `python3 scripts/stack-prs --help` shows `--dry-run` and exits 0.
