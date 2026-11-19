---
"bg-skills": patch
---

Decomp skills (in progress): `search` samples a template too large for one block, best-first from priors (spec #162).

- **Budget.** A block works out how many compiles it fits from its compile rate and deadline. A space that fits is still tried whole, most likely first.
- **Sampling.** A larger space is picked one candidate at a time by seeded Thompson sampling over each alternative's likelihood, updated after every scored candidate. At least 20 percent of picks are exploratory and aim at pairs of alternatives not yet tried together. At equal likelihood a natural alternative ranks above a steering one.
- **Priors.** An alternative written as the closest matched functions from `similar` are written gets a higher likelihood, beside the writer's own and the project history.
- **Slow compilers.** With a budget under 100 compiles, sampling opens with a pairwise covering sample, likeliest first.
- **Summary.** `pairs` names up to 3 pairs of alternatives whose joint effect differs from the sum of their single effects. A sampled block's `counts` add `budget`, `pairwise`, `sampled`, and `explored`.
- **Block constants.** `budget` and `seed` join the overrides in `local.json`.
- **`LAYOUT.md`** documents the sampling, the constants, and the new summary fields.
