---
"bg-skills": patch
---

Decomp skills (in progress): a round's counts say what they measure, and report the whole call (spec #186, finding 11).

- **`call_s`.** The search summary's `counts` and the block's performance record gain `call_s`, the seconds of the whole `search` call: calibration, probes, and the block. It is never smaller than `wall_s`, which stays the block's seconds alone.
- **Layout.** `LAYOUT.md` says that `budget` is the estimate made when sampling began and that `compiled` can pass it, and that `best_score_end` is the block's own best and can be worse than `best_score_start`.
- No field is renamed.
