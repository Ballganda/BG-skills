---
"bg-skills": patch
---

Decomp skills (in progress): a speed flag's streak is counted over the blocks that could have raised it.

- **A block that measured nothing is passed over.** For the four measured flags, a block that built fewer than 2 candidates per worker (a cached repeat, a short matching block) neither adds to the streak nor ends it.
- **A block of another unit is passed over.** The streak is counted over the same compiler and the same unit, so two writers on two units no longer keep the notice from showing.
- **The notice says "in 3 blocks in a row of this unit".** The once-per-streak rule and the threshold of 3 are unchanged.
