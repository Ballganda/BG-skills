---
"bg-skills": patch
---

Decomp skills (in progress): a choice point frozen as inert at the baseline is tried again against each new object, so the freeze hides no matching candidate (spec #230).

- **Retry.** The first time a candidate gives an object the block has not seen, each frozen choice point is tried once per other alternative against that candidate, before the next candidate of the rest of the space.
- **Unfreezing.** A retry that gives anything but that candidate's object unfreezes its choice point for the rest of the block, for the whole space and for a sampled one.
- **`exhausted`.** A block ends `exhausted` only when no retry is owed. One whose deadline or plateau comes first ends on that reason.
- **`inert`.** Each entry reads `"<label>: <n> of <m> objects"`: how many of the round's objects the freeze held against. The stop advice for a template whose every choice point is inert needs every entry to hold them all.
- **Readers.** `decomp-match` and its docs page say a listed choice point is safe to leave out when `n` equals `m`.
- **Unchanged.** A round with no object identity freezes nothing, as before.
