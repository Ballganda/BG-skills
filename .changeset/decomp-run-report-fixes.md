---
"bg-skills": patch
---

Decomp skills (in progress): two mismatches found on a real project.

- **`verify --category none`**: a writer that matched reports `category: none`, and `verify` stopped on it as an unknown category. It now reads `none` as no category.
- **Reference lock**: `decomp-run` took the `reference` lock before starting the repair subagent, and `decomp-reference` stops when the lock is already held, so no repair could run. The repair subagent now takes the lock, and the coordinator only releases it.
