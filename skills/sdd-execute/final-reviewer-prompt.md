# Final Reviewer Prompt Template

Use after every task has passed its per-task gate.

```
Dispatch a fresh isolated subagent (Cursor Task tool, or Claude Code Agent tool).

Subagent task:
  description: "Review the complete branch"
  prompt: |
    You are reviewing the whole branch against the plan.

    ## Plan

    [PLAN_PATH]

    ## Review Package

    Read [DIFF_FILE] (MERGE_BASE..HEAD). Do not re-derive the diff.
    Read-only.

    ## Deferred Minors

    [MINOR_LEDGER]

    Triage which Minor items must be fixed before merge.

    ## What to Check

    Plan alignment, code quality, architecture, testing, production
    readiness. Categorize Critical / Important / Minor. Cite file:line.

    ## Output Format

    ### Strengths
    ### Issues
    #### Critical (Must Fix)
    #### Important (Should Fix)
    #### Minor (Nice to Have)
    ### Assessment
    **Ready to merge?** [Yes | No | With fixes]
    **Reasoning:** [1-2 sentences]
```
