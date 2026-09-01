---
name: sdd-review-fix
description: Apply one GitHub review to an open stacked PR whose head is sdd-stack/task-N. Use after sdd-finish option 4 when the human names that PR or task. Do not use during sdd-execute. Do not use for finish option 2 (single PR).
---

# SDD Review Fix

Announce: "I'm using sdd-review-fix."

One open stacked PR per run. Do not poll GitHub. The human names the Task number or the PR.

## Stop first

If the request is any of the following, stop. Do not touch git. Do not create a branch.

- Merge (`gh pr merge` or landing PRs yourself). Tell the human to land from the bottom on GitHub (Task 1, then 2, then N). If they asked to merge PR N+1 while PR N is still open, say that too.
- Create a branch or a PR, `--force`, rebase, restack, amend, or re-run `stack-prs`.
- Fix two or more PRs in this run.
- Resolve a land conflict by restacking. Return it to the human.

Do not call `gh pr create` or `gh pr merge` at any later step.

## Evaluate

Use receiving-code-review. Do not implement unsound items.

## Confirm the PR

If they named a PR number:

```bash
gh pr view <n> --json headRefName,state
```

If they named Task N:

```bash
gh pr list --head sdd-stack/task-N --state open --json number,headRefName,state
```

Stop unless the PR is open and `headRefName` is `sdd-stack/task-N`. If `headRefName` is `owner:sdd-stack/task-N`, accept it only when the ref after the colon is `sdd-stack/task-N`. Any other head: stop. Do not touch git.

## Checkout

Use using-git-worktrees **Attach** with target `sdd-stack/task-N`. That skill implements current → reuse → `git worktree add "$LOCATION/sdd-stack-task-N" "sdd-stack/task-N"` with no `-b`. Do not ask the execute isolation prompt.

If the review checkout is dirty, stop and ask the human to commit or stash. Do not switch to the tip.

If attach fails and this checkout is not `sdd-stack/task-N`, stop. Do not edit in place.

An implementation worktree on another branch may stay.

## Implement

In the review checkout, implement one review item at a time. Test each. Commit on `sdd-stack/task-N`.

Do not update `.sdd/progress.md` Task complete lines.

After the fixes, run the tests again in that checkout. If they fail, do not push.

## Push

```bash
git push origin sdd-stack/task-N
```

No `--force`. Do not push `main`. If the push is not a fast-forward, stop. Do not force.

Do not run `stack-prs`.

## Close

Tell the human to land from the bottom on GitHub. Do not merge. Do not delete the review worktree. Reuse it on the next review round for this PR.
