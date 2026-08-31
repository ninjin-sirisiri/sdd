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

    ## Your Job

    Implement the brief. Write the tests it names. Commit when the work is done.

    If you cannot proceed without a decision the brief does not make, stop
    and report BLOCKED or NEEDS_CONTEXT. Do not invent requirements.

    test-driven-development is available if you want it. It is not a gate.

    ## Report

    Write [REPORT_FILE] with:
    - What you implemented
    - Tests run and results
    - Files changed
    - Notes or concerns, if any

    Then report back with ONLY (under 15 lines):
    - **Status:** DONE | BLOCKED | NEEDS_CONTEXT
    - Commits created (short SHA + subject)
    - One-line test summary
    - Notes, if any
    - The report file path
```
