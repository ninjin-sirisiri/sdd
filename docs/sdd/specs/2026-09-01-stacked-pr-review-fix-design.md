# Stacked PR review-fix

**Classification:** architectural

**Chosen approach:** Add pipeline skill `sdd-review-fix` and an attach path on `using-git-worktrees`. Do not spread the loop across `sdd-finish` and `receiving-code-review`. Do not keep finish option 4 open as a review session.

This spec amends post-stack review and worktree rules. The v1 framework spec (`docs/superpowers/specs/2026-08-28-sdd-framework-design.md`) still governs design, execute, stack-prs, and the optional implementation worktree. Where that document says a linked worktree must never create another worktree, this spec wins for **review worktrees** on a different **stack branch**. Land-without-restack is `docs/adr/0001-land-stacked-prs-without-restack.md`. Terms are in `CONTEXT.md`.

## Problem

Stacked PRs are refs (`sdd-stack/task-N`) created at finish. GitHub review then needs commits on a lower PR. `using-git-worktrees` always runs `git worktree add -b`, so a fix lands on a new branch (often from the stack tip). That extra branch is outside the stack chain and makes land painful. Restacking descendants would need force-push, which this pack forbids.

## Goals

- After finish option 4, GitHub review fixes update the existing stack branch in place. No new branch. No new PR.
- If the current checkout is not that stack branch, attach a review worktree to it (`-b` forbidden). Reuse that worktree on later rounds. Do not delete it.
- After tests pass in that checkout, `git push origin sdd-stack/task-N` with no `--force`.
- Descendants are not restacked. Integration is **land** from the bottom, by the human on GitHub. The agent never merges.
- Agents can find this loop: `sdd` routes to `sdd-review-fix`. Skill and prompt text stay English.

## Non-goals

- Single PR (finish option 2). Push to that PR head stays as it is.
- Review loops during sdd-execute. Polling GitHub for reviews.
- Restack, rebase of descendants, `--force`, amend, re-running `stack-prs` after review fixes.
- `gh pr create` and `gh pr merge`.
- Deleting review worktrees or making an implementation worktree required.
- A new CLI. Changes to `stack-prs`, `task-brief`, or `review-package` behavior.
- Unit tests of skill Markdown. CI that runs subagents.

## Architecture

sdd-review-fix is the controller for one open stacked PR at a time. It evaluates feedback with receiving-code-review, then uses using-git-worktrees **attach** (not isolate) so git work happens on the PR head.

Isolate (`-b`, optional, asked once before execute) and attach (existing ref, not asked) are different entries on the same worktree skill. Native worktree tools that create a new branch are forbidden for attach; fall back to `git worktree add <path> <stack-branch>`.

No new Python script. `gh` is used only to confirm an open PR whose head is `sdd-stack/task-N` (for example `gh pr view`). Push is git. Merge is the human.

## Components

- `skills/sdd-review-fix/SKILL.md` — loop. Announce: `I'm using sdd-review-fix.`
- `skills/using-git-worktrees/SKILL.md` — add attach. Isolate path unchanged for execute / bounded TDD.
- `skills/sdd/SKILL.md` — route: GitHub review on a stacked PR → sdd-review-fix.
- `skills/sdd-finish/SKILL.md` — after option 4 succeeds, point to sdd-review-fix and say land is bottom-up on GitHub. Finish does not merge and does not create review worktrees.
- `skills/receiving-code-review/SKILL.md` — evaluation only. One sentence: git on a stack branch is sdd-review-fix; this skill does not create branches.
- `README.md` — document the skill. Plugin manifests already load `./skills/`; no extra skill list.

## Data flow

1. The human asks to apply a GitHub review and names the Task or PR. Do not poll.
2. Run receiving-code-review. Do not implement unsound items.
3. Confirm there is an open PR whose head is `sdd-stack/task-N`. If not, stop. Do not touch git.
4. Resolve checkout (Working tree resolution).
5. In that checkout, implement one item at a time, test, commit on `sdd-stack/task-N`.
6. If those tests pass, `git push origin sdd-stack/task-N` with no `--force`. Do not push `main`. Do not open a PR.
7. Tell the human to land from the bottom on GitHub. The agent does not merge. Leave the review worktree in place.

