---
name: sdd-plan
description: Turn an approved architectural spec into a task plan with Markdown and HTML. Use after sdd-design when a spec file exists.
---

# SDD Plan

Announce: "I'm using sdd-plan."

Do not invoke Superpowers writing-plans. Input is the spec path. Do not start from a chat-only bounded design.

## Header (required, in this order)

```markdown
# [Feature] Implementation Plan

**Goal:** [one sentence]

**Architecture:** [two or three sentences]

**Tech Stack:** [key tools]

**Spec:** [path to the spec]

## Global Constraints

[Copy exact values and wording from the spec, one line each]
```

Then file structure, then tasks.

## Tasks

Each task is the smallest unit with its own test cycle and review gate. Fold scaffolding into the task that needs it. Heading format is exactly:

```markdown
## Task N: <title>
```

Example: `## Task 1: Render docs script`

Steps inside a task are not PR units. Task N is the stacked-PR boundary.

Assume the implementer is skilled but does not know this repo. No TBD, no "similar to Task N", no steps without the actual commands or file contents.

## HTML and commit

After writing the plan, run:

```text
python3 <pack-root>/scripts/render-docs docs/sdd/plans/<file>.md
```

If HTML fails, warn and continue. Commit the plan Markdown and its HTML. Then tell the human to run sdd-execute.
