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

Each task is the smallest unit a subagent can finish and the controller can mark complete. Fold scaffolding into the task that needs it. Heading format is exactly:

```markdown
## Task N: <title>
```

Example: `## Task 1: Render docs script`

Steps inside a task are not PR units. Task N is the stacked-PR boundary.

Assume the implementer is skilled but does not know this repo. No TBD, no "similar to Task N".

## Task content

Each task must give the implementer:

- the deliverable and observable acceptance criteria;
- dependencies on earlier tasks, specs, or decisions;
- relevant paths and the existing interfaces or constraints that prevent a known failure;
- how to verify the result and what evidence to report;
- the governing spec path and the shared-contract parts the task must honor.

Include concrete commands or short snippets when they prevent a known failure or
ambiguity. Do not require the complete contents of every file or a fully expanded
step list. A skilled implementer may choose a better method that stays inside the
agreed contract and acceptance criteria.

Reference the canonical spec in the task or in the context passed with the brief;
do not rely on conversation memory. When the task consumes a shared contract
from an earlier phase, name the spec and the applicable sections.

## Agent-authored HTML and commit

After writing the plan Markdown, author `docs/sdd/plans/<file>.html` beside it
in a separate native file-edit operation. Put the current digest of the exact
Markdown bytes in the HTML head:

```html
<meta name="sdd-source-digest" content="sha256:<64 lowercase hexadecimal characters>">
```

Preserve the exact plan header above and every `## Task N:` heading. Each task
is an independent article with no invented status. Use the shared
`docs/sdd/assets/sdd.css` stylesheet and preserve all source facts, content,
and order. Do not edit the plan Markdown and HTML in one tool call or patch.

Validate both files from the consuming repository before committing:

```text
python3 <pack-root>/scripts/html-docs check --paths docs/sdd/plans/<file>.md docs/sdd/plans/<file>.html
```

If validation fails, fix the authored companion and validate again; do not
create or repair it with a renderer. Commit the plan Markdown and its HTML
only after validation passes. Then tell the human to run sdd-execute.

`<pack-root>` is the directory that contains `skills/` and `scripts/` — the same definition as the `sdd` skill.
