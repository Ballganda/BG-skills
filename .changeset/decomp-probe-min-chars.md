---
"bg-skills": patch
---

Decomp skills (in progress): calibration skips the single-function probe when there is too little to cut (spec #186).

- **Skip.** When the bodies of the other marked functions hold fewer characters together than `probe_min_chars`, the probe builds nothing and its calibration record is `skipped`, with the count in its `reason`.
- **Threshold.** `probe_min_chars` joins the block constants `local.json` can override. Its default, 2,000 characters, is an estimate and has not been measured.
