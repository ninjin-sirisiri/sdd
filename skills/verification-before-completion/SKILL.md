---
name: verification-before-completion
description: Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires verification evidence that covers the current target; evidence before assertions always
---

# Verification Before Completion

## Overview

**Core principle:** Evidence before claims, always.

A success claim needs evidence that covers the current target. Evidence does
not have to come from this message or from the agent making the claim.

## The Evidence Contract

A usable verification record contains:

- **Executor** — who or what ran the check: you, a subagent, CI, or the human.
- **Command** — the exact command or equivalent action.
- **Actual result** — output, exit status, failure counts, or the observed
  result. "Passed" alone is not output.
- **Target change** — the commit, revision, files, or diff the result covers.
- **Verification scope** — what the check covers and what it does not.

Evidence from another executor is usable when it satisfies this contract and
still covers the current target. Reuse it and cite it. Do not run the check
again only because you did not run it yourself.

Re-run only what the impact requires when:

- the target changed after the run;
- a dependency, configuration, or related specification changed;
- the recorded scope does not cover the claim; or
- the evidence is insufficient (missing executor, command, output, target,
  or scope).

Never present an unexecuted result as successful.

## Three Failure States

- **Bare success claim** — "all tests pass", "done", "fixed" with no command,
  output, target, or scope. Not evidence. Obtain the record or run the check.
- **Stale evidence** — the command and output exist, but the target changed
  after the run. Re-run the affected checks; unaffected results stay usable
  when their scope is still valid.
- **Insufficient evidence** — a field of the contract is missing, or the scope
  does not support the claim. Obtain the missing part or run the check.

## The Gate Function

```
BEFORE claiming any status or expressing satisfaction:

1. IDENTIFY: What claim are you making, and what evidence would prove it?
2. COLLECT: Find the existing verification record. Check the executor,
   command, actual result, target change, and scope.
3. VALIDATE: Does it still cover the current target and the claim?
   - Valid      → reuse it and cite the record
   - Stale      → re-run the affected checks
   - Bare claim → obtain the evidence or run the check
   - Insufficient → obtain the missing part or run the check
4. READ: Full output, exit code, failures.
5. VERIFY: Does the output confirm the claim?
   - NO: State the actual status with evidence.
   - YES: State the claim WITH evidence.
6. ONLY THEN: Make the claim.
```

## Common Failures

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | Command, actual output, target revision, scope covering the current state | Previous run, "should pass", bare "all tests pass" |
| Linter clean | Linter output: 0 errors | Partial check, extrapolation |
| Build succeeds | Build command: exit 0 | Linter passing, logs look good |
| Bug fixed | Reproduction or regression evidence that the symptom is gone | Code changed, assumed fixed |
| Regression test works | Evidence the test fails when the bug is present | Test passes once |
| Agent completed | Report with the evidence fields and a diff matching the target | Agent reports "success" |
| Requirements met | Line-by-line checklist | Tests passing |

## Red Flags - STOP

- Using "should", "probably", "seems to"
- Expressing satisfaction before evidence
- About to commit/push/PR without evidence
- A success report with no command, output, target, or scope
- Evidence from before the target changed, presented as current
- Relying on partial verification for a full claim
- Thinking "just this once"
- Tired and wanting work over
- **ANY wording implying success without evidence that covers the target**

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "Should work now" | Run it or find evidence that covers it. |
| "I'm confident" | Confidence ≠ evidence. |
| "Just this once" | The evidence requirement does not depend on the occasion. |
| "Linter passed" | Linter ≠ compiler. |
| "Agent said success" | Check the report's evidence and target. A valid subagent record is reusable; a bare claim is not. |
| "I'm tired" | Exhaustion ≠ excuse. |
| "Partial check is enough" | Say what it covers. Run what the claim requires. |
| "Different words so rule doesn't apply" | The meaning of the claim decides, not the wording. |

## Key Patterns

**Tests:**
```
✅ [Run test command] [See: 34/34 pass at HEAD abc123] "All tests pass"
✅ [Read report: executor implementer, command `pytest -q`, output 34 passed,
    target HEAD abc123, scope full suite, HEAD unchanged] "All tests pass"
❌ "Should pass now" / "Looks correct"
❌ "All tests pass" with no command or output
```

**Regression tests:**
```
✅ Test fails with the bug present → fix → test passes
✅ Code came first: break the behavior temporarily → test fails → restore → passes
❌ "I've written a regression test" without evidence that it can fail
```

**Build:**
```
✅ [Run build] [See: exit 0] "Build passes"
❌ "Linter passed" (linter doesn't check compilation)
```

**Requirements:**
```
✅ Re-read plan → Create checklist → Verify each → Report gaps or completion
❌ "Tests pass, phase complete"
```

**Agent delegation:**
```
✅ Report has executor, command, actual output, target, and scope; target unchanged
   → reuse the evidence and cite it
✅ Report is bare, stale, or outside its scope → obtain the missing evidence
   or run the affected checks
❌ Trust "success" with no evidence
```

## When To Apply

**ALWAYS before:**
- ANY variation of success/completion claims
- ANY expression of satisfaction
- ANY positive statement about work state
- Committing, PR creation, task completion
- Moving to next task
- Delegating to agents

**Rule applies to:**
- Exact phrases
- Paraphrases and synonyms
- Implications of success
- ANY communication suggesting completion/correctness
