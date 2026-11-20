---
"bg-skills": patch
---

Decomp skills (in progress): `search` learns across rounds and advises when to stop (spec #162).

- **Mutation and crossover.** A later block of a template also builds candidates from the best earlier ones, with a bandit sharing picks between sampling, mutation, and crossover.
- **History.** Attempts the ledger recorded raise the likelihood of the kinds that fixed a category before, and the summary's `history` line says so.
- **Stop.** The summary's `stop` advises giving up when every choice point is inert or 2 rounds in a row brought no new best score.
- **Performance log.** `.decomp/perf.jsonl` records each block and raises regression flags, shown to the user after 3 in a row.
