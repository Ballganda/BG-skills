---
"bg-skills": patch
---

Decomp skills (in progress): a deadline block finishes its last pass (spec #186).

- **Last pass.** When a `search` block reaches its deadline with no more candidates left in the space than it runs workers, it builds them and ends `exhausted`, with no `continues_s` and no background search.
- **Bounded.** A hung compile in the last pass is still killed by the hang limit. With more candidates left than workers, the block ends `deadline` as before.
