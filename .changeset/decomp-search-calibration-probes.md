---
"bg-skills": patch
---

Decomp skills (in progress): `search` probes three faster ways to build before a ticket's first block, and keeps one only if it is faster and byte-identical (spec #162).

- **Single-function build.** The body of every other marked function is cut from the candidate. A match found this way is built once more as the full unit.
- **Batching.** An optional `build_batch` adapter compiles 4 to 16 candidates in one compiler call.
- **Resolved compiler.** An optional `build_resolve` adapter hands over the compiler's argument list and environment. The probe records whether running it directly is faster and byte-identical. No block uses it: adopting it needs an ADR.
- **Records.** Each probe writes one calibration record to `.decomp/perf.jsonl`. The summary's `counts` add `single_function` and `batch`.
- **Block constants.** `probe_gain` and `probe_runs` join the overrides in `local.json`.
