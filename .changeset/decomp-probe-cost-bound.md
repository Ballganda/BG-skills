---
"bg-skills": patch
---

Decomp skills (in progress): the batching and resolved-compiler probes of a `search` call have a cost bound (spec #234, trial #212 finding 4).

- **Bound.** The two probes together cost at most `probe_cost_frac` (default 0.5) of the ceiling of the block they precede. A step whose predicted cost does not fit is not run: a batching size that does not fit ends the probe and keeps the best size proven so far, and a resolved-compiler probe that does not fit is `skipped`. Each record of a probe cut short or skipped for cost holds `predicted_s` and `bound_s`. `probe_cost_frac` of 0 switches both probes off.
- **Diff runs.** Under `function` hashing the batching probe diffs one object per size, the last, instead of every object. The baseline's single build and its byte identity are taken once per calibration for both probes.
- **Constant.** `probe_cost_frac` joins the block constants `local.json` can override. Its default is a judgment and has not been measured.
