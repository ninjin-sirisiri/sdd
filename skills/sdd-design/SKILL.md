---
name: sdd-design
description: Use before implementation when the work is new, the words are unsettled, an architectural change has no spec yet, or the user wants to grill a design.
---

# SDD Design

Do not invoke the Superpowers plugin, grill-with-docs, grilling, or domain-modeling. Design rules live in this skill. For bounded implementation after yes, use test-driven-development when it fits the behavior and risk.

Announce: "I'm using sdd-design."

## Classify first

Say spike / bounded / architectural out loud. Treat the label as an initial
judgment that investigation can raise or lower; when unsure, take the heavier
path. If hidden complexity appears, upgrade and say so. Never downgrade to avoid
an approval or a required spec.

If the goal needs multiple specs, decompose first and follow Spec roadmaps before
designing an individual piece. This includes dependent phases, such as separate
backend and frontend specs, not only independent subsystems too large for one
spec. Do not refine a project that must be split as though it were one spec.

## Explore

Read the consuming repo's CONTEXT.md (or ask which file if CONTEXT-MAP.md exists), docs/adr/, README, related specs, and enough code that (1) the codebase can answer questions instead of the human, and (2) you can contradict the human when their claim and the code disagree. When the change follows an earlier phase or has a later consumer, read the specs, ADRs, implementation, and tests that establish the shared behavior.

If this checkout records design history, also search the case before interviewing (see Confirm before saving). A recorded answer is evidence of what the person said, not a replacement for an approved document.

## Spec roadmaps

When a goal is split into multiple specs, create or update a Spec roadmap before
the detailed interview or design of the next individual spec. Reuse an approved
roadmap when its split and dependencies still apply; starting another spec does
not by itself require a new roadmap or another roadmap approval. Explore enough
to justify the boundaries and dependencies, and ask only important open
questions needed to draft the roadmap without designing every piece upfront.
If the split becomes clear during an individual interview, pause that design
and take this step. Single-spec work, bounded changes, and spikes do not require
a roadmap.

Record:

- the overall goal, completion criteria, and non-goals;
- each spec's stable label, purpose, scope boundary, and observable completion
  criteria; distinguish existing spec paths from planned specs not yet written;
- dependencies and their reasons, the proposed design order, and the next spec
  to design; distinguish required ordering from a suggested order for independent
  pieces;
- which spec owns each cross-spec contract and which specs consume it;
- important unresolved items, their affected work, and when they must be resolved.

Keep the roadmap lightweight. Do not expand every spec into a detailed design,
implementation tasks, or a calendar. Shared behavior still belongs to its
canonical owning spec under Shared specification and later phases; the roadmap
identifies ownership and dependencies, not a second authority for API or other
contract details. Do not create placeholder individual spec files.

Write `docs/sdd/specs/YYYY-MM-DD-<topic>-roadmap.md`. Before writing, present the
overall goal, completion criteria, non-goals, split, and order, and get explicit
confirmation (see Confirm before saving). It uses the existing spec Target
category, not a new synchronization category. After the Markdown edit,
author the adjacent `.html` in a separate native file-edit operation with the
current source digest, following Target companions. Validate from the consuming
repository:

```text
python3 <pack-root>/scripts/html-docs check --paths docs/sdd/specs/YYYY-MM-DD-<topic>-roadmap.md docs/sdd/specs/YYYY-MM-DD-<topic>-roadmap.html
```

Present the saved roadmap and wait for explicit human approval before starting
the individual spec's detailed interview or design. A chat-only outline is not
the saved roadmap. Roadmap approval accepts the split and order, not any
individual spec, implementation scope, or permission to run sdd-plan or
sdd-execute. After approval, design the selected spec through the normal
interview and approval flow; do not automatically design all remaining specs.

At each later spec design, read the existing roadmap and the relevant canonical
specs, implementation, and tests. Reference the roadmap path and the selected
scope in the individual spec, and add actual spec paths to the roadmap as they
become available. Update the roadmap when scope boundaries, dependencies,
contract ownership, or the next design step change. Re-confirm important
changes to the agreed split or ordering before dependent design continues;
link-only updates do not need another approval round. For existing multi-spec
work without a roadmap, recover it from the settled documents and facts, then
obtain approval before the next individual design; do not reopen approved specs
or repeat settled interviews just to backfill it.

## Interview

The interview ends when you and the human share the goal, acceptance criteria,
important constraints, and the decisions that affect later phases, or when a
remaining item is unresolved and its impact is explicit. It does not end only
when every implementation detail is decided. There is no required number or
format of questions.

Confirm with the human:

- unagreed user-facing behavior;
- permissions, safety, and destructive operations;
- external side effects beyond an existing authorization;
- costly or irreversible changes;
- shared contracts that a later phase depends on.

Facts are your job. Never ask the human for something CONTEXT.md, ADRs, README,
related specs, tests, or the codebase already answers. When a question needs a
fact from the environment, look it up yourself. For 2+ independent lookups, use
dispatching-parallel-agents. If the host cannot dispatch a sub-agent, look the
fact up in this session.

