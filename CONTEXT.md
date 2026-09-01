# SDD

Skill pack for spec-driven design, plans, isolated execution, and stacked PRs.

## Terms

**Implementation worktree**:
The optional isolated git checkout created before execute (or bounded TDD). At most one per plan. Its branch is not a stack branch.

_Avoid_: review worktree

**Review worktree**:
A git worktree attached to an existing stack branch so that stacked PR can be updated in place.

_Avoid_: review branch, fix branch

**Stack branch**:
The git ref `sdd-stack/task-N` that is the head of that task's stacked PR. Review fixes move this ref; they do not add another branch.

_Avoid_: worktree

**Land**:
Merge stacked PRs from the bottom of the stack into the confirmed base branch, without rebasing or restacking descendants.

_Avoid_: restack

**Canonical Markdown**:
The authoritative Markdown document from which the human-facing document artifact is derived.

_Avoid_: HTML source, preview source

**Agent-authored HTML**:
A human-facing HTML artifact whose content structure and visual hierarchy are intentionally shaped by the agent rather than copied as a near-verbatim Markdown preview.

_Avoid_: Markdown preview, mechanical conversion

**Agent edit hook**:
A host-level hook that observes or rejects an agent's file-edit operation to enforce the ordering between a canonical Markdown document and its Agent-authored HTML.

_Avoid_: Git hook, commit hook

**HTML freshness gate**:
A repository-level check that prevents a change from being committed when an edited Canonical Markdown document lacks its current Agent-authored HTML companion.

_Avoid_: preview check, render hook

**Target document**:
A Canonical Markdown document at `CONTEXT.md`, `docs/adr/`, `docs/sdd/specs/`, or `docs/sdd/plans/` whose Agent-authored HTML companion is governed by the SDD synchronization rules.

_Avoid_: arbitrary Markdown, source document

**Document digest**:
The SHA-256 identity of a Target document's exact content, recorded with its Agent-authored HTML to establish that the two artifacts correspond.

_Avoid_: file timestamp, commit-only freshness

**HTML bootstrap**:
An explicit first-time operation that creates Agent-authored HTML companions for existing Target documents without relaxing the normal Markdown-before-HTML edit order.

_Avoid_: automatic backfill, preview generation

**Edit-order guarantee**:
A Target document must be successfully edited before its Agent-authored HTML may be edited, and one operation may not edit both artifacts.

_Avoid_: atomic Markdown/HTML edit, HTML-first edit
