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

**Creation failure:** If `git worktree add` fails — permission, sandbox denial, unusable path — stop. Report the failure and the attempted path. Ask the human to choose an alternative isolation mechanism or explicitly allow work in the current checkout. Do not run setup, tests, or edits in place without that permission. An explicit instruction from the human that already allows in-place work in this session is the only exception; a creation failure is not permission.

### Step 2: Project Setup

Choose setup from the README, lockfiles, and existing configuration, and run
only what this work needs. Read the README and configuration before running a
package manager. Do not infer the package manager from one manifest, and do not
create or modify a lockfile during setup.

```bash
# Node.js — the lockfile and README decide the package manager
if [ -f pnpm-lock.yaml ]; then pnpm install
elif [ -f yarn.lock ]; then yarn install
elif [ -f bun.lock ] || [ -f bun.lockb ]; then bun install
elif [ -f package-lock.json ]; then npm ci
fi
# package.json with no lockfile: follow the README's documented setup. Do not
# run `npm install` just because package.json exists, and do not create a
# lockfile.

# Rust — build only when the work needs it
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

# Go — download only when the work needs dependencies
if [ -f go.mod ]; then go mod download; fi
```

Skip an install when the dependencies are already present and this work does not
change them. If the README names a setup this list does not cover, follow the
README. If two sources disagree about the package manager or installer, ask the
human.

### Step 3: Verify Clean Baseline

Run tests to ensure the workspace starts clean. Use the project-appropriate
command from the README:

```bash
# For example
pnpm test / npm test / cargo test / pytest / go test ./...
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

**Creation failure:** If add fails and the current checkout is not the target branch, stop. Tell the human attach failed. Do not work in place.

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
| Isolate, create fails (permission, sandbox, path) | Stop. Ask for another mechanism or explicit in-place permission; do not continue automatically |
| Isolate, `package.json` without a lockfile | Follow the README; do not default to `npm install` or create a lockfile |
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
| No lockfile/README setup, or dependencies not needed | Skip dependency install |

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "I'm obviously not in a worktree — no need to check" | Run isolate Step 0. Harness-created isolation and submodules both fool eyeballing; the detection commands settle it. |
| "`git worktree add` is quicker than hunting for a native tool" | For isolate, a native tool owns placement. For attach, native tools that create a new branch are forbidden — use `git worktree add <path> <existing-branch>`. |
| "The worktree directory is surely ignored already" | Run `git check-ignore`. An unignored worktree directory commits the whole tree into the repo. |
| "Any directory name works" | Explicit instructions beat an existing project-local directory, which beats the `.worktrees/` default. Attach paths are `$LOCATION/sdd-stack-task-N`. |
| "The workspace is fresh — baseline tests can wait" | Isolate: a dirty baseline makes every later failure ambiguous. Attach: do not require a green baseline before the review fix; sdd-review-fix tests after the fix. |
| "The sandbox blocked the worktree, so working in place is the only option" | Isolation was requested. Stop and ask for another mechanism or explicit in-place permission. A creation failure is not consent. |
| "`package.json` means `npm install`" | The lockfile, README, and existing configuration decide the package manager. Do not create or modify a lockfile during setup. |
| "Attach failed, I'll edit in this checkout" | If this checkout is not the target stack branch, stop. Attach failure never becomes in-place work. |
| "Already in a worktree, so I must not attach another" | Isolate skips a second isolate worktree. Attach of a different branch is allowed. |
