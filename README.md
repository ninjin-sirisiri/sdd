# sdd

Skill pack for spec-driven development on Cursor and Claude Code.

Markdown is canonical. HTML is generated beside it. Install this repository as a whole pack — do not copy a single SKILL.md.

## Install

**Claude Code:** from this repo, install it as a local plugin (the `.claude-plugin/` manifest).

**Cursor:** install this repo as a plugin, or point Cursor at this folder so it loads `./skills/`.

Python 3.11+ is required for `scripts/`. `gh` is required only for finish options 2 and 4.

## Pipeline

sdd-design → sdd-plan → sdd-execute → sdd-finish

## Supporting Superpowers skills

This pack vendors Superpowers 6.3.0 skills used during implementation. You do not need the Superpowers plugin. Pipeline work still uses sdd-* (not brainstorming / writing-plans / executing-plans / subagent-driven-development / finishing-a-development-branch).

| Skill | When |
|---|---|
| test-driven-development | Bounded features, bugfixes, and implementer TDD |
| systematic-debugging | Bugs, test failures, unexpected behavior |
| verification-before-completion | Before claiming complete, fixed, or passing |
| using-git-worktrees | Optional isolation (sdd-execute does not require it) |
| requesting-code-review | Reviews outside sdd-execute |
| receiving-code-review | Acting on review feedback |
| dispatching-parallel-agents | Independent investigations (not plan implementers) |

## Manual check

1. In a throwaway git repo, invoke sdd-design, answer one glossary question, confirm `CONTEXT.md` and `CONTEXT.html` appear.
2. On Cursor and on Claude Code, confirm the `sdd` skill is visible, and that `test-driven-development` / `systematic-debugging` are visible.
3. `python3 scripts/stack-prs --help` shows `--dry-run`.
