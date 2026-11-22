---
"bg-skills": patch
---

Decomp skills (in progress): a batched block compares its reference compile with a single build and starts no batch after its time (spec #232).

- **Reference base.** In a block that builds in batches, the base of the reference compile is one single build of the baseline, made as the block begins. A quiet machine keeps its workers and raises no `contention-or-throttle`. The record's `t_ref_ms` is a single build's time, or `null` with the reference off. Unbatched blocks are unchanged.
- **No batch after the time.** A worker that holds its compile slot for a batch looks again before the compiler call, and builds nothing once the block or the background search has ended or its time has come. A batch in hand still runs to its end, so the overrun is one batch. The layout document says so.
