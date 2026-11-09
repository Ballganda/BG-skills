---
name: domain-modeling
description: Build and sharpen a project's domain model. Use when discussing codebase terminology, writing or editing a GLOSSARY.md, or recording or editing an ADR.
---

# Domain Modeling

The *active* discipline: changing the domain model as you design, not just reading `GLOSSARY.md` for vocabulary.

## Where files live

One context: `GLOSSARY.md` at the root, ADRs in `docs/adr/`. If a root `GLOSSARY-MAP.md` exists, it points to each context's own `GLOSSARY.md` and `docs/adr/`; system-wide ADRs stay in the root `docs/adr/`.

Create files lazily: `GLOSSARY.md` when the first term is resolved, `docs/adr/` when the first ADR is needed.

## During the session

- **Challenge against the glossary.** When a term conflicts with `GLOSSARY.md`, call it out at once and ask: "Your glossary defines 'cancellation' as X, but you seem to mean Y. Which is it?" If the user already handed you the naming, still call the clash out, then say which name you picked.
- **Sharpen fuzzy language.** For a vague or overloaded term, propose a precise canonical one ("Customer or User?").
- **Probe with scenarios.** Invent edge cases that force the boundaries between concepts to be exact.
- **Cross-reference with code.** When the user states how something works, check the code and surface any contradiction.
- **Update GLOSSARY.md inline**, the moment a term is resolved, using [GLOSSARY-FORMAT.md](./GLOSSARY-FORMAT.md). It is a glossary and nothing else: no implementation details, spec, or scratch notes.

## Offer ADRs sparingly

Offer an ADR only when all three hold:

1. **Hard to reverse**: changing your mind later costs something meaningful.
2. **Surprising without context**: a future reader will ask "why this way?"
3. **A real trade-off**: there were genuine alternatives, and one was picked for specific reasons.

Missing any one, skip it. Write it using [ADR-FORMAT.md](./ADR-FORMAT.md).
