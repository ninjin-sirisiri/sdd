---
name: sdd
description: Route spec-driven work to sdd-design, sdd-plan, sdd-execute, sdd-goal, sdd-finish, or sdd-review-fix, and supporting Superpowers skills (TDD, debugging, verification). Use when the user wants SDD, a spec, a plan, implementation, a completion-condition loop, a branch finish, TDD, systematic debugging, or a design grill.
---

# SDD

Pack root is the directory that contains `skills/` and `scripts/`. This file lives at `<pack-root>/skills/sdd/SKILL.md`. Install the whole pack. Never copy one SKILL.md.

Format templates live at `<pack-root>/docs/formats/`. Scripts live at `<pack-root>/scripts/`.

## Route

| Situation | Skill |
|---|---|
| New idea, fuzzy words, a design grill, or any architectural change without a spec | sdd-design |
| Approved architectural spec, no plan yet | sdd-plan |
| Plan exists, implement it | sdd-execute |
| Keep working until a condition holds (/goal) | sdd-goal |
| Implementation green, integrate | sdd-finish |
| GitHub review on a stacked PR (`sdd-stack/task-N`) | sdd-review-fix |
| User asks to "just implement" something architectural | sdd-design first |
| Bounded feature, bugfix, or refactor (no architectural spec) | test-driven-development |
| Bug, test failure, or unexpected behavior | systematic-debugging |
| About to claim the branch is complete (sdd-finish) | verification-before-completion |
| Isolated workspace / git worktree (after the human said yes) | using-git-worktrees isolate |
| Checkout of an existing stack branch for a stacked-PR review | using-git-worktrees attach (from sdd-review-fix) |
| Review the human asked for | requesting-code-review |
| Acting on review feedback | receiving-code-review |
| 2+ independent investigations (not plan tasks) | dispatching-parallel-agents |

Do not run sdd-execute without a plan file. Do not run architectural implementation without a spec file.

Before controller-session implementation (sdd-execute Task 1, or test-driven-development that is not an execute implementer), the matching skill asks once whether to create a worktree. Do not ask from an implementer subagent.

Do not invoke the Superpowers plugin, grill-with-docs, grilling, or domain-modeling. Supporting skills in this pack are the Superpowers copies (TDD, debugging, verification, worktrees, review). Pipeline skills stay sdd-* — do not use brainstorming, writing-plans, executing-plans, subagent-driven-development, or finishing-a-development-branch.
