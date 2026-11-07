---
name: sdd-finish
description: Use after sdd-execute is complete, or after bounded work is green when the user asks to integrate. Merge locally, open one PR, keep the branch, or open stacked PRs one per plan task.
---

# SDD Finish

Announce: "I'm using sdd-finish."

Use verification-before-completion. Require full-suite evidence that covers the final state: executor, exact command, actual output, target revision or commit, and scope. Reuse evidence from the task reports or an earlier run when it still covers the final state. Otherwise run the consuming repo's full test suite and read the output. If it fails, report failures and do not show the menu.

Confirm the base branch (plan, conversation, or upstream). If unsure, ask.

## Spec reflection check

Before the menu, confirm the handoff is complete:

- Decisions recorded in the task reports that affect later phases are reflected in the canonical spec, including any shared-contract change made during implementation. Any dependent document that restates the old contract is aligned or confirmed to delegate.
- If a decision is missing from the canonical spec, or a dependent document still states the old contract, surface it and settle it with the human before declaring completion. Do not rewrite an already recorded task's commit range or a past ledger line to add it.
- If no later phase depends on this work, skip this check.

## Menu

Named branch (normal repo or named worktree), present exactly:

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Push stacked PRs, one per plan Task

Which option?
```

Detached HEAD: omit 1. Bounded work with no `.sdd/progress.md` complete lines: omit 4.

Wait for the human. Do not add extra options.

## Execute

1. Checkout base, pull, merge the feature branch, re-run the full suite. On failure, stop and leave the branch. On success, delete the feature branch only after tests pass.
2. `git push -u origin <feature-branch>` then `gh pr create` for that single branch. Needs `gh`.
3. Do nothing.
4. Run:

```text
python3 <pack-root>/scripts/stack-prs --base <base-branch> --ledger .sdd/progress.md --plan <plan-path>
```

If the command exits non-zero, report any PR URLs it printed and which tasks remain. Do not force-push. Do not rebase or amend. Needs `gh`. Two or more PRs are also linked as a GitHub stack (`POST /repos/{owner}/{repo}/stacks`). If that step fails, report the PR URLs and that the stack was not created.

After option 4 succeeds, later GitHub review fixes use sdd-review-fix. Land stacked PRs from the bottom on GitHub. Do not merge, restack, or create review worktrees from finish.

Option 4 is unavailable without a ledger. Do not invent task boundaries from `git log` guesswork.

worktree cleanup is out of scope unless this checkout is a git worktree you created in this session (including after the sdd-execute workspace prompt). Creating a worktree is optional.

`<pack-root>` is the directory that contains `skills/` and `scripts/` — the same definition as the `sdd` skill.
