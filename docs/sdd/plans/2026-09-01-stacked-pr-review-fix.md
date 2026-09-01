# Stacked PR review-fix Implementation Plan

**Goal:** After stacked PRs exist, a GitHub review updates the existing `sdd-stack/task-N` head in place via an attached review worktree, with no extra branch and no restack.

**Architecture:** `sdd-review-fix` owns the loop (evaluate, confirm the open PR, implement, test, push). `using-git-worktrees` gains an attach mode that checks out an existing stack branch with no `-b`. Isolate (`-b`, optional before execute) stays a separate entry. Finish and receiving-code-review only point here; they do not merge or create branches.

**Tech Stack:** English skill Markdown, git worktrees, `gh` for PR state only, existing pytest (no new CLI).

**Spec:** `docs/sdd/specs/2026-09-01-stacked-pr-review-fix-design.md`

## Global Constraints

- After finish option 4, GitHub review fixes update the existing stack branch in place. No new branch. No new PR.
- If the current checkout is not that stack branch, attach a review worktree to it (`-b` forbidden). Reuse that worktree on later rounds. Do not delete it.
- After tests pass in that checkout, `git push origin sdd-stack/task-N` with no `--force`.
- Descendants are not restacked. Integration is **land** from the bottom, by the human on GitHub. The agent never merges.
- Agents can find this loop: `sdd` routes to `sdd-review-fix`. Skill and prompt text stay English.
- Single PR (finish option 2) is out of scope for sdd-review-fix.
- Do not add review loops during sdd-execute. Do not poll GitHub for reviews.
- Do not restack, rebase descendants, `--force`, amend, or re-run `stack-prs` after review fixes.
- Do not call `gh pr create` or `gh pr merge`.
- Do not delete review worktrees or make an implementation worktree required.
- Do not add a new CLI. Do not change `stack-prs`, `task-brief`, or `review-package` behavior.
- Do not unit-test skill Markdown. Do not run subagents in CI.
- Review worktree path: `$LOCATION/sdd-stack-task-N`.
- Push remote: `origin`. Push ref: that stack branch only.
- Force-push: never.
- New stack branch names: never for review fixes.
- Ledger: do not rewrite Task complete lines after review commits.
- Checkout resolution is current → reuse → attach.
- One open stacked PR per sdd-review-fix run.
- If attach fails (including sandbox) and the current checkout is not the target stack branch, do not fall back to working in place. Stop.

## File structure

| Path | Responsibility |
|---|---|
| `skills/using-git-worktrees/SKILL.md` | Isolate (`-b`) and attach (existing branch) |
| `skills/sdd-review-fix/SKILL.md` | Review-fix loop |
| `skills/sdd/SKILL.md` | Route stacked-PR reviews to sdd-review-fix |
| `skills/sdd-finish/SKILL.md` | After option 4, point to sdd-review-fix and land |
| `skills/receiving-code-review/SKILL.md` | Evaluation only; stack git is sdd-review-fix |
| `skills/sdd-execute/SKILL.md` | No review worktrees from execute |
| `README.md` | Document sdd-review-fix |
| `docs/superpowers/specs/2026-08-28-sdd-framework-design.md` | Pointer to this spec for post-stack review |

Do not add scripts, pytest files, or plugin manifest skill lists.

## Task 1: Attach path on using-git-worktrees

Replace `skills/using-git-worktrees/SKILL.md` with the file below. Isolate behavior stays: ask is still owned by execute/bounded TDD; `-b` still creates the isolation branch; sandbox denial may still work in place **for isolate only**. Attach never uses `-b`, never asks the execute prompt, never uses a native tool that would create a branch, and never falls back in place when the current checkout is not the target branch.

Write `skills/using-git-worktrees/SKILL.md` as exactly:

````markdown
---
name: using-git-worktrees
description: Use isolate when the human requests isolation, or when sdd-execute's workspace prompt (or bounded TDD's equivalent) was answered yes. Use attach when sdd-review-fix names an existing stack branch. Do not use for sdd-execute Task implementers. Never create an isolate worktree during sdd-execute unless the human already said yes. Never use -b during attach.
---

