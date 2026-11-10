---
"bg-skills": patch
---

Decomp skills (in progress): the `link` command and its milestones (spec #39).

- **`link`** links the whole binary from the reconstructed source plus raw blocks of the target, compares it with the edition on this machine, and records a `link` event.
- **Link milestone.** The contract's Tracking section holds a milestone size beside the revalidation interval, as a percentage or a byte count (`link_milestone` in `decomp.json`), defaulting to 5% of the in-scope bytes with a floor of 16 KB. `report` prints a `milestone:` line: `due` when the in-scope bytes of units fully matched since the last recorded link reach it, never when the link is unavailable.
- **`/decomp-run`** runs the link after revalidation when a milestone is due, and always when the state is `finished`. The finish message states the link result, or that a whole-binary link is not available for this target.
