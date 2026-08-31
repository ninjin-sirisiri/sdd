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
