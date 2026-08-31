---
name: sdd-execute
description: Execute an SDD plan with one isolated implementer per task, a spec+quality review, and a progress ledger. Use when a plan file exists and the user wants it implemented.
---

# SDD Execute

Announce: "I'm using sdd-execute."

Do not invoke Superpowers subagent-driven-development. Do not pin a model name. Per-task review uses this skill's prompts and `scripts/review-package`, not requesting-code-review. Do not use dispatching-parallel-agents for plan implementers.

## Preconditions

- Require a plan file path. If missing, stop.
- If `.gitignore` has no `.sdd/` line, append it and commit only `.gitignore`.
- Scan the plan once for contradictions or Global Constraints conflicts. Ask them in one batch. If none, say nothing.

## Host

- Cursor: Task tool, fresh subagent, no inherited chat.
- Claude Code: Agent tool, fresh subagent, no inherited chat.
- If the host cannot isolate a subagent, stop with `HOST_SUBAGENT_UNAVAILABLE`. Do not implement in this controller session.

## Workspace

Before the first Task, decide the checkout. Do not dispatch Task 1 until this is settled.

1. If `.sdd/progress.md` already has a `Worktree:` line, honor it. Do not ask again (including after compaction).
2. If already in a linked worktree (not a submodule), append `Worktree: existing <full-path>` if that line is missing, then continue here. Do not ask. Do not create another worktree.
3. If this conversation already recorded a yes/no, honor it without asking.
4. Otherwise stop and ask once. Present exactly:

```
Implementation is about to start. Create an isolated git worktree first?

1. Yes — create a worktree (keeps this checkout unchanged)
2. No — implement in this checkout

Which option?
```

Wait for the human. Do not add extra options. Creating a worktree is optional.

- **Yes:** use using-git-worktrees. They already consented — do not ask again inside that skill. After it reports ready, continue this skill from that worktree. Append `Worktree: created <full-path>` to `.sdd/progress.md` in the checkout you will implement in (create the file if needed). If creation fails and that skill falls back in place, append `Worktree: in-place` instead.
- **No:** append `Worktree: in-place` and continue in this checkout.

Do not use using-git-worktrees for Task implementer subagents. `[WORKDIR]` is this chosen checkout.

If the checkout you will implement in is still dirty after the `.gitignore` commit, stop and ask the human to commit or stash. A new worktree from HEAD is clean even when the original checkout is dirty; do not block on dirt in the checkout you left behind.

## Branch baseline

Before the first Task (and again when resuming after compaction):

1. If `.sdd/progress.md` already has a `Branch baseline: <sha>` line, use that SHA. Do not replace it.
2. Otherwise resolve `git rev-parse HEAD` to a full SHA and append `Branch baseline: <full-sha>` to `.sdd/progress.md` (create the file if needed).

That SHA is the final-review base. Never pass the literal string `MERGE_BASE`.

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

After every task is complete, run:

```text
python3 <pack-root>/scripts/review-package BRANCH_BASELINE HEAD -o .sdd/reviews/final.diff.md
```

`BRANCH_BASELINE` is the `Branch baseline:` SHA recorded above. Then dispatch final-reviewer-prompt.md once, including deferred Minors. If findings remain, one fix subagent for the whole list, then re-run final review. Then use sdd-finish.

`<pack-root>` is the directory containing `skills/` and `scripts/` — the same definition as the `sdd` skill.
