---
name: improve-codebase-architecture
description: Find deepening opportunities as candidates ready for /spec-gen, then grill through the one you pick.
disable-model-invocation: true
---

# Improve Codebase Architecture

Find **deepening opportunities**: refactors that turn shallow modules into deep ones, for testability and AI-navigability. Change no code.

Call the Skill tool with "codebase-design" for the vocabulary (**module**, **interface**, **depth**, **seam**, **adapter**, **leverage**, **locality**) and the **deletion test**. Use those terms exactly; never "component", "service", "API", or "boundary". Name domain concepts in `GLOSSARY.md` vocabulary ("the Order intake module", not "the FooBarHandler"). Don't re-litigate ADRs in `docs/adr/`.

## 1. Explore

- If the user named a direction, scan only there.
- Otherwise run `git log --oneline -n 50 --name-only` and scan the hot spots first; widen only if changes are scattered.

Read `GLOSSARY.md` and ADRs for the area. Then dispatch one exploration subagent with a fresh context window, scoped to those paths, asking for a report under 400 words of where it hit friction:

- one concept spread across many small modules;
- **shallow** modules (interface nearly as complex as the implementation);
- pure functions extracted for testability while bugs hide in the callers (no **locality**);
- coupling that leaks across **seams**;
- code untested or hard to test through its interface.

Keep only candidates that pass the deletion test: deleting the module would concentrate complexity, not just move it.

## 2. Present candidates

In chat, a markdown list, one entry per candidate:

```
### A1: <deepened module, in domain terms>: Strong | Worth exploring | Speculative
- Modules: <modules involved>
- Problem: <the friction>
- Solution: <what changes, plain English>
- Test seam: <where the deepened module gets tested>
- Benefit: <locality and leverage; which tests get simpler>
- ADR conflict: <only if it contradicts an ADR: which one and why reopen it>
```

Add a small before/after diagram (ASCII or Mermaid) only when it says more than the text. Surface an ADR-contradicting candidate only when the friction justifies reopening the ADR. End with **Top recommendation**: the ID and one line on why.

Don't propose interfaces yet. Ask: "Which of these would you like to explore?" The IDs let the user carry one straight into `/spec-gen`.

## 3. Grilling loop

On the picked candidate, call the Skill tool with "grilling": constraints, dependencies, the deepened module's shape, what sits behind the seam, which tests survive. Call the Skill tool with "domain-modeling" and apply side effects inline:

- New concept naming a deepened module: add it to `GLOSSARY.md` (create lazily).
- Fuzzy term sharpened: update `GLOSSARY.md` now.
- Candidate rejected for a reason a future run would need: offer an ADR so it isn't re-suggested. Skip ephemeral or self-evident reasons.
- Alternative interfaces wanted: use the "codebase-design" design-it-twice pattern.