Within the agreed goal and constraints, decide reversible implementation
details yourself: internal structure, naming, component-local state, and the
order of investigation, implementation, and tests. Record the assumptions and
reasons that affect later work; do not record every detail.

A recommendation is not an accepted decision. Put an important open decision to
the human and wait. Do not treat a recommendation as accepted because the human
did not object to a different question. Do not manufacture agreement for an item
that blocks implementation.

Ask only what changes the design and is still unsettled: user-facing behavior,
acceptance criteria, important constraints, and contracts a later phase depends
on. Combine independent topics into one round; sequence dependent ones, because
the answer to the first changes the second. One question is fine when one
decision is open. When a choice has meaningfully different options, present them
with a recommendation and the reason, and accept a free-text answer that is none
of them. Do not use a fixed form, do not wait for approval after each section,
and do not set a minimum or maximum number of questions.

### Domain pressure

While you interview, actively sharpen the model. These are questions, not notes
to yourself:

- If the human's word conflicts with CONTEXT.md, call it out immediately: which meaning is right?
- If a term is vague or overloaded, propose a precise canonical term and make them pick.
- When relationships are in play, invent a concrete edge-case scenario that forces the boundary between concepts.
- When the human states how something works, check the code. If they disagree, surface it: which is right?

A glossary collision (the human's word vs CONTEXT.md) is an unsettled
prerequisite. Resolve it before questions that hang off that word.

Write resolved terms and qualifying ADRs in the same session (see below). Do not batch them until the end.

### Ungrillable and stop conditions

Some questions cannot be settled by talking (how something should look or feel).
Classify that remainder as a spike, or leave it to frontend design or to
implementation when it is reversible and local. Do not keep rephrasing.

"I don't know" is an answer. Do not force a guess.

If the human says to wrap up, stop. State remaining assumptions and unresolved
items with their impact, then ask whether the understanding is shared.

## Confirm before saving

The interview settles the design. Before a spec or roadmap is written or
rewritten, reconcile the planned content with the recorded answers and the
conversation, then present it once for explicit confirmation. This is a separate
gate from the post-save document review and from implementation approval, and it
does not replace either of them.

### Recorded history

Where this checkout records design history, search the case before writing:

```text
<pack-root>/scripts/design-history search --case <case>
```

Ask design questions through the recording form (`design_question`) when the
host provides it, and use the case ID you searched. A question asked only in
free chat is not recorded, so it cannot be reconciled later.

Use `--query` for a topic and `--question-id` for one question. Search the case
this design will use, and treat another case's answer as unrelated evidence
until the person says it applies. Branch on the JSON `status`, never on an empty
`results`:

- `ok`: compare every planned statement that the history covers against the
  recorded question and answer.
- `no-matches` (exit 3): the recorder is healthy and nothing matched this
  filter. Treat the point as unsettled only if the design still needs it; do
  not conclude that no answer exists.
- `no-database` (exit 4): recording never ran here. Say automatic recording is
  absent and use the current conversation and approved documents.
- `recording-unavailable` (exit 5): the recorder is stopped or failed, so an
  empty result is not silence. Say so and recover before relying on it.
- `unavailable` (exit 5): the store cannot be read. Stop and report the cause;
  do not guess at the answers.
- `invalid` (exit 2): the filter or request is wrong. Fix it; do not read it as
  "no answers".

Exit codes are 0 ok, 2 invalid, 3 no-matches, 4 no-database, 5 unavailable,
6 Git-refused. `design-history status` reports when the store is Git-refused
(exit 6): fix the ignore rule or untrack the database before recording.
Recorded answers are excerpts of what the person said: evidence to reconcile
agreement, not approval of a document. Never rewrite a raw record, and never
treat your reading of an answer as the person's words or consent. Imported past
logs (`--source design-history.import`) are excerpts the person chose; they are
the same kind of evidence. Import only a named log and case: show
`import-preview` pairs and exclusion reasons, and run `import-confirm` with the
same arguments only after the person agrees that those pairs may be used.

### New documents

Before writing a new spec Markdown, present the goal, completion criteria,
non-goals, and important constraints in chat once, and get explicit
confirmation. For a roadmap, present the split and order too. For a truly new
roadmap, confirm the split and order before saving and keep the approval after
saving. A chat outline is not a saved document.

Keep each important undecided item undecided, with its impact and the point
where it must be resolved. Never write an assumption as a settled fact. If
nothing is unsettled, do not invent extra questions to fill the confirmation.

### Existing documents

Do not rewrite an existing spec or roadmap until the target, the meaning being
changed, and the impact on dependent work are explicitly agreed. History is
evidence for that reconciliation; it does not outrank an approved document and
is never a second authority for the shared contract. When a shared-contract
change is agreed, reflect it in the owning spec, then align the affected
dependent specs and plans.

An edit that does not change meaning, such as adding a link or fixing a typo,
needs no new approval round. State what changes and why, then make it.

### When a required record is missing

If recording is enabled for the session and an answer the document depends on
cannot be obtained, stop that document's save. Say which decision is missing,
what depends on it, and how to recover: re-ask in a session where recording
works, repair the recorder, or import a named past log. Do not save the document
and do not back-fill the answer from the model later.

On a host without recording support, or in a checkout where recording is not
enabled, say plainly that automatic recording is absent. Use the current
conversation and the approved documents for the same confirmation. Every
protection above still applies except the recorder-specific stop.

## Shared specification and later phases

When a backend or other earlier-phase design will be consumed by a later phase
(a frontend, a separate spec, or another plan), identify the shared contract
during design and record it in the earlier-phase spec. Use a recognizable
section; do not create a separate shared-spec file and do not require a fixed
heading. Record only what applies:

- the user operations and the expected success and failure results;
- the contracts later phases depend on: API, data meaning, permissions, state changes, and error behavior;
- settled items, and undecided items with the work they affect and when they must be resolved;
- what implementation settled or changed, and the constraints that remain.

This is not a checklist to ask the human item by item. Choose topics from the
intended use cases and the later phase's needs. For example, list ordering,
pagination, and delete cancellation belong before backend work that depends on
them. Page layout, colors, and component-local state can stay in frontend design
when they do not change the shared contract.

For a destructive operation, ask explicitly whether it is immediate and final,
or can be cancelled or undone, and what a failed or repeated operation returns.
A recommendation or an assumed non-goal is not the human's agreement.

Do not implement on top of an important undecided item by inventing agreement.
Choose investigation, a small probe, or a question to the human. Independent
work may proceed. Distinguish a deliberate deferral from an unnoticed decision.

### Starting a later phase

When starting a frontend or other later-phase design:

- Read the canonical earlier-phase spec and the implementation and tests it names.
- Do not re-ask facts that the spec, code, or tests already settle.
- Confirm only important unresolved items, contradictions, or new requirements, and state their impact.
- Reference the canonical spec path and the dependent scope in the later-phase spec. A summary or quoted constraint is fine, but do not edit the later-phase spec as an independent authority for the shared contract.
- When a shared-contract change is agreed, update the canonical spec and align the affected later-phase specs and plans.
- For UI-only changes, or changes with no later phase, do not require a fictional backend spec or new dependencies.

If an existing earlier-phase spec has no dedicated shared-contract section,
recover the known items from its documents, code, and tests. Do not rerun the
whole interview; confirm only the important open items.

## Implementation approval

Before implementation, summarize the agreed understanding: goal, acceptance
criteria, important constraints, settled shared-contract items, and unresolved
items with their impact and when they must be resolved. Wait for explicit
approval of the spec or design scope. Only then follow Endings.

Do not wait for approval after every section or for reversible implementation
details. Re-confirm only a decision that the approval changed in a way that
affects the agreed scope, contract, risk, or cost.

Spike: grill only until the probe is specified, then the spike ending. Bounded
and architectural: reach the summary above, then confirm, then Endings.

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

Do not enter Endings while an important decision in the agreed scope is
unresolved without an explicit impact and resolution point, except a spike whose
probe is already specified.

**Spike:** Two or three sentences for the probe, get a nod, investigate cheaply, report a recommendation. Label leftover code throwaway. No spec or plan. Glossary/ADR writes still apply if they qualify.

**Bounded:** Short design in chat. Stop until an explicit yes. Before implementation, ask once whether to create an isolated git worktree (same prompt as sdd-execute Workspace). Already in a linked worktree, or a yes/no already recorded this conversation: do not ask. Yes: use using-git-worktrees, then implement there. No: implement in this checkout. Use test-driven-development when it fits the behavior and risk; TDD is not a gate for every bounded change. No spec file, no plan file.

**Architectural:** If the interview did not already choose among 2–3 approaches, propose them now, recommended first. Present the settled design once; do not wait for approval after each section. Run Confirm before saving — for a new spec, the goal, completion criteria, non-goals, and important constraints; for an existing spec, the target, meaning changed, and impact. Then write `docs/sdd/specs/YYYY-MM-DD-<topic>-design.md`, author the adjacent `.html` companion in a separate native file-edit operation with the current source digest, and run `python3 <pack-root>/scripts/html-docs check --paths docs/sdd/specs/YYYY-MM-DD-<topic>-design.md docs/sdd/specs/YYYY-MM-DD-<topic>-design.html`. Self-review: no placeholders, no contradictions, one interpretation per requirement, scope that fits one plan. Commit the spec plus this session's CONTEXT.md / ADR / HTML changes only after validation. Ask the human to review the spec file. Further spec edits are new commits (do not amend). After they approve, use sdd-plan. Do not use writing-plans.

Spec must record: classification, chosen approach, architecture, components, data flow, error handling, testing, goals/non-goals, consuming paths, any numeric defaults, negative requirements, or ordering guarantees that did not earn an ADR, and the shared contract when a later phase depends on it. Do not end the session with those only in chat.

## Pack root

`<pack-root>` is the directory that contains `skills/` and `scripts/` — the same definition as the `sdd` skill. Format files are `<pack-root>/docs/formats/context.md` and `<pack-root>/docs/formats/adr.md`. Do not copy this SKILL.md alone into another repo.
