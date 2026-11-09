# In Progress

Beta. These skills are public on purpose: try them and tell me what breaks. They're excluded from the plugin and the top-level README until they graduate to a stable bucket, they get no docs pages, and they can change or disappear without warning.

The plugin won't give you these. Install one directly:

```bash
npx skills@latest add Ballganda/BG-skills --skill=<name>
```

- **[loop-me](./loop-me/SKILL.md)**: Grill yourself into implementable workflow specs over multiple sessions, using the current directory as a stateful workspace. User-invoked.
- **[writing-beats](./writing-beats/SKILL.md)**: Shape an article as a journey of beats, choose-your-own-adventure style. Pick a starting beat, write only that beat, then pivot to the next, until the article reaches a natural end.
- **[writing-fragments](./writing-fragments/SKILL.md)**: Grilling session that mines you for fragments (heterogeneous nuggets of writing) and appends them to a single document as raw material for a future article.
- **[writing-shape](./writing-shape/SKILL.md)**: Take a markdown file of raw material and shape it into an article paragraph by paragraph, arguing format choices at each step.
- **[claude-handoff](./claude-handoff/SKILL.md)**: Hand the current conversation off to a fresh background agent that picks up the work immediately, seeded with a handoff summary via `claude --bg`. User-invoked.
- **[setup-ts-deep-modules](./setup-ts-deep-modules/SKILL.md)**: Wire dependency-cruiser into a TypeScript repo so each package is a deep module: implementation hidden in subfolders, reachable only through its entry-point files, tests exercising it through those. User-invoked.
- **[software-factory](./software-factory/SKILL.md)**: Shared language for designing a software factory: the tasks it runs and the services it plugs into. Call it alongside a grilling session. User-invoked.
- **[decomp-setup](./decomp-setup/SKILL.md)**: Agree a byte-for-byte decompilation contract and set up the private project that enforces it: compiler identification, toolchain provisioning, guardrail tooling, and a pipeline check. No decomp. User-invoked.
- **[decomp-start](./decomp-start/SKILL.md)**: Read a set-up target, list every function, and turn them into unit specs and function tickets, mostly by script. User-invoked.
- **[decomp-run](./decomp-run/SKILL.md)**: Work decomp tickets to verified byte matches with separate writer, auditor, and repair subagents, recording each proven lesson. User-invoked.
- **[decomp-identify](./decomp-identify/SKILL.md)**: Find a binary's format, architecture, compiler, and flags from evidence in the file, and list the toolchain it needs.
- **[decomp-spec-gen](./decomp-spec-gen/SKILL.md)**: Group a decomp inventory into units and write one spec per unit.
- **[decomp-ticket-gen](./decomp-ticket-gen/SKILL.md)**: Write one ticket per in-scope decomp function, mirrored to GitHub when enabled.
- **[decomp-match](./decomp-match/SKILL.md)**: Reconstruct one decomp function until the original compiler emits its bytes exactly.
- **[decomp-reference](./decomp-reference/SKILL.md)**: Repair shared decomp declarations from evidence without breaking any existing match.
- **[decomp-standards](./decomp-standards/SKILL.md)**: Shared decomp rules: acceptance criterion, guardrails, size tiers, mismatch categories, project layout.
