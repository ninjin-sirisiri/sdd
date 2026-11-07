# Implementer Subagent Prompt Template

Use this template when dispatching an implementer subagent.

```
Dispatch a fresh isolated subagent (Cursor Task tool, or Claude Code Agent tool).

Subagent task:
  description: "Implement Task [N]: [TASK_NAME]"
  prompt: |
    You are implementing Task [N]: [TASK_NAME]

    Read the brief first: [BRIEF_FILE]
    Work from: [WORKDIR]
    Write a short report to: [REPORT_FILE]

    ## Context

    [CONTEXT]

    ## Global Constraints

    [GLOBAL_CONSTRAINTS]

    ## Shared specification

    [SHARED_SPEC]

    ## Your Job

    Implement the brief. Write the tests it names. Commit when the work is done.

    ## Judgment

    Within the agreed brief, Global Constraints, and shared specification, make
    reversible decisions yourself: internal structure, naming, and the order of
    implementation and tests. Record only assumptions that affect later work.

    Return BLOCKED or NEEDS_CONTEXT instead of inventing agreement when a
    decision changes important unagreed user-facing behavior, permissions or
    safety, destructive operations, external side effects beyond existing
    authorization, or costly or irreversible changes. Name the decision, the
    options, and its impact. Do not call an important decision a low-risk
    assumption.

    If an agreed decision changes a premise a later phase depends on, include
    the canonical spec update in this task's deliverables and commit range
    before you report DONE. Do not leave it only in the report, the ledger, or
    chat. Do not rewrite an already recorded task's completion range.

    test-driven-development is available if you want it. It is not a gate.

    ## Report

    Write [REPORT_FILE] with:
    - What you implemented
    - Verification evidence for each named check: executor, exact command,
      actual output or result, target change (commit/files), and scope. Do not
      write only "tests pass".
    - Decisions that affect later phases: settled or changed items, the
      canonical spec path, and whether it was updated (or "none")
    - Files changed
    - Notes or concerns, if any

    Then report back with ONLY (under 15 lines):
    - **Status:** DONE | BLOCKED | NEEDS_CONTEXT
    - Commits created (short SHA + subject)
    - One-line test summary
    - Notes, if any
    - The report file path
```
