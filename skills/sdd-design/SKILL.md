---
name: sdd-design
description: Classify a change, interview until shared understanding, write CONTEXT.md/ADRs inline, then a Markdown spec plus HTML. Use before implementation when the work is new or the words are unsettled.
---

# SDD Design

Do not invoke Superpowers, grill-with-docs, grilling, or domain-modeling. This skill contains those rules.

Announce: "I'm using sdd-design."

## Classify first

Say spike / bounded / architectural out loud. When unsure, take the heavier path. If hidden complexity appears, upgrade and say so. Never downgrade.

## Explore

Read CONTEXT.md (or ask which file if CONTEXT-MAP.md exists), docs/adr/, README, and enough code that the codebase can answer questions instead of the human.

## Interview

- One question per message. Prefer multiple choice. Always give a recommended answer.
- Do not ask what CONTEXT.md, ADRs, README, or the codebase already answer.
- If the human's word conflicts with CONTEXT.md, resolve the collision before any other question.
- Walk dependencies in order.

## CONTEXT.md

When a term resolves, write it immediately using docs/formats/context.md. Then run:

```text
python3 <pack-root>/scripts/render-docs CONTEXT.md
```

If render-docs exits non-zero, warn and continue. Never put implementation detail in CONTEXT.md.

## ADRs

Offer an ADR only when all three gates in docs/formats/adr.md hold. After the human agrees, write `docs/adr/NNNN-slug.md` and render that file. If a gate is missing, put the decision in the spec instead (architectural) or keep it in the short chat design (bounded).

## Endings

**Spike:** Two or three sentences for the probe, get a nod, investigate cheaply, report a recommendation. Label leftover code throwaway. No spec or plan. Glossary/ADR writes still apply if they qualify.

**Bounded:** Short design in chat. Stop until an explicit yes. Then TDD in this session. No spec file, no plan file.

**Architectural:** Propose 2–3 approaches, recommended first. Present the design in sections; wait for approval after each. Then write `docs/sdd/specs/YYYY-MM-DD-<topic>-design.md` and render it. Self-review: no placeholders, no contradictions, one interpretation per requirement, scope that fits one plan. Commit the spec plus this session's CONTEXT.md / ADR / HTML changes. Ask the human to review the spec file. Further spec edits are new commits (do not amend). After they approve, use sdd-plan. Do not use writing-plans.

Spec must record: classification, chosen approach, architecture, components, data flow, error handling, testing, goals/non-goals, consuming paths, and any numeric defaults, negative requirements, or ordering guarantees that did not earn an ADR. Do not end the session with those only in chat.

## Pack root

Resolve `<pack-root>` as the directory that contains `scripts/` and `skills/`. Do not copy this SKILL.md alone into another repo.
