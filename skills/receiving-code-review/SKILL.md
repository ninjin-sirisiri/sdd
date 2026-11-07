---
name: receiving-code-review
description: Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable - requires technical rigor and verification, not performative agreement or blind implementation
---

# Code Review Reception

## Overview

Code review requires technical evaluation, not emotional performance. Courtesy
is fine; agreement is not evidence. Verify each item against the code before
acting on it.

**Core principle:** Verify before implementing. Ask before assuming. Technical correctness over social comfort.

If the pull request head is a stack branch (`sdd-stack/task-N`), git operations (worktree, commit, push) are sdd-review-fix. This skill does not create branches.

## The Response Pattern

```
WHEN receiving code review feedback:

1. READ: Complete feedback without reacting
2. UNDERSTAND: Restate each requirement in your own words; identify what is unclear
3. VERIFY: Check each item against codebase reality
4. EVALUATE: Is it technically sound for THIS codebase? Does it depend on an unresolved answer?
5. RESPOND: State the technical finding, ask about unclear items, or push back with reasoning
6. ACT: Implement independent items (batched when useful), hold only dependent items, verify the affected scope
```

## Courtesy and Substance

Normal courtesy is welcome. What matters is that it does not replace
verification.

```
✅ "Thanks — fixed in app/items.py:42; the covering test now passes."
✅ "Fixed. I checked the call sites and changed the guard."
✅ [Just fix it and show the code and verification]

❌ "You're absolutely right!" without checking anything
❌ "Great point!" followed by blind implementation
```

A brief thanks is not the problem. Performative agreement is a problem when it
substitutes for checking whether the feedback is correct.

## Handling Unclear Feedback

Work item by item instead of treating the whole review as one block.

```
FOR each item in the feedback:
  IF the requirement is clear:
    verify and act on it
  IF the requirement is unclear:
    ask for clarification before implementing that item
    do not guess

  IF another item depends on the unresolved answer:
    hold that item too and say what it depends on
  ELSE:
    continue with the independent item and its verification
```

If you cannot tell whether an item depends on the answer, treat it as dependent
and hold it. If the unresolved question changes the scope or design of the whole
change, say so and hold the affected work; do not use that as a reason to stop
unrelated, independently verifiable work.

**Example:**
```
Reviewer asks for 1-6.
You understand 1,2,3,5,6. Item 4 is unclear, and item 6 depends on 4.

✅ RIGHT: "I understand 1,2,3,5,6. Item 4 is unclear: do you mean X or Y?
   Item 6 depends on that answer, so I am holding it. 1,2,3,5 are
   independent and fixed; the affected tests pass."
❌ WRONG: Stop all work until 4 is answered, including the independent fixes.
❌ WRONG: Guess at 4 and implement everything.
```

## Source-Specific Handling

### From your human partner
- **Trusted** - implement after understanding
- **Still verify against the codebase** - the same technical standard applies
- **Still ask** if scope or an item is unclear
- **Substance over performance** - state the fix or the reason, not agreement
- **Skip to action** or a brief technical acknowledgment

### From External Reviewers
```
BEFORE implementing:
  1. Check: Technically correct for THIS codebase?
  2. Check: Breaks existing functionality?
  3. Check: Reason for current implementation?
  4. Check: Works on all platforms/versions?
  5. Check: Does reviewer understand full context?

IF suggestion seems wrong:
  Push back with technical reasoning

IF can't easily verify:
  Say so: "I can't verify this without [X]. Should I [investigate/ask/proceed]?"

IF conflicts with your human partner's prior decisions:
  Stop and discuss with your human partner first
```

**your human partner's rule:** "External feedback - be skeptical, but check carefully"

## YAGNI Check for "Professional" Features

```
IF reviewer suggests "implementing properly":
  grep codebase for actual usage

  IF unused: "This endpoint isn't called. Remove it (YAGNI)?"
  IF used: Then implement properly
```

**your human partner's rule:** "You and reviewer both report to me. If we don't need this feature, don't add it."

