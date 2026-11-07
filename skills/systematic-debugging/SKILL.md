---
name: systematic-debugging
description: Use when a bug, test failure, or unexpected behavior needs a cause investigation proportionate to its risk
---

# Systematic Debugging

## Overview

**Core principle:** Find and understand the cause before you fix it, and keep evidence that the fix addresses that cause. Symptom fixes that leave the cause in place are failure.

Investigation scales with the problem. A typo-level defect may need one reproduction and one focused check. A failure that crosses process, network, or storage boundaries may need instrumentation at each boundary. The phases below are questions to answer, not a ceremony that requires equal effort in every phase.

For a small defect, start with the failing test and the code path it exercises. Do not open a design interview, read unrelated modules end to end, or add defense layers with no bypass path. When the evidence already identifies the cause, stop investigating and fix it.

**Proportionality check:** Before opening a file, ask what question it answers. If the failing test and its imports already identify the cause, do not read unrelated modules. If you only need to confirm a module is unrelated, its docstring or a search for its callers is enough; do not read it end to end.

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you have not investigated, you cannot responsibly propose a fix. For a small defect the investigation can be small — reproduce it, read the error, confirm the cause — but it still comes first.

## Secret Values in Diagnostics

Diagnostics must show presence, not content. Use a presence check:

```bash
if [ -n "${IDENTITY:-}" ]; then echo 'IDENTITY: SET'; else echo 'IDENTITY: UNSET'; fi
```

Never run `env`, `set`, `printenv IDENTITY`, `echo "$IDENTITY"`, or any other command that expands a secret value. Even when you only need to know whether it is set, `printenv` and `echo` print the value when it is present. If a tool output already contains a secret, do not repeat it in your report or transcript.

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

**Don't skip the investigation when:**
- Issue seems simple (simple bugs have causes too)
- You're in a hurry (rushing guarantees rework)
- Manager wants it fixed NOW (systematic is faster than thrashing)

## The Four Phases

Treat these as a loop. Spend effort where uncertainty and impact are highest. Compress or skip a phase when the evidence already answers its questions, and say what you are relying on.

### Phase 1: Root Cause Investigation

**BEFORE attempting a fix:**

1. **Read Error Messages Carefully**
   - Don't skip past errors or warnings
   - They often contain the exact solution
   - Read stack traces completely
   - Note line numbers, file paths, error codes

2. **Reproduce Consistently**
   - Can you trigger it reliably?
   - What are the exact steps?
   - Does it happen every time?
   - If not reproducible → gather more data, don't guess

3. **Check Recent Changes**
   - What changed that could cause this?
   - Git diff, recent commits
   - New dependencies, config changes
   - Environmental differences

4. **Gather Evidence in Multi-Component Systems**

   **WHEN the system has multiple components (CI → build → signing, API → service → database):**

   **BEFORE proposing fixes, consider diagnostic instrumentation:**
   ```
   For the component boundaries the failure could cross:
     - Log what data enters the component
     - Log what data exits the component
     - Verify environment/config propagation
     - Check state at each layer

   Run once to gather evidence showing WHERE it breaks
   THEN analyze evidence to identify the failing component
   THEN investigate that specific component
   ```

   **Example (multi-layer signing system):**
   ```bash
   # Layer 1: Workflow — report presence, never the value
   echo "=== Workflow environment: ==="
   if [ -n "${IDENTITY:-}" ]; then echo 'IDENTITY: SET'; else echo 'IDENTITY: UNSET'; fi

   # Layer 2: Build script — same presence check
   echo "=== Build environment: ==="
   if [ -n "${IDENTITY:-}" ]; then echo 'IDENTITY: SET'; else echo 'IDENTITY: UNSET'; fi

   # Layer 3: Signing script — non-sensitive metadata only
   echo "=== Keychain state: ==="
   security list-keychains
   security find-identity -v -p codesigning | wc -l

   # Layer 4: Actual signing
   codesign --sign "$IDENTITY" --verbose=4 "$APP"
   ```

   **Never print secret values.** Log presence (`SET`/`UNSET`), counts, paths, exit status, or other non-sensitive metadata. Do not run `env`, `set`, or `printenv`, and do not use `echo "$IDENTITY"` or any other command that expands the value; these print the value when the variable is set. Use a presence check like the one above.

   **This reveals:** which layer fails (identity present in the workflow, missing in the build script, and so on).

5. **Trace Data Flow**

   **WHEN error is deep in call stack:**

   See `root-cause-tracing.md` in this directory for the complete backward tracing technique.

   **Quick version:**
   - Where does bad value originate?
   - What called this with bad value?
   - Keep tracing up until you find the source
   - Fix at source, not at symptom

### Phase 2: Pattern Analysis

**Find the pattern before fixing. Choose the depth by how much the cause is still unclear. Skip this phase when the failing test and the called code already identify the cause:**

1. **Find Working Examples**
   - Locate similar working code in same codebase
   - What works that's similar to what's broken?

2. **Compare Against References**
   - If implementing a pattern, read the part of the reference that governs the failing behavior
   - Start from the failing path; use imports, stack traces, and search results to decide what to read
   - Use the failing test's import graph as the starting path; do not enumerate and read the whole repository
   - Do not read unrelated modules end to end just because they are nearby
   - For an unfamiliar or subtle pattern, reading the whole reference may be justified; for a small change, the relevant paths and their contracts may be enough
   - State what you did not read and why it is safe to skip

3. **Identify Differences**
   - What's different between working and broken?
   - List the differences that could plausibly affect the behavior
   - Don't assume "that can't matter" without a reason

