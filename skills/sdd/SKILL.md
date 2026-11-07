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
| Backend change whose behavior a later phase will consume | sdd-design; record the shared contract in the backend spec |
| Approved architectural spec, no plan yet | sdd-plan |
| Plan exists, implement it | sdd-execute |
| Keep working until a condition holds (/goal) | sdd-goal |
| Implementation green, integrate | sdd-finish |
| GitHub review on a stacked PR (`sdd-stack/task-N`) | sdd-review-fix |
| User asks to "just implement" something architectural | sdd-design first |
| Bounded feature, bugfix, or refactor (no architectural spec) | implement in this session; use test-driven-development when it fits |
| Bug, test failure, or unexpected behavior | systematic-debugging |
| About to claim the branch is complete (sdd-finish) | verification-before-completion |
| Isolated workspace / git worktree (after the human said yes) | using-git-worktrees isolate |
| Checkout of an existing stack branch for a stacked-PR review | using-git-worktrees attach (from sdd-review-fix) |
| Review the human asked for | requesting-code-review |
| Acting on review feedback | receiving-code-review |
| 2+ independent investigations (not plan tasks) | dispatching-parallel-agents |

Do not run sdd-execute without a plan file. Do not run architectural implementation without a spec file.

## Judgment

Confirm with the human only for unagreed user-facing behavior, permissions and
safety, destructive operations, external side effects beyond an existing
authorization, and costly or irreversible changes.

Investigate repository facts before asking. Within an agreed spec, goal, and
constraints, make reversible implementation decisions yourself: internal
structure, naming, and the order of investigation, implementation, and tests.
Record only assumptions that affect later work.

A supporting skill supplies a method. It does not override the agreed spec, the
constraints, or the calling skill's execution contract, and it does not add its
own mandatory TDD rule, review gate, or global stop condition. Safety boundaries
and the evidence needed for a success claim stay in force on every path.

## Shared specifications

When a backend spec will be consumed by a later phase, sdd-design records the
shared contract in that spec. A later phase reads the canonical spec and the
implementation it names instead of re-asking settled facts. A frontend spec
names the canonical backend spec and the dependent scope. Do not create a
separate shared-spec document.

## Implementation entry

Before controller-session implementation (sdd-execute Task 1, or a bounded change implemented without an execute implementer), ask once whether to create a worktree. This applies whether or not the bounded change uses test-driven-development. Do not ask from an implementer subagent.

TDD is a strong way to protect behavior, not a gate. Bounded work may use it or another verification approach justified by the behavior and regression risk. sdd-execute applies the same standard.

Do not invoke the Superpowers plugin, grill-with-docs, grilling, or domain-modeling. Supporting skills in this pack are the Superpowers copies (TDD, debugging, verification, worktrees, review). Pipeline skills stay sdd-* — do not use brainstorming, writing-plans, executing-plans, subagent-driven-development, or finishing-a-development-branch.

## HTML synchronization

For the Target documents (`CONTEXT.md`, `docs/adr/*.md`,
`docs/sdd/specs/*.md`, and `docs/sdd/plans/*.md`), route every HTML
synchronization question or failure to the common policy in
`scripts/sddlib/html_policy.py` through `scripts/html-docs`:

- Native host edit permission: `html-docs edit-check` with the host adapter's
  JSON request on stdin.
- Companion validation and Git freshness: `html-docs check --paths`,
  `html-docs check --staged`, or `html-docs check --base <ref>`.
- First-time companion permission: `html-docs bootstrap <explicit Target Markdown paths>`.
- Host setup diagnosis: `html-docs doctor`.

The policy owns target resolution, exact Markdown-byte digests, document
validation, and freshness decisions. Cursor, Claude Code, and OpenCode
adapters only translate host payloads and results; they must not duplicate
policy logic. The policy never creates or repairs Agent-authored HTML. A
Target Markdown edit must succeed before its adjacent HTML companion is
authored in a separate operation, and Git / CI remains the enforcement
boundary for shell, MCP, manual, or hook-disabled writes.

Keep the existing SDD pipeline and its no-Superpowers rule. `sdd-execute`
continues to dispatch one isolated subagent per plan Task, but CI must run
provider-neutral policy and test commands only: no host application, no
subagent, no network service, and no `gh` invocation.
