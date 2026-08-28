---
name: sdd
description: Route spec-driven work to sdd-design, sdd-plan, sdd-execute, or sdd-finish. Use when the user wants SDD, a spec, a plan, implementation of a plan, or to finish a branch.
---

# SDD

This directory is the pack root. Install the whole pack. Never copy one SKILL.md.

## Route

| Situation | Skill |
|---|---|
| New idea, fuzzy words, or any architectural change without a spec | sdd-design |
| Approved architectural spec, no plan yet | sdd-plan |
| Plan exists, implement it | sdd-execute |
| Implementation green, integrate | sdd-finish |
| User asks to "just implement" something architectural | sdd-design first |

Do not run sdd-execute without a plan file. Do not run architectural implementation without a spec file.

Do not invoke Superpowers or grill-with-docs.

Pack root = the directory containing `skills/` and `scripts/`.
