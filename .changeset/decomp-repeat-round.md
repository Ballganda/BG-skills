---
"bg-skills": patch
---

Decomp skills (in progress): a repeat round is no round in the performance log or the block ceiling.

- **Marked in the log.** A repeat's block record carries `repeat: true` and the number of the last counted round, so no two counted rounds share a number.
- **Ceiling kept.** A repeat no longer writes the round-end time, so the next block's ceiling runs from the last counted round and an accidental repeat does not shorten it to the floor.
