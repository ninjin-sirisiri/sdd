---
name: dispatching-parallel-agents
description: Use to delegate independent investigations when the benefit justifies the coordination cost and context isolation, outside sdd-execute. Do not use for plan Task implementers or to obtain a review the human did not request.
---

# Dispatching Parallel Agents

Do not use this skill to run sdd-execute implementers in parallel. Plan tasks stay serial. Delegating an investigation does not authorize parallel plan-task implementation, and it is not a request for a code review.

## Overview

You delegate work to specialized agents with isolated context. By precisely crafting their instructions and context, you keep them focused and preserve your own context for coordination.

Delegation is a choice, not a default for two or more problems. Weigh the time and context it saves against the setup, coordination, integration, and duplicate-work cost. A single investigation you can do cheaply is often better than three agents and a merge step. The host's ability to run sessions concurrently is one input, not the decision.

**Core principle:** Delegate independent work when the benefit justifies the cost. Run work concurrently only when the host and the work make that safe.

## When to Use

**Consider delegation when all of these hold:**
- 2+ investigations are independent: each can be understood without the others' findings
- There is no shared writable state between them
- The benefit in time or context is worth the coordination cost
- The host can isolate a fresh session; otherwise keep the investigation sequential

**Use for:**
- 3+ test files failing with different root causes
- Multiple subsystems broken independently
- Each problem can be understood without context from others
- No shared state between investigations

**Don't use when:**
- Failures are related (fix one might fix others)
- You need to understand full system state
- You do not yet know what is broken, so you cannot partition the work
- Agents would interfere with each other
- One agent or your own investigation is cheaper
- The work is sdd-execute plan Tasks — those stay serial
- The human did not ask for a review — investigation is not a review request

## Read-Only Investigation vs Parallel Editing

These are different and need different safeguards.

### Read-only investigation

This is the default for parallel delegation.

- Agents inspect files, history, tests, logs, and other evidence.
- Agents do not edit files, stage, commit, switch branches, or change HEAD, the index, or worktree state.
- Commands must be non-mutating. If a check would write into a shared checkout, use a disposable copy or skip the run and say so.
- Each agent returns findings with file:line references and the commands or output behind them.
- Parallel investigation is safe when no agent can write to shared state.

### Parallel editing

Use only when the work is already partitioned well enough to merge safely. Before dispatch, identify:

- **Owned files:** each agent's write set, with no overlap.
- **Shared resources:** lockfiles, generated files, migrations, schema, configuration, package manifests, test databases, ports, caches, and any single checkout.
- **Integration responsibility:** who merges, who resolves conflicts, the merge order, and who runs the combined verification.
- **Isolation:** each editor works in its own checkout or worktree, or the write sets are disjoint and no one changes the shared checkout's HEAD, index, or branch.

If ownership, shared resources, or integration are unclear, serialize the work or give it to one owner. Editing agents must not change another agent's checkout or the shared checkout's git state.

## The Pattern

### 1. Decide whether to delegate

Estimate the benefit and cost. If the investigations are small, coupled, or need the same context, do them yourself or use one agent.

### 2. Identify Independent Domains

Group work by what is actually separate:
- File A tests: Tool approval flow
- File B tests: Batch completion behavior
- File C tests: Abort functionality

Each domain is independent when understanding one does not require another's findings.

### 3. Create Focused Agent Tasks

Each agent gets:
- **Specific scope:** one test file, subsystem, or question
- **Clear goal and mode:** investigate read-only, or edit specific owned files
- **Constraints:** what not to change, and which shared resources are off limits
- **Expected output:** findings with evidence, or changed files and verification

### 4. Dispatch

Send each dispatch as the host requires. Some hosts run calls issued in the same response concurrently; others do not. Issuing them together does not by itself guarantee concurrency, isolation, or ordering. Check the host's behavior. If you cannot confirm it, treat the dispatches as sequential and do not rely on overlap.

```text
Subagent (general-purpose): "Investigate agent-tool-abort.test.ts failures"
Subagent (general-purpose): "Investigate batch-completion-behavior.test.ts failures"
Subagent (general-purpose): "Investigate tool-approval-race-conditions.test.ts failures"
# Each investigation is read-only and owns no writable state.
```

### 5. Review and Integrate

When agents return:
- Read each result and check it against the code and evidence
- Verify investigations used the expected scope and did not modify files
- For edits, check ownership and conflicts before integrating
- Run the verification that covers the combined result
- Integrate all changes and spot check for systematic errors

