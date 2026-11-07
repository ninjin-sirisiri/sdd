---
name: requesting-code-review
description: Use when the human asks for a code review, including after a major feature or before merging. Do not start a review on your own after a feature, a stalled task, or every sdd-execute Task; it is not an execute gate.
---

# Requesting Code Review

A review happens when the human asks for one. sdd-execute and sdd-finish do not dispatch a reviewer as a gate. Do not start a review just because a feature is complete, a task is stuck, or every Task ended. If you think a review would help, say why and let the human decide.

The reviewer gets precisely crafted context — never your session's history.

**Core principle:** Review when asked, with isolated context.

## When to Request Review

**Use when the human asks for a review.** The situation explains why the review may be useful:

- after a feature or major change
- before merging
- for a fresh perspective on a problem
- as a baseline before refactoring
- after a complex bug fix

The human's request starts the review. Use this skill to run it well, not to decide on your own that one is required.

**Do not use:**
- After each sdd-execute Task — the controller judges complete and moves on
- Because a feature is complete or a task is stalled — neither is a review request
- As a substitute for sdd-execute's completeness check or sdd-finish's verification
- As a new mandatory gate in sdd-execute or sdd-finish

## How to Request

**1. Get git SHAs:**
```bash
BASE_SHA=$(git merge-base HEAD origin/main)  # or the execute branch baseline
HEAD_SHA=$(git rev-parse HEAD)
```

Use the task or feature range the human wants reviewed, not the whole history.

**2. Dispatch code reviewer subagent:**

Dispatch a `general-purpose` subagent, filling the template at [code-reviewer.md](code-reviewer.md)

**Placeholders:**
- `{DESCRIPTION}` - Brief summary of what you built
- `{PLAN_OR_REQUIREMENTS}` - What it should do
- `{BASE_SHA}` - Starting commit
- `{HEAD_SHA}` - Ending commit

**3. Act on feedback:**
- Verify each finding against the code and requirements before changing anything; use receiving-code-review
- Fix Critical issues the human asked you to address
- Fix Important issues before proceeding, or tell the human why not
- Note Minor issues for later
- Push back if the reviewer is wrong (with reasoning and evidence)
- Report the outcome and the verification that covers it

## Example

```
[Human: "Review the Task 2 changes before I merge."]

BASE_SHA=<Task 1 completion commit>
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
| "I'll just review the diff myself instead of dispatching a reviewer" | The human asked for a review. Dispatch a reviewer subagent: the diff and the evaluation live in its context, and only the findings come back to you. |
| "The reviewer needs my whole session history to understand the change" | Hand it precisely crafted context, never your session's history. That keeps the reviewer on the work product, not your thought process. |
| "The feature is complete, so a review should run now" | Completion is not a review request. Ask the human, or continue without one. |
| "The implementer is stuck, so dispatch a reviewer" | Being stuck is not a review request. Use systematic-debugging or ask the human for the direction you need. |

## Red Flags

**Never:**
- Dispatch a review without a human request
- Use review findings as an automatic execute or finish gate
- Ignore Critical issues the human asked you to address
- Argue with valid technical feedback

**If reviewer wrong:**
- Push back with technical reasoning
- Show code/tests that prove it works
- Request clarification

See template at: [code-reviewer.md](code-reviewer.md)
