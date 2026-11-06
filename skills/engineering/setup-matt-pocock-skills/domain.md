# Domain docs

Before exploring, read:

- **`GLOSSARY.md`** at the repo root.
- ADRs in **`docs/adr/`** that touch the area you're working in.

<!-- if: multi-context -->
This repo is multi-context: **`GLOSSARY-MAP.md`** at the root points at one `GLOSSARY.md` per context (`src/<context>/GLOSSARY.md`); read each one relevant to the topic. `docs/adr/` holds system-wide decisions; `src/<context>/docs/adr/` holds context-scoped ones.
<!-- end -->

If any of these don't exist, **proceed silently**: don't flag their absence or suggest creating them. `/domain-modeling` (via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when a term or decision is resolved.

## Use the glossary's vocabulary

When your output names a domain concept (issue title, refactor proposal, hypothesis, test name), use the glossary's term, not a synonym it avoids. A concept missing from the glossary means you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an ADR, say so explicitly rather than silently overriding it:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because..._
