---
name: sdd-design
description: Use before implementation when the work is new, the words are unsettled, an architectural change has no spec yet, or the user wants to grill a design.
---

# SDD Design

Do not invoke the Superpowers plugin, grill-with-docs, grilling, or domain-modeling. Design rules live in this skill. For bounded implementation after yes, use test-driven-development.

Announce: "I'm using sdd-design."

## Classify first

Say spike / bounded / architectural out loud. When unsure, take the heavier path. If hidden complexity appears, upgrade and say so. Never downgrade.

If the request spans independent subsystems too large for one spec, decompose first. Grill the first piece. Do not spend rounds refining a project that must be split.

## Explore

Read the consuming repo's CONTEXT.md (or ask which file if CONTEXT-MAP.md exists), docs/adr/, README, and enough code that (1) the codebase can answer questions instead of the human, and (2) you can contradict the human when their claim and the code disagree.

## Interview

Interview relentlessly until you and the human share one understanding. Map the subject as a **design tree**: every decision branches into the decisions that hang off it.

The session is not done when you "have a pretty good idea." It is done when the **frontier is empty**: every branch visited, nothing left silently assumed. A silent default is an unasked question. If you were about to pick an "obvious" store, shape, sync model, or default because it felt settled, ask it.

**Thin session (failure):** a handful of questions, then a design or an outline. Do not do that. There is no question cap. Several rounds is normal; a couple of questions is not an interview.

### Rounds and the frontier

The **frontier** is every decision whose prerequisites are already settled: the questions you can ask *now* without guessing at answers you haven't heard yet.

Work the tree in **rounds**. Ask the whole frontier in one chat message. Then wait. A question whose answer depends on another question still open in this round belongs to a later round, not this one.

Each round of answers reshapes the tree. Recompute the frontier. Ask the next round. Repeat until the frontier is empty.

Do not dump the whole tree in one message. That is not a round.

If the human asks for one question at a time, do that, but still walk the whole tree until the frontier is empty.

Put the round in chat in the format below. Do not collapse a multi-question frontier into a one-question form control.

