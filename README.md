# sdd

Skill pack for spec-driven development on Cursor and Claude Code.

Markdown is canonical. HTML is generated beside it. Install this repository as a whole pack — do not copy a single SKILL.md.

## Install

**Claude Code:** from this repo, install it as a local plugin (the `.claude-plugin/` manifest).

**Cursor:** install this repo as a plugin, or point Cursor at this folder so it loads `./skills/`.

Python 3.11+ is required for `scripts/`. `gh` is required only for finish options 2 and 4.

## Pipeline

sdd-design → sdd-plan → sdd-execute → sdd-finish

## Manual check

1. In a throwaway git repo, invoke sdd-design, answer one glossary question, confirm `CONTEXT.md` and `CONTEXT.html` appear.
2. On Cursor and on Claude Code, confirm the `sdd` skill is visible.
3. `python3 scripts/stack-prs --help` shows `--dry-run`.
