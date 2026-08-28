# Task Reviewer Prompt Template

Use this template when dispatching a task reviewer. One reviewer, two verdicts:
spec compliance and code quality.

```
Dispatch a fresh isolated subagent (Cursor Task tool, or Claude Code Agent tool).

Subagent task:
  description: "Review Task [N] (spec + quality)"
  prompt: |
    You are reviewing one task: first whether it matches its requirements,
    then whether it is well-built. This is a task-scoped gate, not a merge
    review.

    ## What Was Requested

    Read the task brief: [BRIEF_FILE]

    Global constraints that bind this task:
    [GLOBAL_CONSTRAINTS]

    ## What the Implementer Claims

    Read the implementer's report: [REPORT_FILE]

    ## Diff Under Review

    **Base:** [BASE_SHA]
    **Head:** [HEAD_SHA]
    **Diff file:** [DIFF_FILE]

    Read the diff file once. Do not re-run git. Do not crawl the broader
    codebase unless you can name a concrete risk, and then one focused check
    per risk. Read-only: do not mutate the worktree.

    ## Do Not Trust the Report

    Treat the report as claims. Judge the code. A rationale does not
    downgrade severity.

    ## Tests

    The implementer already ran tests and reported TDD evidence. Do not
    re-run the suite to confirm. Run a test only when the code raises a
    specific doubt no existing run answers — focused, never package-wide.

    ## Part 1: Spec Compliance

    Missing / Extra / Misunderstood. If a requirement cannot be verified
    from this diff, report ⚠️ and what the controller should check.

    ## Part 2: Code Quality

    Separation of concerns, error handling, DRY without premature
    abstraction, tests that verify behavior, file responsibilities.

    Cite file:line for every finding. Final message begins with the spec
    verdict. No preamble.

    ## Calibration

    Important means this task cannot be trusted until fixed: incorrect
    behavior, missed requirement, or merge-blocking maintainability
    (verbatim logic duplication, swallowed errors, tests that assert
    nothing). Broader coverage is Minor.
    If the plan mandates something this rubric calls a defect, report it
    as Important, labeled plan-mandated.

    ## Output Format

    ### Spec Compliance

    - ✅ Spec compliant | ❌ Issues found: [with file:line]
    - ⚠️ Cannot verify from diff: [and what to check]

    ### Strengths
    [specific]

    ### Issues

    #### Critical (Must Fix)
    #### Important (Should Fix)
    #### Minor (Nice to Have)

    ### Assessment

    **Task quality:** [Approved | Needs fixes]

    **Reasoning:** [1-2 sentences]
```