A glossary collision (the human's word vs CONTEXT.md) is an unsettled prerequisite. Resolve it before any question that hangs off that word.

### Round format

```
❓ **Q1** - **<title>**: <body, including choices when you can>

➡️ <your recommended answer>

---

❓ **Q2** - **<title>**: <body>

➡️ <your recommended answer>
```

Prefer multiple choice. Always give a recommended answer. Number questions so the human can answer by number.

If the frontier is genuinely one decision, one question is a valid round. Do not invent fake branches. Do not stop while real branches remain.

Each round must pressure the domain, not only collect happy-path preferences. Include at least one question that is an edge case, a negative, an ordering, a failure, a synonym collision, or a code contradiction — unless no such branch exists for this change.

### Facts vs decisions

Facts are your job. Never ask the human for something CONTEXT.md, ADRs, README, or the codebase already answers. When a frontier question needs a fact from the environment, look it up yourself. For 2+ independent lookups, use dispatching-parallel-agents. A running lookup is an unsettled prerequisite: only questions downstream of it wait; ask the rest of the frontier now.

If the host cannot dispatch a sub-agent, look the fact up in this session. Do not stop the interview.

Decisions are the human's. Put each to them and wait. Do not answer your own decisions. Do not treat a recommendation as accepted because they did not object to a different question.

### Domain pressure

While you interview, actively sharpen the model. These are questions, not notes to yourself:

- If the human's word conflicts with CONTEXT.md, call it out immediately: which meaning is right?
- If a term is vague or overloaded, propose a precise canonical term and make them pick.
- When relationships are in play, invent a concrete edge-case scenario that forces the boundary between concepts.
- When the human states how something works, check the code. If they disagree, surface it: which is right?

Write resolved terms and qualifying ADRs in the same session (see below). Do not batch them until the end.

### Ungrillable and stop conditions

Some questions cannot be settled by talking (how something should look or feel). Do not keep rephrasing. Classify that remainder as a spike, or say so and move on.

"I don't know" is an answer. Do not force a guess.

If the human says to wrap up, stop. State remaining assumptions out loud, then ask whether the understanding is shared.

### Confirmation gate

When the frontier is empty, do not act. Summarize the shared understanding and wait for an explicit confirmation. Only then follow Endings.

Spike: grill only until the probe is specified, then the spike ending. Bounded and architectural: empty the frontier of this change, then confirm, then Endings.

## Target companions

The synchronization contract applies only to `CONTEXT.md`, `docs/adr/*.md`,
`docs/sdd/specs/*.md`, and `docs/sdd/plans/*.md`. Each Target document has an
adjacent same-stem `.html` Agent-authored HTML companion. Markdown remains the
source of truth, and the shared stylesheet is `docs/sdd/assets/sdd.css`.

After a successful Canonical Markdown edit:

1. Read the exact Markdown bytes, including line endings, trailing whitespace,
   and the final newline. Put the current lowercase SHA-256 value in the HTML
   head as `<meta name="sdd-source-digest" content="sha256:<64 lowercase hexadecimal characters>">`.
2. Author the adjacent HTML companion in a separate native file-edit
   operation. Do not edit the Markdown and HTML in one tool call or patch, and
   never invoke the retired Markdown-to-HTML renderer.
3. Run the common validator from the consuming repository:

   ```text
   python3 <pack-root>/scripts/html-docs check --paths <target>.md <target>.html
   ```

The companion must preserve source facts, visible content, headings, code,
lists, tables, links, and reading order. The validator owns synchronization,
security, structure, and text-fidelity decisions; it does not create or repair
HTML. A missing companion for an existing Target document requires explicit
`html-docs bootstrap <target>.md` before separate authoring.

## CONTEXT.md

When a term resolves, write it immediately using the template at `<pack-root>/docs/formats/context.md`. Then author the adjacent `CONTEXT.html` in the separate operation described above and validate it with:

```text
python3 <pack-root>/scripts/html-docs check --paths CONTEXT.md CONTEXT.html
```

Never put implementation detail in `CONTEXT.md`.

## ADRs

Offer an ADR only when all three gates in `<pack-root>/docs/formats/adr.md` hold. After the human agrees, write `docs/adr/NNNN-slug.md` in the consuming repo, then author its adjacent `docs/adr/NNNN-slug.html` in a separate native file-edit operation and validate the pair with `python3 <pack-root>/scripts/html-docs check --paths docs/adr/NNNN-slug.md docs/adr/NNNN-slug.html`. If a gate is missing, put the decision in the spec instead (architectural) or keep it in the short chat design (bounded). Keep the ADR formatting requirements unchanged.

## Endings

Do not enter Endings while the frontier is non-empty, except a spike whose probe is already specified.

**Spike:** Two or three sentences for the probe, get a nod, investigate cheaply, report a recommendation. Label leftover code throwaway. No spec or plan. Glossary/ADR writes still apply if they qualify.

**Bounded:** Short design in chat. Stop until an explicit yes. Before TDD, ask once whether to create an isolated git worktree (same prompt as sdd-execute Workspace). Already in a linked worktree, or a yes/no already recorded this conversation: do not ask. Yes: use using-git-worktrees, then TDD there. No: TDD in this checkout. Then use test-driven-development in this session. No spec file, no plan file.

**Architectural:** If the interview did not already choose among 2–3 approaches, propose them now, recommended first. Present the settled design in sections; wait for approval after each. Then write `docs/sdd/specs/YYYY-MM-DD-<topic>-design.md`, author the adjacent `.html` companion in a separate native file-edit operation with the current source digest, and run `python3 <pack-root>/scripts/html-docs check --paths docs/sdd/specs/YYYY-MM-DD-<topic>-design.md docs/sdd/specs/YYYY-MM-DD-<topic>-design.html`. Self-review: no placeholders, no contradictions, one interpretation per requirement, scope that fits one plan. Commit the spec plus this session's CONTEXT.md / ADR / HTML changes only after validation. Ask the human to review the spec file. Further spec edits are new commits (do not amend). After they approve, use sdd-plan. Do not use writing-plans.

Spec must record: classification, chosen approach, architecture, components, data flow, error handling, testing, goals/non-goals, consuming paths, and any numeric defaults, negative requirements, or ordering guarantees that did not earn an ADR. Do not end the session with those only in chat.

## Pack root

`<pack-root>` is the directory that contains `skills/` and `scripts/` — the same definition as the `sdd` skill. Format files are `<pack-root>/docs/formats/context.md` and `<pack-root>/docs/formats/adr.md`. Do not copy this SKILL.md alone into another repo.
