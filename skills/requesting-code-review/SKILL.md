---
name: requesting-code-review
description: Use when the human requests a review after a major feature or before merging. Do not use as an sdd-execute task gate.
---

# Requesting Code Review

sdd-execute does not review as a gate. Use this skill only when the human asks for a review, or before merge if they want one. The reviewer gets precisely crafted context — never your session's history.

**Core principle:** Review when asked, with isolated context.

## When to Request Review

**Use:**
- The human asked for a review
- After completing a major feature (outside the execute loop)
- Before merge to main, if they want a review

**Optional:**
- When stuck (fresh perspective)
- Before refactoring (baseline check)
- After fixing a complex bug

**Do not use:**
- After each sdd-execute Task — the controller judges complete and moves on
- As a substitute for sdd-execute's completeness check

## How to Request

**1. Get git SHAs:**
```bash
BASE_SHA=$(git merge-base HEAD origin/main)  # or the execute branch baseline
HEAD_SHA=$(git rev-parse HEAD)
```

**2. Dispatch code reviewer subagent:**

Dispatch a `general-purpose` subagent, filling the template at [code-reviewer.md](code-reviewer.md)

**Placeholders:**
- `{DESCRIPTION}` - Brief summary of what you built
- `{PLAN_OR_REQUIREMENTS}` - What it should do
- `{BASE_SHA}` - Starting commit
- `{HEAD_SHA}` - Ending commit

**3. Act on feedback:**
- Fix Critical issues immediately
- Fix Important issues before proceeding
- Note Minor issues for later
- Push back if reviewer is wrong (with reasoning)

## Example

```
[Human asked for a review after Task 2]

BASE_SHA=$(git log --oneline | grep "Task 1" | head -1 | awk '{print $1}')
HEAD_SHA=$(git rev-parse HEAD)

[Dispatch code reviewer subagent]
  DESCRIPTION: Added verifyIndex() and repairIndex() with 4 issue types
  PLAN_OR_REQUIREMENTS: Task 2 from docs/sdd/plans/deployment-plan.md
  BASE_SHA: a7981ec
  HEAD_SHA: 3df7661
```

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "I'll just review the diff myself instead of dispatching a reviewer" | You're the coordinator — reviewing the diff inline burns the context window you need to keep driving the work. Dispatch a reviewer subagent: the diff and the evaluation live in its context, and only the findings come back to you. |
| "The reviewer needs my whole session history to understand the change" | Hand it precisely crafted context, never your session's history. That keeps the reviewer on the work product, not your thought process. |

## Red Flags

**Never:**
- Ignore Critical issues the human asked you to address
- Argue with valid technical feedback

**If reviewer wrong:**
- Push back with technical reasoning
- Show code/tests that prove it works
- Request clarification

See template at: [code-reviewer.md](code-reviewer.md)