Do not update `.sdd/progress.md` commit ranges. Do not run `stack-prs` again.

## Working tree resolution

Use this order. Stop at the first match.

1. If the current checkout already has `sdd-stack/task-N` checked out, work there. Do not add a second worktree for that branch (git forbids it).
2. Else if a review worktree for that branch already exists, reuse it (path `$LOCATION/sdd-stack-task-N` if it is still a worktree of that branch).
3. Else attach: `git worktree add "$LOCATION/sdd-stack-task-N" "sdd-stack/task-N"` with no `-b`. Do not ask the execute isolation prompt.

`LOCATION` follows using-git-worktrees isolate: declared path, else existing `.worktrees` or `worktrees` (`.worktrees` wins if both exist), else `.worktrees`. If `$LOCATION` is not ignored, add it to `.gitignore`, commit that, then create the worktree.

An implementation worktree may already exist. Attach is still allowed when the target is a different branch.

Attach runs the same dependency install as isolate so tests can run. It does not require a green baseline before implementing review items. After the fix, tests must pass before push.

If attach fails (including sandbox) and the current checkout is not the target stack branch, **do not** fall back to working in place. Stop. Isolate may still fall back in place on sandbox denial; attach must not.

## Ordering guarantees

- One open stacked PR per sdd-review-fix run.
- Checkout resolution is current → reuse → attach.
- Evaluate before any commit.
- Push only after tests pass in the review checkout.
- Land order is Task 1, then 2, then N. The agent never merges. If asked to merge PR N+1 while PR N is still open, stop and say to land from the bottom on GitHub. If asked to merge at all, same reply.

## Error handling

Stop with no further git (no new branch, no in-place fix on the wrong branch):

- No stacked PRs, head is not `sdd-stack/task-N`, or the PR is missing/closed/merged.
- Request to create a branch or PR, `--force`, rebase/restack, amend, re-run `stack-prs`, `gh pr create`, or `gh pr merge`.
- Request to fix two or more PRs in one run.
- Target branch is checked out in some other worktree that is neither the current directory nor a known review worktree path, and that path cannot be used.
- Review checkout is dirty. Ask the human to commit or stash. Do not switch to the tip.
- Tests fail. Do not push.
- `git push` is not a fast-forward. Do not force. Stop.
- Attach fails and the current checkout is not the target branch.
- Human asks to resolve a land conflict by restacking. Return it to the human.

If the target branch is already checked out in another worktree and that path is known, continue there (step 1 or 2). Do not create a new branch to dodge the checkout lock.

## Testing

No new CLI, so no new pytest. Do not change `stack-prs` contracts (no force, refuse to move a checked-out ref to the wrong SHA).

Manual check after implementation:

- Attach uses no `-b` and checks out `sdd-stack/task-N`.
- A second review round reuses `$LOCATION/sdd-stack-task-N`.
- Wrong-branch checkout never falls back in place when attach fails.
- Push has no `--force`.
- The skill refuses merge, new PRs, and `stack-prs` re-run.

## Consuming paths

- Human invokes sdd-review-fix, or sdd routes a stacked-PR review request there.
- sdd-finish option 4 output points here; it does not enter this loop itself.
- sdd-execute implementers do not call attach and do not create review worktrees.
- Bounded TDD still uses isolate (ask once), not attach.

## Defaults and negative requirements

- Review worktree path: `$LOCATION/sdd-stack-task-N`.
- Push remote: `origin`. Push ref: that stack branch only.
- Force-push: never.
- New stack branch names: never for review fixes.
- Ledger: do not rewrite Task complete lines after review commits.

## Success

- A review comment on stacked PR Task 1 is committed and pushed on `sdd-stack/task-1` with no extra branch.
- Task 2 is not rebased. The human lands Task 1 on GitHub first.
- An implementation worktree on another branch can stay put while a review worktree is attached to Task 1.
- `using-git-worktrees` isolate still asks once before execute and still uses `-b` for that isolation branch.