# Using Git Worktrees

This skill has two modes. The caller picks one.

- **Isolate** — new branch with `-b`. sdd-execute / bounded TDD after the human said yes.
- **Attach** — existing branch, no `-b`. sdd-review-fix only.

Do not use this skill for sdd-execute Task implementers.

If the caller named an existing branch (for stacked PR review, `sdd-stack/task-N`), follow **Attach**. Otherwise follow **Isolate**.

## Isolate

sdd-execute asks once before Task 1 whether to create a worktree. It is optional. Use isolate after they said yes, or when they independently request isolation.

### Overview

Ensure work happens in an isolated workspace. Prefer your platform's native worktree tools. Fall back to manual git worktrees only when no native tool is available.

**Core principle:** Detect existing isolation first. Then use native tools. Then fall back to git. Never fight the harness.

**Announce at start:** "I'm using the using-git-worktrees skill to set up an isolated workspace."

### Step 0: Detect Existing Isolation

**Before creating anything, check if you are already in an isolated workspace.**

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
BRANCH=$(git branch --show-current)
```

**Submodule guard:** `GIT_DIR != GIT_COMMON` is also true inside git submodules. Before concluding "already in a worktree," verify you are not in a submodule:

```bash
# If this returns a path, you're in a submodule, not a worktree — treat as normal repo
git rev-parse --show-superproject-working-tree 2>/dev/null
```

**If `GIT_DIR != GIT_COMMON` (and not a submodule):** You are already in a linked worktree. Skip to Step 2 (Project Setup). Do NOT create another isolate worktree. This skip is isolate-only. It does not refuse Attach of a different branch in a later invocation.

Report with branch state:
- On a branch: "Already in isolated workspace at `<path>` on branch `<name>`."
- Detached HEAD: "Already in isolated workspace at `<path>` (detached HEAD, externally managed). Branch creation needed at finish time."

**If `GIT_DIR == GIT_COMMON` (or in a submodule):** You are in a normal repo checkout.

Has the user already indicated their worktree preference in your instructions? If not, ask for consent before creating a worktree:

> "Would you like me to set up an isolated worktree? It protects your current branch from changes."

Honor any existing declared preference without asking. If the user declines consent, work in place and skip to Step 2.

### Step 1: Create Isolated Workspace

**You have two mechanisms. Try them in this order.**

#### 1a. Native Worktree Tools (preferred)

The user has asked for an isolated workspace (Step 0 consent). Do you already have a way to create a worktree? It might be a tool with a name like `EnterWorktree`, `WorktreeCreate`, a `/worktree` command, or a `--worktree` flag. If you do, use it and skip to Step 2.

Native tools handle directory placement, branch creation, and cleanup automatically. Using `git worktree add` when you have a native tool creates phantom state your harness can't see or manage.

Only proceed to Step 1b if you have no native worktree tool available.

#### 1b. Git Worktree Fallback

**Only use this if Step 1a does not apply** — you have no native worktree tool available. Create a worktree manually using git.

##### Directory Selection

Follow this priority order. Explicit user preference always beats observed filesystem state. Store the chosen directory in `LOCATION` and use only that path for ignore checks and creation.

1. **Check your instructions for a declared worktree directory preference.** If the user has already specified one, set `LOCATION` to that path without asking.

2. **Check for an existing project-local worktree directory:**
   ```bash
   ls -d .worktrees 2>/dev/null     # Preferred (hidden)
   ls -d worktrees 2>/dev/null      # Alternative
   ```
   If `.worktrees` exists, `LOCATION=.worktrees`. Else if `worktrees` exists, `LOCATION=worktrees`. If both exist, `.worktrees` wins.

3. **If there is no other guidance available**, set `LOCATION=.worktrees` at the project root.

##### Safety Verification (project-local directories only)

**MUST verify the selected directory is ignored before creating a worktree:**

```bash
git check-ignore -q "$LOCATION"
```

Check only `$LOCATION`. Do not treat a different candidate as proof that the selected path is ignored.

**If NOT ignored:** Add `$LOCATION` to .gitignore, commit the change, then proceed.

**Why critical:** Prevents accidentally committing worktree contents to repository.

##### Create the Worktree

```bash
# Determine path based on chosen location
path="$LOCATION/$BRANCH_NAME"

