---
name: sdd-execute
description: Execute an SDD plan by dispatching one isolated subagent per task. When the controller judges that task complete, move to the next. Use when a plan file exists and the user wants it implemented.
---

# SDD Execute

Announce: "I'm using sdd-execute."

Do not invoke Superpowers subagent-driven-development. Do not pin a model name. Do not use dispatching-parallel-agents for plan implementers. Do not dispatch a task-reviewer, a final-reviewer, or requesting-code-review as a gate. Review is optional and only when the human asks.

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

Do not use using-git-worktrees for Task implementer subagents. Do not attach review worktrees. Isolate only, and only after the human said yes. `[WORKDIR]` is this chosen checkout.

If the checkout you will implement in is still dirty after the `.gitignore` commit, stop and ask the human to commit or stash. A new worktree from HEAD is clean even when the original checkout is dirty; do not block on dirt in the checkout you left behind.

## Branch baseline

Before the first Task (and again when resuming after compaction):

1. If `.sdd/progress.md` already has a `Branch baseline: <sha>` line, use that SHA. Do not replace it.
2. Otherwise resolve `git rev-parse HEAD` to a full SHA and append `Branch baseline: <full-sha>` to `.sdd/progress.md` (create the file if needed).

That SHA is the branch start for stacked PRs. Never pass the literal string `MERGE_BASE`.

## Loop

Serial tasks only. Never dispatch two implementers at once. Do not wait for the human between tasks. Do not ask "continue to the next task?".

For each Task N not already `complete` in `.sdd/progress.md`:

1. Record current HEAD as BASE (full SHA).
2. `python3 <pack-root>/scripts/task-brief PLAN_FILE N`
3. Dispatch one implementer using implementer-prompt.md. Fill `[BRIEF_FILE]`, `[REPORT_FILE]` (`.sdd/reports/task-N-report.md`), `[N]`, `[TASK_NAME]`, `[WORKDIR]`, `[GLOBAL_CONSTRAINTS]` (verbatim from the plan), `[CONTEXT]` (where this task fits + interfaces from earlier tasks + your resolution of brief ambiguity). Do not paste the plan. Do not paste diffs.
4. If the implementer returns `BLOCKED` or `NEEDS_CONTEXT`, add context, split the task, or fix the plan, then re-dispatch. Never retry the identical prompt.
5. Judge completeness yourself. Do not dispatch a reviewer. Task N is complete when all of:
   - Status is `DONE` (notes/concerns are fine; they are not a gate)
   - The brief's named deliverables exist
   - Tests the brief named were run this task and passed (trust the report, or run that command once)
   - `HEAD` moved from BASE, unless the brief had no code to commit
6. If it is not complete: resume the same contract once, naming what is missing. If it is still not complete, stop and tell the human. Do not open a review loop.
7. On complete, append to `.sdd/progress.md`:
   `Task N: complete (commits <base7>..<head7>)`
   head7 is HEAD. base7 is the BASE you recorded. Then start Task N+1 immediately.

## Controller stops

Only for destructive ops, security, side effects outside this worktree (push, merge, publish), or a plan so broken the next step is a guess. Otherwise decide from the spec, write `Ruling: <decision> — <why> — <cost if wrong>` to the ledger, and continue.

After compaction, trust the ledger and `git log`. Do not re-dispatch completed tasks. `git clean -fdx` deletes the ledger; recover from `git log`.

## Close

After every task is complete, use sdd-finish. Do not run a final-reviewer subagent. If the human asks for a review, use requesting-code-review.

If sdd-goal (or the host `/goal` / CreateGoal) is already active, keep working this loop until that condition holds. Do not yield just to report progress.

`<pack-root>` is the directory containing `skills/` and `scripts/` — the same definition as the `sdd` skill.
