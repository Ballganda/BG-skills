---
"bg-skills": patch
---

Decomp skills (in progress): a `search` block tunes its own worker count and watches a reference compile (spec #162).

- **Tuning.** Every 2 seconds a block compares its unique compiles per second with the tick before. A gain above 5 percent adds a worker; a loss above 10 percent, or a p95 compile time above 2 times the median, takes one back. The count stays between half the starting count and the search's share of the slot pool. A `workers` set in `local.json` is kept as it is.
- **Reference compile.** Every 30 seconds the block recompiles the baseline. A run more than 30 percent over the block's first compiles halves the worker count and raises `contention-or-throttle`.
- **Starved blocks.** A block the slot pool holds below its worker floor for over half its time raises `starved-by-writers`.
- **Performance log.** A block record's `workers_min`, `workers_max`, and `workers_end` now move, and it gains `unit`, `workers_floor`, `starved_frac`, `t_ref_base_ms`, and `t_ref_max_ms`.
- **Block constants.** `tune_s`, `tune_gain`, `tune_loss`, `tune_spread`, and `reference_s` join the overrides in `local.json`.
- **`LAYOUT.md`** documents the tuning, the reference compile, the constants, and the two flags.
