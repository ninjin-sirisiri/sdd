---
name: sdd-execute
description: Execute an SDD plan with one isolated implementer per task, a spec+quality review, and a progress ledger. Use when a plan file exists and the user wants it implemented.
---

# SDD Execute

Announce: "I'm using sdd-execute."

Do not invoke Superpowers subagent-driven-development. Do not pin a model name.

## Preconditions

- Require a plan file path. If missing, stop.
- If `.gitignore` has no `.sdd/` line, append it and commit only `.gitignore`.
- If the worktree is still dirty after that commit, stop and ask the human to commit or stash.
- Scan the plan once for contradictions or Global Constraints conflicts. Ask them in one batch. If none, say nothing.

## Host

- Cursor: Task tool, fresh subagent, no inherited chat.
- Claude Code: Agent tool, fresh subagent, no inherited chat.
- If the host cannot isolate a subagent, stop with `HOST_SUBAGENT_UNAVAILABLE`. Do not implement in this controller session.

## Loop

Serial tasks only. Never dispatch two implementers at once.

For each Task N not already `complete` in `.sdd/progress.md`:

1. Record current HEAD as BASE (full SHA).
2. `python3 <pack-root>/scripts/task-brief PLAN_FILE N`
3. Dispatch implementer using implementer-prompt.md. Fill `[BRIEF_FILE]`, `[REPORT_FILE]` (`.sdd/reports/task-N-report.md`), `[N]`, `[TASK_NAME]`, `[WORKDIR]`, `[CONTEXT]` (where this task fits + interfaces from earlier tasks + your resolution of brief ambiguity). Do not paste the plan. Do not paste diffs.
4. If the implementer asks questions, answer and resume the same contract.
5. `DONE_WITH_CONCERNS` about correctness or scope: resolve before review. Observations: ledger them and review.
6. `DONE` or observational concerns: `python3 <pack-root>/scripts/review-package BASE HEAD -o .sdd/reviews/task-N.diff.md` (overwrite on re-review).
7. Dispatch task-reviewer-prompt.md with brief, report, diff path, and Global Constraints copied verbatim from the plan.
8. Critical/Important: dispatch a fix implementer (same prompt contract, covering tests named), then re-review with the same reviewer template.
9. A finding that contradicts plan text: do not fix; show the human the finding and the plan sentence once.
10. On spec ✅ and quality Approved, append to `.sdd/progress.md`:
    `Task N: complete (commits <base7>..<head7>, review clean)`
    head7 is HEAD after fixes. base7 is the BASE you recorded.

## Controller stops

Only for destructive ops, security, side effects outside this worktree (push, merge, publish), or a plan so broken the next step is a guess. Otherwise decide from the spec, write `Ruling: <decision> — <why> — <cost if wrong>` to the ledger, and continue.

After compaction, trust the ledger and `git log`. Do not re-dispatch completed tasks. `git clean -fdx` deletes the ledger; recover from `git log`.

`NEEDS_CONTEXT` / `BLOCKED`: add context, split the task, or fix the plan. Never retry the identical prompt.

## Close

After every task is complete, `review-package MERGE_BASE HEAD -o .sdd/reviews/final.diff.md` and dispatch final-reviewer-prompt.md once, including deferred Minors. If findings remain, one fix subagent for the whole list, then re-run final review. Then use sdd-finish.

Pack root is the directory containing `scripts/` and `skills/`.
