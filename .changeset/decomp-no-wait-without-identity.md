---
"bg-skills": patch
---

Decomp skills (in progress): a block no longer holds workers for the opening sweep when nothing can be frozen (spec #210).

- **No identity, no wait.** When hashing falls back to the function's bytes and the first diffed candidate carried no `function_sha256`, a free worker takes the next candidate of the rest of the space without waiting for the sweep's results.
- **Unchanged with identity.** Where objects are repeatable or a diff result carried `function_sha256`, the rest still waits for the sweep and inert choice points are frozen.
- **`idle_frac`.** The layout says the wait for the sweep is part of it, and absent when the round has no object identity.