## Implementation Order

```
FOR multi-item feedback:
  1. Group items by dependency.
     Clarify unclear items, but hold only the items that depend on the answer.
  2. Implement in this order:
     - Blocking issues (breaks, security)
     - Simple fixes (typos, imports)
     - Complex fixes (refactoring, logic)
  3. Independent fixes may be batched when that is simpler. Keep each change
     attributable to the review item it addresses.
  4. Verify the affected behavior and the scope the caller needs. A batch needs
     verification that covers the batch and its interactions. Reuse valid
     evidence per the caller's verification contract; do not claim a fix from a
     bare success statement.
  5. If a change affects shared behavior or other items, verify the affected
     scope again.
```

If the calling skill defines a stricter order or per-item verification (for
example `sdd-review-fix`'s one item at a time), follow the caller. This section
is the default when no stricter contract applies.

## When To Push Back

Push back when:
- Suggestion breaks existing functionality
- Reviewer lacks full context
- Violates YAGNI (unused feature)
- Technically incorrect for this stack
- Legacy/compatibility reasons exist
- Conflicts with your human partner's architectural decisions

**How to push back:**
- Use technical reasoning, not defensiveness
- Ask specific questions
- Reference working tests/code
- Involve your human partner if architectural

**If you're uncomfortable pushing back out loud:** Name that tension, then tell your partner about the issue you've seen. They'll appreciate your honesty.

## Acknowledging Correct Feedback

When feedback IS correct, acknowledge it briefly or just make the change. State
what changed and the evidence that covers it.

```
✅ "Fixed in api/items.py:88. The owner-scoping test now passes."
✅ "Checked this and you're right: the client sends an id cursor. Updated the
   handler; the cursor test passes."
✅ [Just fix it and show the code and verification]

❌ "You're absolutely right!" with no verification, followed by a blind change
```

**Why substance matters:** The acknowledgment is secondary. What proves the
review was handled is the change and the verification behind it.

## Gracefully Correcting Your Pushback

If you pushed back and were wrong:
```
✅ "You were right - I checked [X] and it does [Y]. Implementing now."
✅ "Verified this and you're correct. My initial understanding was wrong because [reason]. Fixing."

❌ Long apology
❌ Defending why you pushed back
❌ Over-explaining
```

State the correction factually and move on.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Performative agreement | Verify, then state the finding or make the change |
| Blind implementation | Verify against the codebase first |
| Batched fixes with no verification | Verify the affected behavior and interactions |
| Assuming reviewer is right | Check whether it breaks something |
| Avoiding pushback | Technical correctness > comfort |
| Holding every item because one is unclear | Hold only the items that depend on the answer |
| Guessing at an unclear item | Ask, and hold that item; continue independent work |
| Can't verify, proceed anyway | State the limitation, ask for direction |

## Real Examples

**Performative Agreement (Bad):**
```
Reviewer: "Remove legacy code"
❌ "You're absolutely right! Let me remove that..." (without checking)
```

**Technical Verification (Good):**
```
Reviewer: "Remove legacy code"
✅ "Checking... build target is 10.15+, this API needs 13+. Need legacy for backward compat. Current impl has wrong bundle ID - fix it or drop pre-13 support?"
```

**YAGNI (Good):**
```
Reviewer: "Implement proper metrics tracking with database, date filters, CSV export"
✅ "Grepped codebase - nothing calls this endpoint. Remove it (YAGNI)? Or is there usage I'm missing?"
```

**Mixed Independent and Unclear Items (Good):**
```
your human partner: "Fix items 1-6"
You understand 1,2,3,5,6. Unclear on 4. Item 6 depends on 4.
✅ "1,2,3,5 are independent and fixed; their tests pass. Item 4 is unclear:
   do you mean X or Y? Item 6 depends on that answer and is held."
```

## GitHub Thread Replies

When replying to inline review comments on GitHub, reply in the comment thread (`gh api repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies`), not as a top-level PR comment.
