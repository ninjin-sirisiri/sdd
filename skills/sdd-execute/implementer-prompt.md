# Implementer Subagent Prompt Template

Use this template when dispatching an implementer subagent.

```
Dispatch a fresh isolated subagent (Cursor Task tool, or Claude Code Agent tool).

Subagent task:
  description: "Implement Task [N]: [TASK_NAME]"
  prompt: |
    You are implementing Task [N]: [TASK_NAME]

    ## Task Description

    Read your task brief first: [BRIEF_FILE]
    It contains the full task text from the plan.

    ## Context

    [CONTEXT]

    ## Before You Begin

    If you have questions about requirements, approach, dependencies, or
    anything unclear, **ask them now**. Do not start work while guessing.

    ## Your Job

    Once you're clear:
    1. Follow test-driven-development (RED-GREEN-REFACTOR). If that skill
       is available, read and obey it. Minimum: write a failing test, run
       it and confirm it fails for the expected reason, write the minimal
       code, run the test and confirm it passes. Repeat per step in the brief.
    2. Run the focused test while iterating; run the full suite once before
       commit.
    3. Commit.
    4. Self-review (below).
    5. Write the full report to [REPORT_FILE].

    Work from: [WORKDIR]

    If something unexpected appears, ask. Do not invent requirements.

    ## Code Organization

    Follow the file structure in the brief. One responsibility per file.
    If a file grows past the brief's intent, stop and report DONE_WITH_CONCERNS.
    Do not split files the brief did not ask for.

    ## When You're in Over Your Head

    STOP and report BLOCKED or NEEDS_CONTEXT when the task needs an
    architectural choice the brief does not make, you cannot find the code
    you need, or you are unsure the approach is correct.

    ## Before Reporting Back: Self-Review

    Completeness, quality, YAGNI, and tests that verify behavior (not mocks).
    Fix issues before reporting.

    ## After Review Findings

    If you fix reviewer findings, re-run the tests that cover the amended
    code and append command + output to [REPORT_FILE].

    ## Report Format

    Write the full report to [REPORT_FILE]:
    - What you implemented (or attempted, if blocked)
    - What you tested and results
    - **TDD Evidence**:
      - RED: command, failing output, why that failure was expected
      - GREEN: command and passing output
    - Files changed
    - Self-review findings
    - Concerns

    Then report back with ONLY (under 15 lines):
    - **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
    - Commits created (short SHA + subject)
    - One-line test summary
    - Concerns, if any
    - The report file path

    If BLOCKED or NEEDS_CONTEXT, put the specifics in the final message.
    Use DONE_WITH_CONCERNS if you finished but doubt correctness or scope.
```