4. **Understand Dependencies**
   - What other components does this need?
   - What settings, config, environment?
   - What assumptions does it make?

### Phase 3: Hypothesis and Testing

**Scientific method, proportional to the uncertainty:**

1. **Form a Hypothesis**
   - State clearly: "I think X is the cause because Y"
   - Write it down
   - Be specific, not vague

2. **Test Minimally**
   - Prefer the smallest change or probe that distinguishes the hypothesis from the alternatives
   - One variable at a time when you need to attribute the result

3. **Verify Before Continuing**
   - Did it work? Yes → Phase 4
   - Didn't work? Form a NEW hypothesis from the new evidence
   - DON'T add more fixes on top

4. **When You Don't Know**
   - Say "I don't understand X"
   - Don't pretend to know
   - Ask for help
   - Research more

### Phase 4: Implementation

**Fix the cause, not the symptom:**

1. **Reproduce or Specify the Failure**
   - Preferred: a failing test that demonstrates the defect, when practical
   - Otherwise: a recorded reproduction — exact command, input, expected result, actual result
   - If correct implementation already exists, keep it; add regression evidence and confirm it catches the break when practical
   - TDD is one method here, not a requirement. Use `test-driven-development` when it fits the behavior and risk

2. **Implement the Fix**
   - Address the cause identified
   - Keep the change focused; do not bundle unrelated refactoring
   - If you must change several things together, verify their effects separately

3. **Verify the Fix**
   - Re-run the reproduction or regression test
   - Run the checks the change could plausibly affect
   - Confirm no new failure
   - Use the `verification-before-completion` skill before claiming success
   - Verification scales with cause and regression risk: a one-line change may need a focused test and the nearest suite; a cross-cutting change may need the full suite

4. **If the Fix Doesn't Work**
   - Return to Phase 1 with the new information
   - Do not pile on unverified changes
   - Reassess the stall by progress, uncertainty, and impact:
     - **Progress:** is each attempt narrowing the cause, or only moving the symptom?
     - **Uncertainty:** can you state the cause and the evidence, or are you still guessing?
     - **Impact:** is the remaining work local, or does it threaten a shared contract, data, or safety?
   - If you are not making progress and the impact is high, report the evidence and ask for help
   - Respect the calling skill's retry or resume limit. A controller that allows one resume does not get overridden by this skill

5. **When Repeated Fixes Point at the Architecture**
   - Consider this when each fix reveals new shared state, coupling, or a failure in a different place
   - Also consider it when a fix requires broad refactoring or creates new symptoms elsewhere
   - Repeated failures are a signal to re-examine your model of the cause, not an automatic architecture review
   - If the evidence suggests the design is wrong, state the evidence and discuss the options with your human partner
   - A fixed failure count is not the decision rule; progress, uncertainty, and impact are

## Red Flags - Return to Evidence

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "Skip the test, I'll manually verify"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "Pattern says X but I'll adapt it differently"
- "Here are the main problems: [lists fixes without investigation]"
- Proposing solutions before tracing data flow
- **"One more fix attempt" after several failures without new evidence**
- **Each fix reveals new problem in different place**
- **About to run `printenv`, `env`, or `echo "$SECRET"` to check a secret**

**These mean: return to the evidence. Re-read the error, re-check the reproduction, or gather the missing data before changing more code.**

## your human partner's Signals You're Doing It Wrong

**Watch for these redirections:**
- "Is that not happening?" - You assumed without verifying
- "Will it show us...?" - You should have added evidence gathering
- "Stop guessing" - You're proposing fixes without understanding
- "Ultra-think this" - Question fundamentals, not just symptoms
- "We're stuck?" (frustrated) - Your approach isn't working

**When you see these:** pause and return to the evidence.

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need investigation" | Simple issues have causes too. The investigation can be quick, but reproduce and confirm the cause. |
| "Emergency, no time for process" | Systematic debugging is usually faster than guess-and-check thrashing. |
| "Just try this first, then investigate" | The first fix sets the pattern. Investigate before changing behavior. |
| "I'll write a test after confirming the fix works" | A fix without a check is weak evidence. Add regression evidence and confirm it catches the break when practical; TDD is one way, not the only way. |
| "Multiple fixes at once saves time" | You can't isolate what worked. Verify changes separately when attribution matters. |
| "Reference too long, I'll adapt the pattern" | Understand the part that governs the failing behavior. For a subtle pattern, that may be all of it. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding the cause. |
| "One more fix attempt" (after several failures) | Repeated failures mean your model of the cause is wrong. Return to evidence and reassess, don't stack guesses. |
| "Small bug, no need to verify" | Verification scales with risk, but an unverified fix is not done. |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes, gather evidence | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare relevant differences | Identify the cause, not every difference |
| **3. Hypothesis** | Form theory, test minimally | Confirmed or replaced by a better hypothesis |
| **4. Implementation** | Reproduce, fix, verify proportionally | Cause addressed, verification covers the risk |

## When Investigation Reveals "No Root Cause"

If investigation reveals the issue is truly environmental, timing-dependent, or external:

1. You've completed the investigation
2. Document what you investigated
3. Implement appropriate handling (retry, timeout, error message)
4. Add monitoring/logging for future investigation

**But:** many "no root cause" cases are incomplete investigation. Say what remains unknown.

## Supporting Techniques

These techniques are part of systematic debugging and available in this directory:

- **`root-cause-tracing.md`** - Trace bugs backward through the call stack to find the original trigger
- **`defense-in-depth.md`** - Add checks at the boundaries the failure can pass through, proportionate to trust boundaries and bypass paths
- **`condition-based-waiting.md`** - Replace arbitrary timeouts with condition polling
