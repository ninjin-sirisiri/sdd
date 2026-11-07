---
name: sdd-goal
description: Set a decidable completion condition and keep working until it holds, like Claude Code /goal. Use when the user says /goal, /sdd-goal, keep going until, or wants a session to run unattended to a finish line.
argument-hint: "<completion condition>"
---

# SDD Goal

Announce: "I'm using sdd-goal."

This is the portable analog of Claude Code `/goal`: a condition, then keep working until it holds. It does not install a Stop hook and does not replace Claude Code's native `/goal` overlay.

## Condition

Take the condition from the invocation arguments or the rest of the user's message.

If it is missing or vague ("make it good"), rewrite it into one measurable end state this session can prove in its own output, then state the rewritten condition before working. Prefer:

- a command and exit: `` `npm test` exits 0 ``
- a ledger: every `## Task N:` in the plan has a `Task N: complete` line in `.sdd/progress.md`
- a file or queue: `CHANGELOG.md` has an entry for each listed PR

Include a bound when the user did not: `or stop after 20 turns` (or a time clause). Add constraints that must not move (`do not modify other test files`).

If you cannot make it decidable, stop and ask once.

## Host

- **Cursor:** the user asked for a goal — call CreateGoal with the condition. UpdateGoal `complete` only when the condition holds. You cannot pause via the tool; the human pauses. If they paused and ask to resume, UpdateGoal `active`.
- **Claude Code:** if native `/goal` is already active, that condition wins. Do the work anyway. Do not refuse because native `/goal` exists. Do not tell the human to go run `/goal` instead of you working.

One goal per session. A new sdd-goal invocation replaces the previous condition (Cursor: CreateGoal again).

## Loop

Do not return control to ask "continue?". Do not judge while a subagent or background shell is still running.

1. If the condition is completing an SDD plan (or the user invoked this with execute), use sdd-execute. That loop already advances when a Task is complete.
2. Otherwise do the next useful unit of work. Dispatch a subagent when the unit is an implementation task; do not implement plan Tasks in this controller session.
3. When that unit finishes, judge the condition against available evidence (commands and results, files you read, ledger lines, or a task report's verification record). Verdict:
   - **Met** — Cursor: UpdateGoal `complete`. Stop. Tell the human what held.
   - **Not yet** — say what is missing in one line, then continue.
   - **Impossible** — stop. Cursor: leave the goal active (do not mark complete). Tell the human why.
4. Controller stops from sdd-execute still apply (destructive ops, security, publish, a plan that is a guess). Those are Impossible until the human decides.
5. No tool use and no progress for several steps: stop, leave the goal set, tell the human. Do not spin.

Unrecoverable host errors (auth, credits, context overflow compaction cannot clear) end the loop. Say the condition was not met. Cursor: do not mark complete.

## After compaction

Re-read `.sdd/progress.md` and the stated condition. Resume. Do not redo completed plan Tasks.

`<pack-root>` is the directory containing `skills/` and `scripts/` — the same definition as the `sdd` skill.