## Agent Prompt Structure

Good agent prompts are:
1. **Focused** - One clear problem domain
2. **Self-contained** - All context needed to understand the problem
3. **Specific about mode** - Read-only investigation or explicit file ownership
4. **Specific about output** - What should the agent return?

Read-only investigation:

```markdown
Investigate the 3 failing tests in src/agents/agent-tool-abort.test.ts:
1. "should abort tool with partial output capture" - expects 'interrupted at' in message
2. "should handle mixed completed and aborted tools" - fast tool aborted instead of completed
3. "should properly track pendingToolCount" - expects 3 results but gets 0

Do not edit files, stage, commit, or change branch state. Run only non-mutating
checks. Determine whether these are timing issues, real bugs, or stale test
expectations, and cite the code and output that supports your conclusion.

Return: root cause for each failure, evidence, and the smallest fix you would
recommend.
```

Parallel editing (only with explicit ownership):

```markdown
Own these files only: src/agents/agent-tool-abort.test.ts and
src/agents/abort.ts. Do not edit other files. Do not touch package.json,
lockfiles, generated files, or git state outside your checkout.

Fix the 3 failing tests listed in the brief. Follow the existing test patterns.
Run the covering test file and report the command and actual output.

Return: files changed, root cause, verification output, and anything the
integrator must check.
```

## Common Mistakes

**❌ Too broad:** "Fix all the tests" - agent gets lost
**✅ Specific:** "Investigate agent-tool-abort.test.ts" - focused scope

**❌ No context:** "Fix the race condition" - agent doesn't know where
**✅ Context:** Paste the error messages and test names

**❌ No constraints:** Agent might refactor everything
**✅ Constraints:** "Do NOT change production code" or "Own only these files"

**❌ Vague output:** "Fix it" - you don't know what changed
**✅ Specific:** "Return root cause, evidence, and changed files"

**❌ Unstated shared state:** Two editors touch package.json or the same checkout
**✅ Ownership:** Name each write set, shared resource, and the integration owner

**❌ "Same response means parallel":** The host may run them sequentially
**✅ Check:** Confirm concurrency, or plan as sequential

## When NOT to Use

**Related failures:** Fixing one might fix others - investigate together first
**Need full context:** Understanding requires seeing entire system
**Exploratory debugging:** You don't know what's broken yet, so you cannot partition it
**Shared state:** Agents would interfere (editing same files, using same resources)
**Plan tasks:** sdd-execute implementers stay serial
**Review request:** A review happens only when the human asks; use requesting-code-review instead

## Real Example from Session

**Scenario:** 6 test failures across 3 files after major refactoring

**Failures:**
- agent-tool-abort.test.ts: 3 failures (timing issues)
- batch-completion-behavior.test.ts: 2 failures (tools not executing)
- tool-approval-race-conditions.test.ts: 1 failure (execution count = 0)

**Decision:** Independent domains - abort logic separate from batch completion separate from race conditions. The benefit of three read-only investigations outweighed the coordination cost.

**Dispatch:**
```
Agent 1 → Investigate agent-tool-abort.test.ts (read-only)
Agent 2 → Investigate batch-completion-behavior.test.ts (read-only)
Agent 3 → Investigate tool-approval-race-conditions.test.ts (read-only)
```

**Results:**
- Agent 1: Replaced timeouts with event-based waiting
- Agent 2: Fixed event structure bug (threadId in wrong place)
- Agent 3: Added wait for async tool execution to complete

**Integration:** All fixes independent, no conflicts, full suite green. Because the
investigations were read-only, the fixes were applied by one owner after the
coordinator checked the findings.

## Verification

After agents return:
1. **Review each result** - Understand what was found or changed
2. **Check scope and side effects** - Did investigations stay read-only? Did editors touch only their files?
3. **Check for conflicts** - Did agents edit the same code or shared resource?
4. **Run the covering verification** - Full suite for combined edits; affected tests for investigation conclusions that led to changes
5. **Spot check** - Agents can make systematic errors

## Boundaries

- Investigation delegation is a choice about how to gather evidence. It is not permission to parallelize sdd-execute Task implementers.
- It is not a code review. A review happens only when the human asks (requesting-code-review).
- Use the isolation the host already provides. Do not require a new host-specific tool or pin a model.