git worktree add "$path" -b "$BRANCH_NAME"
cd "$path"
```

**Sandbox fallback:** If `git worktree add` fails with a permission error (sandbox denial), tell the user the sandbox blocked worktree creation and you're working in the current directory instead. Then run setup and baseline tests in place.

### Step 2: Project Setup

Auto-detect and run appropriate setup:

```bash
# Node.js
if [ -f package.json ]; then npm install; fi

# Rust
if [ -f Cargo.toml ]; then cargo build; fi

# Python — detect the installer. pyproject.toml alone is not Poetry.
if [ -f poetry.lock ] || grep -q '^\[tool\.poetry\]' pyproject.toml 2>/dev/null; then
  poetry install
elif [ -f uv.lock ]; then
  uv sync
elif [ -f pdm.lock ]; then
  pdm install
elif [ -f Pipfile.lock ]; then
  pipenv install
elif [ -f requirements.txt ]; then
  pip install -r requirements.txt
elif [ -f pyproject.toml ]; then
  echo "pyproject.toml found but the installer is unclear. Ask the human how to install dependencies; do not run poetry/uv/pip automatically."
fi

# Go
if [ -f go.mod ]; then go mod download; fi
```

### Step 3: Verify Clean Baseline

Run tests to ensure workspace starts clean:

```bash
# Use project-appropriate command
npm test / cargo test / pytest / go test ./...
```

**If tests fail:** Report failures, ask whether to proceed or investigate.

**If tests pass:** Report ready.

#### Report

```
Worktree ready at <full-path>
Tests passing (<N> tests, 0 failures)
Ready to implement <feature-name>
```

## Attach

Use only when the caller named an existing branch. For stacked PR review the target is `sdd-stack/task-N`.

**Announce at start:** "I'm using the using-git-worktrees skill to attach to an existing branch."

Do not ask the execute isolation prompt. Do not use `-b`. Do not use a native worktree tool if it would create a new branch. Use git.

N is the integer in `sdd-stack/task-N`. `LOCATION` uses the same Directory Selection and Safety Verification as isolate Step 1b. The worktree path is `$LOCATION/sdd-stack-task-N`.

Resolve the checkout in this order. Stop at the first match.

1. If `git branch --show-current` equals the target branch, stay. Run Project Setup (isolate Step 2). Do not run isolate Step 3 as a gate. Do not add a second worktree for this branch. Report the current path.
2. Else if `"$LOCATION/sdd-stack-task-N"` exists, is a git worktree, and `git -C "$LOCATION/sdd-stack-task-N" branch --show-current` equals the target, `cd` there. Run Project Setup. Report that path.
3. Else create:

```bash
git worktree add "$LOCATION/sdd-stack-task-N" "sdd-stack/task-N"
cd "$LOCATION/sdd-stack-task-N"
```

Then run Project Setup. Do not require a green isolate baseline before returning. After sdd-review-fix implements, tests must pass before push (that is sdd-review-fix, not this step).

If `git worktree add` fails because the branch is already checked out, read `git worktree list --porcelain`. If a worktree has `branch refs/heads/sdd-stack/task-N`, continue in that path (step 1 or 2). If that path cannot be used, stop. Do not `git worktree add -b` to dodge the lock.

**Sandbox / permission failure:** If add fails and the current checkout is not the target branch, stop. Tell the human attach failed. Do not work in place. Isolate sandbox fallback does not apply.

Do not delete the review worktree.

#### Attach report

```
Review worktree attached at <full-path> on <branch>
```

## Quick Reference

| Situation | Action |
|---|---|
| Isolate, already in linked worktree | Skip isolate creation (Step 0) |
| Isolate, in a submodule | Treat as normal repo (Step 0 guard) |
| Isolate, native worktree tool available | Use it (Step 1a) |
| Isolate, no native tool | Git worktree fallback with `-b` (Step 1b) |
| Isolate, permission error on create | Sandbox fallback, work in place |
| Attach | Never `-b`. Never native tools that create a branch |
| Attach, already on target branch | Stay, setup, do not add another worktree |
| Attach, `$LOCATION/sdd-stack-task-N` exists for that branch | Reuse it |
| Attach, else | `git worktree add "$LOCATION/sdd-stack-task-N" "sdd-stack/task-N"` |
| Attach, add fails and current branch is not the target | Stop. Do not work in place |
| `.worktrees/` exists | Use it (verify ignored) |
| `worktrees/` exists | Use it (verify ignored) |
| Both exist | Use `.worktrees/` |
| Neither exists | Check instruction file, then default `.worktrees/` |
| Directory not ignored | Add `$LOCATION` to .gitignore + commit |
| Tests fail during isolate baseline | Report failures + ask |
| No package.json/Cargo.toml | Skip dependency install |

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "I'm obviously not in a worktree — no need to check" | Run isolate Step 0. Harness-created isolation and submodules both fool eyeballing; the detection commands settle it. |
| "`git worktree add` is quicker than hunting for a native tool" | For isolate, a native tool owns placement. For attach, native tools that create a new branch are forbidden — use `git worktree add <path> <existing-branch>`. |
| "The worktree directory is surely ignored already" | Run `git check-ignore`. An unignored worktree directory commits the whole tree into the repo. |
| "Any directory name works" | Explicit instructions beat an existing project-local directory, which beats the `.worktrees/` default. Attach paths are `$LOCATION/sdd-stack-task-N`. |
| "The workspace is fresh — baseline tests can wait" | Isolate: a dirty baseline makes every later failure ambiguous. Attach: do not require a green baseline before the review fix; sdd-review-fix tests after the fix. |
| "Attach failed, I'll edit in this checkout" | If this checkout is not the target stack branch, stop. In-place fallback is isolate-only. |
| "Already in a worktree, so I must not attach another" | Isolate skips a second isolate worktree. Attach of a different branch is allowed. |
````

Run:

```bash
test -f skills/using-git-worktrees/SKILL.md
grep -F 'git worktree add "$path" -b "$BRANCH_NAME"' skills/using-git-worktrees/SKILL.md
grep -F 'git worktree add "$LOCATION/sdd-stack-task-N" "sdd-stack/task-N"' skills/using-git-worktrees/SKILL.md
grep -F 'Never use -b during attach' skills/using-git-worktrees/SKILL.md
grep -F 'Do not work in place' skills/using-git-worktrees/SKILL.md
python3 -m pytest -q
```

Expect: both `git worktree add` lines present, pytest pass (scripts unchanged).

```bash
git add skills/using-git-worktrees/SKILL.md
git commit -m "Add worktree attach so stacked PR reviews checkout existing branches."
```

## Task 2: sdd-review-fix skill

Create `skills/sdd-review-fix/SKILL.md` as exactly:

````markdown
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
````

Run:

```bash
test -f skills/sdd-review-fix/SKILL.md
grep -F "I'm using sdd-review-fix." skills/sdd-review-fix/SKILL.md
grep -F 'git push origin sdd-stack/task-N' skills/sdd-review-fix/SKILL.md
grep -F 'Do not call `gh pr create` or `gh pr merge`' skills/sdd-review-fix/SKILL.md
python3 -m pytest -q
```

```bash
git add skills/sdd-review-fix/SKILL.md
git commit -m "Add sdd-review-fix so stacked PR reviews update stack heads in place."
```

## Task 3: Route, finish pointer, and README

Keep each edit surgical. Do not rewrite whole files.

### `skills/sdd/SKILL.md`

In the frontmatter `description`, change `sdd-design, sdd-plan, sdd-execute, sdd-goal, or sdd-finish` to `sdd-design, sdd-plan, sdd-execute, sdd-goal, sdd-finish, or sdd-review-fix`.

In the Route table, after the `sdd-finish` row, add:

```markdown
| GitHub review on a stacked PR (`sdd-stack/task-N`) | sdd-review-fix |
```

Change the using-git-worktrees row to:

```markdown
| Isolated workspace / git worktree (after the human said yes) | using-git-worktrees isolate |
| Checkout of an existing stack branch for a stacked-PR review | using-git-worktrees attach (from sdd-review-fix) |
```

### `skills/sdd-finish/SKILL.md`

Immediately after the paragraph that starts `If the command exits non-zero, report any PR URLs` (option 4), add:

```markdown
After option 4 succeeds, later GitHub review fixes use sdd-review-fix. Land stacked PRs from the bottom on GitHub. Do not merge, restack, or create review worktrees from finish.
```

### `skills/receiving-code-review/SKILL.md`

Immediately after the `**Core principle:**` line, add:

```markdown
If the pull request head is a stack branch (`sdd-stack/task-N`), git operations (worktree, commit, push) are sdd-review-fix. This skill does not create branches.
```

### `skills/sdd-execute/SKILL.md`

Replace the line `Do not use using-git-worktrees for Task implementer subagents. `[WORKDIR]` is this chosen checkout.` with:

```markdown
Do not use using-git-worktrees for Task implementer subagents. Do not attach review worktrees. Isolate only, and only after the human said yes. `[WORKDIR]` is this chosen checkout.
```

### `README.md`

In Claude Code invoke list, add `/sdd:sdd-review-fix`. In Cursor invoke sentence, add `/sdd-review-fix`.

After the pipeline paragraph about `sdd-finish`, add:

```markdown
After stacked PRs exist, GitHub review fixes use `sdd-review-fix` (existing `sdd-stack/task-N` only). Land from the bottom on GitHub.
```

In the supporting skills table, change the using-git-worktrees row to:

```markdown
| using-git-worktrees | Isolate: optional before implementation. Attach: existing `sdd-stack/task-N` from sdd-review-fix (`-b` forbidden) |
```

Add a pipeline-adjacent row above the supporting table, as a new small table after the sdd-goal paragraph:

```markdown
| Skill | When |
|---|---|
| sdd-review-fix | GitHub review on an open stacked PR after finish option 4 |
```

In Manual check, add item 4:

```markdown
4. After stacked PRs exist, `/sdd-review-fix` (Claude Code: `/sdd:sdd-review-fix`) is visible. Confirm the skill forbids `-b`, `gh pr merge`, and `stack-prs` re-run.
```

### `docs/superpowers/specs/2026-08-28-sdd-framework-design.md`

Immediately after the sentence `ブランチ名は `sdd-stack/task-N`。Task 1 の PR の base は確認済み base branch。Task N の PR の base は `sdd-stack/task-(N-1)`。途中失敗時は、作れた PR の URL と未作成 Task を報告する。` add:

```markdown
公開後の GitHub レビュー修正は `docs/sdd/specs/2026-09-01-stacked-pr-review-fix-design.md` が正。既存の stack branch に attach し、restack しない。
```

If that spec file is also rendered to HTML in-repo, run:

```bash
python3 scripts/render-docs docs/superpowers/specs/2026-08-28-sdd-framework-design.md
```

If HTML fails, warn and continue. If no HTML sibling exists for that spec, do not create a new HTML layout; skip render.

Run:

```bash
grep -F 'sdd-review-fix' skills/sdd/SKILL.md
grep -F 'later GitHub review fixes use sdd-review-fix' skills/sdd-finish/SKILL.md
grep -F 'git operations (worktree, commit, push) are sdd-review-fix' skills/receiving-code-review/SKILL.md
grep -F 'Do not attach review worktrees' skills/sdd-execute/SKILL.md
grep -F 'sdd-review-fix' README.md
grep -F '2026-09-01-stacked-pr-review-fix-design.md' docs/superpowers/specs/2026-08-28-sdd-framework-design.md
python3 -m pytest -q
```

```bash
git add skills/sdd/SKILL.md skills/sdd-finish/SKILL.md skills/receiving-code-review/SKILL.md skills/sdd-execute/SKILL.md README.md docs/superpowers/specs/2026-08-28-sdd-framework-design.md
```

If a matching HTML file was regenerated, add it too.

```bash
git commit -m "Route stacked PR reviews to sdd-review-fix and point finish at land."
```
