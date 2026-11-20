---
"bg-skills": patch
---

Decomp skills (in progress): `search` reads the full template grammar and skips repeated work (spec #162).

- **Grammar.** Labels, kinds, likelihoods, `PERM_VAR`, `PERM_ONCE`, `PERM_INT`, `PERM_LINESWAP`, and `PERM_IGNORE`, with limits the tool enforces.
- **Sweep.** A round tries the baseline, then each one-choice change, and freezes a choice point no alternative changes (`inert`). The summary adds `effects`.
- **Dedupe and cache.** A candidate is built once per round, and scores persist in `.decomp/search-cache.json` across rounds. `first_differ` from the `diff` adapter centres the summary's window.
